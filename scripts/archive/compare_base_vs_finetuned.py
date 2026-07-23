"""Qualitative validation: compare base vs fine-tuned model predictions.

Loads a few patches from the Tobarra dataset, runs both models, and reports
how many burning-cell neighbor predictions match the ground truth. This is a
sanity check that fine-tuning has not destroyed the base policy and that the
thermal signal is being consumed.

Usage::

    set PYTHONPATH=. && python scripts/compare_base_vs_finetuned.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

# scripts/archive/<this file> → repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from models.model import A3C_PerCellModel_LSTM  # noqa: E402
from wildfire_front.ml.dataset import WildfireDataset  # noqa: E402
from wildfire_front.ml.weights import load_pretrained_weights  # noqa: E402


def evaluate(model: torch.nn.Module, dataloader, device, label: str) -> dict:
    model.eval()
    total_cells = 0
    correct = 0
    predicted_spread = 0
    target_spread = 0
    with torch.no_grad():
        for seq, current_fire, target_fire in dataloader:
            seq = seq.to(device)
            current_fire = current_fire.to(device)
            target_fire = target_fire.to(device)
            features, _ = model.forward(seq, current_fire)
            burning_cells = model.get_burning_cells(current_fire)
            H, W = current_fire.shape[1], current_fire.shape[2]
            for i, j in burning_cells:
                logits = model.predict_8_neighbors(features, i, j)
                preds = (torch.sigmoid(logits.squeeze(0)) > 0.5).float()
                neighbors = model.get_8_neighbor_coords(i, j, H, W)
                for n_idx, neighbor in enumerate(neighbors):
                    if neighbor is None:
                        continue
                    ni, nj = neighbor
                    target_label = float(
                        target_fire[0, ni, nj] > 0.5 and current_fire[0, ni, nj] <= 0.5
                    )
                    pred_label = float(preds[n_idx])
                    total_cells += 1
                    correct += int(pred_label == target_label)
                    predicted_spread += int(pred_label == 1)
                    target_spread += int(target_label == 1)
    acc = correct / total_cells if total_cells else 0.0
    print(
        f"[{label}] neighbor-pairs={total_cells}  acc={acc:.3f}  "
        f"pred_spread={predicted_spread}  target_spread={target_spread}"
    )
    return {
        "label": label,
        "acc": acc,
        "total": total_cells,
        "pred_spread": predicted_spread,
        "target_spread": target_spread,
    }


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    images_dir = ROOT / "artifacts" / "tobarra_reprojected_lwir"
    masks_dir = ROOT / "artifacts" / "tobarra_lwir_masks"
    base_weights = ROOT / "models" / "v3.pt"
    ft_weights = ROOT / "models" / "tobarra_finetuned.pt"

    if not ft_weights.exists():
        print(f"ERROR: fine-tuned weights not found: {ft_weights}")
        return 1

    dataset = WildfireDataset(
        images_dir, masks_dir, sequence_length=3, patch_size=30, max_patches=30
    )
    dataloader = DataLoader(dataset, batch_size=1, shuffle=False)

    print(f"Dataset: {len(dataset)} patches from {images_dir.name}")
    print()

    # Base model
    base_model = A3C_PerCellModel_LSTM(in_channels=17, lstm_hidden=256, sequence_length=3)
    load_pretrained_weights(base_model, base_weights)
    base_model.to(device)
    evaluate(base_model, dataloader, device, "BASE")

    # Fine-tuned model
    ft_model = A3C_PerCellModel_LSTM(in_channels=17, lstm_hidden=256, sequence_length=3)
    load_pretrained_weights(ft_model, ft_weights)
    ft_model.to(device)
    evaluate(ft_model, dataloader, device, "FINE-TUNED")

    print()
    print("Interpretation:")
    print("  - If FINE-TUNED acc >= BASE acc, fine-tuning improved (or preserved) predictions.")
    print("  - target_spread > 0 confirms the materialized masks contain real spread transitions.")
    print("  - pred_spread > 0 confirms the model is emitting non-trivial spread predictions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
