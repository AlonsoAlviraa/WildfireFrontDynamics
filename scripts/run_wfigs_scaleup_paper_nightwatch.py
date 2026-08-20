#!/usr/bin/env python3
"""Tune WFIGS adaptation on expanded VAL, then evaluate a prospective TEST once."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_external_eval import (  # noqa: E402
    evaluate_adapted_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402

SWEEP_RECIPES: tuple[tuple[str, WFIGSAdaptConfig], ...] = (
    (
        "all_low_lr",
        WFIGSAdaptConfig(
            epochs=12,
            patience=4,
            lr=3e-5,
            trainable_scope="all",
            source_seeds=(47,),
        ),
    ),
    (
        "decoder_only",
        WFIGSAdaptConfig(
            epochs=12,
            patience=4,
            lr=1e-4,
            trainable_scope="decoder",
            source_seeds=(47,),
        ),
    ),
    (
        "decoder_front_ring",
        WFIGSAdaptConfig(
            epochs=12,
            patience=4,
            lr=1e-4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            source_seeds=(47,),
        ),
    ),
)


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _validation_score(report: dict[str, Any]) -> float:
    reports = report.get("reports") or []
    if (
        report.get("test_used_for_selection") is not False
        or report.get("wfigs_test_loaded") is not False
        or len(reports) != 1
        or reports[0].get("test_evaluated") is not False
        or reports[0].get("threshold_selected_on") != "wfigs_validation"
    ):
        raise ValueError("invalid validation-only WFIGS adaptation report")
    return float(reports[0]["validation"]["selected"]["event_macro_iou"])


def _validate_preregistered_inventory(
    preregistration: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    rows = inventory.get("rows") or []
    event_ids = sorted({str(row["event_id"]) for row in rows if row.get("event_id")})
    pair_ids = sorted(str(row["pair_id"]) for row in rows if row.get("pair_id"))
    event_hash = _set_digest(event_ids)
    pair_hash = _set_digest(pair_ids)
    if event_hash != preregistration.get("event_ids_sha256") or pair_hash != preregistration.get(
        "pair_ids_sha256"
    ):
        raise ValueError("materialized prospective cohort differs from preregistration")
    return {
        "event_ids_sha256": event_hash,
        "pair_ids_sha256": pair_hash,
        "events_selected": len(event_ids),
        "pairs_selected": len(pair_ids),
        "events_materialized": sum(row.get("training_ready") is True for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-final",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_paper_nightwatch_20260819/FINAL_SUMMARY_PAPER_METRICS.json",
    )
    parser.add_argument(
        "--scaleup-dataset",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_tensor_dataset_scaleup_20260820",
    )
    parser.add_argument(
        "--train-inventory",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_training_campaign_20260819/INVENTORY.json",
    )
    parser.add_argument(
        "--validation-inventory",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_validation_campaign_20260819/INVENTORY.json",
    )
    parser.add_argument(
        "--prospective-inventory",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_prospective_test_campaign_20260820/INVENTORY.json",
    )
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_prospective_holdout_20260820/PREREGISTRATION.json",
    )
    parser.add_argument(
        "--prospective-dataset",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_tensor_dataset_prospective_20260820",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_scaleup_paper_20260820",
    )
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=30.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600.0
    scaleup_state_path = args.scaleup_dataset / "NIGHTWATCH_STATE.json"
    while _read(scaleup_state_path).get("phase") != "complete":
        _atomic_write_json(
            state_path,
            {
                "phase": "waiting_for_expanded_train_validation",
                "updated_at": utc_now(),
                "test_evaluated": False,
            },
        )
        if time.monotonic() >= deadline:
            raise TimeoutError("expanded WFIGS TRAIN/VALIDATION did not finish")
        time.sleep(max(10, args.poll_seconds))
    if (args.scaleup_dataset / "test.json").exists():
        raise ValueError("scale-up tuning dataset unexpectedly contains TEST")

    rows: list[dict[str, Any]] = []
    for index, (name, config) in enumerate(SWEEP_RECIPES, start=1):
        recipe_root = args.output / "recipes" / name
        summary_path = recipe_root / "WFIGS_ADAPTATION_VAL_ONLY.json"
        report = _read(summary_path)
        if not report:
            _atomic_write_json(
                state_path,
                {
                    "phase": "validation_only_adaptation_sweep",
                    "updated_at": utc_now(),
                    "active_recipe": name,
                    "recipe_index": index,
                    "recipes_total": len(SWEEP_RECIPES),
                    "completed": rows,
                    "test_evaluated": False,
                },
            )
            report = adapt_frozen_rcda_on_wfigs(
                final_summary_path=args.source_final,
                wfigs_dataset_root=args.scaleup_dataset,
                rcda_normalization_path=(
                    ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
                ),
                output_root=recipe_root,
                adaptation=config,
            )
        rows.append(
            {
                "name": name,
                "val_event_macro_iou": _validation_score(report),
                "configuration": asdict(config),
                "summary": str(summary_path),
                "summary_sha256": _sha256(summary_path),
            }
        )
        rows.sort(key=lambda row: float(row["val_event_macro_iou"]), reverse=True)
        _atomic_write_json(
            args.output / "WFIGS_SCALEUP_ADAPTATION_SWEEP_VAL_ONLY.json",
            {
                "schema": "wfd_wfigs_scaleup_adaptation_sweep_v1",
                "generated_at": utc_now(),
                "selection_split": "wfigs_validation",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": rows,
            },
        )

    winner = rows[0]
    winner_config = next(config for name, config in SWEEP_RECIPES if name == winner["name"])
    frozen_path = args.output / "FROZEN_SCALEUP_ADAPTATION.json"
    frozen = {
        "schema": "wfd_wfigs_scaleup_adaptation_frozen_v1",
        "frozen_at": utc_now(),
        "winner": winner,
        "final_seeds": [11, 29, 47],
        "selection_split": "wfigs_validation",
        "prospective_test_evaluated": False,
        "preregistration_sha256": _sha256(args.preregistration),
    }
    _atomic_write_json(frozen_path, frozen)

    final_root = args.output / "final_adaptation"
    final_summary_path = final_root / "WFIGS_ADAPTATION_VAL_ONLY.json"
    final_adaptation = _read(final_summary_path)
    if not final_adaptation:
        _atomic_write_json(
            state_path,
            {
                "phase": "training_frozen_adaptation_three_seeds",
                "updated_at": utc_now(),
                "winner": winner["name"],
                "test_evaluated": False,
            },
        )
        final_adaptation = adapt_frozen_rcda_on_wfigs(
            final_summary_path=args.source_final,
            wfigs_dataset_root=args.scaleup_dataset,
            rcda_normalization_path=(
                ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
            ),
            output_root=final_root,
            adaptation=replace(winner_config, source_seeds=None),
        )
    if len(final_adaptation.get("reports") or []) != 3:
        raise ValueError("frozen WFIGS adaptation did not produce three seeds")

    while not args.prospective_inventory.is_file():
        _atomic_write_json(
            state_path,
            {
                "phase": "frozen_waiting_for_prospective_test",
                "updated_at": utc_now(),
                "winner": winner["name"],
                "test_evaluated": False,
            },
        )
        if time.monotonic() >= deadline:
            raise TimeoutError("prospective WFIGS TEST did not finish")
        time.sleep(max(10, args.poll_seconds))
    preregistration = _read(args.preregistration)
    prospective_inventory = _read(args.prospective_inventory)
    cohort = _validate_preregistered_inventory(
        preregistration,
        prospective_inventory,
    )
    _atomic_write_json(
        state_path,
        {
            "phase": "building_preregistered_prospective_dataset",
            "updated_at": utc_now(),
            "cohort": cohort,
            "test_evaluated": False,
        },
    )
    WFIGSTensorDatasetBuilder(
        inventory_paths=[
            args.train_inventory,
            args.validation_inventory,
            args.prospective_inventory,
        ],
        output_root=args.prospective_dataset,
    ).build()
    result_path = args.output / "WFIGS_PROSPECTIVE_TEST_EVAL.json"
    result = evaluate_adapted_rcda_on_wfigs(
        adaptation_summary_path=final_summary_path,
        wfigs_dataset_root=args.prospective_dataset,
        rcda_normalization_path=(
            ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
        ),
        geometry_baseline_path=(
            ROOT / "data/open_if/wfigs_history_2020_2026/ml/GEOMETRY_BASELINE.json"
        ),
        output_path=result_path,
    )
    final = {
        "phase": "complete",
        "status": "complete",
        "updated_at": utc_now(),
        "winner": winner,
        "frozen_recipe": str(frozen_path),
        "cohort": cohort,
        "prospective_test_loaded_after_recipe_freeze": True,
        "result": str(result_path),
        "summary": result["summary"],
    }
    _atomic_write_json(state_path, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
