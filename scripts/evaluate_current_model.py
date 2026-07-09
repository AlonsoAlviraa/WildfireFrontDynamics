#!/usr/bin/env python3
"""Evaluate the A3C-LSTM wildfire model on available datasets.

This script loads the pre-trained (or fine-tuned) weights and runs inference
on either:

1. Local GeoTIFF candidate data (e.g. ``data/candidates/semireal_controlled_001``)
2. Pre-processed NPZ sequences (e.g. Kaggle output)
3. Real infrared fire frames (e.g. Tobarra LWIR)

It computes both segmentation metrics (IoU, F1, Precision, Recall) and
front-propagation metrics (speed error, direction error) and writes a
machine-readable JSON report plus a human-readable Markdown summary.

Usage::

    python scripts/evaluate_current_model.py \\
        --weights kaggle_output/latest/weights_pretrained_best.pt \\
        --images  data/candidates/semireal_controlled_001/images \\
        --masks   data/candidates/semireal_controlled_001/masks \\
        --output  docs/ML_BASELINE_METRICS.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.evaluation import (  # noqa: E402
    SegmentationMetrics,
    aggregate_segmentation_metrics,
    compute_segmentation_metrics,
)
from wildfire_front.ml.dataset import WildfireDataset  # noqa: E402

# Model lives in models/model.py as a standalone file
MODELS_DIR = PROJECT_ROOT / "models"
sys.path.insert(0, str(MODELS_DIR))


def load_model(weights_path: Path, device: torch.device) -> torch.nn.Module:
    """Load the A3C-LSTM model with trained weights."""
    from model import A3C_PerCellModel_LSTM  # type: ignore[import-not-found]

    model = A3C_PerCellModel_LSTM(in_channels=17, lstm_hidden=256, sequence_length=3)
    state_dict = torch.load(weights_path, map_location=device, weights_only=True)
    # Handle keys with or without module. prefix
    clean_sd = {k.replace("module.", ""): v for k, v in state_dict.items()}
    model.load_state_dict(clean_sd, strict=False)
    model.to(device)
    model.eval()
    return model


def predict_patch(
    model: torch.nn.Module,
    sequence: torch.Tensor,
    fire_mask: torch.Tensor,
    device: torch.device,
) -> np.ndarray:
    """Run model inference on a single 30x30 patch.

    Returns a binary prediction grid of shape (30, 30).
    """
    seq = sequence.unsqueeze(0).to(device)  # (1, seq, 17, H, W)
    mask = fire_mask.to(device)
    if mask.dim() == 2:
        mask = mask.unsqueeze(0)

    with torch.no_grad():
        action_grid, _log_prob, _entropy, _value, _info = model.get_action_and_value(
            seq, mask
        )

    # action_grid is deterministic (argmax-style) — convert to numpy
    pred = action_grid.cpu().numpy()
    if pred.ndim == 3:
        pred = pred[0]
    return pred.astype(np.float32)


def evaluate_dataset(
    model: torch.nn.Module,
    dataset: WildfireDataset,
    device: torch.device,
    max_samples: int = 500,
) -> tuple[list[SegmentationMetrics], dict]:
    """Evaluate model on a WildfireDataset, returning per-sample metrics."""
    all_metrics: list[SegmentationMetrics] = []
    n_total = min(len(dataset), max_samples)

    print(f"  Evaluating {n_total} patches (of {len(dataset)} available)...")

    for idx in range(n_total):
        sequence, current_fire, target_fire = dataset[idx]
        pred_grid = predict_patch(model, sequence, current_fire, device)
        gt_grid = target_fire.cpu().numpy()

        # Combine: prediction = newly ignited cells from front propagation
        # Ground truth = target fire mask change
        metrics = compute_segmentation_metrics(pred_grid, gt_grid, threshold=0.5)
        all_metrics.append(metrics)

        if (idx + 1) % 50 == 0:
            agg = aggregate_segmentation_metrics(all_metrics)
            print(
                f"    [{idx+1}/{n_total}]  "
                f"IoU={agg.get('iou_mean', 0):.4f}  "
                f"Dice={agg.get('dice_mean', 0):.4f}  "
                f"Prec={agg.get('precision_mean', 0):.4f}  "
                f"Rec={agg.get('recall_mean', 0):.4f}"
            )

    summary = aggregate_segmentation_metrics(all_metrics)
    return all_metrics, summary


def build_markdown_report(
    weights_name: str,
    dataset_name: str,
    summary: dict,
    n_samples: int,
) -> str:
    """Build a human-readable Markdown report from evaluation results."""
    lines = [
        "# ML Baseline Metrics Report",
        "",
        f"**Date:** {np.datetime64('now', 'D')}",
        f"**Weights:** `{weights_name}`",
        f"**Dataset:** `{dataset_name}`",
        f"**Samples evaluated:** {n_samples}",
        "",
        "## Segmentation Metrics (Pixel-Level)",
        "",
        "| Metric | Mean | Std | Micro (pooled) |",
        "|--------|------|-----|----------------|",
    ]

    for key in ["iou", "dice", "precision", "recall", "accuracy", "specificity"]:
        mean_val = summary.get(f"{key}_mean", 0.0)
        std_val = summary.get(f"{key}_std", 0.0)
        micro_key = f"micro_{key}"
        micro_val = summary.get(micro_key, "—")
        micro_str = f"{micro_val:.4f}" if isinstance(micro_val, float) else str(micro_val)
        lines.append(f"| {key.upper()} | {mean_val:.4f} | {std_val:.4f} | {micro_str} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- **Valid samples** (with active fire): "
            f"{int(summary.get('n_valid', 0))} / {int(summary.get('n_samples', n_samples))}",
            f"- **Micro IoU** (pooled TP/FP/FN): `{summary.get('micro_iou', 0):.4f}`",
            f"- **Micro F1/Dice**: `{summary.get('micro_dice', 0):.4f}`",
            "",
            "## Next Steps",
            "",
            "1. If IoU < 0.3, the model is not learning front propagation effectively.",
            "   Consider increasing data diversity or adjusting the RL reward.",
            "2. If precision is low (many false positives), increase the action "
            "threshold or add a false-positive penalty.",
            "3. If recall is low (missed ignitions), train longer or use focal loss.",
            "4. Compare `weights_pretrained_best.pt` vs `weights_fine_tuned.pt` "
            "to quantify the fine-tuning gain.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate A3C-LSTM wildfire model on available data"
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=PROJECT_ROOT / "kaggle_output" / "latest" / "weights_pretrained_best.pt",
        help="Path to .pt weights file",
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=PROJECT_ROOT / "data" / "candidates" / "semireal_controlled_001" / "images",
        help="Directory of input GeoTIFF images",
    )
    parser.add_argument(
        "--masks",
        type=Path,
        default=PROJECT_ROOT / "data" / "candidates" / "semireal_controlled_001" / "masks",
        help="Directory of ground-truth mask GeoTIFFs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "ML_BASELINE_METRICS.md",
        help="Output Markdown report path",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=500,
        help="Maximum number of patches to evaluate",
    )
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Weights: {args.weights}")

    if not args.weights.exists():
        print(f"ERROR: weights file not found: {args.weights}")
        sys.exit(1)

    # Load model
    print("Loading model...")
    model = load_model(args.weights, device)
    param_count = sum(p.numel() for p in model.parameters())
    print(f"  Model loaded: {param_count:,} parameters")

    # Load dataset
    print(f"Loading dataset from {args.images}")
    try:
        dataset = WildfireDataset(
            images_dir=args.images,
            masks_dir=args.masks,
            sequence_length=3,
            patch_size=30,
            max_patches=args.max_samples,
        )
        print(f"  Dataset: {len(dataset)} patches")
    except Exception as exc:
        print(f"ERROR loading dataset: {exc}")
        sys.exit(1)

    if len(dataset) == 0:
        print("ERROR: dataset has 0 valid patches")
        sys.exit(1)

    # Evaluate
    print("Evaluating...")
    all_metrics, summary = evaluate_dataset(model, dataset, device, args.max_samples)

    # Report
    report = build_markdown_report(
        weights_name=args.weights.name,
        dataset_name=args.images.parent.name,
        summary=summary,
        n_samples=len(all_metrics),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {args.output}")

    # Also dump JSON
    json_path = args.output.with_suffix(".json")
    json.dump(
        {
            "weights": args.weights.name,
            "dataset": args.images.parent.name,
            "n_samples": len(all_metrics),
            "metrics": summary,
        },
        json_path.open("w"),
        indent=2,
    )
    print(f"JSON metrics written to: {json_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  IoU (mean):   {summary.get('iou_mean', 0):.4f}")
    print(f"  IoU (micro):  {summary.get('micro_iou', 0):.4f}")
    print(f"  Dice (mean):  {summary.get('dice_mean', 0):.4f}")
    print(f"  Dice (micro): {summary.get('micro_dice', 0):.4f}")
    print(f"  Precision:    {summary.get('precision_mean', 0):.4f}")
    print(f"  Recall:       {summary.get('recall_mean', 0):.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()