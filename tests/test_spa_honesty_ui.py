"""Agent A honesty UI: uncertainty bar, H1 eng, SR ladder, decision-log."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.spa_honesty_ui import (
    SR_NON_CLAIMS,
    UNCERTAINTY_BAR_LABEL,
    UNCERTAINTY_BAR_NOTE,
    build_h1_eng_rehearsal,
    build_sr_ladder,
    build_uncertainty_bar_view,
    load_decision_log_surface,
)

ROOT = Path(__file__).resolve().parents[1]


def test_uncertainty_bar_conf_only_no_invented_scores():
    """Mes2 PR1-A: bar from existing conf only; empty → sin conf; rails OFF."""
    empty = build_uncertainty_bar_view()
    assert empty["marker"] == "uncertainty-bar"
    assert empty["empty"] is True
    assert empty["fill_pct"] == 0
    assert empty["band"] == "sin conf"
    assert empty["confidence_pred"] is None
    assert empty["invents_scores"] is False
    assert empty["is_ros"] is False
    assert empty["field_ops_ml_live_fusion"] == "OFF"
    assert empty["go_q_invent_forbidden"] is True
    assert "no es ROS" in empty["note"]
    assert empty["note"] == UNCERTAINTY_BAR_NOTE
    assert empty["label"] == UNCERTAINTY_BAR_LABEL

    mid = build_uncertainty_bar_view(confidence_pred=0.55)
    assert mid["empty"] is False
    assert mid["confidence_pred"] == 0.55
    assert mid["fill_pct"] == 55
    assert mid["band"] == "media"
    assert mid["is_ros"] is False

    labeled = build_uncertainty_bar_view(confidence_pred=0.9, confidence_label="HIGH")
    assert labeled["band"] == "HIGH"
    assert labeled["fill_pct"] == 90

    # Clamp + reject non-finite
    hi = build_uncertainty_bar_view(confidence_pred=1.7)
    assert hi["confidence_pred"] == 1.0
    assert hi["fill_pct"] == 100
    bad = build_uncertainty_bar_view(confidence_pred="nope")  # type: ignore[arg-type]
    assert bad["empty"] is True
    assert bad["band"] == "sin conf"


def test_sr_ladder_non_claims_and_fusion_off():
    ladder = build_sr_ladder(decision="ABSTAIN")
    assert ladder["marker"] == "sr-ladder"
    assert ladder["active_id"] == "S0"
    assert ladder["field_ops_ml_live_fusion"] == "OFF"
    assert ladder["go_q_invent_forbidden"] is True
    ids = {lv["id"] for lv in ladder["levels"]}
    assert ids == {"S0", "S1", "S2", "S3"}
    for claim in SR_NON_CLAIMS:
        assert claim in ladder["non_claims"]
    assert "field GO" in ladder["claims_guardian"] or "field GO" in " ".join(ladder["non_claims"])

    hold = build_sr_ladder(decision="HOLD")
    assert hold["active_id"] == "S1"
    # Card GO still must not sell field GO (clamped)
    go = build_sr_ladder(decision="GO")
    assert go["active_id"] == "S2"
    assert "field GO" in go["note"] or "fusion OFF" in go["note"]


def test_h1_eng_rehearsal_never_sets_go_q_met():
    block = build_h1_eng_rehearsal(repo_root=ROOT, live_ops_enabled=False)
    assert block["marker"] == "h1-rehearsal"
    assert block["go_q_met"] is False
    assert block["product_unlock"] is False
    assert block["field_ops_ml_live_fusion"] == "OFF"
    assert "serve" in block["serve_cmd"]
    assert "demo-day" in block["demo_day_cmd"]
    assert any(
        "GO_Q" in s.get("detail", "") or "Rails" in s.get("title", "") for s in block["steps"]
    )


def test_decision_log_empty_no_invented_id():
    """Without work_dir / without jsonl: honest stub — no invented decision_id."""
    stub = load_decision_log_surface(
        work_dir=None, decision_card={"decision": "HOLD", "event_id": "E1"}
    )
    assert stub["mode"] == "stub"
    assert stub["go_q_met"] is False
    assert stub["ack_ui_only"] is True
    assert stub["field_ops_ml_live_fusion"] == "OFF"
    assert stub["id"] is None
    assert stub["decision_id"] is None
    assert stub["acked"] is False
    assert stub["ack"] is None
    assert "sin sidecar" in stub["note"].lower() or "Sin sidecar" in stub["note"]
    # Card decision may appear as context only
    assert stub["decision"] == "HOLD"

    empty = load_decision_log_surface(
        work_dir=None,
        decision_card=None,
    )
    assert empty["mode"] == "stub"
    assert empty["decision_id"] is None


def test_decision_log_real_sidecar_via_append(tmp_path: Path):
    """Drive real #31 append_decision → SPA surface reads decision_log.jsonl."""
    from wildfire_front.product.decision_log import append_decision
    from wildfire_front.product.decide_service import decide_from_request

    work = tmp_path / "inc_real"
    work.mkdir()
    card = decide_from_request(
        {
            "event_id": "IF_SPA_LOG",
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
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    side = load_decision_log_surface(
        work_dir=work,
        decision_card={"decision": "HOLD", "event_id": "E1"},
        base=tmp_path,
        include_repo_root=False,
    )
    assert side["mode"] == "sidecar_read"
    assert side["decision_id"] == entry["decision_id"]
    assert side["id"] == entry["decision_id"]
    assert side["decision"] == entry["decision"]
    assert side["confidence_pred"] == entry["confidence_pred"]
    assert side["path_rel"] == "decision_log.jsonl"
    assert side["go_q_met"] is False
    assert side["field_ops_ml_live_fusion"] == "OFF"
    assert side["acked"] is False
    assert side["ack_ui_only"] is False
    assert side["n_entries"] == 1

    # Wrong-path outbox JSON alone must not invent a sidecar read
    empty_wd = tmp_path / "inc_outbox_only"
    out = empty_wd / "outbox"
    out.mkdir(parents=True)
    (out / "decision_log.json").write_text(
        json.dumps({"id": "fake-99", "decision": "ABSTAIN"}),
        encoding="utf-8",
    )
    not_side = load_decision_log_surface(
        work_dir=empty_wd,
        base=tmp_path,
        include_repo_root=False,
    )
    assert not_side["mode"] == "stub"
    assert not_side["decision_id"] is None


def test_payload_embeds_uncertainty_bar_and_a6_a7_a8_html_markers():
    payload = build_product_app_payload(live=False, scan=False)
    ub = payload["uncertainty_bar"]
    assert ub["marker"] == "uncertainty-bar"
    assert ub["field_ops_ml_live_fusion"] == "OFF"
    assert ub["go_q_invent_forbidden"] is True
    assert ub["invents_scores"] is False
    assert ub["is_ros"] is False
    assert "no es ROS" in ub["note"]
    assert ub["source"] == "existing_confidence_pred_only"

    assert payload["h1_eng_rehearsal"]["go_q_met"] is False
    assert payload["h1_eng_rehearsal"]["marker"] == "h1-rehearsal"
    assert payload["sr_ladder"]["marker"] == "sr-ladder"
    assert payload["sr_ladder"]["field_ops_ml_live_fusion"] == "OFF"
    assert payload["decision_log"]["go_q_met"] is False
    assert payload["decision_log"]["marker"] == "decision-log"
    assert str(payload["rails"]["field_ops_ml_live_fusion"]).upper() == "OFF"
    assert payload["rails"]["go_q_invent_forbidden"] is True

    html = render_product_app_html(payload)
    assert 'id="uncertainty-bar"' in html or 'data-marker="uncertainty-bar"' in html
    assert "no es ROS" in html
    assert "IoU" in html and "ROS" in html
    assert 'data-marker="uncertainty-no-ros"' in html
    assert "uncertainty_bar" in html or "uncertaintyBar" in html
    assert 'data-marker="h1-rehearsal"' in html
    assert 'data-marker="sr-ladder"' in html
    assert 'data-marker="decision-log"' in html
    assert "runDlogAck" in html or "ack_decision" in html
    assert "go_q_met" in html
    assert "Claims Guardian" in html or "sr-claims" in html
    assert "fusion OFF" in html
    assert '"field_ops_ml_live_fusion": "OFF"' in html
    assert "go_q_invent_forbidden" in html
    assert "liveUnavailableFallback" in html


def test_payload_reads_real_sidecar_and_html_marker(tmp_path: Path):
    """Product payload path: real append → build_product_app_payload decision_log."""
    from wildfire_front.product.decision_log import append_decision
    from wildfire_front.product.decide_service import decide_from_request

    # Place work_dir under repo so default allowlist works without custom base
    # Use tmp under REPO outputs-style via base=tmp and build surface helper assert;
    # full payload uses repo cwd — here we pin via load + render of custom surface.
    work = tmp_path / "wd_payload"
    work.mkdir()
    card = decide_from_request(
        {
            "event_id": "IF_PAYLOAD",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 4.0,
                "n_frames_staged": 8,
                "speed_vs_ref_ratio": 0.85,
            },
            "ml_metrics": {"test_iou": 0.8, "improvement_vs_copy_iou": 0.2},
            "channel": "pytest",
            "trust_client_reliability": True,
        }
    )
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    surface = load_decision_log_surface(
        work_dir=work, base=tmp_path, include_repo_root=False
    )
    payload = build_product_app_payload(live=False, scan=False)
    payload = {**payload, "decision_log": surface}
    html = render_product_app_html(payload)
    assert surface["mode"] == "sidecar_read"
    assert surface["decision_id"] == entry["decision_id"]
    assert entry["decision_id"] in html or surface["decision_id"] in html
    assert 'data-marker="decision-log"' in html
    assert payload["decision_log"]["go_q_met"] is False
