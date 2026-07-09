"""Supervised Fine-Tuning Routine for A3C-LSTM Policy.

Loads pre-trained weights, processes sequences from WildfireDataset, and performs
gradient descent using binary cross-entropy on local neighbor transitions.
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from models.model import A3C_PerCellModel_LSTM

from .dataset import WildfireDataset
from .physics import physics_loss_cell
from .types import LocalSpreadModel
from .weights import load_pretrained_weights

# --- Loss helpers ---

# pos_weight penalizes false negatives 3× more than false positives.
# In wildfire spread, missing a fire cell (FN) is far more costly than a false alarm (FP).
DEFAULT_POS_WEIGHT = 3.0
DEFAULT_FOCAL_GAMMA = 2.0  # 0.0 disables focal, standard range 1.0-5.0
DEFAULT_LAMBDA_PHYSICS = 0.1  # Weight for physics-informed loss (Rothermel ROS)


def focal_loss_with_logits(
    logits: torch.Tensor,
    targets: torch.Tensor,
    gamma: float = DEFAULT_FOCAL_GAMMA,
    pos_weight: float = DEFAULT_POS_WEIGHT,
) -> torch.Tensor:
    """Focal loss with positive class weighting.

    Focal loss down-weights well-classified examples so the model focuses
    on hard-to-detect fire spread cells. Combined with ``pos_weight`` to
    further penalize false negatives (missed ignitions).
    """
    # --- NaN GUARD: sanitize logits before loss computation ---
    # If logits contain Inf/NaN (from upstream overflow), clamp to safe range.
    # Sigmoid(±10) ≈ 1.0/0.0 — any value beyond is numerically unstable.
    logits = torch.clamp(logits, -10.0, 10.0)
    # Replace any residual NaN with 0 (neutral logit = probability 0.5)
    logits = torch.where(torch.isnan(logits), torch.zeros_like(logits), logits)

    # Per-element BCE without reduction
    bce = F.binary_cross_entropy_with_logits(
        logits, targets, reduction="none", pos_weight=torch.tensor(pos_weight, device=logits.device)
    )
    # Compute p_t (probability of correct class) for focal modulation
    p = torch.sigmoid(logits)
    p_t = p * targets + (1.0 - p) * (1.0 - targets)
    focal_factor = (1.0 - p_t) ** gamma
    loss = (focal_factor * bce).mean()

    # Final safety: if loss is NaN (shouldn't happen after guards), return 0
    if torch.isnan(loss):
        return torch.tensor(0.0, device=logits.device, requires_grad=True)
    return loss


def calculate_local_spread_loss(
    model: LocalSpreadModel,
    features: torch.Tensor,
    current_fire: torch.Tensor,
    target_fire: torch.Tensor,
    sequence: torch.Tensor | None = None,
    pos_weight: float = DEFAULT_POS_WEIGHT,
    focal_gamma: float = DEFAULT_FOCAL_GAMMA,
    spread_bonus: float = 0.5,
    lambda_physics: float = DEFAULT_LAMBDA_PHYSICS,
) -> torch.Tensor | None:
    """Compute focal-weighted loss for burning-cell neighbor spread (LEGACY — per-cell loop).

    Kept for backwards compatibility. Prefer ``calculate_local_spread_loss_vectorized``
    which is 10-50x faster for training.

    Combines:
    1. **Focal BCE with pos_weight**: Penalizes false negatives heavily
       (missed fire spread is the #1 cause of low recall).
    2. **Spread-direction bonus**: Adds a small reward when the model
       correctly predicts the direction of active spread, encouraging
       it to "commit" to real propagation patterns.
    3. **Physics-informed penalty (Sprint 4)**: When ``sequence`` is provided,
       penalises predictions that violate Rothermel's maximum rate of spread.
    """
    burning_cells = model.get_burning_cells(current_fire)
    if not burning_cells:
        return None

    loss_sum = torch.tensor(0.0, device=features.device)
    bonus_sum = torch.tensor(0.0, device=features.device)
    physics_sum = torch.tensor(0.0, device=features.device)
    count = 0

    H, W = current_fire.shape[1], current_fire.shape[2]

    use_physics = sequence is not None and lambda_physics > 0
    if use_physics and sequence is not None:
        last_ts = sequence[0, -1]
        wind_grid = last_ts[4]
        slope_grid = last_ts[0]
        ffmc_grid = last_ts[16] if last_ts.shape[0] > 16 else None

    for i, j in burning_cells:
        logits = model.predict_8_neighbors(features, i, j).squeeze(0)
        labels = torch.zeros(8, device=features.device)
        neighbors = model.get_8_neighbor_coords(i, j, H, W)
        for n_idx, neighbor in enumerate(neighbors):
            if neighbor is not None:
                ni, nj = neighbor
                if target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5:
                    labels[n_idx] = 1.0

        cell_loss = focal_loss_with_logits(logits, labels, gamma=focal_gamma, pos_weight=pos_weight)

        with torch.no_grad():
            probs = torch.sigmoid(logits)
        predicted_positive = (probs > 0.5).float()
        tp = (predicted_positive * labels).sum()
        fp = (predicted_positive * (1 - labels)).sum()
        fn = ((1 - predicted_positive) * labels).sum()
        denom = tp + fp + fn
        soft_iou = tp / denom.clamp(min=1.0)
        bonus_sum -= spread_bonus * soft_iou

        if use_physics:
            ws = float(wind_grid[i, j].cpu().item())
            sr = float(slope_grid[i, j].cpu().item())
            ffmc = float(ffmc_grid[i, j].cpu().item()) if ffmc_grid is not None else 90.0
            probs_for_physics = torch.sigmoid(logits).detach()
            physics_sum += physics_loss_cell(
                probs_for_physics, ws, sr, ffmc=ffmc, lambda_physics=lambda_physics
            )

        loss_sum += cell_loss
        count += 1

    if count == 0:
        return None
    base_loss = loss_sum / count
    avg_bonus = bonus_sum / count
    avg_physics = physics_sum / count
    return base_loss + avg_bonus + avg_physics


# ------------------------------------------------------------------ #
# VECTORIZED LOSS — v7 (10-50x faster than per-cell loop)
# ------------------------------------------------------------------ #


def _build_neighbor_label_grid(
    target_fire: torch.Tensor, current_fire: torch.Tensor
) -> torch.Tensor:
    """Build a full (H, W, 8) grid of spread labels via vectorized shifts.

    For every cell (i,j), computes whether each of its 8 neighbors will ignite:
        label[i,j,k] = 1 if neighbor_k is burning in target but NOT in current.

    This replaces the per-cell ``get_8_neighbor_coords`` + if-chain with
    8 ``F.pad + roll`` operations — fully vectorized on GPU.

    Returns:
        spread_grid: (H, W, 8) float tensor on same device as inputs.
    """
    # New ignition = target has fire AND current does not
    new_ignition = (target_fire > 0.5).float() * (current_fire <= 0.5).float()  # (1,H,W)

    H, W = new_ignition.shape[1], new_ignition.shape[2]
    grid = new_ignition[0]  # (H, W)

    # Offset order must match get_8_neighbor_coords:
    # 0:(-1,0) 1:(-1,+1) 2:(0,+1) 3:(+1,+1) 4:(+1,0) 5:(+1,-1) 6:(0,-1) 7:(-1,-1)
    # For each offset (di,dj), we shift the grid so that position (i,j) contains
    # the value of its neighbor at (i+di, j+dj).
    # We use F.pad + slice to handle borders (out-of-bounds = 0, no spread).

    padded = F.pad(grid, (1, 1, 1, 1), mode="constant", value=0.0)  # (H+2, W+2)
    # In padded coords, original (i,j) maps to (i+1, j+1).
    # Neighbor (i+di, j+dj) maps to (i+1+di, j+1+dj).
    # To get a grid G where G[i,j] = padded[i+1+di, j+1+dj], we slice accordingly.

    shifts = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    channels = []
    for di, dj in shifts:
        # padded row range: [1+0+di : 1+H+di], col range: [1+0+dj : 1+W+dj]
        # With padding, indices that go out of [0..H+1] are clipped by the pad.
        # Since di,dj in [-1,1] and we padded by 1, this is always valid.
        r0 = 1 + di
        c0 = 1 + dj
        shifted = padded[r0 : r0 + H, c0 : c0 + W]
        channels.append(shifted)

    spread_grid = torch.stack(channels, dim=-1)  # (H, W, 8)
    return spread_grid


def calculate_local_spread_loss_vectorized(
    model: LocalSpreadModel,
    features: torch.Tensor,
    current_fire: torch.Tensor,
    target_fire: torch.Tensor,
    sequence: torch.Tensor | None = None,
    pos_weight: float = DEFAULT_POS_WEIGHT,
    focal_gamma: float = DEFAULT_FOCAL_GAMMA,
    spread_bonus: float = 0.5,
    lambda_physics: float = DEFAULT_LAMBDA_PHYSICS,
) -> torch.Tensor | None:
    """VECTORIZED loss — replaces per-cell Python loop with batched GPU ops.

    Speedup: 10-50x over ``calculate_local_spread_loss``.

    How it works:
    1. Use ``F.unfold`` to extract ALL 3x3 patches from features in one op.
    2. Run ``policy_head`` once on the entire batch of patches.
    3. Build labels via vectorized grid shifts (no per-cell if-chains).
    4. Index only the burning cells and compute focal BCE in one shot.

    Args:
        features: (1, 256, H, W) fused spatial features from model.forward()
        current_fire: (1, H, W) current fire mask
        target_fire: (1, H, W) target fire mask

    Returns:
        Scalar loss tensor, or None if no burning cells.
    """
    # 1. Find burning cells
    fire_2d = current_fire[0] if current_fire.dim() == 3 else current_fire
    burning_mask = fire_2d > 0.5  # (H, W) bool
    N_burning = int(burning_mask.sum().item())

    if N_burning == 0:
        return None

    H, W = fire_2d.shape

    # 2. Extract ALL 3x3 patches in ONE operation via unfold
    #    features: (1, 256, H, W) -> unfold(3) -> (1, 256*9, (H-2)*(W-2))
    #    We pad features by 1px so edge cells get zero-padded patches.
    padded_features = F.pad(features, (1, 1, 1, 1), mode="constant", value=0)  # (1,256,H+2,W+2)
    # unfold kernel=3, stride=1: output positions correspond to top-left of each 3x3 window
    # Position (0,0) in unfolded = patch centered at (1,1) in padded = (0,0) in original
    patches = F.unfold(padded_features, kernel_size=3, stride=1)  # (1, 256*9, H*W)
    patches = patches.permute(0, 2, 1).squeeze(0)  # (H*W, 256*9)

    # 3. Run policy_head ONCE on all patches
    all_logits = model.policy_head(patches)  # (H*W, 8)
    # Reshape to spatial grid: (H, W, 8)
    all_logits = all_logits.view(H, W, 8)

    # 4. Extract logits ONLY for burning cells
    burning_logits = all_logits[burning_mask]  # (N_burning, 8)

    # 5. Build labels via vectorized grid shifts
    spread_grid = _build_neighbor_label_grid(target_fire, current_fire)  # (H, W, 8)
    burning_labels = spread_grid[burning_mask]  # (N_burning, 8)

    # 6. Focal BCE — batched for all burning cells at once
    #    focal_loss_with_logits expects (N, *) shaped inputs and averages.
    loss = focal_loss_with_logits(
        burning_logits,
        burning_labels,
        gamma=focal_gamma,
        pos_weight=pos_weight,
    )

    # 7. Spread-direction bonus (soft IoU) — vectorized
    with torch.no_grad():
        probs = torch.sigmoid(burning_logits)  # (N, 8)
    predicted_positive = (probs > 0.5).float()
    tp = (predicted_positive * burning_labels).sum(dim=1)  # (N,)
    fp = (predicted_positive * (1 - burning_labels)).sum(dim=1)
    fn = ((1 - predicted_positive) * burning_labels).sum(dim=1)
    denom = tp + fp + fn
    soft_iou = tp / denom.clamp(min=1.0)  # (N,)
    bonus = -spread_bonus * soft_iou.mean()

    # 8. Physics loss (optional, kept simple/vectorized)
    physics_term = torch.tensor(0.0, device=features.device)
    if sequence is not None and lambda_physics > 0:
        last_ts = sequence[0, -1]  # (C, H, W)
        wind_grid = last_ts[4][burning_mask]  # (N,)
        slope_grid = last_ts[0][burning_mask]  # (N,)
        ffmc_grid = (
            last_ts[16][burning_mask]
            if last_ts.shape[0] > 16
            else torch.full((N_burning,), 90.0, device=features.device)
        )
        probs_det = torch.sigmoid(burning_logits).detach()
        # Vectorized physics loss per cell (mean over 8 neighbors)
        for idx in range(N_burning):
            physics_term += physics_loss_cell(
                probs_det[idx],
                float(wind_grid[idx]),
                float(slope_grid[idx]),
                ffmc=float(ffmc_grid[idx]),
                lambda_physics=lambda_physics,
            )
        physics_term = physics_term / N_burning

    return loss + bonus + physics_term


def fine_tune_model(
    images_dir: Path,
    masks_dir: Path,
    weights_path: Path,
    output_weights_path: Path,
    epochs: int = 5,
    lr: float = 1e-4,
    max_patches: int | None = None,
) -> dict[str, object]:
    """
    Perform behavior-cloning fine-tuning on the local dataset.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1. Initialize dataset and dataloader (batch size must be 1 due to model assertions)
    dataset = WildfireDataset(
        images_dir, masks_dir, sequence_length=3, patch_size=30, max_patches=max_patches
    )
    dataloader = DataLoader(dataset, batch_size=1, shuffle=True)

    # 2. Load model and restore pre-trained weights
    model: LocalSpreadModel = A3C_PerCellModel_LSTM(  # type: ignore[assignment]
        in_channels=17, lstm_hidden=256, sequence_length=3
    )

    print(f"Loading pre-trained weights from {weights_path}...")
    load_pretrained_weights(model, weights_path)
    model.to(device)

    # 3. Optimize policy weights
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()

    history = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        steps = 0
        for sequence, current_fire, target_fire in dataloader:
            sequence = sequence.to(device)
            current_fire = current_fire.to(device)
            target_fire = target_fire.to(device)

            # Forward pass: extract features
            # sequence shape: (1, 3, 16, 30, 30)
            # current_fire shape: (1, 30, 30)
            features, value = model.forward(sequence, current_fire)

            # Compute local transitions loss
            loss = calculate_local_spread_loss(model, features, current_fire, target_fire)

            if loss is not None:
                optimizer.zero_grad()
                loss.backward()
                # Gradient clipping to stabilize recurrent updates
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
                optimizer.step()

                epoch_loss += loss.item()
                steps += 1

        avg_loss = epoch_loss / steps if steps > 0 else 0.0
        print(f"Epoch {epoch + 1}/{epochs} - Loss: {avg_loss:.6f}")
        history.append(avg_loss)

    # 4. Save the fine-tuned model checkpoint
    output_weights_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "epochs": epochs,
            "final_loss": history[-1] if history else 0.0,
        },
        output_weights_path,
    )
    print(f"Fine-tuned weights successfully saved to {output_weights_path}")
    return {"status": "success", "loss_history": history}
