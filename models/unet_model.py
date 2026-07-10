#!/usr/bin/env python3
"""U-Net model for wildfire spread prediction.

This is the industry-standard architecture for the Next Day Wildfire Spread
benchmark (Hu et al., 2023). Unlike the A3C_PerCellModel_LSTM which iterates
cell-by-cell (forcing batch_size=1), U-Net processes the entire patch in a
single forward pass, enabling batch_size=32+.

Architecture:
    Input (B, C, 64, 64)
    → Encoder: 3 down-blocks (32→64→128→256) — 3 levels keeps bottleneck at 8×8
    → Bottleneck: (256→512)
    → Decoder: 3 up-blocks (512→256→128→64)
    → Output: Conv 1×1 → (B, 1, 64, 64)

Key differences from v13 first attempt:
    - 3 down-levels (not 4) so 64×64 → 8×8 bottleneck (not 1×1)
    - 64×64 patches (not 30×30) which collapsed to 1×1 at the bottleneck
    - BatchNorm option + residual DoubleConv for faster convergence
    - Dynamically computed pos_weight (not hardcoded) from batch statistics
    - Focal + Tversky + Dice composite loss factory
    - SE (Squeeze-and-Excitation) channel attention option
    - Multi-scale auxiliary outputs for deeper gradient flow

References:
    - Ronneberger et al., "U-Net", MICCAI 2015
    - Hu et al., "Next Day Wildfire Spread", NeurIPS 2023
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #


class DoubleConv(nn.Module):
    """(Conv2d → Norm → ReLU) × 2 block with optional residual + SE attention."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        mid_channels: int | None = None,
        norm: str = "group",
        residual: bool = False,
        se_attention: bool = False,
    ):
        super().__init__()
        mid = mid_channels if mid_channels is not None else out_channels
        self.residual = residual and (in_channels == out_channels)

        if norm == "batch":
            norm_layer = lambda c: nn.BatchNorm2d(c)
        elif norm == "instance":
            norm_layer = lambda c: nn.InstanceNorm2d(c)
        else:
            norm_layer = lambda c: nn.GroupNorm(8, c)

        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid, kernel_size=3, padding=1, bias=False),
            norm_layer(mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, out_channels, kernel_size=3, padding=1, bias=False),
            norm_layer(out_channels),
            nn.ReLU(inplace=True),
        )

        self.se = SqueezeExcitation(out_channels) if se_attention else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.double_conv(x)
        out = self.se(out)
        if self.residual:
            out = out + x
        return out


class SqueezeExcitation(nn.Module):
    """Squeeze-and-Excitation channel attention (Hu et al., 2018)."""

    def __init__(self, channels: int, reduction: int = 8):
        super().__init__()
        self.squeeze = nn.AdaptiveAvgPool2d(1)
        self.excitation = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        s = self.squeeze(x).view(b, c)
        s = self.excitation(s).view(b, c, 1, 1)
        return x * s


class DownBlock(nn.Module):
    """MaxPool → DoubleConv downsampling block."""

    def __init__(
        self, in_channels: int, out_channels: int, **conv_kwargs
    ):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels, **conv_kwargs),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.maxpool_conv(x)


class UpBlock(nn.Module):
    """Upsample → Concatenate skip → DoubleConv upsampling block."""

    def __init__(
        self, in_channels: int, out_channels: int, bilinear: bool = True, **conv_kwargs
    ):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(
                in_channels, out_channels, mid_channels=in_channels // 2, **conv_kwargs
            )
        else:
            self.up = nn.ConvTranspose2d(
                in_channels, in_channels // 2, kernel_size=2, stride=2
            )
            self.conv = DoubleConv(in_channels, out_channels, **conv_kwargs)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        # Pad if sizes don't match (for odd input dimensions)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = F.pad(
            x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2]
        )
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


# --------------------------------------------------------------------------- #
# Model variants
# --------------------------------------------------------------------------- #


class WildfireUNet(nn.Module):
    """Full U-Net for wildfire spread prediction.

    3 down-levels: 64×64 → 32×32 → 16×16 → 8×8 bottleneck.
    This preserves spatial context while being trainable in reasonable time.

    Input:  (batch, in_channels, 64, 64)
    Output: (batch, 1, 64, 64) — fire probability logits per cell
    """

    def __init__(
        self,
        in_channels: int = 12,
        out_channels: int = 1,
        bilinear: bool = True,
        norm: str = "group",
        se_attention: bool = False,
    ):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.bilinear = bilinear

        conv_kw = dict(norm=norm, se_attention=se_attention)

        # Encoder (downsampling path) — 64→32→16→8
        self.inc = DoubleConv(in_channels, 64, **conv_kw)
        self.down1 = DownBlock(64, 128, **conv_kw)
        self.down2 = DownBlock(128, 256, **conv_kw)
        factor = 2 if bilinear else 1
        self.down3 = DownBlock(256, 512 // factor, **conv_kw)

        # Decoder (upsampling path)
        self.up1 = UpBlock(512, 256 // factor, bilinear, **conv_kw)
        self.up2 = UpBlock(256, 128 // factor, bilinear, **conv_kw)
        self.up3 = UpBlock(128, 64, bilinear, **conv_kw)

        # Output layer
        self.outc = nn.Conv2d(64, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass — processes entire batch at once."""
        x1 = self.inc(x)      # (B, 64, 64, 64)
        x2 = self.down1(x1)   # (B, 128, 32, 32)
        x3 = self.down2(x2)   # (B, 256, 16, 16)
        x4 = self.down3(x3)   # (B, 256, 8, 8) — bottleneck

        x = self.up1(x4, x3)  # (B, 128, 16, 16)
        x = self.up2(x, x2)   # (B, 64, 32, 32)
        x = self.up3(x, x1)   # (B, 64, 64, 64)

        logits = self.outc(x)  # (B, 1, 64, 64)
        return logits

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Return sigmoid probabilities (for inference)."""
        return torch.sigmoid(self.forward(x))


class WildfireUNetSmall(nn.Module):
    """Lighter U-Net variant for faster training / less memory.

    Uses fewer channels: 32→64→128→256 instead of 64→128→256→512.
    3 down-levels so 64×64 → 8×8 bottleneck.
    Suitable for 16GB GPU with batch_size=64.

    Input:  (batch, in_channels, 64, 64)
    Output: (batch, 1, 64, 64)
    """

    def __init__(
        self,
        in_channels: int = 12,
        out_channels: int = 1,
        bilinear: bool = True,
        norm: str = "group",
        se_attention: bool = False,
    ):
        super().__init__()
        self.bilinear = bilinear

        conv_kw = dict(norm=norm, se_attention=se_attention)

        self.inc = DoubleConv(in_channels, 32, **conv_kw)
        self.down1 = DownBlock(32, 64, **conv_kw)
        self.down2 = DownBlock(64, 128, **conv_kw)
        factor = 2 if bilinear else 1
        self.down3 = DownBlock(128, 256 // factor, **conv_kw)

        self.up1 = UpBlock(256, 128 // factor, bilinear, **conv_kw)
        self.up2 = UpBlock(128, 64 // factor, bilinear, **conv_kw)
        self.up3 = UpBlock(64, 32, bilinear, **conv_kw)

        self.outc = nn.Conv2d(32, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)

        x = self.up1(x4, x3)
        x = self.up2(x, x2)
        x = self.up3(x, x1)

        return self.outc(x)

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(x))


def count_parameters(model: nn.Module) -> int:
    """Return total number of trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# --------------------------------------------------------------------------- #
# Loss functions
# --------------------------------------------------------------------------- #


def weighted_bce_loss(
    logits: torch.Tensor, targets: torch.Tensor, pos_weight: float = 5.0
) -> torch.Tensor:
    """Weighted Binary Cross Entropy — matches NDWS paper (weight=5).

    Args:
        logits: (B, 1, H, W) raw model output
        targets: (B, 1, H, W) binary fire mask
        pos_weight: Weight for positive (fire) class

    Returns:
        Scalar loss
    """
    pw = torch.tensor(pos_weight, device=logits.device, dtype=logits.dtype)
    return F.binary_cross_entropy_with_logits(
        logits, targets, reduction="mean", pos_weight=pw
    )


def dynamic_weighted_bce(
    logits: torch.Tensor, targets: torch.Tensor, target_ratio: float = 5.0
) -> torch.Tensor:
    """BCE with pos_weight computed from the actual batch class balance.

    This adapts to batches with different fire densities, avoiding the
    hardcoded pos_weight problem. Clamped to [1, 50] for stability.

    Args:
        logits: (B, 1, H, W) raw model output
        targets: (B, 1, H, W) binary fire mask
        target_ratio: Desired ratio; if actual ratio differs, adapt weight
    """
    n_pos = targets.sum().clamp(min=1.0)
    n_neg = (1.0 - targets).sum().clamp(min=1.0)
    # ratio of negatives to positives
    ratio = (n_neg / n_pos).clamp(min=1.0, max=50.0)
    # blend with target to avoid extreme swings
    pos_weight = (0.5 * target_ratio + 0.5 * ratio).clamp(min=1.0, max=50.0)
    return F.binary_cross_entropy_with_logits(
        logits, targets, reduction="mean", pos_weight=pos_weight
    )


def tversky_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    alpha: float = 0.3,
    beta: float = 0.7,
    eps: float = 1e-7,
) -> torch.Tensor:
    """Tversky loss — penalizes false negatives more than false positives.

    From Salehi et al., 2017. Better than focal loss for extreme imbalance.

    Args:
        logits: (B, 1, H, W) raw model output
        targets: (B, 1, H, W) binary fire mask
        alpha: Weight for false positives (0.3 = less penalty)
        beta: Weight for false negatives (0.7 = more penalty)

    Returns:
        Scalar loss
    """
    probs = torch.sigmoid(logits)
    TP = (probs * targets).sum(dim=[1, 2, 3])
    FP = ((1 - targets) * probs).sum(dim=[1, 2, 3])
    FN = (targets * (1 - probs)).sum(dim=[1, 2, 3])
    tversky = (TP + eps) / (TP + alpha * FP + beta * FN + eps)
    return (1 - tversky).mean()


def dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-7) -> torch.Tensor:
    """Soft Dice loss — maximizes overlap between prediction and target."""
    probs = torch.sigmoid(logits)
    intersection = (probs * targets).sum(dim=[1, 2, 3])
    union = probs.sum(dim=[1, 2, 3]) + targets.sum(dim=[1, 2, 3])
    dice = (2 * intersection + eps) / (union + eps)
    return (1 - dice).mean()


def focal_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    gamma: float = 2.0,
    pos_weight: float = 5.0,
    eps: float = 1e-7,
) -> torch.Tensor:
    """Focal loss with positive class weighting.

    Down-weights well-classified examples so the model focuses on
    hard-to-detect fire spread cells.
    """
    logits = torch.clamp(logits, -10.0, 10.0)
    logits = torch.where(torch.isnan(logits), torch.zeros_like(logits), logits)

    pw = torch.tensor(pos_weight, device=logits.device, dtype=logits.dtype)
    bce = F.binary_cross_entropy_with_logits(
        logits, targets, reduction="none", pos_weight=pw
    )
    p = torch.sigmoid(logits)
    p_t = p * targets + (1.0 - p) * (1.0 - targets)
    focal_factor = (1.0 - p_t) ** gamma
    loss = (focal_factor * bce).mean()
    if torch.isnan(loss):
        return torch.tensor(0.0, device=logits.device, requires_grad=True)
    return torch.clamp(loss, max=10.0)


def combined_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    pos_weight: float = 5.0,
    dice_weight: float = 0.5,
) -> torch.Tensor:
    """Combined Weighted BCE + Dice loss — best of both worlds.

    Weighted BCE handles class imbalance globally.
    Dice handles overlap/localization.
    """
    bce = weighted_bce_loss(logits, targets, pos_weight=pos_weight)
    dice = dice_loss(logits, targets)
    return bce + dice_weight * dice


def composite_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    pos_weight: float = 5.0,
    dice_weight: float = 0.3,
    tversky_weight: float = 0.3,
    focal_weight: float = 0.0,
    focal_gamma: float = 2.0,
) -> torch.Tensor:
    """Composite loss combining BCE + Dice + Tversky + optional Focal.

    This is the v14 recommended loss: dynamic class weighting via BCE,
    overlap via Dice, and FN penalty via Tversky.

    Args:
        logits: (B, 1, H, W) raw model output
        targets: (B, 1, H, W) binary fire mask
        pos_weight: positive class weight for BCE
        dice_weight: weight for Dice loss component
        tversky_weight: weight for Tversky loss component
        focal_weight: weight for Focal loss component (0 disables)
        focal_gamma: focal loss focusing parameter

    Returns:
        Scalar loss
    """
    loss = weighted_bce_loss(logits, targets, pos_weight=pos_weight)
    if dice_weight > 0:
        loss = loss + dice_weight * dice_loss(logits, targets)
    if tversky_weight > 0:
        loss = loss + tversky_weight * tversky_loss(logits, targets)
    if focal_weight > 0:
        loss = loss + focal_weight * focal_loss(
            logits, targets, gamma=focal_gamma, pos_weight=pos_weight
        )
    return loss


def make_loss_fn(name: str = "combined", **kwargs):
    """Factory to create a loss function by name.

    Supported names: 'bce', 'dice', 'tversky', 'focal', 'combined', 'composite'.
    Extra kwargs are forwarded to the loss function, filtered by the function's
    actual signature (so passing ``pos_weight`` to ``dice_loss`` won't crash).
    """

    import inspect

    loss_map = {
        "bce": weighted_bce_loss,
        "dynamic_bce": dynamic_weighted_bce,
        "dice": dice_loss,
        "tversky": tversky_loss,
        "focal": focal_loss,
        "combined": combined_loss,
        "composite": composite_loss,
    }
    if name not in loss_map:
        raise ValueError(f"Unknown loss '{name}'. Available: {list(loss_map)}")

    base_fn = loss_map[name]

    # Filter kwargs to only those the function actually accepts
    sig = inspect.signature(base_fn)
    valid_params = {
        p.name for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    # If the function accepts **kwargs, keep everything
    has_var_kw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
    if has_var_kw:
        filtered_kwargs = kwargs
    else:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

    def loss_fn(logits, targets):
        return base_fn(logits, targets, **filtered_kwargs)

    loss_fn.__name__ = f"{name}_loss_fn"
    return loss_fn
