"""Tests for decision card / confidence / abstention."""

from __future__ import annotations

from wildfire_front.product.confidence import (
    Decision,
    build_decision_card,
    content_hash,
    system_reliability_report,
)


def test_empty_abstains():
    card = build_decision_card("e")
    assert card.decision == Decision.ABSTAIN
    assert card.confidence_pred < 0.2


def test_open_only_hold_or_abstain_not_go_with_require_ops():
    card = build_decision_card(
        "o",
        open_metrics={
            "max_area_ha": 2000,
            "n_timeline_steps": 5,
            "activation": "EMSR578",
        },
        require_ops_for_go=True,
    )
    assert card.decision in (Decision.HOLD, Decision.ABSTAIN)


def test_ops_a_can_go():
    card = build_decision_card(
        "a",
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 15,
            "area_ha_max": 39,
            "speed_vs_ref_ratio": 0.8,
        },
        open_metrics={"max_area_ha": 1000, "n_timeline_steps": 3},
        ml_metrics={"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
    )
    assert card.decision in (Decision.GO, Decision.HOLD)
    assert card.confidence_pred >= 0.4
    assert "input_hash" in card.audit
    assert card.disclaimers


def test_determinism_of_scores():
    kwargs = dict(
        ml_metrics={"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
        ops_metrics={"quality_grade": "B", "n_frames_staged": 5},
    )
    a = build_decision_card("d", **kwargs)
    b = build_decision_card("d", **kwargs)
    assert a.confidence_pred == b.confidence_pred
    assert a.decision == b.decision
    ha = content_hash({"c": a.confidence_pred, "d": a.decision.value, "s": a.sources})
    hb = content_hash({"c": b.confidence_pred, "d": b.decision.value, "s": b.sources})
    assert ha == hb


def test_five_nines_is_system_not_fire():
    rep = system_reliability_report(
        gates_ok=True,
        determinism_ok=True,
        abstention_enforced=True,
        provenance_ok=True,
    )
    assert rep["system_reliability_pass"] is True
    assert rep["residual_silent_go_risk_bound"] == 1e-6
    assert rep["fire_prediction_accuracy_claim"] == "NOT_CLAIMED"
    assert "NOT" in rep["five_nines_claim"] or "not" in rep["five_nines_claim"].lower()
