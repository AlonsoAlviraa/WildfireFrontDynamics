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
    # No R1–R4 check is auto-claimed True without measurement
    assert checks.get("R1_determinism") is None
    assert checks.get("R2_gates") is None
    assert checks.get("R3_abstention_enforced") is None
    assert checks.get("R4_provenance") is None
    # Heuristic lives outside checks
    assert "abstention_heuristic_ok" in card.audit
    assert card.audit.get("provenance_hashes_attached") is True


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


def test_ok_only_gate_report_does_not_pass():
    """Bare {\"ok\": true} must not grant R1–R4 PASS."""
    card = build_decision_card(
        "ok_only",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
        reliability_gate={"ok": True},
    )
    assert card.system_reliability_pass is False
    sys_rel = card.audit["system_reliability"]
    assert sys_rel["status"] == "unknown"
    assert sys_rel["residual_silent_go_risk_bound"] == 1.0
    checks = sys_rel["checks"]
    assert checks["R1_determinism"] is None
    assert checks["R2_gates"] is None
    assert checks["R3_abstention_enforced"] is None
    assert checks["R4_provenance"] is None


def test_field_ops_cli_cannot_enable_ml_live_fusion():
    """field_ops hard-clamps live fusion even if kwargs/CLI pass allow=True."""
    live = {
        "available": True,
        "confidence": 0.9,
        "actionable": True,
        "abstained": False,
        "diagnostics": {"ensemble_disagreement": 0.05},
    }
    card = build_decision_card(
        "fo_no_or",
        policy_id="field_ops",
        ml_live_metrics=live,
        allow_ml_live_in_fusion=True,
    )
    assert card.metrics.get("allow_ml_live_in_fusion") is False
    snap = (card.audit or {}).get("policy_snapshot") or {}
    assert snap.get("allow_ml_live_in_fusion") is False
    assert snap.get("effective_allow_ml_live_in_fusion") is False
    # Live source may be present but fusion weight must be zero when fusion disallowed
    live_src = next(
        (s for s in (card.sources or []) if "live" in str(s.get("id", "")).lower()),
        None,
    )
    if live_src is not None:
        assert float(live_src.get("weight") or 0.0) == 0.0


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
    # Fixture must produce GO on default — otherwise fail-closed branch is untested
    assert default.decision == Decision.GO, "fixture must yield GO under default policy"
    field = build_decision_card("go_field", policy_id="field_ops", **strong)
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
    assert field_ok.decision == Decision.GO
    assert field_ok.system_reliability_pass is True


def test_reliability_gate_report_injection(tmp_path):
    report = {
        "ok": True,
        "event_id": "from_report",
        "suite_only": False,
        "field_unlock": True,
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


def test_suite_only_report_does_not_unlock():
    """docs-style suite_only / field_unlock=false reports must not grant PASS."""
    report = {
        "ok": True,
        "suite_only": True,
        "field_unlock": False,
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    card = build_decision_card(
        "suite",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
        reliability_gate=report,
    )
    assert card.system_reliability_pass is False


def test_gate_report_event_id_mismatch_rejected():
    report = {
        "event_id": "other_event",
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    card = build_decision_card(
        "my_event",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
        reliability_gate=report,
    )
    assert card.system_reliability_pass is False


def test_score_ops_source_requires_positive_ros():
    """A3: grade alone is not enough — finite primary_ros_m_min > 0 required."""
    from wildfire_front.product.confidence import score_ops_source

    no_ros = score_ops_source({"quality_grade": "A", "n_frames_staged": 12})
    assert no_ros["available"] is False
    assert no_ros["weight"] == 0.0

    zero_ros = score_ops_source(
        {"quality_grade": "A", "primary_ros_m_min": 0.0, "n_frames_staged": 12}
    )
    assert zero_ros["available"] is False

    neg = score_ops_source({"quality_grade": "B", "primary_ros_m_min": -1.0, "n_frames_staged": 5})
    assert neg["available"] is False

    ok = score_ops_source(
        {
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 10,
            "speed_vs_ref_ratio": 0.9,
        }
    )
    assert ok["available"] is True
    assert ok["weight"] > 0.0


def test_ml_holdout_not_fused_into_live_confidence():
    """Static catalog IoU is holdout_quality research metadata, weight 0."""
    from wildfire_front.product.confidence import score_ml_source

    src = score_ml_source({"test_iou": 0.9, "improvement_vs_copy_iou": 0.25})
    assert src["role"] == "holdout_quality"
    assert src["weight"] == 0.0
    assert src["actionable"] is False
    assert float(src["holdout_quality"]) <= 0.75
    # Alone: ABSTAIN, never conf=1.0 phenomenon certainty
    card = build_decision_card(
        "holdout_only",
        ml_metrics={"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
    )
    assert card.decision == Decision.ABSTAIN
    assert card.confidence_pred == 0.0
    assert "ml_holdout_research_only_conf_zero" in " ".join(card.reasons)
    assert src["weight"] == 0.0
    assert src["available"] is True
    # Ops-only fusion must match ops+ml fusion (ml not fused)
    ops = {
        "quality_grade": "A",
        "primary_ros_m_min": 5.0,
        "n_frames_staged": 10,
        "speed_vs_ref_ratio": 0.9,
    }
    a = build_decision_card("a", ops_metrics=ops)
    b = build_decision_card(
        "b",
        ops_metrics=ops,
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
    )
    assert abs(a.confidence_pred - b.confidence_pred) < 1e-9


def test_suite_run_report_does_not_unlock_field():
    """suite_run (reliability_gate.py live output) must not unlock field_ops."""
    report = {
        "ok": True,
        "suite_only": False,
        "field_unlock": True,
        "provenance": {"kind": "suite_run"},
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    card = build_decision_card(
        "incident_x",
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 6.0,
            "n_frames_staged": 20,
            "speed_vs_ref_ratio": 0.9,
        },
        reliability_gate=report,
        policy_id="field_ops",
    )
    assert card.system_reliability_pass is False
    assert card.decision == Decision.ABSTAIN


def test_field_gate_requires_event_id_match():
    """Full checks without event_id must not unlock when card has an event_id."""
    report = {
        "field_unlock": True,
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    card = build_decision_card(
        "needs_event",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
        reliability_gate=report,
    )
    assert card.system_reliability_pass is False
