from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_wfigs_expansion_nightwatch import (
    _claim_confirmation,
    _resume_confirmation,
)
from wildfire_front.ml.wfigs_expansion import (
    paired_event_comparison,
    split_validation_inventory,
    validate_inventory_isolation,
)


def _inventory(path: Path, split: str, events: list[str]) -> Path:
    rows = [
        {
            "event_id": event,
            "pair_id": f"pair-{event}",
            "split": split,
            "status": "materialized",
            "training_ready": True,
            "relative_path": f"{event}.npz",
        }
        for event in events
    ]
    path.write_text(
        json.dumps({"configuration": {"split": split}, "rows": rows}),
        encoding="utf-8",
    )
    return path


def test_validation_expansion_split_is_deterministic_and_disjoint(tmp_path: Path) -> None:
    source = _inventory(tmp_path / "source.json", "validation", [f"event-{i}" for i in range(30)])
    first = split_validation_inventory(
        source,
        development_path=tmp_path / "dev.json",
        confirmation_path=tmp_path / "confirm.json",
    )
    second = split_validation_inventory(
        source,
        development_path=tmp_path / "dev2.json",
        confirmation_path=tmp_path / "confirm2.json",
    )
    dev = json.loads((tmp_path / "dev.json").read_text())["rows"]
    confirm = json.loads((tmp_path / "confirm.json").read_text())["rows"]
    assert first == second
    assert {row["event_id"] for row in dev}.isdisjoint({row["event_id"] for row in confirm})
    assert first["development_ready"] + first["confirmation_ready"] == 30


def test_inventory_isolation_rejects_prospective_reuse(tmp_path: Path) -> None:
    train = _inventory(tmp_path / "train.json", "train", ["train"])
    dev = _inventory(tmp_path / "dev.json", "validation", ["dev"])
    confirm = _inventory(tmp_path / "confirm.json", "validation", ["confirm"])
    forbidden = _inventory(tmp_path / "forbidden.json", "test", ["confirm"])
    with pytest.raises(ValueError, match="event leakage"):
        validate_inventory_isolation(
            train_inventory_paths=[train],
            development_inventory_paths=[dev],
            confirmation_inventory_path=confirm,
            forbidden_inventory_path=forbidden,
        )


def test_paired_confirmation_bootstrap_reports_positive_delta() -> None:
    candidate = {
        "per_event": {event: {"iou": value} for event, value in {"a": 0.4, "b": 0.5}.items()}
    }
    baseline = {
        "per_event": {event: {"iou": value} for event, value in {"a": 0.1, "b": 0.2}.items()}
    }
    report = paired_event_comparison(candidate, baseline, n_resamples=100)
    assert report["events"] == 2
    assert report["paired_delta"] == pytest.approx(0.3)
    assert report["paired_delta_event_bootstrap_95_ci"][0] > 0


def test_confirmation_claim_resumes_without_reopening(tmp_path: Path) -> None:
    evidence = {"freeze": "a", "candidate": "b"}
    claim = tmp_path / "claim.json"
    result = tmp_path / "result.json"
    _claim_confirmation(claim, evidence)
    result.write_text(json.dumps({"evidence": evidence, "comparison": {}}), encoding="utf-8")
    assert _resume_confirmation(claim_path=claim, result_path=result, evidence=evidence) is not None
    with pytest.raises(ValueError, match="different frozen evidence"):
        _claim_confirmation(claim, {"freeze": "changed"})
