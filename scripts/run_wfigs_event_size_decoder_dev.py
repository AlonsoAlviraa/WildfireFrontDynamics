#!/usr/bin/env python3
"""Tune a fixed previous-fire-size threshold decoder on WFIGS DEV only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_wfigs_weighted_ensemble_dev import (  # noqa: E402
    _assert_dev_only,
    _load_probability_cache,
)
from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    confusion,
    make_loader,
    metrics_from_confusion,
)
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402

AREA_BINS = (0, 100, 500, 2000, float("inf"))
THRESHOLD_VALUES = (0.25, 0.30, 0.35, 0.40, 0.45)
MAX_DISTANCE_GRID = (None, 8.0, 12.0, 16.0, 24.0, 32.0)


def _area_bin(area_pixels: int) -> int:
    for index, upper in enumerate(AREA_BINS[1:]):
        if area_pixels < upper:
            return index
    return len(AREA_BINS) - 2


def _evaluate(
    probabilities: np.ndarray,
    uids: list[str],
    previous: np.ndarray,
    distance: np.ndarray,
    targets: np.ndarray,
    thresholds: tuple[float, ...],
    max_distance_px: float | None,
) -> dict[str, float | int | None]:
    per_event: dict[str, np.ndarray] = {}
    total = np.zeros(4, dtype=np.int64)
    mean_probability = probabilities.mean(axis=1)
    for index, uid in enumerate(uids):
        threshold = thresholds[_area_bin(int(previous[index].sum()))]
        prediction = (mean_probability[index] >= threshold) & ~previous[index]
        if max_distance_px is not None:
            prediction &= distance[index] <= max_distance_px
        row = confusion(prediction, targets[index])
        total += row
        per_event.setdefault(uid, np.zeros(4, dtype=np.int64))
        per_event[uid] += row
    result = metrics_from_confusion(total)
    event_iou = [float(metrics_from_confusion(row)["iou"]) for row in per_event.values()]
    result.update(
        {
            "event_macro_iou": float(np.mean(event_iou)) if event_iou else 0.0,
            "n_events": len(event_iou),
            "thresholds_by_area_bin": list(thresholds),
            "max_distance_px": max_distance_px,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_checkpoints", type=Path, nargs=3)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)
    manifest = json.loads((args.wfigs_dev_root / "validation.json").read_text(encoding="utf-8"))
    normalization = json.loads(args.rcda_normalization.read_text(encoding="utf-8"))
    if normalization.get("fit_split") != "train":
        raise ValueError("normalization must be fitted on TRAIN")
    dataset = WFIGSExternalDataset(
        dataset_root=args.wfigs_dev_root,
        manifest=manifest,
        rcda_normalization=normalization,
        augment=False,
    )
    loader = make_loader(dataset, batch_size=4, shuffle=False, weighted=False, num_workers=0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    probabilities, uids, previous, distance, targets = _load_probability_cache(
        list(args.source_checkpoints), loader, device
    )
    ranking = []
    import itertools

    for thresholds in itertools.product(THRESHOLD_VALUES, repeat=4):
        for max_distance_px in MAX_DISTANCE_GRID:
            ranking.append(
                _evaluate(
                    probabilities,
                    uids,
                    previous,
                    distance,
                    targets,
                    thresholds,
                    max_distance_px,
                )
            )
    ranking.sort(key=lambda row: float(row["event_macro_iou"]), reverse=True)
    report = {
        "schema": "wfd_wfigs_event_size_decoder_dev_v1",
        "selection_split": "wfigs_development_validation",
        "events": len(set(uids)),
        "samples": len(uids),
        "area_bins_previous_pixels": list(AREA_BINS),
        "threshold_grid": list(THRESHOLD_VALUES),
        "max_distance_grid_px": list(MAX_DISTANCE_GRID),
        "best": ranking[0],
        "ranking": ranking,
        "confirmation_loaded": False,
        "prospective_test_loaded": False,
        "test_used_for_selection": False,
        "raw_artifacts_published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(ranking[0], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
