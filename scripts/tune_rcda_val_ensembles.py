#!/usr/bin/env python3
"""Explore fixed probability ensembles on sealed RCDA VALIDATION only.

The script deliberately has no TEST-manifest argument.  It streams predictions
and confusion matrices instead of retaining the complete prediction tensor, so
the audit remains inexpensive and reproducible on a CPU workstation.
"""

from __future__ import annotations

import argparse
import hashlib
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
    SEALED_CHANNEL_NAMES,
    THRESHOLDS,
    SealedRCDADataset,
    _threshold_confusions,
    build_model,
    load_protocol,
    make_loader,
    metrics_from_confusion,
    prepare_inputs_for_device,
    prepare_model_for_device,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_named_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        alias, separator, raw_path = value.partition("=")
        alias = alias.strip()
        raw_path = raw_path.strip()
        if not separator or not alias or not raw_path:
            raise ValueError("--checkpoint requires ALIAS=PATH")
        if alias in parsed:
            raise ValueError(f"duplicate checkpoint alias: {alias}")
        parsed[alias] = Path(raw_path)
    return parsed


def parse_combinations(values: list[str]) -> dict[str, tuple[str, ...]]:
    parsed: dict[str, tuple[str, ...]] = {}
    for value in values:
        name, separator, raw_members = value.partition("=")
        name = name.strip()
        members = tuple(member.strip() for member in raw_members.split(",") if member.strip())
        if not separator or not name or not members:
            raise ValueError("--combination requires NAME=ALIAS[,ALIAS...]")
        if name in parsed:
            raise ValueError(f"duplicate combination name: {name}")
        parsed[name] = members
    return parsed


def load_val_checkpoint(path: Path, device: torch.device) -> tuple[torch.nn.Module, dict[str, Any]]:
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    if checkpoint.get("selection_split") != "val":
        raise ValueError(f"{path} was not selected on VAL")
    if checkpoint.get("test_evaluated") not in (None, False):
        raise ValueError(f"{path} contains a TEST-evaluated candidate")
    model = build_model(
        str(checkpoint["model_name"]),
        in_channels=len(SEALED_CHANNEL_NAMES),
        base=int(checkpoint.get("base_channels", 32)),
    )
    model = prepare_model_for_device(model, device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


def summarize_confusions(
    pooled: np.ndarray,
    by_event: dict[str, np.ndarray],
    thresholds: tuple[float, ...],
    *,
    samples: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for threshold_index, threshold in enumerate(thresholds):
        event_ious = [
            float(metrics_from_confusion(values[threshold_index])["iou"])
            for values in by_event.values()
        ]
        pooled_metrics = metrics_from_confusion(pooled[threshold_index])
        rows.append(
            {
                "threshold": float(threshold),
                "event_macro_iou": float(np.mean(event_ious)) if event_ious else 0.0,
                "event_median_iou": float(np.median(event_ious)) if event_ious else 0.0,
                "pooled_iou": float(pooled_metrics["iou"]),
                "events": len(event_ious),
                "samples": samples,
            }
        )
    return sorted(rows, key=lambda row: float(row["event_macro_iou"]), reverse=True)


def selected_event_ious(
    by_event: dict[str, np.ndarray],
    thresholds: tuple[float, ...],
    selected_threshold: float,
) -> dict[str, float]:
    threshold_index = min(
        range(len(thresholds)),
        key=lambda index: abs(float(thresholds[index]) - float(selected_threshold)),
    )
    if not np.isclose(float(thresholds[threshold_index]), float(selected_threshold)):
        raise ValueError(f"selected threshold {selected_threshold} is not in the fixed grid")
    return {
        event_id: float(metrics_from_confusion(values[threshold_index])["iou"])
        for event_id, values in sorted(by_event.items())
    }


def paired_event_bootstrap(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    n_resamples: int = 10_000,
    seed: int = 20260819,
) -> dict[str, Any]:
    if set(baseline) != set(candidate):
        raise ValueError("paired ensemble comparison requires identical event ids")
    event_ids = sorted(baseline)
    deltas = np.asarray(
        [float(candidate[event_id]) - float(baseline[event_id]) for event_id in event_ids],
        dtype=np.float64,
    )
    if deltas.size == 0:
        raise ValueError("paired ensemble comparison requires at least one event")
    rng = np.random.default_rng(seed)
    sampled = rng.choice(deltas, size=(int(n_resamples), deltas.size), replace=True)
    bootstrap_means = sampled.mean(axis=1)
    return {
        "events": int(deltas.size),
        "mean_delta_iou": float(deltas.mean()),
        "median_delta_iou": float(np.median(deltas)),
        "event_bootstrap_95_ci": [
            float(np.quantile(bootstrap_means, 0.025)),
            float(np.quantile(bootstrap_means, 0.975)),
        ],
        "wins_event_fraction": float(np.mean(deltas > 0.0)),
        "ties_event_fraction": float(np.mean(np.isclose(deltas, 0.0))),
        "bootstrap_resamples": int(n_resamples),
        "bootstrap_seed": int(seed),
        "interpretation": "Descriptive paired uncertainty after selection on VAL; not confirmatory TEST evidence.",
    }


@torch.no_grad()
def tune_validation_ensembles(
    checkpoint_paths: dict[str, Path],
    combinations: dict[str, tuple[str, ...]],
    *,
    dataset_root: Path,
    protocol_dir: Path,
    batch_size: int = 8,
    thresholds: tuple[float, ...] = THRESHOLDS,
) -> dict[str, Any]:
    if not checkpoint_paths:
        raise ValueError("at least one checkpoint is required")
    if not combinations:
        raise ValueError("at least one combination is required")
    unknown = {
        member
        for members in combinations.values()
        for member in members
        if member not in checkpoint_paths
    }
    if unknown:
        raise ValueError(f"unknown checkpoint aliases: {sorted(unknown)}")

    protocol = load_protocol(protocol_dir)
    val_manifest = protocol["manifests"]["val"]
    if val_manifest.get("split") != "val":
        raise ValueError("ensemble tuning requires the sealed VAL manifest")
    dataset = SealedRCDADataset(
        dataset_root,
        val_manifest,
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
    loaded = {
        alias: load_val_checkpoint(path, device)
        for alias, path in checkpoint_paths.items()
    }
    pooled = {
        name: np.zeros((len(thresholds), 4), dtype=np.int64)
        for name in combinations
    }
    by_event: dict[str, dict[str, np.ndarray]] = {
        name: defaultdict(lambda: np.zeros((len(thresholds), 4), dtype=np.int64))
        for name in combinations
    }
    samples = 0
    threshold_array = np.asarray(thresholds, dtype=np.float32)
    for batch in loader:
        inputs = batch["input"]
        prepared = prepare_inputs_for_device(inputs, device)
        previous = inputs[:, 0:1].numpy() > 0.5
        targets = batch["target"].numpy()[:, 0].astype(bool)
        probabilities: dict[str, np.ndarray] = {}
        for alias, (model, _checkpoint) in loaded.items():
            probability = torch.sigmoid(model(prepared)).cpu().numpy()
            # Growth cannot occupy an already-burning t0 pixel.  Apply this
            # physical constraint uniformly, including growth-trained models.
            probability[previous] = 0.0
            probabilities[alias] = probability
        for name, members in combinations.items():
            ensemble_probability = np.mean(
                np.stack([probabilities[member] for member in members], axis=0),
                axis=0,
            )
            predictions = (
                ensemble_probability[:, None]
                >= threshold_array[None, :, None, None, None]
            )
            for index, event_id in enumerate(batch["uid"]):
                rows = _threshold_confusions(predictions[index, :, 0], targets[index])
                pooled[name] += rows
                by_event[name][str(event_id)] += rows
        samples += len(batch["uid"])

    ranking: list[dict[str, Any]] = []
    complete_grids: dict[str, list[dict[str, Any]]] = {}
    for name, members in combinations.items():
        grid = summarize_confusions(
            pooled[name], by_event[name], thresholds, samples=samples
        )
        complete_grids[name] = grid
        ranking.append({"name": name, "members": list(members), **grid[0]})
    ranking.sort(key=lambda row: float(row["event_macro_iou"]), reverse=True)
    selected_by_event = {
        row["name"]: selected_event_ious(
            by_event[row["name"]], thresholds, float(row["threshold"])
        )
        for row in ranking
    }
    best_individual = max(
        (row for row in ranking if len(row["members"]) == 1),
        key=lambda row: float(row["event_macro_iou"]),
    )
    best_multi_model = max(
        (row for row in ranking if len(row["members"]) > 1),
        key=lambda row: float(row["event_macro_iou"]),
        default=None,
    )
    multi_delta = (
        float(best_multi_model["event_macro_iou"])
        - float(best_individual["event_macro_iou"])
        if best_multi_model
        else None
    )
    paired_validation = (
        paired_event_bootstrap(
            selected_by_event[best_individual["name"]],
            selected_by_event[best_multi_model["name"]],
        )
        if best_multi_model
        else None
    )

    return {
        "schema": "wfd_rcda_val_probability_ensemble_tune_v2",
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "physical_growth_constraint": "probability forced to zero inside t0 extent",
        "averaging": "equal-weight arithmetic mean of probabilities",
        "thresholds": [float(value) for value in thresholds],
        "checkpoints": {
            alias: {
                "path": portable_path(path),
                "sha256": sha256_file(path),
                "model_name": checkpoint["model_name"],
                "target_mode": checkpoint.get("target_mode", "growth"),
                "epoch": int(checkpoint["epoch"]),
            }
            for alias, path in checkpoint_paths.items()
            for _model, checkpoint in [loaded[alias]]
        },
        "decision": {
            "best_individual": best_individual["name"],
            "best_multi_model": best_multi_model["name"] if best_multi_model else None,
            "best_multi_minus_individual": multi_delta,
            "paired_validation": paired_validation,
            "preregister_multi_model_ensemble": bool(
                multi_delta is not None and multi_delta > 0.0
            ),
            "reason": (
                "best multi-model ensemble did not improve sealed VAL event-macro IoU"
                if multi_delta is not None and multi_delta <= 0.0
                else "multi-model ensemble improved sealed VAL event-macro IoU"
            ),
        },
        "ranking": ranking,
        "selected_per_event_iou": selected_by_event,
        "grids": complete_grids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_paper_nightwatch_20260819/tuning_output/rcda_paper_tune",
    )
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
    parser.add_argument(
        "--checkpoint",
        action="append",
        default=[],
        metavar="ALIAS=PATH",
        help="Explicit VAL-only checkpoint; repeatable. Overrides --checkpoint-dir defaults.",
    )
    parser.add_argument(
        "--combination",
        action="append",
        default=[],
        metavar="NAME=ALIAS[,ALIAS...]",
        help="Explicit ensemble member set; repeatable. Requires --checkpoint.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_paper_nightwatch_20260819/PHASE1_VAL_ENSEMBLES.json",
    )
    args = parser.parse_args()
    if args.checkpoint:
        checkpoints = parse_named_paths(args.checkpoint)
        if not args.combination:
            raise ValueError("explicit --checkpoint entries require --combination")
        combinations = parse_combinations(args.combination)
    else:
        if args.combination:
            raise ValueError("--combination requires explicit --checkpoint entries")
        checkpoints = {
            "resunet_hybrid_v1": args.checkpoint_dir / "resunet_hybrid_v1_seed0_best.pt",
            "unet_growth_v2": args.checkpoint_dir / "unet_growth_v2_seed0_best.pt",
            "aspp_growth_v1": args.checkpoint_dir / "aspp_growth_v1_seed0_best.pt",
        }
        combinations = {
            "res_only": ("resunet_hybrid_v1",),
            "res_unet": ("resunet_hybrid_v1", "unet_growth_v2"),
            "res_aspp": ("resunet_hybrid_v1", "aspp_growth_v1"),
            "triple": ("resunet_hybrid_v1", "unet_growth_v2", "aspp_growth_v1"),
            "unet_aspp": ("unet_growth_v2", "aspp_growth_v1"),
        }
    report = tune_validation_ensembles(
        checkpoints,
        combinations,
        dataset_root=args.dataset_root,
        protocol_dir=args.protocol_dir,
        batch_size=args.batch_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "ranking": report["ranking"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
