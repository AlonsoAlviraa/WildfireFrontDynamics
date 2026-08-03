"""Tests for F3.4 envelope scorecard and F3.5 Decision Card attach."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.fuel.envelope import compute_hybrid_envelope
from wildfire_front.fuel.envelope_scorecard import (
    SCHEMA,
    attach_envelope_to_decision_card,
    build_tobarra_envelope_scorecard,
    check_envelope_structure,
    check_ensemble_honesty,
    check_multi_window_consistency,
)


def test_structure_pass() -> None:
    env = compute_hybrid_envelope(
        None,
        observed_ros_m_min=5.71,
        wind_10m_ms=4.4,
        wind_from_deg=270.0,
        dead_fmc_pct=7.0,
        slope_deg=3.3,
    )
    checks = check_envelope_structure(env)
    assert all(c.status != "fail" for c in checks)


def test_ensemble_honesty() -> None:
    env = compute_hybrid_envelope(
        None,
        observed_ros_m_min=5.71,
        wind_10m_ms=4.4,
        wind_from_deg=270.0,
        dead_fmc_pct=7.0,
        slope_deg=3.3,
        with_ensemble=True,
    )
    checks = check_ensemble_honesty(env)
    ids = {c.id: c.status for c in checks}
    assert ids.get("hybrid_head_flat") == "pass"
    assert ids.get("physics_only_labeled") == "pass"


def test_multi_window_head_stable() -> None:
    from wildfire_front.fuel.envelope_scorecard import build_multi_window_envelopes

    windows = build_multi_window_envelopes(with_ensemble=False)
    checks = check_multi_window_consistency(windows)
    assert any(c.id == "multi_window_head_stable" and c.status == "pass" for c in checks)


def test_attach_card_weight_zero() -> None:
    env = compute_hybrid_envelope(
        None,
        observed_ros_m_min=5.71,
        wind_10m_ms=4.4,
        wind_from_deg=270.0,
        dead_fmc_pct=7.0,
    )
    card = {
        "event_id": "test",
        "decision": "GO",
        "confidence_pred": 0.7,
        "reasons": ["ops_thermal_front:ok"],
        "disclaimers": ["Not a tactical dispatch order."],
        "sources": [],
        "metrics": {"allow_ml_live_in_fusion": False},
        "audit": {},
    }
    out = attach_envelope_to_decision_card(card, env)
    assert out["decision"] == "GO"
    assert out["metrics"]["allow_ml_live_in_fusion"] is False
    assert out["metrics"]["envelope_v3_hybrid"]["fusion_weight"] == 0.0
    assert any(r.startswith("envelope_v3:") for r in out["reasons"])
    assert any(s.get("id") == "envelope_v3_hybrid" for s in out["sources"])
    assert out["sources"][-1]["weight"] == 0.0
    assert out["sources"][-1]["actionable"] is False


def test_full_scorecard(tmp_path: Path) -> None:
    inv = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "real_if"
        / "pablo_geacam_20260730_tobarra"
        / "inventory.json"
    )
    score = build_tobarra_envelope_scorecard(
        pablo_inventory=inv if inv.is_file() else None,
        decision_card={
            "event_id": "tobarra",
            "decision": "HOLD",
            "reasons": [],
            "disclaimers": [],
            "sources": [],
            "metrics": {},
            "audit": {},
        },
        with_ensemble=True,
    )
    assert score["schema"] == SCHEMA
    assert score["verdict"] == "PASS"
    assert score["counts"]["fail"] == 0
    assert score["decision_card"] is not None
    p = tmp_path / "score.json"
    p.write_text(json.dumps(score), encoding="utf-8")
    assert p.is_file()
