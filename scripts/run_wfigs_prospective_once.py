#!/usr/bin/env python3
"""Evaluate the frozen WFIGS source on the preregistered holdout once."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_wfigs_scaleup_paper_nightwatch import (  # noqa: E402
    _validate_preregistered_inventory,
)
from wildfire_front.ml.wfigs_external_eval import (  # noqa: E402
    evaluate_adapted_rcda_on_wfigs,
)
from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402

FREEZE_SCHEMA = "wfd_wfigs_adaptation_source_freeze_v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_prospective_gate(
    source_freeze_path: Path,
    preregistration_path: Path,
    inventory_path: Path,
) -> dict[str, Any]:
    freeze = _read(source_freeze_path)
    winner = freeze.get("winner") or {}
    if not (
        freeze.get("schema") == FREEZE_SCHEMA
        and freeze.get("selection_split") == "wfigs_validation"
        and freeze.get("test_used_for_selection") is False
        and freeze.get("prospective_test_evaluated") is False
    ):
        raise ValueError("WFIGS adaptation source is not frozen before TEST")
    summary_path = Path(str(winner.get("summary") or ""))
    if not summary_path.is_file() or _sha256(summary_path) != winner.get(
        "summary_sha256"
    ):
        raise ValueError("frozen winner summary is missing or its hash changed")
    adaptation = _read(summary_path)
    ensemble = adaptation.get("ensemble") or {}
    if not (
        adaptation.get("test_used_for_selection") is False
        and adaptation.get("wfigs_test_loaded") is False
        and len(adaptation.get("reports") or []) >= 3
        and ensemble.get("threshold_selected_on") == "wfigs_validation"
        and ensemble.get("test_used_for_selection") is False
        and ensemble.get("test_evaluated") is False
    ):
        raise ValueError("frozen winner is not an isolated multi-seed VAL model")
    preregistration = _read(preregistration_path)
    inventory = _read(inventory_path)
    cohort = _validate_preregistered_inventory(preregistration, inventory)
    return {
        "source_freeze": str(source_freeze_path.resolve()),
        "source_freeze_sha256": _sha256(source_freeze_path),
        "adaptation_summary": str(summary_path.resolve()),
        "adaptation_summary_sha256": _sha256(summary_path),
        "preregistration": str(preregistration_path.resolve()),
        "preregistration_sha256": _sha256(preregistration_path),
        "inventory": str(inventory_path.resolve()),
        "inventory_sha256": _sha256(inventory_path),
        "cohort": cohort,
        "selection_split": "wfigs_validation",
        "test_evaluated": False,
    }


def _claim_or_resume(path: Path, gate: dict[str, Any]) -> dict[str, Any]:
    identity_keys = (
        "source_freeze_sha256",
        "adaptation_summary_sha256",
        "preregistration_sha256",
        "inventory_sha256",
    )
    claim = {
        "schema": "wfd_wfigs_prospective_open_once_v1",
        "opened_at": utc_now(),
        "phase": "claimed",
        **gate,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(claim, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return claim
    except FileExistsError:
        existing = _read(path)
        if any(existing.get(key) != gate.get(key) for key in identity_keys):
            raise ValueError(
                "prospective TEST was already claimed by different evidence"
            ) from None
        return existing


def _validate_resume_artifacts(claim_path: Path, result_path: Path) -> None:
    if result_path.is_file() and not claim_path.is_file():
        raise ValueError("prospective result exists without its one-time claim")
    if claim_path.is_file():
        claim = _read(claim_path)
        if claim.get("phase") == "complete" and not result_path.is_file():
            raise ValueError("completed prospective claim is missing its result")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prospective-inventory", type=Path, required=True)
    parser.add_argument("--train-inventory", type=Path, required=True)
    parser.add_argument("--validation-inventory", type=Path, required=True)
    parser.add_argument("--prospective-dataset", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--geometry-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-open-prospective-test", action="store_true")
    args = parser.parse_args()
    if not args.confirm_open_prospective_test:
        raise ValueError("explicit --confirm-open-prospective-test is required")
    args.output.mkdir(parents=True, exist_ok=True)
    gate = validate_prospective_gate(
        args.source_freeze,
        args.preregistration,
        args.prospective_inventory,
    )
    claim_path = args.output / "PROSPECTIVE_OPEN_ONCE.json"
    result_path = args.output / "WFIGS_PROSPECTIVE_TEST_EVAL.json"
    _validate_resume_artifacts(claim_path, result_path)
    claim = _claim_or_resume(claim_path, gate)
    if result_path.is_file():
        result = _read(result_path)
    else:
        _atomic_write_json(claim_path, {**claim, "phase": "building_dataset"})
        WFIGSTensorDatasetBuilder(
            inventory_paths=[
                args.train_inventory,
                args.validation_inventory,
                args.prospective_inventory,
            ],
            output_root=args.prospective_dataset,
        ).build()
        _atomic_write_json(claim_path, {**claim, "phase": "evaluating_once"})
        result = evaluate_adapted_rcda_on_wfigs(
            adaptation_summary_path=Path(gate["adaptation_summary"]),
            wfigs_dataset_root=args.prospective_dataset,
            rcda_normalization_path=args.rcda_normalization,
            geometry_baseline_path=args.geometry_baseline,
            output_path=result_path,
        )
    final = {
        **claim,
        "phase": "complete",
        "completed_at": utc_now(),
        "result": str(result_path.resolve()),
        "result_sha256": _sha256(result_path),
        "summary": result["summary"],
        "test_evaluated": True,
    }
    _atomic_write_json(claim_path, final)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
