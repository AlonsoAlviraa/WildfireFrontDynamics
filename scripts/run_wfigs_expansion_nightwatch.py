#!/usr/bin/env python3
"""Build a larger WFIGS corpus, tune on DEV, then open fresh confirmation once."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_dataset_audit import audit_wfigs_tensor_dataset  # noqa: E402
from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_expansion import (  # noqa: E402
    evaluate_frozen_adaptation_on_validation,
    fit_converted_train_normalization,
    paired_event_comparison,
    sha256_file,
    split_validation_inventory,
    validate_inventory_isolation,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402

PILOT_RECIPES: tuple[tuple[str, WFIGSAdaptConfig, str], ...] = (
    (
        "decoder_front_ring_control",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
    (
        "decoder_light_front_ring",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.05,
            front_ring_radius_px=16.0,
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
    (
        "decoder_no_front_ring",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="decoder",
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
    (
        "all_low_lr",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=3e-5,
            trainable_scope="all",
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
    (
        "all_low_lr_wfigs_normalized",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=3e-5,
            trainable_scope="all",
            source_seeds=(47,),
        ),
        "wfigs_converted_train",
    ),
    (
        "all_medium_lr_wfigs_normalized",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="all",
            source_seeds=(47,),
        ),
        "wfigs_converted_train",
    ),
    (
        "decoder_balanced_tversky",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            tversky_alpha=0.5,
            tversky_beta=0.5,
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
    (
        "decoder_precision_tversky",
        WFIGSAdaptConfig(
            epochs=18,
            patience=5,
            lr=1e-4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            tversky_alpha=0.7,
            tversky_beta=0.3,
            source_seeds=(47,),
        ),
        "rcda_train",
    ),
)


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _wait_for(paths: list[Path], *, deadline: float, poll_seconds: int) -> None:
    while not all(path.is_file() for path in paths):
        if time.monotonic() >= deadline:
            raise TimeoutError("WFIGS expansion inventories did not finish")
        time.sleep(max(10, poll_seconds))


def _audit_or_raise(dataset_root: Path) -> dict[str, Any]:
    if (dataset_root / "test.json").exists():
        raise ValueError("expansion dataset unexpectedly contains TEST")
    report = audit_wfigs_tensor_dataset(dataset_root)
    checks = report.get("checks") or {}
    if report.get("status") != "pass" or int((report.get("counts") or {}).get("issues") or 0):
        raise ValueError("WFIGS expansion dataset failed audit")
    if not all(
        checks.get(name) is True
        for name in (
            "event_disjoint",
            "unique_pair_ids",
            "normalization_recomputed_from_train_only",
        )
    ):
        raise ValueError("WFIGS expansion dataset failed isolation checks")
    if checks.get("test_used_for_selection") is not False:
        raise ValueError("WFIGS expansion audit does not prove TEST isolation")
    return report


def _pilot_score(report: dict[str, Any]) -> float:
    rows = report.get("reports") or []
    if len(rows) != 1 or report.get("wfigs_test_loaded") is not False:
        raise ValueError("pilot is not a single-seed validation-only report")
    return float(rows[0]["validation"]["selected"]["event_macro_iou"])


def _claim_confirmation(claim_path: Path, evidence: dict[str, str]) -> dict[str, Any]:
    existing = _read(claim_path)
    if existing:
        if existing.get("evidence") != evidence:
            raise ValueError("confirmation claim belongs to different frozen evidence")
        return existing
    claim = {
        "schema": "wfd_wfigs_expansion_confirmation_claim_v1",
        "claimed_at": utc_now(),
        "phase": "claimed",
        "evidence": evidence,
    }
    _atomic_write_json(claim_path, claim)
    return claim


def _resume_confirmation(
    *,
    claim_path: Path,
    result_path: Path,
    evidence: dict[str, str],
) -> dict[str, Any] | None:
    result = _read(result_path)
    if not result:
        return None
    claim = _read(claim_path)
    if not claim:
        raise ValueError("confirmation result exists without its one-time claim")
    if claim.get("evidence") != evidence or result.get("evidence") != evidence:
        raise ValueError("confirmation result belongs to different frozen evidence")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-train-inventory", type=Path, required=True)
    parser.add_argument("--base-validation-inventory", type=Path, required=True)
    parser.add_argument("--expansion-train-root", type=Path, required=True)
    parser.add_argument("--expansion-validation-root", type=Path, required=True)
    parser.add_argument("--forbidden-prospective-inventory", type=Path, required=True)
    parser.add_argument("--source-final", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--tuning-dataset", type=Path, required=True)
    parser.add_argument("--confirmation-dataset", type=Path, required=True)
    parser.add_argument("--baseline-adaptation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=24.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600
    expansion_train = args.expansion_train_root / "INVENTORY.json"
    expansion_validation = args.expansion_validation_root / "INVENTORY.json"
    _atomic_write_json(
        state_path,
        {"phase": "waiting_for_expansion", "updated_at": utc_now(), "test_loaded": False},
    )
    _wait_for(
        [expansion_train, expansion_validation],
        deadline=deadline,
        poll_seconds=args.poll_seconds,
    )

    development_inventory = args.expansion_validation_root / "DEVELOPMENT_INVENTORY.json"
    confirmation_inventory = args.expansion_validation_root / "CONFIRMATION_INVENTORY.json"
    split = split_validation_inventory(
        expansion_validation,
        development_path=development_inventory,
        confirmation_path=confirmation_inventory,
    )
    isolation = validate_inventory_isolation(
        train_inventory_paths=[args.base_train_inventory, expansion_train],
        development_inventory_paths=[args.base_validation_inventory, development_inventory],
        confirmation_inventory_path=confirmation_inventory,
        forbidden_inventory_path=args.forbidden_prospective_inventory,
    )
    _atomic_write_json(
        state_path,
        {
            "phase": "building_development_and_confirmation",
            "updated_at": utc_now(),
            "split": split,
            "isolation": isolation,
            "test_loaded": False,
        },
    )
    WFIGSTensorDatasetBuilder(
        inventory_paths=[
            args.base_train_inventory,
            expansion_train,
            args.base_validation_inventory,
            development_inventory,
        ],
        output_root=args.tuning_dataset,
    ).build()
    _audit_or_raise(args.tuning_dataset)
    WFIGSTensorDatasetBuilder(
        inventory_paths=[
            args.base_train_inventory,
            expansion_train,
            confirmation_inventory,
        ],
        output_root=args.confirmation_dataset,
    ).build()
    _audit_or_raise(args.confirmation_dataset)
    converted_normalization_path = (
        args.tuning_dataset / "normalization_wfigs_converted_train_only.json"
    )
    converted_normalization = fit_converted_train_normalization(
        dataset_root=args.tuning_dataset,
        reference_normalization_path=args.rcda_normalization,
        output_path=converted_normalization_path,
    )
    normalization_paths = {
        "rcda_train": args.rcda_normalization,
        "wfigs_converted_train": converted_normalization_path,
    }

    preregistration = {
        "schema": "wfd_wfigs_expansion_adaptation_preregistration_v1",
        "registered_at": utc_now(),
        "source_final_sha256": sha256_file(args.source_final),
        "tuning_audit_sha256": sha256_file(args.tuning_dataset / "DATASET_AUDIT.json"),
        "confirmation_audit_sha256": sha256_file(args.confirmation_dataset / "DATASET_AUDIT.json"),
        "split": split,
        "isolation": isolation,
        "pilot_seed": 47,
        "pilot_recipes": [
            {
                "name": name,
                "configuration": asdict(config),
                "normalization": normalization_mode,
                "normalization_sha256": sha256_file(normalization_paths[normalization_mode]),
            }
            for name, config, normalization_mode in PILOT_RECIPES
        ],
        "converted_train_normalization": {
            "path": str(converted_normalization_path),
            "sha256": sha256_file(converted_normalization_path),
            "samples_used": converted_normalization["samples_used"],
            "test_loaded": False,
        },
        "selection_rule": "max_wfigs_development_event_macro_iou_then_recipe_order",
        "final_seeds": [11, 29, 47],
        "confirmation_rule": "evaluate_frozen_thresholds_once_after_recipe_freeze",
        "prospective_test_never_loaded": True,
    }
    preregistration_path = args.output / "PREREGISTRATION.json"
    if preregistration_path.exists():
        existing = _read(preregistration_path)
        for key in (
            "source_final_sha256",
            "tuning_audit_sha256",
            "confirmation_audit_sha256",
            "pilot_recipes",
        ):
            if existing.get(key) != preregistration.get(key):
                raise ValueError("expansion preregistration changed after creation")
        preregistration = existing
    else:
        _atomic_write_json(preregistration_path, preregistration)

    ranking: list[dict[str, Any]] = []
    for index, (name, config, normalization_mode) in enumerate(PILOT_RECIPES, start=1):
        recipe_root = args.output / "pilots" / name
        summary_path = recipe_root / "WFIGS_ADAPTATION_VAL_ONLY.json"
        report = _read(summary_path)
        if not report:
            _atomic_write_json(
                state_path,
                {
                    "phase": "development_pilot_sweep",
                    "updated_at": utc_now(),
                    "active_recipe": name,
                    "recipe_index": index,
                    "recipes_total": len(PILOT_RECIPES),
                    "test_loaded": False,
                },
            )

            def pilot_progress(
                row: dict[str, Any],
                *,
                active_name: str = name,
                active_index: int = index,
                active_normalization: str = normalization_mode,
            ) -> None:
                _atomic_write_json(
                    state_path,
                    {
                        "phase": "development_pilot_sweep",
                        "updated_at": utc_now(),
                        "active_recipe": active_name,
                        "normalization": active_normalization,
                        "recipe_index": active_index,
                        "recipes_total": len(PILOT_RECIPES),
                        "training_progress": row,
                        "test_loaded": False,
                    },
                )

            report = adapt_frozen_rcda_on_wfigs(
                final_summary_path=args.source_final,
                wfigs_dataset_root=args.tuning_dataset,
                rcda_normalization_path=normalization_paths[normalization_mode],
                output_root=recipe_root,
                adaptation=config,
                progress_callback=pilot_progress,
            )
        ranking.append(
            {
                "name": name,
                "development_event_macro_iou": _pilot_score(report),
                "summary": str(summary_path),
                "summary_sha256": sha256_file(summary_path),
                "configuration": asdict(config),
                "normalization": normalization_mode,
                "normalization_sha256": sha256_file(normalization_paths[normalization_mode]),
            }
        )
    order = {name: index for index, (name, _config, _normalization) in enumerate(PILOT_RECIPES)}
    ranking.sort(key=lambda row: (-float(row["development_event_macro_iou"]), order[row["name"]]))
    winner = ranking[0]
    winner_config, winner_normalization_mode = next(
        (config, normalization_mode)
        for name, config, normalization_mode in PILOT_RECIPES
        if name == winner["name"]
    )
    winner_normalization_path = normalization_paths[winner_normalization_mode]
    freeze = {
        "schema": "wfd_wfigs_expansion_recipe_freeze_v1",
        "frozen_at": utc_now(),
        "preregistration_sha256": sha256_file(preregistration_path),
        "ranking": ranking,
        "winner": winner,
        "selection_split": "wfigs_development_validation",
        "confirmation_loaded": False,
        "prospective_test_loaded": False,
    }
    freeze_path = args.output / "FROZEN_RECIPE.json"
    existing_freeze = _read(freeze_path)
    if existing_freeze:
        for key in ("preregistration_sha256", "ranking", "winner"):
            if existing_freeze.get(key) != freeze.get(key):
                raise ValueError("frozen expansion recipe changed after selection")
        freeze = existing_freeze
    else:
        _atomic_write_json(freeze_path, freeze)

    final_root = args.output / "final_three_seed"
    final_summary_path = final_root / "WFIGS_ADAPTATION_VAL_ONLY.json"
    final_report = _read(final_summary_path)
    if not final_report:
        _atomic_write_json(
            state_path,
            {
                "phase": "replicating_frozen_recipe",
                "updated_at": utc_now(),
                "winner": winner["name"],
                "confirmation_loaded": False,
                "test_loaded": False,
            },
        )

        def final_progress(row: dict[str, Any]) -> None:
            _atomic_write_json(
                state_path,
                {
                    "phase": "replicating_frozen_recipe",
                    "updated_at": utc_now(),
                    "winner": winner["name"],
                    "normalization": winner_normalization_mode,
                    "training_progress": row,
                    "confirmation_loaded": False,
                    "test_loaded": False,
                },
            )

        final_report = adapt_frozen_rcda_on_wfigs(
            final_summary_path=args.source_final,
            wfigs_dataset_root=args.tuning_dataset,
            rcda_normalization_path=winner_normalization_path,
            output_root=final_root,
            adaptation=replace(winner_config, source_seeds=None),
            progress_callback=final_progress,
        )
    if len(final_report.get("reports") or []) != 3:
        raise ValueError("expanded final adaptation did not produce three seeds")

    evidence = {
        "frozen_recipe_sha256": sha256_file(freeze_path),
        "candidate_summary_sha256": sha256_file(final_summary_path),
        "baseline_summary_sha256": sha256_file(args.baseline_adaptation),
        "confirmation_audit_sha256": sha256_file(args.confirmation_dataset / "DATASET_AUDIT.json"),
        "candidate_normalization_sha256": sha256_file(winner_normalization_path),
    }
    claim_path = args.output / "CONFIRMATION_CLAIM.json"
    result_path = args.output / "CONFIRMATION_RESULT.json"
    resumed = _resume_confirmation(
        claim_path=claim_path,
        result_path=result_path,
        evidence=evidence,
    )
    if resumed is not None:
        _atomic_write_json(
            state_path,
            {
                "phase": "complete",
                "updated_at": utc_now(),
                "winner": winner,
                "comparison": resumed["comparison"],
                "confirmation_gate": resumed["confirmation_gate"],
                "prospective_test_loaded": False,
                "resumed_without_reopening_confirmation": True,
            },
        )
        print(json.dumps(_read(state_path), indent=2))
        return 0
    _claim_confirmation(claim_path, evidence)
    _atomic_write_json(
        state_path,
        {
            "phase": "opening_confirmation_once",
            "updated_at": utc_now(),
            "frozen_recipe_sha256": evidence["frozen_recipe_sha256"],
            "prospective_test_loaded": False,
        },
    )
    candidate = evaluate_frozen_adaptation_on_validation(
        adaptation_summary_path=final_summary_path,
        dataset_root=args.confirmation_dataset,
        rcda_normalization_path=winner_normalization_path,
    )
    baseline = evaluate_frozen_adaptation_on_validation(
        adaptation_summary_path=args.baseline_adaptation,
        dataset_root=args.confirmation_dataset,
        rcda_normalization_path=args.rcda_normalization,
    )
    candidate_metrics = (candidate.get("ensemble") or {})["metrics"]
    baseline_metrics = (baseline.get("ensemble") or {})["metrics"]
    comparison = paired_event_comparison(candidate_metrics, baseline_metrics)
    result = {
        "schema": "wfd_wfigs_expansion_confirmation_result_v1",
        "generated_at": utc_now(),
        "evidence": evidence,
        "candidate": candidate,
        "baseline": baseline,
        "comparison": comparison,
        "confirmation_opened_once": True,
        "prospective_test_loaded": False,
        "confirmation_gate": (
            comparison["paired_delta"] > 0
            and comparison["paired_delta_event_bootstrap_95_ci"][0] > 0
        ),
    }
    _atomic_write_json(result_path, result)
    claim = _read(claim_path)
    _atomic_write_json(
        claim_path,
        {
            **claim,
            "phase": "complete",
            "completed_at": utc_now(),
            "result_sha256": sha256_file(result_path),
        },
    )
    _atomic_write_json(
        state_path,
        {
            "phase": "complete",
            "updated_at": utc_now(),
            "winner": winner,
            "comparison": comparison,
            "confirmation_gate": result["confirmation_gate"],
            "prospective_test_loaded": False,
        },
    )
    print(json.dumps(_read(state_path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
