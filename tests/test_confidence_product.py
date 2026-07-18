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
    kwargs = {
        "ml_metrics": {"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
        "ops_metrics": {"quality_grade": "B", "n_frames_staged": 5},
    }
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


def test_default_card_does_not_claim_reliability_pass():
    """Adversarial: cards without measured gates must not hard-code PASS / 1e-6."""
    card = build_decision_card(
        "honesty",
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
    assert card.system_reliability_pass is False
    sys_rel = card.audit.get("system_reliability") or {}
    assert sys_rel.get("system_reliability_pass") is False
    assert sys_rel.get("residual_silent_go_risk_bound") != 1e-6
    assert sys_rel.get("status") in ("unknown", "fail")
    checks = sys_rel.get("checks") or {}
    # Gates / determinism not measured by default
    assert checks.get("R2_gates") is not True
    assert checks.get("R1_determinism") is not True
    # Old bug: abstention_enforced was always True via conf >= 0.0
    assert "conf >= 0.0" not in str(sys_rel)


def test_unmeasured_gates_report_unknown_not_pass():
    rep = system_reliability_report()
    assert rep["system_reliability_pass"] is False
    assert rep["status"] == "unknown"
    assert rep["residual_silent_go_risk_bound"] == 1.0
    assert "UNKNOWN" in rep["five_nines_claim"] or "not measured" in rep["five_nines_claim"].lower()


def test_explicit_gates_can_pass():
    card = build_decision_card(
        "gated",
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 15,
            "speed_vs_ref_ratio": 0.8,
        },
        ml_metrics={"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
        gates_ok=True,
        determinism_ok=True,
        abstention_enforced=True,
        provenance_ok=True,
    )
    assert card.system_reliability_pass is True
    sys_rel = card.audit["system_reliability"]
    assert sys_rel["residual_silent_go_risk_bound"] == 1e-6
    assert sys_rel["status"] == "pass"


def test_field_ops_fail_closed_without_gates():
    """field_ops must not GO when system reliability is unverified."""
    strong = {
        "ops_metrics": {
            "quality_grade": "A",
            "primary_ros_m_min": 6.0,
            "n_frames_staged": 20,
            "speed_vs_ref_ratio": 0.9,
            "area_ha_max": 50,
        },
        "open_metrics": {"max_area_ha": 2000, "n_timeline_steps": 5},
        "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
    }
    default = build_decision_card("go_default", policy_id="default", **strong)
    field = build_decision_card("go_field", policy_id="field_ops", **strong)
    # Default may GO; field_ops without gates fails closed to ABSTAIN
    if default.decision == Decision.GO:
        assert field.decision == Decision.ABSTAIN
        assert any("fail_closed" in r for r in field.reasons)
    field_ok = build_decision_card(
        "go_field_ok",
        policy_id="field_ops",
        gates_ok=True,
        determinism_ok=True,
        abstention_enforced=True,
        provenance_ok=True,
        **strong,
    )
    if default.decision == Decision.GO:
        assert field_ok.decision == Decision.GO
        assert field_ok.system_reliability_pass is True


def test_reliability_gate_report_injection(tmp_path):
    report = {
        "ok": True,
        "system_reliability": {
            "system_reliability_pass": True,
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            },
        },
    }
    path = tmp_path / "RELIABILITY_GATE_REPORT.json"
    path.write_text(__import__("json").dumps(report), encoding="utf-8")
    card = build_decision_card(
        "from_report",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
        reliability_gate=path,
    )
    assert card.system_reliability_pass is True
