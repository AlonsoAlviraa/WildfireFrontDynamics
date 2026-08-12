"""Forensic acta, radio-bridge, and decision replay."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.confidence import build_decision_card
from wildfire_front.product.decide_service import decide_from_request
from wildfire_front.product.forensics import (
    RADIO_MAX_CHARS,
    _reliability_gate_from_card,
    extract_replay_sources,
    load_and_replay_bundle,
    render_radio_bridge,
    replay_decision,
    write_forensic_bundle,
)


def _sample_card() -> dict:
    return decide_from_request(
        {
            "event_id": "forensic_test",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.7,
                "n_frames_staged": 12,
                "speed_vs_ref_ratio": 0.85,
                "area_ha_max": 40,
            },
            "ml_metrics": {
                "test_iou": 0.8963,
                "improvement_vs_copy_iou": 0.2545,
            },
            "open_metrics": {
                "max_area_ha": 2000,
                "n_timeline_steps": 5,
                "activation": "EMSR_TEST",
            },
            "require_ops_for_go": True,
            "channel": "test",
        }
    )


def test_radio_bridge_short_and_has_decision():
    card = _sample_card()
    text = render_radio_bridge(card)
    assert len(text) <= RADIO_MAX_CHARS
    assert card["decision"] in text
    assert "NO es orden" in text or "NOT dispatch" in text


def test_forensic_bundle_and_replay_ok(tmp_path: Path):
    card = _sample_card()
    ops = {
        "quality_grade": "A",
        "primary_ros_m_min": 5.7,
        "n_frames_staged": 12,
        "speed_vs_ref_ratio": 0.85,
        "area_ha_max": 40,
    }
    ml = {"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545}
    open_m = {
        "max_area_ha": 2000,
        "n_timeline_steps": 5,
        "activation": "EMSR_TEST",
    }
    paths = write_forensic_bundle(
        tmp_path,
        card,
        ml_metrics=ml,
        ops_metrics=ops,
        open_metrics=open_m,
        require_ops_for_go=True,
        operator="sala_test",
    )
    assert Path(paths["acta"]).is_file()
    assert Path(paths["radio"]).is_file()
    assert Path(paths["manifest"]).is_file()
    assert paths["self_replay_ok"] == "True"
    acta = Path(paths["acta"]).read_text(encoding="utf-8")
    assert "Acta de decisión" in acta
    assert "output_hash" in acta
    assert "sala_test" in acta

    result = load_and_replay_bundle(tmp_path)
    assert result["replay_ok"] is True
    assert result["match_output_hash"] is True
    assert result["match_decision"] is True


def test_replay_detects_tamper(tmp_path: Path):
    card = _sample_card()
    ops = {
        "quality_grade": "A",
        "primary_ros_m_min": 5.7,
        "n_frames_staged": 12,
        "speed_vs_ref_ratio": 0.85,
    }
    write_forensic_bundle(
        tmp_path,
        card,
        ops_metrics=ops,
        ml_metrics={"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
        require_ops_for_go=True,
    )
    src = json.loads((tmp_path / "replay_sources.json").read_text(encoding="utf-8"))
    # tamper expected decision
    src["expected_decision"] = "ABSTAIN"
    result = replay_decision(src)
    assert result["replay_ok"] is False
    assert result["match_decision"] is False


def test_extract_replay_from_card_alone():
    card = _sample_card()
    src = extract_replay_sources(card, require_ops_for_go=True)
    # Without raw metrics, replay still rebuilds from embedded source metrics
    result = replay_decision(src)
    assert result["match_decision"] is True
    # output hash should match when sources metrics sufficient
    assert result["replay_ok"] is True
    assert result.get("event_id") == "forensic_test"


def test_reliability_gate_from_card_partial_checks_returns_none():
    """Partial / non-bool R1–R4 must not embed a field unlock gate."""
    card = {
        "event_id": "partial",
        "decision": "GO",
        "audit": {
            "system_reliability": {
                "system_reliability_pass": True,
                "checks": {
                    "R1_determinism": True,
                    "R2_gates": None,  # unmeasured
                    "R3_abstention_enforced": True,
                    "R4_provenance": True,
                },
            }
        },
    }
    assert _reliability_gate_from_card(card) is None


def test_reliability_gate_from_card_all_true_embeds_pass():
    card = {
        "event_id": "full_pass",
        "decision": "GO",
        "audit": {
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "system_reliability": {
                "system_reliability_pass": True,
                "status": "pass",
                "checks": {
                    "R1_determinism": True,
                    "R2_gates": True,
                    "R3_abstention_enforced": True,
                    "R4_provenance": True,
                },
            },
        },
    }
    gate = _reliability_gate_from_card(card)
    assert gate is not None
    assert gate["field_unlock"] is True
    assert gate["suite_only"] is False
    assert gate["event_id"] == "full_pass"
    assert gate["provenance"]["kind"] == "this_run"
    assert gate["provenance"]["input_hash"] == "a" * 64
    assert gate["system_reliability"]["checks"]["R2_gates"] is True


def test_field_ops_go_replay_with_embedded_this_run_gate():
    """field_ops GO needs this-run-shaped gate; without it replay fails closed to ABSTAIN."""
    ops = {
        "quality_grade": "A",
        "primary_ros_m_min": 5.7,
        "n_frames_staged": 12,
        "speed_vs_ref_ratio": 0.85,
        "area_ha_max": 40,
    }
    open_m = {"max_area_ha": 2000, "n_timeline_steps": 5, "activation": "X"}
    # Card with measured R1–R4 (as live publish would attach)
    card = build_decision_card(
        "field_ops_replay",
        ops_metrics=ops,
        open_metrics=open_m,
        policy_id="field_ops",
        require_ops_for_go=True,
        gates_ok=True,
        determinism_ok=True,
        abstention_enforced=True,
        provenance_ok=True,
    )
    assert card.decision.value == "GO"
    payload = card.to_dict()
    gate = _reliability_gate_from_card(payload)
    assert gate is not None and gate["field_unlock"] is True

    src = extract_replay_sources(
        payload,
        ops_metrics=ops,
        open_metrics=open_m,
        require_ops_for_go=True,
    )
    assert src.get("reliability_gate") is not None
    result = replay_decision(src)
    assert result["replay_ok"] is True
    assert result["got_decision"] == "GO"
    assert result.get("event_id") == "field_ops_replay"

    # Without embedded gate, field_ops fail-closed → ABSTAIN (not a silent GO)
    src_no_gate = dict(src)
    src_no_gate["reliability_gate"] = None
    bad = replay_decision(src_no_gate)
    assert bad["got_decision"] == "ABSTAIN"
    assert bad["match_decision"] is False
