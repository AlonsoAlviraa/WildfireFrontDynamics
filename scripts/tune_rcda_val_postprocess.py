#!/usr/bin/env python3
"""Tune a small spatial post-processing grid on sealed RCDA VALIDATION only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy.ndimage import binary_dilation, label

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    SEALED_CHANNEL_NAMES,
    SealedRCDADataset,
    build_model,
    confusion,
    load_protocol,
    make_loader,
    metrics_from_confusion,
)

THRESHOLDS = tuple(float(value) for value in np.arange(0.05, 1.0, 0.05))
DILATION_RADII = (0, 1, 2)
CONNECTIVITY_OPTIONS = (False, True)
STRUCTURE = np.ones((3, 3), dtype=bool)


def postprocess_growth(
    prediction: np.ndarray,
    previous: np.ndarray,
    *,
    dilation_radius: int,
    require_t0_connection: bool,
) -> np.ndarray:
    """Expand a growth front and optionally retain only components touching t0."""

    growth = np.asarray(prediction, dtype=bool) & ~np.asarray(previous, dtype=bool)
    previous_bool = np.asarray(previous, dtype=bool)
    if dilation_radius > 0:
        growth = binary_dilation(
            growth,
            structure=STRUCTURE,
            iterations=int(dilation_radius),
        )
        growth &= ~previous_bool
    if require_t0_connection and previous_bool.any() and growth.any():
        components, _count = label(previous_bool | growth, structure=STRUCTURE)
        touching = np.unique(components[previous_bool])
        touching = touching[touching != 0]
        growth = np.isin(components, touching) & ~previous_bool
    return growth


def evaluate_postprocess_grid(
    probabilities: np.ndarray,
    targets: np.ndarray,
    previous: np.ndarray,
    event_ids: list[str],
    *,
    thresholds: tuple[float, ...] = THRESHOLDS,
    dilation_radii: tuple[int, ...] = DILATION_RADII,
    connectivity_options: tuple[bool, ...] = CONNECTIVITY_OPTIONS,
) -> list[dict[str, Any]]:
    if not (
        len(probabilities) == len(targets) == len(previous) == len(event_ids)
    ):
        raise ValueError("prediction arrays and event_ids must have equal length")
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        thresholded = probabilities >= threshold
        for radius in dilation_radii:
            for connected in connectivity_options:
                pooled = np.zeros(4, dtype=np.int64)
                by_event: dict[str, np.ndarray] = defaultdict(
                    lambda: np.zeros(4, dtype=np.int64)
                )
                for index, event_id in enumerate(event_ids):
                    prediction = postprocess_growth(
                        thresholded[index],
                        previous[index],
                        dilation_radius=radius,
                        require_t0_connection=connected,
                    )
                    result = confusion(prediction, targets[index])
                    pooled += result
                    by_event[event_id] += result
                event_ious = [
                    float(metrics_from_confusion(result)["iou"])
                    for result in by_event.values()
                ]
                pooled_metrics = metrics_from_confusion(pooled)
                rows.append(
                    {
                        "threshold": threshold,
                        "dilation_radius_px": radius,
                        "require_t0_connection": connected,
                        "event_macro_iou": float(np.mean(event_ious)),
                        "pooled_iou": float(pooled_metrics["iou"]),
                        "events": len(by_event),
                    }
                )
    return sorted(rows, key=lambda row: float(row["event_macro_iou"]), reverse=True)


@torch.no_grad()
def collect_validation_predictions(
    checkpoint_path: Path,
    dataset_root: Path,
    protocol_dir: Path,
    *,
    batch_size: int = 8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], dict[str, Any]]:
    protocol = load_protocol(protocol_dir)
    dataset = SealedRCDADataset(
        dataset_root,
        protocol["manifests"]["val"],
        protocol["normalization"],
        augment=False,
    )
    loader = make_loader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        weighted=False,
        num_workers=0,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if checkpoint.get("selection_split") != "val":
        raise ValueError("checkpoint was not selected on VAL")
    model = build_model(
        str(checkpoint["model_name"]),
        in_channels=len(SEALED_CHANNEL_NAMES),
        base=int(checkpoint.get("base_channels", 32)),
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    probabilities: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    previous: list[np.ndarray] = []
    event_ids: list[str] = []
    for batch in loader:
        inputs = batch["input"]
        probs = torch.sigmoid(model(inputs.to(device))).cpu().numpy()[:, 0]
        previous_batch = inputs[:, 0].numpy() > 0.5
        if str(checkpoint.get("target_mode", "growth")) in {"extent", "hybrid"}:
            probs[previous_batch] = 0.0
        probabilities.extend(probs.astype(np.float16))
        targets.extend(batch["target"].numpy()[:, 0].astype(bool))
        previous.extend(previous_batch)
        event_ids.extend(str(value) for value in batch["uid"])
    return (
        np.asarray(probabilities),
        np.asarray(targets),
        np.asarray(previous),
        event_ids,
        checkpoint,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/dataset",
    )
    parser.add_argument(
        "--protocol-dir",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/protocol",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    probabilities, targets, previous, event_ids, checkpoint = (
        collect_validation_predictions(
            args.checkpoint,
            args.dataset_root,
            args.protocol_dir,
            batch_size=args.batch_size,
        )
    )
    ranking = evaluate_postprocess_grid(
        probabilities,
        targets,
        previous,
        event_ids,
    )
    report = {
        "schema": "wfd_rcda_val_postprocess_tune_v1",
        "selection_split": "val",
        "test_evaluated": False,
        "checkpoint": str(args.checkpoint),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "model_name": checkpoint["model_name"],
        "target_mode": checkpoint.get("target_mode", "growth"),
        "grid": {
            "thresholds": list(THRESHOLDS),
            "dilation_radii_px": list(DILATION_RADII),
            "require_t0_connection": list(CONNECTIVITY_OPTIONS),
        },
        "best": ranking[0],
        "ranking": ranking,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["best"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
