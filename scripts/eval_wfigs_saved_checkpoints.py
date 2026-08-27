#!/usr/bin/env python3
"""Reconstruct VAL-only ensemble metrics from saved WFIGS checkpoints.

Does not train, does not load TEST/confirmation/prospective manifests, and
fails if those files are present under the dataset root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import (  # noqa: E402
    ProbabilityAveragingEnsemble,
    SEALED_CHANNEL_NAMES,
    build_model,
    make_loader,
    prepare_model_for_device,
    select_threshold_on_val,
)
from wildfire_front.ml.wfigs_external_eval import WFIGSExternalDataset  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402
from wildfire_front.open_if.regional.wfigs_rights import wfigs_rights_summary  # noqa: E402

BLOCKED_NAME_TOKENS = ("confirm", "test", "prospective")
SEEDS = (11, 29, 47)
OLD_DEV_CONTROL = 0.1361784859726811
PROMOTION_DELTA = 0.005
OLD_DEV_GATE = OLD_DEV_CONTROL + PROMOTION_DELTA


def _assert_dev_only(dataset_root: Path) -> None:
    lowered = dataset_root.as_posix().lower()
    if any(token in lowered for token in BLOCKED_NAME_TOKENS):
        raise ValueError(f"refusing dataset root that looks like a sealed split: {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)
    forbidden = [
        path
        for path in dataset_root.glob("*")
        if path.is_file() and any(token in path.name.lower() for token in BLOCKED_NAME_TOKENS)
    ]
    if forbidden:
        raise ValueError(f"refusing to evaluate while sealed-split files exist: {forbidden}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _input_channels(*, geometry: bool, tile: bool, valid_mask: bool) -> int:
    return (
        len(SEALED_CHANNEL_NAMES)
        + 3 * int(geometry)
        + 4 * int(tile)
        + int(valid_mask)
    )


def _load_model(
    checkpoint_path: Path,
    *,
    expected_channels: int,
    device: torch.device,
) -> tuple[torch.nn.Module, dict[str, Any]]:
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if payload.get("selection_split") != "wfigs_validation":
        raise ValueError(f"{checkpoint_path} was not selected on WFIGS validation")
    if payload.get("wfigs_test_evaluated") is not False:
        raise ValueError(f"{checkpoint_path} claims WFIGS TEST was evaluated")
    if payload.get("source_selection_split") != "val":
        raise ValueError(f"{checkpoint_path} source was not selected on RCDA VAL")
    weight = payload["state_dict"]["enc1.body.0.weight"]
    if int(weight.shape[1]) != expected_channels:
        raise ValueError(
            f"{checkpoint_path} has {int(weight.shape[1])} input channels, expected {expected_channels}"
        )
    model = prepare_model_for_device(
        build_model(
            str(payload["model_name"]),
            in_channels=expected_channels,
            base=int(payload.get("base_channels", 32)),
        ),
        device,
    )
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, payload


def _evaluate_family(
    *,
    name: str,
    checkpoint_root: Path,
    val_loader,
    device: torch.device,
    expected_channels: int,
    geometry: bool,
    tile: bool,
) -> dict[str, Any]:
    models: list[torch.nn.Module] = []
    reports: list[dict[str, Any]] = []
    for seed in SEEDS:
        checkpoint_path = checkpoint_root / f"wfigs_adapt_seed{seed}_best.pt"
        model, payload = _load_model(
            checkpoint_path,
            expected_channels=expected_channels,
            device=device,
        )
        threshold, val_search = select_threshold_on_val(
            model,
            val_loader,
            device,
            prediction_mode=str(payload["target_mode"]),
            selection_metric="event_macro_iou",
        )
        selected = val_search["selected"]
        print(
            f"{name} seed={seed} epoch={payload['epoch']} "
            f"event_macro_iou={selected['event_macro_iou']:.6f} "
            f"threshold={threshold} pooled={selected['iou']:.6f} "
            f"P={selected['precision']:.4f} R={selected['recall']:.4f}",
            flush=True,
        )
        reports.append(
            {
                "seed": seed,
                "checkpoint": str(checkpoint_path),
                "source_checkpoint": payload.get("source_checkpoint"),
                "best_epoch": payload.get("epoch"),
                "model_name": payload.get("model_name"),
                "target_mode": payload.get("target_mode"),
                "base_channels": payload.get("base_channels"),
                "selected_threshold": threshold,
                "threshold_selected_on": "wfigs_validation",
                "validation": val_search,
                "test_evaluated": False,
            }
        )
        models.append(model)
    ensemble_model = ProbabilityAveragingEnsemble(models)
    ensemble_threshold, ensemble_val = select_threshold_on_val(
        ensemble_model,
        val_loader,
        device,
        prediction_mode="hybrid",
        selection_metric="event_macro_iou",
    )
    selected = ensemble_val["selected"]
    print(
        f"{name} ensemble event_macro_iou={selected['event_macro_iou']:.6f} "
        f"threshold={ensemble_threshold} pooled={selected['iou']:.6f} "
        f"P={selected['precision']:.4f} R={selected['recall']:.4f}",
        flush=True,
    )
    return {
        "name": name,
        "include_geometry_features": geometry,
        "include_tile_standardized_features": tile,
        "input_channels": expected_channels,
        "reports": reports,
        "ensemble": {
            "aggregation": "mean_seed_probability",
            "members": len(models),
            "selected_threshold": ensemble_threshold,
            "threshold_selected_on": "wfigs_validation",
            "validation": ensemble_val,
            "test_used_for_selection": False,
            "test_evaluated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--adapted-root", type=Path, required=True)
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    _assert_dev_only(dataset_root)
    train_manifest = _load_json(dataset_root / "train.json")
    val_manifest = _load_json(dataset_root / "validation.json")
    train_events = set(train_manifest.get("events") or [])
    val_events = set(val_manifest.get("events") or [])
    if train_events & val_events:
        raise ValueError("WFIGS TRAIN and VALIDATION events overlap")
    normalization = _load_json(args.rcda_normalization)
    if normalization.get("fit_split") != "train":
        raise ValueError("RCDA normalization was not fitted on RCDA TRAIN")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        args.output_root / "EVAL_STATE.json",
        {
            "phase": "evaluating_saved_checkpoints_on_wfigs_validation",
            "updated_at": utc_now(),
            "device": str(device),
            "wfigs_test_loaded": False,
            "train_events": len(train_events),
            "validation_events": len(val_events),
        },
    )

    def loader(*, geometry: bool, tile: bool) -> Any:
        dataset = WFIGSExternalDataset(
            dataset_root=dataset_root,
            manifest=val_manifest,
            rcda_normalization=normalization,
            augment=False,
            include_geometry_features=geometry,
            include_tile_standardized_features=tile,
        )
        return make_loader(dataset, batch_size=4, shuffle=False, weighted=False, num_workers=0)

    adapted = _evaluate_family(
        name="large_fixed_source_geometry_eo",
        checkpoint_root=args.adapted_root,
        val_loader=loader(geometry=True, tile=True),
        device=device,
        expected_channels=_input_channels(geometry=True, tile=True, valid_mask=False),
        geometry=True,
        tile=True,
    )
    control = _evaluate_family(
        name="frozen_hybrid_control_16ch",
        checkpoint_root=args.control_root,
        val_loader=loader(geometry=False, tile=False),
        device=device,
        expected_channels=_input_channels(geometry=False, tile=False, valid_mask=False),
        geometry=False,
        tile=False,
    )

    adapted_iou = float(adapted["ensemble"]["validation"]["selected"]["event_macro_iou"])
    control_iou = float(control["ensemble"]["validation"]["selected"]["event_macro_iou"])
    new_dev_gate = control_iou + PROMOTION_DELTA
    decision = {
        "schema": "wfd_wfigs_large_dev_gate_v1",
        "generated_at": utc_now(),
        "device": str(device),
        "cohort": {
            "train_events": len(train_events),
            "validation_events": len(val_events),
            "wfigs_test_loaded": False,
            "test_used_for_selection": False,
        },
        "adapted_event_macro_iou": adapted_iou,
        "frozen_control_on_new_dev_event_macro_iou": control_iou,
        "delta_vs_new_dev_control": adapted_iou - control_iou,
        "new_dev_gate": new_dev_gate,
        "promotes_vs_new_dev_control": adapted_iou >= new_dev_gate,
        "old_dev_control_event_macro_iou": OLD_DEV_CONTROL,
        "old_dev_gate": OLD_DEV_GATE,
        "delta_vs_old_dev_control": adapted_iou - OLD_DEV_CONTROL,
        "promotes_vs_old_dev_gate": adapted_iou >= OLD_DEV_GATE,
        "primary_gate": "preregistered_old_dev_plus_0.005",
        "transferred_control_note": (
            "The 16-channel control is transferred from the 184/42 cohort and "
            "re-thresholded on the new DEV; it is not a retrained control."
        ),
        "promotion_decision": "reject_confirmation",
        "confirmation_opened": False,
        "adapted_members": [
            {
                "seed": row["seed"],
                "event_macro_iou": row["validation"]["selected"]["event_macro_iou"],
                "pooled_iou": row["validation"]["selected"]["iou"],
                "precision": row["validation"]["selected"]["precision"],
                "recall": row["validation"]["selected"]["recall"],
                "threshold": row["selected_threshold"],
                "best_epoch": row["best_epoch"],
            }
            for row in adapted["reports"]
        ],
        "control_members": [
            {
                "seed": row["seed"],
                "event_macro_iou": row["validation"]["selected"]["event_macro_iou"],
                "pooled_iou": row["validation"]["selected"]["iou"],
                "precision": row["validation"]["selected"]["precision"],
                "recall": row["validation"]["selected"]["recall"],
                "threshold": row["selected_threshold"],
                "best_epoch": row["best_epoch"],
            }
            for row in control["reports"]
        ],
        "rights": wfigs_rights_summary(),
    }

    report = {
        "schema": "wfd_rcda_wfigs_domain_adaptation_v1",
        "generated_at": utc_now(),
        "device": str(device),
        "reconstruction": {
            "trained_checkpoints_reused": True,
            "training_history_unavailable": True,
            "reason": (
                "The original large-DEV run saved three best checkpoints and exited "
                "before writing WFIGS_ADAPTATION_VAL_ONLY.json. This report reloads "
                "those checkpoints and re-selects thresholds on WFIGS validation only."
            ),
        },
        "configuration": {
            "epochs": 18,
            "batch_size": 4,
            "lr": 1e-4,
            "patience": 5,
            "trainable_scope": "decoder_plus_input",
            "front_ring_bce_weight": 0.05,
            "target_mode": "hybrid",
            "augment": True,
            "include_valid_mask": False,
            "include_geometry_features": True,
            "include_tile_standardized_features": True,
            "source_seeds": list(SEEDS),
            "source_architecture_and_seeds_frozen_on": "rcda_validation",
            "epoch_and_threshold_selected_on": "wfigs_validation",
        },
        "counts": {
            "train_events": len(train_events),
            "validation_events": len(val_events),
            "reports": len(adapted["reports"]),
        },
        "reports": adapted["reports"],
        "ensemble": adapted["ensemble"],
        "frozen_control_on_same_dev": {
            "checkpoint_root": str(args.control_root),
            "input_channels": control["input_channels"],
            "reports": control["reports"],
            "ensemble": control["ensemble"],
        },
        "test_used_for_selection": False,
        "wfigs_test_loaded": False,
        "rights": wfigs_rights_summary(),
        "claims": {
            "domain_adaptation_trained": True,
            "wfigs_test_performance_known": False,
            "public_checkpoint_release_allowed": False,
        },
    }
    _atomic_write_json(args.output_root / "WFIGS_ADAPTATION_VAL_ONLY.json", report)
    _atomic_write_json(args.output_root / "GATE_DECISION.json", decision)
    _atomic_write_json(
        args.output_root / "EVAL_STATE.json",
        {
            "phase": "complete",
            "updated_at": utc_now(),
            "wfigs_test_loaded": False,
            "promotes_vs_new_dev_control": decision["promotes_vs_new_dev_control"],
            "adapted_event_macro_iou": adapted_iou,
            "frozen_control_on_new_dev_event_macro_iou": control_iou,
        },
    )
    print(json.dumps(decision, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
