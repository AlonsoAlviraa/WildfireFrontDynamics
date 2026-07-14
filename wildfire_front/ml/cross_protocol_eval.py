"""Evaluate saved U-Net checkpoints on a shared test split (cross-protocol)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.unet_train import (
    UNetTrainConfig,
    build_model,
    evaluate_loader,
    select_device,
)


def evaluate_checkpoint(
    weights_path: Path | str,
    data_dir: Path | str,
    *,
    version_tag: str,
    architecture: str = "standard",
    target_mode: str = "absolute",
    batch_size: int = 32,
    primary_threshold: float = 0.5,
) -> dict:
    """Load weights and run NDWS evaluation on ``data_dir/test``."""
    weights_path = Path(weights_path)
    data_dir = Path(data_dir)
    test_dir = data_dir / "test"
    if not weights_path.is_file():
        raise FileNotFoundError(f"Weights not found: {weights_path}")
    if not test_dir.is_dir():
        raise FileNotFoundError(f"Test split not found: {test_dir}")

    config = UNetTrainConfig(
        batch_size=batch_size,
        architecture=architecture,
        target_mode=target_mode,
        version_tag=version_tag,
        data_dir=str(data_dir),
        output_dir=str(data_dir / "_eval_scratch"),
        smoke_test=False,
        weighted_sampler=False,
        early_stop_metric="improvement_vs_copy_iou",
        primary_threshold=primary_threshold,
    )

    test_ds = NpzWildfireDataset(test_dir, augment=False)
    if len(test_ds) == 0:
        raise RuntimeError(f"No test patches in {test_dir}")

    test_loader = DataLoader(
        test_ds,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
    )

    device, use_amp = select_device()
    sample_seq, sample_curr, _ = test_ds[0]
    in_channels = sample_seq.shape[0] * sample_seq.shape[1] + 1
    model = build_model(config, in_channels).to(device)
    state = torch.load(weights_path, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()

    results = evaluate_loader(model, test_loader, device, config, use_amp=use_amp)
    primary = results.get(f"thresh_{primary_threshold}", {})
    return {
        "version": version_tag,
        "architecture": model.__class__.__name__,
        "target_mode": target_mode,
        "weights_path": str(weights_path),
        "test_samples": len(test_ds),
        "test_iou": float(primary.get("model_iou", 0.0)),
        "copy_baseline_iou": float(primary.get("copy_baseline_iou", 0.0)),
        "dilated_copy_baseline_iou": float(primary.get("dilated_copy_baseline_iou", 0.0)),
        "improvement_vs_copy_iou": float(primary.get("improvement_vs_copy_iou", 0.0)),
        "improvement_vs_dilated_copy_iou": float(
            primary.get("improvement_vs_dilated_copy_iou", 0.0)
        ),
        "model_iou_changed": float(primary.get("model_iou_changed", 0.0)),
        "improvement_vs_copy_iou_changed": float(
            primary.get("improvement_vs_copy_iou_changed", 0.0)
        ),
        "legacy_improvement_vs_naive_copy_iou_changed": float(
            primary.get("legacy_improvement_vs_naive_copy_iou_changed", 0.0)
        ),
        "model_iou_growth": float(primary.get("model_iou_growth", 0.0)),
        "improvement_vs_dilated_copy_iou_growth": float(
            primary.get("improvement_vs_dilated_copy_iou_growth", 0.0)
        ),
        "config": asdict(config),
        "test_metrics": results,
    }


def run_cross_protocol_eval(
    checkpoints: dict[str, dict],
    data_dir: Path | str,
    output_path: Path | str,
) -> dict:
    """Evaluate multiple checkpoints on the same test directory."""
    data_dir = Path(data_dir)
    output_path = Path(output_path)
    report: dict = {
        "protocol": "v19_test_any_fire",
        "data_dir": str(data_dir),
        "results": {},
    }
    for name, spec in checkpoints.items():
        report["results"][name] = evaluate_checkpoint(
            spec["weights"],
            data_dir,
            version_tag=name,
            architecture=spec.get("architecture", "standard"),
            target_mode=spec.get("target_mode", "absolute"),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str))
    return report