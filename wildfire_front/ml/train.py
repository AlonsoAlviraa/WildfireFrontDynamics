"""Supervised Fine-Tuning Routine for A3C-LSTM Policy.

Loads pre-trained weights, processes sequences from WildfireDataset, and performs
gradient descent using binary cross-entropy on local neighbor transitions.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from models.model import A3C_PerCellModel_LSTM
from .dataset import WildfireDataset


def calculate_local_spread_loss(
    model: nn.Module,
    features: torch.Tensor,
    current_fire: torch.Tensor,
    target_fire: torch.Tensor,
) -> torch.Tensor | None:
    """
    Compute binary cross entropy loss for all active burning cells spreading to neighbors.
    """
    burning_cells = model.get_burning_cells(current_fire)
    if not burning_cells:
        return None

    loss_sum = torch.tensor(0.0, device=features.device)
    count = 0

    H, W = current_fire.shape[1], current_fire.shape[2]

    for i, j in burning_cells:
        # Predict 8 logits: (1, 8)
        logits = model.predict_8_neighbors(features, i, j)

        # Get target labels for the 8 neighbors
        labels = torch.zeros(8, device=features.device)
        neighbors = model.get_8_neighbor_coords(i, j, H, W)
        for n_idx, neighbor in enumerate(neighbors):
            if neighbor is not None:
                ni, nj = neighbor
                # A spread action is active (1.0) if the neighbor became active in target_fire
                # but was not already active in current_fire.
                if target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5:
                    labels[n_idx] = 1.0

        # Compute Binary Cross Entropy with Logits
        cell_loss = F.binary_cross_entropy_with_logits(logits.squeeze(0), labels)
        loss_sum += cell_loss
        count += 1

    return loss_sum / count if count > 0 else None


def fine_tune_model(
    images_dir: Path,
    masks_dir: Path,
    weights_path: Path,
    output_weights_path: Path,
    epochs: int = 5,
    lr: float = 1e-4,
) -> dict[str, object]:
    """
    Perform behavior-cloning fine-tuning on the local dataset.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1. Initialize dataset and dataloader (batch size must be 1 due to model assertions)
    dataset = WildfireDataset(images_dir, masks_dir, sequence_length=3, patch_size=30)
    dataloader = DataLoader(dataset, batch_size=1, shuffle=True)

    # 2. Load model and restore pre-trained weights
    model = A3C_PerCellModel_LSTM(in_channels=16, lstm_hidden=256, sequence_length=3)
    
    print(f"Loading pre-trained weights from {weights_path}...")
    checkpoint = torch.load(weights_path, map_location=device)
    
    # Extract state dict if it's a structured checkpoint
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
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
