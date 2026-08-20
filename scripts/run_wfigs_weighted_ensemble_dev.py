#!/usr/bin/env python3
"""Tune a tiny fixed-weight WFIGS ensemble grid on DEV only."""

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

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    DISTANCE_CAP_PX,
    SEALED_CHANNEL_NAMES,
    build_model,
    confusion,
    make_loader,
    metrics_from_confusion,
    prepare_inputs_for_device,
    prepare_model_for_device,
    prediction_logits,
)
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402


WEIGHT_GRID = (
    (1 / 3, 1 / 3, 1 / 3),
    (0.25, 0.25, 0.50),
    (0.20, 0.20, 0.60),
    (0.15, 0.15, 0.70),
)
THRESHOLD_GRID = tuple(round(value, 2) for value in np.arange(0.20, 0.51, 0.05))
MAX_DISTANCE_GRID = (None, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0)


def _assert_dev_only(dataset_root: Path) -> None:
    lowered = dataset_root.name.lower()
    if any(token in lowered for token in ("confirm", "test", "prospective")):
        raise ValueError(f"weighted ensemble runner accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def _load_probability_cache(
    checkpoints: list[Path],
    loader: torch.utils.data.DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, list[str], np.ndarray, np.ndarray, np.ndarray]:
    models = []
    for checkpoint_path in checkpoints:
        payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
        if payload.get("selection_split") != "wfigs_validation":
            raise ValueError(f"checkpoint was not selected on WFIGS DEV: {checkpoint_path}")
        if payload.get("wfigs_test_evaluated") is not False:
            raise ValueError(f"checkpoint does not prove TEST isolation: {checkpoint_path}")
        if payload.get("model_name") != "resunet" or payload.get("target_mode") != "hybrid":
            raise ValueError("weighted ensemble requires three hybrid resunet checkpoints")
        model = prepare_model_for_device(
            build_model(
                "resunet",
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(payload.get("base_channels", 32)),
            ),
            device,
        )
        model.load_state_dict(payload["state_dict"])
        model.eval()
        models.append(model)
    probabilities: list[np.ndarray] = []
    uids: list[str] = []
    previous: list[np.ndarray] = []
    distance: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    with torch.no_grad():
        for batch in loader:
            inputs = prepare_inputs_for_device(batch["input"], device)
            member_probs = [
                torch.sigmoid(prediction_logits(model(inputs), "hybrid"))
                .cpu()
                .numpy()[:, 0]
                for model in models
            ]
            probabilities.extend(np.stack(member_probs, axis=1))
            uids.extend(str(uid) for uid in batch["uid"])
            previous.extend(batch["input"][:, 0].numpy() > 0.5)
            distance.extend(batch["input"][:, 13].numpy() * DISTANCE_CAP_PX)
            targets.extend(batch["target"].numpy()[:, 0] > 0.5)
    return (
        np.asarray(probabilities, dtype=np.float32),
        uids,
        np.asarray(previous, dtype=bool),
        np.asarray(distance, dtype=np.float32),
        np.asarray(targets, dtype=bool),
    )


def _evaluate(
    probabilities: np.ndarray,
    uids: list[str],
    previous: np.ndarray,
    distance: np.ndarray,
    targets: np.ndarray,
    weights: tuple[float, ...],
    threshold: float,
    max_distance_px: float | None,
) -> dict[str, float | int | None]:
    per_event: dict[str, np.ndarray] = {}
    total = np.zeros(4, dtype=np.int64)
    weighted = np.average(probabilities, axis=1, weights=np.asarray(weights))
    for index, uid in enumerate(uids):
        prediction = (weighted[index] >= threshold) & ~previous[index]
        if max_distance_px is not None:
            prediction &= distance[index] <= max_distance_px
        row = confusion(prediction, targets[index])
        total += row
        per_event.setdefault(uid, np.zeros(4, dtype=np.int64))
        per_event[uid] += row
    event_iou = [float(metrics_from_confusion(row)["iou"]) for row in per_event.values()]
    result = metrics_from_confusion(total)
    result.update(
        {
            "event_macro_iou": float(np.mean(event_iou)) if event_iou else 0.0,
            "n_events": len(event_iou),
            "threshold": threshold,
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
    cached = _load_probability_cache(list(args.source_checkpoints), loader, device)
    probabilities, uids, previous, distance, targets = cached
    ranking = []
    for weights in WEIGHT_GRID:
        for threshold in THRESHOLD_GRID:
            for max_distance_px in MAX_DISTANCE_GRID:
                metrics = _evaluate(
                    probabilities,
                    uids,
                    previous,
                    distance,
                    targets,
                    weights,
                    threshold,
                    max_distance_px,
                )
                ranking.append(
                    {
                        "weights": list(weights),
                        **metrics,
                    }
                )
    ranking.sort(key=lambda row: float(row["event_macro_iou"]), reverse=True)
    best = ranking[0]
    report = {
        "schema": "wfd_wfigs_weighted_ensemble_dev_v1",
        "selection_split": "wfigs_development_validation",
        "events": len(set(uids)),
        "samples": len(uids),
        "grid": {
            "weights": [list(row) for row in WEIGHT_GRID],
            "thresholds": list(THRESHOLD_GRID),
            "max_distance_px": list(MAX_DISTANCE_GRID),
            "dilation_radius_px": 0,
            "require_t0_connection": False,
        },
        "best": best,
        "ranking": ranking,
        "confirmation_loaded": False,
        "prospective_test_loaded": False,
        "test_used_for_selection": False,
        "raw_artifacts_published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(best, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
