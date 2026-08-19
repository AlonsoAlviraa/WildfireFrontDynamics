"""Tune a growth-ring persistence baseline on RCDA VAL and evaluate TEST once."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL_ROOT = ROOT / "data/external/rcda_net_full"
DEFAULT_OUTPUT = ROOT / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json"
RADII = tuple(range(1, 9))


def _confusion(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    pred = prediction.astype(bool)
    truth = target.astype(bool)
    return np.array(
        [
            np.logical_and(pred, truth).sum(),
            np.logical_and(~pred, ~truth).sum(),
            np.logical_and(pred, ~truth).sum(),
            np.logical_and(~pred, truth).sum(),
        ],
        dtype=np.int64,
    )


def _metrics(confusion: np.ndarray) -> dict[str, float | int]:
    tp, tn, fp, fn = (int(value) for value in confusion)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def _uid(name: str) -> str:
    return name.rsplit("_", 1)[0]


def _evaluate_split(
    full_root: Path,
    manifest: dict[str, Any],
    radii: tuple[int, ...],
) -> tuple[dict[int, np.ndarray], dict[int, dict[str, np.ndarray]], np.ndarray]:
    dataset_root = full_root / "dataset"
    growth_confusions = {radius: np.zeros(4, dtype=np.int64) for radius in radii}
    event_confusions: dict[int, dict[str, np.ndarray]] = {
        radius: defaultdict(lambda: np.zeros(4, dtype=np.int64)) for radius in radii
    }
    copy_extent_confusion = np.zeros(4, dtype=np.int64)
    for index, row in enumerate(manifest["samples"], start=1):
        inputs = np.load(dataset_root / row["input"], mmap_mode="r", allow_pickle=False)
        label = np.load(dataset_root / row["label"], mmap_mode="r", allow_pickle=False)
        previous = np.asarray(inputs[0]) > 0.5
        next_extent = np.asarray(label) > 0.5
        growth = np.logical_and(~previous, next_extent)
        distance = distance_transform_edt(~previous)
        copy_extent_confusion += _confusion(previous, next_extent)
        uid = _uid(row["name"])
        for radius in radii:
            prediction = np.logical_and(~previous, distance <= radius)
            row_confusion = _confusion(prediction, growth)
            growth_confusions[radius] += row_confusion
            event_confusions[radius][uid] += row_confusion
        if index % 250 == 0:
            print(
                f"[rcda-baseline] {manifest['split']} {index}/{manifest['n_samples']}",
                flush=True,
            )
    return growth_confusions, event_confusions, copy_extent_confusion


def evaluate(full_root: Path, output: Path) -> dict[str, Any]:
    protocol_root = full_root / "protocol"
    val_manifest = json.loads((protocol_root / "val.json").read_text(encoding="utf-8"))
    test_manifest = json.loads((protocol_root / "test.json").read_text(encoding="utf-8"))
    val_confusions, val_events, _val_copy = _evaluate_split(
        full_root, val_manifest, RADII
    )
    val_results = {}
    for radius, confusion in val_confusions.items():
        event_ious = np.asarray(
            [_metrics(row)["iou"] for row in val_events[radius].values()],
            dtype=np.float64,
        )
        val_results[str(radius)] = {
            **_metrics(confusion),
            "event_macro_iou": float(event_ious.mean()),
            "event_median_iou": float(np.median(event_ious)),
        }
    selected_radius = max(
        RADII,
        key=lambda radius: float(val_results[str(radius)]["event_macro_iou"]),
    )
    test_confusions, test_events, test_copy = _evaluate_split(
        full_root, test_manifest, (selected_radius,)
    )
    test_result = _metrics(test_confusions[selected_radius])
    copy_extent_result = _metrics(test_copy)
    per_event = {
        uid: _metrics(row)
        for uid, row in sorted(test_events[selected_radius].items())
    }
    event_ious = np.array(
        [float(row["iou"]) for row in per_event.values()], dtype=np.float64
    )
    report = {
        "schema": "wfd_rcda_sealed_dilated_copy_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "complete",
        "protocol": {
            "event_disjoint_manifests": True,
            "selection_split": "val",
            "test_evaluated_after_radius_frozen": True,
            "test_used_for_selection": False,
        },
        "validation": {
            "samples": val_manifest["n_samples"],
            "events": val_manifest["n_events"],
            "candidate_radii_pixels": list(RADII),
            "results": val_results,
            "selected_radius_pixels": selected_radius,
            "selection_metric": "event_macro_growth_iou",
            "test_used_for_selection": False,
        },
        "test": {
            "samples": test_manifest["n_samples"],
            "events": test_manifest["n_events"],
            "growth_ring_result": test_result,
            "copy_full_extent_result": copy_extent_result,
            "event_macro_growth_iou": float(event_ious.mean()),
            "event_median_growth_iou": float(np.median(event_ious)),
            "per_event_growth": per_event,
        },
        "interpretation": {
            "model": "morphological_dilated_copy_baseline",
            "rcda_network": False,
            "purpose": "primary-metric-aligned sealed comparator for RCDA paper evaluation",
            "legacy_note": (
                "The prior pooled-IoU radius selection is preserved separately; "
                "this artifact selects on VAL event-macro IoU to match the paper endpoint."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-root", type=Path, default=DEFAULT_FULL_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate(args.full_root, args.output)
    print(
        json.dumps(
            {
                "status": report["status"],
                "selected_radius": report["validation"]["selected_radius_pixels"],
                "test_growth": report["test"]["growth_ring_result"],
                "test_copy_extent": report["test"]["copy_full_extent_result"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
