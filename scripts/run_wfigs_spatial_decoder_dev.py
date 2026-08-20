#!/usr/bin/env python3
"""Tune a spatial decoder on WFIGS expansion DEV only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    DISTANCE_CAP_PX,
    SEALED_CHANNEL_NAMES,
    ProbabilityAveragingEnsemble,
    build_model,
    confusion,
    make_loader,
    postprocess_growth,
    prepare_inputs_for_device,
    prepare_model_for_device,
    restrict_growth_to_distance,
)
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json  # noqa: E402

THRESHOLDS = tuple(round(value, 2) for value in np.arange(0.10, 0.81, 0.05))
MAX_DISTANCES: tuple[float | None, ...] = (None, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0)
DILATION_RADII = (0, 1, 2)
CONNECTIVITY = (False, True)


def _assert_dev_only(dataset_root: Path) -> None:
    lowered = dataset_root.name.lower()
    if any(token in lowered for token in ("confirm", "test", "prospective")):
        raise ValueError(f"spatial decoder accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def _load_ensemble(final_summary_path: Path, device: torch.device) -> tuple[torch.nn.Module, list[int]]:
    final = json.loads(Path(final_summary_path).read_text(encoding="utf-8"))
    if final.get("test_used_for_selection") is not False:
        raise ValueError("source summary does not prove selection isolation")
    models: list[torch.nn.Module] = []
    seeds: list[int] = []
    for source in final.get("reports") or []:
        checkpoint = Path(source.get("checkpoint") or source.get("local_checkpoint", ""))
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        payload = torch.load(checkpoint, map_location=device, weights_only=False)
        if payload.get("selection_split") != "wfigs_validation":
            raise ValueError(f"source checkpoint was not selected on WFIGS DEV: {checkpoint}")
        if payload.get("wfigs_test_evaluated") is not False:
            raise ValueError(f"source checkpoint has test provenance: {checkpoint}")
        model = prepare_model_for_device(
            build_model(
                str(payload["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(payload["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(payload["state_dict"])
        models.append(model)
        seeds.append(int(payload["seed"]))
    if not models:
        raise ValueError("source summary contains no checkpoints")
    target_modes = {str(source["config"]["target_mode"]) for source in final["reports"]}
    if target_modes != {"hybrid"}:
        raise ValueError(f"spatial decoder requires hybrid sources, got {sorted(target_modes)}")
    return ProbabilityAveragingEnsemble(models), sorted(seeds)


def _collect_predictions(
    model: torch.nn.Module,
    loader: Any,
    device: torch.device,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            inputs = prepare_inputs_for_device(batch["input"], device)
            probabilities = torch.sigmoid(model(inputs)).cpu().numpy()[:, 0]
            previous = batch["input"].numpy()[:, 0] > 0.5
            distances = batch["input"].numpy()[:, 13] * DISTANCE_CAP_PX
            targets = batch["target"].numpy()[:, 0].astype(bool)
            for index, event_id in enumerate(batch["uid"]):
                rows.append(
                    {
                        "event_id": str(event_id),
                        "probabilities": probabilities[index],
                        "previous": previous[index],
                        "distance": distances[index],
                        "target": targets[index],
                    }
                )
    return rows


def _score(rows: list[dict[str, Any]], threshold: float, max_distance: float | None, dilation: int, connected: bool) -> dict[str, Any]:
    by_event: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    for row in rows:
        prediction = row["probabilities"] >= threshold
        prediction = postprocess_growth(
            prediction,
            row["previous"],
            dilation_radius=dilation,
            require_t0_connection=connected,
        )
        if max_distance is not None:
            prediction = restrict_growth_to_distance(
                prediction,
                row["previous"],
                row["distance"],
                max_distance_px=max_distance,
            )
        by_event[row["event_id"]] += confusion(prediction, row["target"])
    per_event = [float(row["iou"]) for row in (  # aggregate only; rows are not written
        _metrics(confusion_row) for confusion_row in by_event.values()
    )]
    pooled = _metrics(sum(by_event.values(), np.zeros(4, dtype=np.int64)))
    return {
        "threshold": threshold,
        "max_distance_px": max_distance,
        "dilation_radius_px": dilation,
        "require_t0_connection": connected,
        "event_macro_iou": float(np.mean(per_event)) if per_event else 0.0,
        "pooled_iou": float(pooled["iou"]),
        "precision": float(pooled["precision"]),
        "recall": float(pooled["recall"]),
        "events": len(per_event),
    }


def _metrics(row: np.ndarray) -> dict[str, float | int]:
    tp, tn, fp, fn = (int(value) for value in row)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)
    normalization = json.loads(Path(args.rcda_normalization).read_text(encoding="utf-8"))
    manifest = json.loads((args.wfigs_dev_root / "validation.json").read_text(encoding="utf-8"))
    dataset = WFIGSExternalDataset(
        dataset_root=args.wfigs_dev_root,
        manifest=manifest,
        rcda_normalization=normalization,
        augment=False,
    )
    loader = make_loader(dataset, batch_size=4, shuffle=False, weighted=False, num_workers=0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, seeds = _load_ensemble(args.final_summary, device)
    rows = _collect_predictions(model, loader, device)
    ranking = [
        _score(rows, threshold, max_distance, dilation, connected)
        for threshold in THRESHOLDS
        for max_distance in MAX_DISTANCES
        for dilation in DILATION_RADII
        for connected in CONNECTIVITY
    ]
    ranking.sort(key=lambda row: row["event_macro_iou"], reverse=True)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "wfd_wfigs_spatial_decoder_dev_v1",
        "dataset_scope": "frozen_wfigs_expansion_dev_only",
        "source_seeds": seeds,
        "selection_metric": "event_macro_iou",
        "validation_events": len(manifest.get("events") or []),
        "confirmation_loaded": False,
        "prospective_loaded": False,
        "grid_size": len(ranking),
        "best": ranking[0],
        "top10": ranking[:10],
        "interpretation": "directional_dev_only_no_new_confirmatory_claim",
    }
    _atomic_write_json(args.output / "SPATIAL_DECODER_DEV_RANKING.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

