from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_wfigs_prospective_once import (
    _claim_or_resume,
    _validate_resume_artifacts,
    validate_prospective_gate,
)


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode()).hexdigest()


def _gate_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    summary = tmp_path / "adaptation.json"
    _write(
        summary,
        {
            "test_used_for_selection": False,
            "wfigs_test_loaded": False,
            "reports": [{}, {}, {}],
            "ensemble": {
                "threshold_selected_on": "wfigs_validation",
                "test_used_for_selection": False,
                "test_evaluated": False,
            },
        },
    )
    freeze = tmp_path / "freeze.json"
    _write(
        freeze,
        {
            "schema": "wfd_wfigs_adaptation_source_freeze_v1",
            "selection_split": "wfigs_validation",
            "test_used_for_selection": False,
            "prospective_test_evaluated": False,
            "winner": {
                "summary": str(summary),
                "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
            },
        },
    )
    preregistration = tmp_path / "prereg.json"
    _write(
        preregistration,
        {"event_ids_sha256": _digest(["e1"]), "pair_ids_sha256": _digest(["p1"])},
    )
    inventory = tmp_path / "inventory.json"
    _write(
        inventory,
        {"rows": [{"event_id": "e1", "pair_id": "p1", "training_ready": True}]},
    )
    return freeze, preregistration, inventory


def test_gate_binds_frozen_model_and_preregistered_cohort(tmp_path: Path) -> None:
    gate = validate_prospective_gate(*_gate_files(tmp_path))

    assert gate["cohort"]["events_selected"] == 1
    assert gate["cohort"]["events_materialized"] == 1
    assert gate["test_evaluated"] is False


def test_gate_rejects_model_changed_after_freeze(tmp_path: Path) -> None:
    freeze, preregistration, inventory = _gate_files(tmp_path)
    summary = Path(json.loads(freeze.read_text())["winner"]["summary"])
    summary.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="hash changed"):
        validate_prospective_gate(freeze, preregistration, inventory)


def test_open_once_resumes_same_evidence_and_rejects_different(tmp_path: Path) -> None:
    claim_path = tmp_path / "claim.json"
    gate = {"source_freeze_sha256": "a", "adaptation_summary_sha256": "b", "preregistration_sha256": "c", "inventory_sha256": "d"}

    first = _claim_or_resume(claim_path, gate)
    resumed = _claim_or_resume(claim_path, gate)
    assert resumed == first
    with pytest.raises(ValueError, match="different evidence"):
        _claim_or_resume(claim_path, {**gate, "inventory_sha256": "changed"})


def test_resume_rejects_orphaned_result_or_completed_claim(tmp_path: Path) -> None:
    claim_path = tmp_path / "claim.json"
    result_path = tmp_path / "result.json"
    result_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="without its one-time claim"):
        _validate_resume_artifacts(claim_path, result_path)

    result_path.unlink()
    _write(claim_path, {"phase": "complete"})
    with pytest.raises(ValueError, match="missing its result"):
        _validate_resume_artifacts(claim_path, result_path)
