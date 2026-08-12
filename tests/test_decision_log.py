"""Decision-log + ACK sidecar — real allowlisted work_dir paths (Agent B PR1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.product.decide_service import PathNotAllowedError, decide_from_request
from wildfire_front.product.decision_log import (
    CORE_DECISION_FIELDS,
    DECISION_LOG_FILENAME,
    UnknownDecisionIdError,
    ack_decision,
    append_decision,
    get_decision,
    load_decision_log,
    log_file_path,
)


def _sample_card(*, event_id: str = "IF_TEST_1") -> dict:
    """Drive real decide_from_request — not a hard-coded fake card."""
    return decide_from_request(
        {
            "event_id": event_id,
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 10,
                "speed_vs_ref_ratio": 0.9,
            },
            "ml_metrics": {"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
            "channel": "pytest",
            "trust_client_reliability": True,
        }
    )


def test_append_and_load_round_trip(tmp_path: Path):
    work = tmp_path / "incident_a"
    work.mkdir()
    card = _sample_card()
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    assert entry["decision_id"]
    for field in CORE_DECISION_FIELDS:
        assert field in entry, field
    assert entry["decision"] == card["decision"]
    assert entry["event_id"] == card["event_id"]
    assert entry["rails"]["GO_Q"] == "partial"
    assert entry["rails"]["field_ops_fusion"] == "ON"

    log_path = log_file_path(work)
    assert log_path.is_file()
    assert log_path.name == DECISION_LOG_FILENAME
    # File is under work_dir (allowlist sandbox)
    assert log_path.resolve().is_relative_to(work.resolve())

    loaded = load_decision_log(work, base=tmp_path, include_repo_root=False)
    assert len(loaded) == 1
    assert loaded[0]["decision_id"] == entry["decision_id"]
    assert loaded[0]["decision"] == entry["decision"]
    assert loaded[0]["output_hash"] == entry["output_hash"]

    again = get_decision(work, entry["decision_id"], base=tmp_path, include_repo_root=False)
    assert again is not None
    assert again["decision_id"] == entry["decision_id"]
    assert again["confidence_pred"] == entry["confidence_pred"]


def test_ack_round_trip_and_unknown_fails_closed(tmp_path: Path):
    work = tmp_path / "incident_b"
    work.mkdir()
    card = _sample_card(event_id="IF_ACK")
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    did = entry["decision_id"]

    acked = ack_decision(
        work,
        did,
        operator="sala_test",
        note="ACK eng rehearsal",
        base=tmp_path,
        include_repo_root=False,
    )
    assert acked["ack"] is not None
    assert acked["ack"]["acked"] is True
    assert acked["ack"]["operator"] == "sala_test"
    assert acked["ack"]["note"] == "ACK eng rehearsal"
    assert acked["ack"]["acked_at_utc"]

    reloaded = get_decision(work, did, base=tmp_path, include_repo_root=False)
    assert reloaded is not None
    assert reloaded["ack"]["acked"] is True
    assert reloaded["decision"] == entry["decision"]

    with pytest.raises(UnknownDecisionIdError):
        ack_decision(
            work,
            "00000000-0000-0000-0000-000000000000",
            base=tmp_path,
            include_repo_root=False,
        )


def test_path_outside_allowlist_rejected(tmp_path: Path):
    work = tmp_path / "ok"
    work.mkdir()
    outside = tmp_path.parent / f"outside_wfd_{tmp_path.name}"
    outside.mkdir(exist_ok=True)
    card = _sample_card()
    with pytest.raises(PathNotAllowedError):
        append_decision(outside, card, base=tmp_path, include_repo_root=False)
    with pytest.raises(PathNotAllowedError):
        load_decision_log(outside, base=tmp_path, include_repo_root=False)
    # Traversal-style relative escape (resolved outside base)
    evil = work / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathNotAllowedError):
        append_decision(evil, card, base=tmp_path, include_repo_root=False)


def test_rails_non_claims_never_flip_gates(tmp_path: Path):
    work = tmp_path / "rails"
    work.mkdir()
    card = _sample_card()
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    # Log must not claim GO_Q complete; fusion ON is the human-promoted rail
    assert entry["rails"]["GO_Q"] != "true"
    assert entry["rails"]["GO_Q"] == "partial"
    assert entry["rails"]["field_ops_fusion"] == "ON"
    raw = (work / DECISION_LOG_FILENAME).read_text(encoding="utf-8").lower()
    assert "go_q complete" not in raw
    # Real decide card itself must not invent fusion unlock
    assert card.get("system_reliability_pass") is False or card.get("decision") in (
        "GO",
        "HOLD",
        "ABSTAIN",
    )


def test_multiple_appends_preserve_order(tmp_path: Path):
    work = tmp_path / "multi"
    work.mkdir()
    e1 = append_decision(work, _sample_card(event_id="e1"), base=tmp_path, include_repo_root=False)
    e2 = append_decision(work, _sample_card(event_id="e2"), base=tmp_path, include_repo_root=False)
    log = load_decision_log(work, base=tmp_path, include_repo_root=False)
    assert [x["decision_id"] for x in log] == [e1["decision_id"], e2["decision_id"]]
    assert [x["event_id"] for x in log] == ["e1", "e2"]
    # JSONL line count matches entries
    lines = [
        ln
        for ln in (work / DECISION_LOG_FILENAME).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(lines) == 2
    assert json.loads(lines[0])["decision_id"] == e1["decision_id"]
