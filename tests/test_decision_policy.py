"""Decision policy profiles: default ≡ legacy; field_ops stricter."""

from __future__ import annotations

import pytest

from wildfire_front.product.confidence import Decision, build_decision_card
from wildfire_front.product.decide_service import decide_from_request
from wildfire_front.product.policy import get_policy, list_policies

ML = {"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545}
OPS_A = {
    "quality_grade": "A",
    "primary_ros_m_min": 5.7,
    "n_frames_staged": 12,
    "speed_vs_ref_ratio": 0.85,
    "area_ha_max": 40,
}
OPEN = {"max_area_ha": 2000, "n_timeline_steps": 5, "activation": "X"}


def test_list_policies_has_core_ids():
    ids = {p["id"] for p in list_policies()}
    assert {"default", "field_ops", "research_open", "demo"} <= ids


def test_default_matches_legacy_require_ops_flag():
    """default policy + require_ops_for_go=True behaves like historical CLI."""
    a = build_decision_card(
        "e",
        open_metrics=OPEN,
        ml_metrics=ML,
        require_ops_for_go=True,
        policy_id="default",
    )
    # open only + require ops → HOLD monitoring (not GO)
    assert a.decision in (Decision.HOLD, Decision.ABSTAIN)
    assert a.decision != Decision.GO


def test_field_ops_blocks_ml_only_hold():
    """Catalog holdout alone never drives HOLD; live is required for ml_ok."""
    demo = build_decision_card("d", ml_metrics=ML, policy_id="default")
    field = build_decision_card("d", ml_metrics=ML, policy_id="field_ops")
    assert demo.confidence_pred == field.confidence_pred
    assert demo.confidence_pred == 0.0
    assert demo.decision == Decision.ABSTAIN
    assert field.decision == Decision.ABSTAIN
    assert "ml_holdout_quality_display" not in " ".join(demo.reasons)
    assert "ml_holdout_research_only_conf_zero" in " ".join(demo.reasons)


def test_field_ops_go_needs_higher_ops_confidence():
    # borderline ops: grade B → conf may be mid; field go_ops_min=0.65 is stricter
    ops_b = {
        "quality_grade": "B",
        "primary_ros_m_min": 4.0,
        "n_frames_staged": 4,
    }
    default = build_decision_card("b", ops_metrics=ops_b, policy_id="default")
    field = build_decision_card("b", ops_metrics=ops_b, policy_id="field_ops")
    # field never looser than default for same ops-only case
    order = {Decision.ABSTAIN: 0, Decision.HOLD: 1, Decision.GO: 2}
    assert order[field.decision] <= order[default.decision]


def test_research_open_more_permissive_hold():
    # weak open only
    weak_open = {"max_area_ha": 100, "n_timeline_steps": 2}
    research = build_decision_card("r", open_metrics=weak_open, policy_id="research_open")
    default = build_decision_card("r", open_metrics=weak_open, policy_id="default")
    # research hold_open_min=0.3 may HOLD where default ABSTAINS
    if default.decision == Decision.ABSTAIN:
        assert research.decision in (Decision.HOLD, Decision.ABSTAIN)


def test_field_ops_fusion_contract_caps():
    """T1.6: field_ops ML live weight ≤ 0.20 and abstain_below 0.45."""
    field = get_policy("field_ops")
    assert field.ml_live_max_weight == pytest.approx(0.20)
    assert field.ml_live_abstain_below == pytest.approx(0.45)
    live = {
        "schema": "ml_live_metrics_v1",
        "available": True,
        "confidence": 0.99,
        "abstain": False,
        "mean_entropy": 0.1,
        "member_disagreement": 0.05,
        "mean_margin": 0.4,
    }
    card = build_decision_card(
        "fusion_cap",
        ops_metrics=OPS_A,
        ml_live_metrics=live,
        policy_id="field_ops",
    )
    live_src = next(s for s in card.sources if "live" in str(s.get("id", "")).lower())
    assert float(live_src.get("weight") or 0.0) <= 0.20 + 1e-9
    assert "iou" not in str(card.metrics.get("ops") or {}).lower()


def test_field_ops_gold_like_unverified_cannot_go():
    """GOLD_IF-like ops+open+ml without R1–R4 sidecar must not GO under field_ops."""
    gold = {
        "ops_metrics": OPS_A,
        "open_metrics": OPEN,
        "ml_metrics": ML,
    }
    research = build_decision_card("gold_open", policy_id="research_open", **gold)
    field = build_decision_card("gold_field", policy_id="field_ops", **gold)
    assert field.system_reliability_pass is False
    assert field.decision != Decision.GO
    assert field.decision == Decision.ABSTAIN
    assert any("fail_closed" in r for r in field.reasons)
    if research.decision == Decision.GO:
        assert research.system_reliability_pass is False


def test_policy_in_audit_and_service():
    card = decide_from_request(
        {
            "event_id": "p",
            "ops_metrics": OPS_A,
            "ml_metrics": ML,
            "policy_id": "field_ops",
        }
    )
    assert card["policy_id"] == "field_ops"
    assert card["audit"]["policy_id"] == "field_ops"
    assert "policy:field_ops" in " ".join(card.get("reasons") or [])


def test_get_policy_unknown_falls_back():
    pol = get_policy("does_not_exist_xyz")
    assert pol.id == "default" or "unknown" in (pol.notes or "").lower()
    # Fail-closed: unknown id must not silently loosen to open default posture
    assert pol.require_ops_for_go is True
    assert pol.allow_ml_only_hold is False
    assert pol.allow_ml_live_in_fusion is False
    assert "fail-closed" in (pol.notes or "").lower() or "unknown" in (pol.notes or "").lower()


def test_policy_catalog_ml_live_fields():
    """Bug 12: live ML policy fields loaded from catalog with design defaults."""
    default = get_policy("default")
    field = get_policy("field_ops")
    research = get_policy("research_open")

    assert default.allow_ml_live_in_fusion is False
    assert default.ml_live_max_weight == pytest.approx(0.25)
    assert default.ml_live_abstain_below == pytest.approx(0.35)
    assert default.ml_live_veto_on_abstain is False

    assert field.allow_ml_live_in_fusion is True
    assert field.ml_live_max_weight == pytest.approx(0.20)
    assert field.ml_live_abstain_below == pytest.approx(0.45)
    assert field.ml_live_veto_on_abstain is False

    # research_open experimental + field_ops human promote 2026-08-13
    assert research.allow_ml_live_in_fusion is True
    assert research.ml_live_max_weight == pytest.approx(0.35)
    assert research.ml_live_abstain_below == pytest.approx(0.25)
    assert research.ml_live_veto_on_abstain is False
