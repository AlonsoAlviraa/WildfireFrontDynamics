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
    # Per-element BCE without reduction
    bce = F.binary_cross_entropy_with_logits(
        logits, targets, reduction="none", pos_weight=torch.tensor(pos_weight, device=logits.device)
    )
    # Compute p_t (probability of correct class) for focal modulation
    p = torch.sigmoid(logits)
    p_t = p * targets + (1.0 - p) * (1.0 - targets)
    focal_factor = (1.0 - p_t) ** gamma
    return (focal_factor * bce).mean()


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
    """Compute focal-weighted loss for burning-cell neighbor spread.

    Combines:
    1. **Focal BCE with pos_weight**: Penalizes false negatives heavily
       (missed fire spread is the #1 cause of low recall).
    2. **Spread-direction bonus**: Adds a small reward when the model
       correctly predicts the direction of active spread, encouraging
       it to "commit" to real propagation patterns.
    3. **Physics-informed penalty (Sprint 4)**: When ``sequence`` is provided,
       penalises predictions that violate Rothermel's maximum rate of spread.

    Args:
        sequence: Optional input sequence (1, seq_len, C, H, W) — used to
                  extract wind/slope channels for physics loss. If None,
                  physics loss is disabled.
        pos_weight: Weight for positive (fire spread) class. Higher = more recall.
        focal_gamma: Focal loss focusing parameter. 0 disables focal modulation.
        spread_bonus: Weight for auxiliary direction-consistency term.
        lambda_physics: Weight for Rothermel ROS physics loss.
    """
    burning_cells = model.get_burning_cells(current_fire)
    if not burning_cells:
        return None

    loss_sum = torch.tensor(0.0, device=features.device)
    bonus_sum = torch.tensor(0.0, device=features.device)
    physics_sum = torch.tensor(0.0, device=features.device)
    count = 0

    H, W = current_fire.shape[1], current_fire.shape[2]

    # Extract wind/slope/FFMC from last timestep for physics loss
    # sequence shape: (1, seq_len, C, H, W)
    use_physics = sequence is not None and lambda_physics > 0
    if use_physics:
        last_ts = sequence[0, -1]  # (C, H, W)
        # Channel 0 = slope (radians), Channel 4 = wind_speed (m/s)
        # Channel 16 = FFMC (if 17-channel dataset), else use default
        wind_grid = last_ts[4]
        slope_grid = last_ts[0]
        ffmc_grid = last_ts[16] if last_ts.shape[0] > 16 else None

    for i, j in burning_cells:
        # Predict 8 logits: (1, 8)
        logits = model.predict_8_neighbors(features, i, j).squeeze(0)

        # Get target labels for the 8 neighbors
        labels = torch.zeros(8, device=features.device)
        neighbors = model.get_8_neighbor_coords(i, j, H, W)
        for n_idx, neighbor in enumerate(neighbors):
            if neighbor is not None:
                ni, nj = neighbor
                if target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5:
                    labels[n_idx] = 1.0

        # Focal-weighted BCE with pos_weight (replaces plain BCE)
        cell_loss = focal_loss_with_logits(
            logits, labels, gamma=focal_gamma, pos_weight=pos_weight
        )

        # Spread-direction bonus: reward when predicted probs correlate with
        # actual spread (soft IoU on 8-neighbor probabilities).
        with torch.no_grad():
            probs = torch.sigmoid(logits)
        predicted_positive = (probs > 0.5).float()
        tp = (predicted_positive * labels).sum()
        fp = (predicted_positive * (1 - labels)).sum()
        fn = ((1 - predicted_positive) * labels).sum()
        denom = tp + fp + fn
        soft_iou = tp / denom.clamp(min=1.0)
        # Bonus is negative (reduces loss) when IoU is high
        bonus_sum -= spread_bonus * soft_iou

        # Physics-informed penalty (Sprint 4): penalise impossible spread
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
