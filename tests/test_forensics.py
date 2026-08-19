"""Forensic acta, radio-bridge, and decision replay."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.decide_service import decide_from_request
from wildfire_front.product.forensics import (
    RADIO_MAX_CHARS,
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


def test_same_inputs_same_output_hash_and_changed_input_differs():
    """R1: identical decide calls share hashes; a changed input does not reuse them."""
    req = {
        "event_id": "r1_ident",
        "ops_metrics": {
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 12,
            "speed_vs_ref_ratio": 0.85,
            "area_ha_max": 40,
        },
        "ml_metrics": {"test_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
        "open_metrics": {"max_area_ha": 2000, "n_timeline_steps": 5},
        "policy_id": "field_ops",
        "channel": "test",
    }
    a = decide_from_request(req)
    b = decide_from_request(req)
    ha = (a.get("audit") or {}).get("output_hash")
    hb = (b.get("audit") or {}).get("output_hash")
    assert ha and hb
    assert ha == hb
    assert a["decision"] == b["decision"]
    src = extract_replay_sources(a, require_ops_for_go=False)
    first = replay_decision(src)
    second = replay_decision(src)
    assert first["replay_ok"] is True
    assert second["replay_ok"] is True
    assert first["got_output_hash"] == second["got_output_hash"] == ha

    changed = dict(req)
    changed["ops_metrics"] = {**req["ops_metrics"], "primary_ros_m_min": 2.1}
    c = decide_from_request(changed)
    hc = (c.get("audit") or {}).get("output_hash")
    assert hc
    assert hc != ha


def test_field_ops_go_replays_with_this_run_gate(tmp_path: Path):
    """Incident GO unlocked by this-run sidecar must replay to the same hash."""
    from wildfire_front.incident.pipeline import publish_decision_card

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    artifacts = publish_decision_card(
        outbox,
        "r1_inc",
        {
            "quality_grade": "A",
            "speed_median_m_min": 5.5,
            "n_frames_staged": 12,
            "area_ha_max": 40,
            "speed_vs_ref_ratio": 0.9,
        },
        n_frames=12,
        include_ml_metrics=False,
        open_metrics={"max_area_ha": 2000, "n_timeline_steps": 5},
        decision_policy="field_ops",
        write_this_run_gate=True,
    )
    assert artifacts["decision"] == "GO"
    card = json.loads((outbox / "fire_decision_card.json").read_text(encoding="utf-8"))
    assert card["decision"] == "GO"
    src = extract_replay_sources(card)
    result = replay_decision(src)
    assert result["match_decision"] is True
    assert result["match_output_hash"] is True
    assert result["replay_ok"] is True
