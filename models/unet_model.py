#!/usr/bin/env python3
"""U-Net model for wildfire spread prediction.

This is the industry-standard architecture for the Next Day Wildfire Spread
benchmark (Hu et al., 2023). Unlike the A3C_PerCellModel_LSTM which iterates
cell-by-cell (forcing batch_size=1), U-Net processes the entire patch in a
single forward pass, enabling batch_size=32+.

Architecture:
    Input (B, 12, 64, 64)
    → Encoder: 4 down-blocks (64→128→256→512)
    → Bottleneck: (512→1024)
    → Decoder: 4 up-blocks (1024→512→256→128→64)
    → Output: Conv 1×1 → (B, 1, 64, 64)

Key differences from A3C-LSTM:
    - batch_size can be 32+ (no per-cell iteration)
    - Fully convolutional (no LSTM bottleneck)
    - Skip connections preserve spatial detail
    - Standard semantic segmentation approach

References:
    - Ronneberger et al., "U-Net", MICCAI 2015
    - Hu et al., "Next Day Wildfire Spread", NeurIPS 2023
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConv(nn.Module):
    """(Conv2d → GroupNorm → ReLU) × 2 block."""

    def __init__(self, in_channels: int, out_channels: int, mid_channels: int | None = None):
        super().__init__()
        mid = mid_channels if mid_channels is not None else out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(8, mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, out_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(8, out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.double_conv(x)


class DownBlock(nn.Module):
    """MaxPool → DoubleConv downsampling block."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.maxpool_conv(x)


class UpBlock(nn.Module):
    """Upsample → Concatenate skip → DoubleConv upsampling block."""

    def __init__(self, in_channels: int, out_channels: int, bilinear: bool = True):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, mid_channels=in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        # Pad if sizes don't match (for odd input dimensions)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class WildfireUNet(nn.Module):
    """U-Net for wildfire spread prediction.

    Input:  (batch, in_channels, 64, 64) — e.g. (32, 12, 64, 64)
    Output: (batch, 1, 64, 64) — fire probability per cell

    Args:
        in_channels: Number of input feature channels (NDWS: 12, our pipeline: 17)
        out_channels: Number of output channels (1 for binary fire/no-fire)
        bilinear: Use bilinear upsampling (True) or transposed conv (False)
    """

    def __init__(self, in_channels: int = 12, out_channels: int = 1, bilinear: bool = True):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.bilinear = bilinear

        # Encoder (downsampling path)
        self.inc = DoubleConv(in_channels, 64)
        self.down1 = DownBlock(64, 128)
        self.down2 = DownBlock(128, 256)
        self.down3 = DownBlock(256, 512)
        factor = 2 if bilinear else 1
        self.down4 = DownBlock(512, 1024 // factor)

        # Decoder (upsampling path)
        self.up1 = UpBlock(1024, 512 // factor, bilinear)
        self.up2 = UpBlock(512, 256 // factor, bilinear)
        self.up3 = UpBlock(256, 128 // factor, bilinear)
        self.up4 = UpBlock(128, 64, bilinear)

        # Output layer
        self.outc = nn.Conv2d(64, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass — processes entire batch at once.

        Args:
            x: Input tensor of shape (batch, in_channels, H, W)

        Returns:
            Output logits of shape (batch, 1, H, W)
        """
        # Encoder
        x1 = self.inc(x)      # (B, 64, H, W)
        x2 = self.down1(x1)   # (B, 128, H/2, W/2)
        x3 = self.down2(x2)   # (B, 256, H/4, W/4)
        x4 = self.down3(x3)   # (B, 512, H/8, W/8)
        x5 = self.down4(x4)   # (B, 512, H/16, W/16) — bottleneck

        # Decoder with skip connections
        x = self.up1(x5, x4)  # (B, 256, H/8, W/8)
        x = self.up2(x, x3)   # (B, 128, H/4, W/4)
        x = self.up3(x, x2)   # (B, 64, H/2, W/2)
        x = self.up4(x, x1)   # (B, 64, H, W)

        # Output
        logits = self.outc(x)  # (B, 1, H, W)
        return logits

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Return sigmoid probabilities (for inference)."""
        return torch.sigmoid(self.forward(x))


class WildfireUNetSmall(nn.Module):
    """Lighter U-Net variant for faster training / less memory.

    Uses fewer channels: 32→64→128→256→512 instead of 64→128→256→512→1024.
    Suitable for 16GB GPU with batch_size=64.

    Input:  (batch, in_channels, 64, 64)
    Output: (batch, 1, 64, 64)
    """

    def __init__(self, in_channels: int = 12, out_channels: int = 1, bilinear: bool = True):
        super().__init__()
        self.bilinear = bilinear

        self.inc = DoubleConv(in_channels, 32)
        self.down1 = DownBlock(32, 64)
        self.down2 = DownBlock(64, 128)
        self.down3 = DownBlock(128, 256)
        factor = 2 if bilinear else 1
        self.down4 = DownBlock(256, 512 // factor)

        self.up1 = UpBlock(512, 256 // factor, bilinear)
        self.up2 = UpBlock(256, 128 // factor, bilinear)
        self.up3 = UpBlock(128, 64 // factor, bilinear)
        self.up4 = UpBlock(64, 32, bilinear)

        self.outc = nn.Conv2d(32, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)

        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)

        return self.outc(x)


# --- Loss functions ---

def weighted_bce_loss(logits: torch.Tensor, targets: torch.Tensor, pos_weight: float = 5.0) -> torch.Tensor:
    """Weighted Binary Cross Entropy — matches NDWS paper (weight=5).

    Args:
        logits: (B, 1, H, W) raw model output
        targets: (B, 1, H, W) binary fire mask
        pos_weight: Weight for positive (fire) class

    Returns:
        Scalar loss
    """
    return F.binary_cross_entropy_with_logits(
        logits, targets, reduction="mean",
        pos_weight=torch.tensor(pos_weight, device=logits.device)
    )


def tversky_loss(logits: torch.Tensor, targets: torch.Tensor,
                 alpha: float = 0.3, beta: float = 0.7, eps: float = 1e-7) -> torch.Tensor:
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


def combined_loss(logits: torch.Tensor, targets: torch.Tensor,
                  pos_weight: float = 5.0, dice_weight: float = 0.5) -> torch.Tensor:
    """Combined Weighted BCE + Dice loss — best of both worlds.

    Weighted BCE handles class imbalance globally.
    Dice handles overlap/localization.
    """
    bce = weighted_bce_loss(logits, targets, pos_weight=pos_weight)
    dice = dice_loss(logits, targets)
    return bce + dice_weight * dice