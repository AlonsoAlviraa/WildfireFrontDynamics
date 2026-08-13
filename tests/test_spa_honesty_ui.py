"""Agent A honesty UI: uncertainty bar, H1 eng, SR ladder, decision-log."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.spa_honesty_ui import (
    SPLIT_CONF_BANNER,
    SR_NON_CLAIMS,
    UNCERTAINTY_BAR_LABEL,
    UNCERTAINTY_BAR_NOTE,
    build_h1_eng_rehearsal,
    build_split_conf_view,
    build_sr_ladder,
    build_uncertainty_bar_view,
    load_decision_log_surface,
    load_vv_scorecard_surface,
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
    assert empty["field_ops_ml_live_fusion"] == "ON"
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


def test_sr_ladder_non_claims_and_fusion_on():
    ladder = build_sr_ladder(decision="ABSTAIN")
    assert ladder["marker"] == "sr-ladder"
    assert ladder["active_id"] == "S0"
    assert ladder["field_ops_ml_live_fusion"] == "ON"
    assert ladder["go_q_invent_forbidden"] is True
    ids = {lv["id"] for lv in ladder["levels"]}
    assert ids == {"S0", "S1", "S2", "S3"}
    for claim in SR_NON_CLAIMS:
        assert claim in ladder["non_claims"]
    guardian = ladder["claims_guardian"]
    assert "fusion ON ≠ GO_Q complete ≠ despacho" in guardian
    assert "go_q_met=false" in guardian
    assert "ABSTAIN/HOLD" in guardian
    assert "no fusion ON" not in guardian
    assert "field GO" in guardian or "field GO" in " ".join(ladder["non_claims"])

    hold = build_sr_ladder(decision="HOLD")
    assert hold["active_id"] == "S1"
    # Card GO still must not sell field GO / GO_Q
    go = build_sr_ladder(decision="GO")
    assert go["active_id"] == "S2"
    assert "GO_Q" in go["note"] or "fusion ON" in go["note"]


def test_h1_eng_rehearsal_never_sets_go_q_met():
    block = build_h1_eng_rehearsal(repo_root=ROOT, live_ops_enabled=False)
    assert block["marker"] == "h1-rehearsal"
    assert block["go_q_met"] is False
    assert block["product_unlock"] is False
    assert block["field_ops_ml_live_fusion"] == "ON"
    assert block["go_q_invent_forbidden"] is True
    assert block["eng_only"] is True
    assert block["not_third_party_acta"] is True
    assert "serve" in block["serve_cmd"]
    assert "demo-day" in block["demo_day_cmd"]
    assert any(
        "GO_Q" in s.get("detail", "") or "Rails" in s.get("title", "") for s in block["steps"]
    )
    nc = " ".join(block["non_claims"])
    assert "go_q_met=false" in nc
    assert "fusion ON ≠ GO_Q complete ≠ despacho" in nc
    assert "ABSTAIN/HOLD" in nc
    assert "No fusion ON" not in nc


def test_split_conf_ml_neq_ros_no_invent():
    """Mes2 PR3-A: split conf from existing fields; missing ops → sin conf ROS."""
    empty = build_split_conf_view()
    assert empty["marker"] == "split-conf"
    assert empty["ml_neq_ros"] is True
    assert empty["iou_is_not_ros"] is True
    assert empty["invents_scores"] is False
    assert empty["field_ops_ml_live_fusion"] == "ON"
    assert empty["go_q_invent_forbidden"] is True
    assert empty["go_q_met"] is False
    assert empty["banner"] == SPLIT_CONF_BANNER
    assert empty["ros"]["empty"] is True
    assert "sin conf ROS" in empty["ros"]["display"]
    assert empty["ml"]["is_ros"] is False
    assert empty["ml"]["confidence_pred"] is None

    mid = build_split_conf_view(confidence_pred=0.42, confidence_label="LOW")
    assert mid["ml"]["confidence_pred"] == 0.42
    assert "42%" in mid["ml"]["display"]
    assert mid["ros"]["empty"] is True

    with_ops = build_split_conf_view(
        confidence_pred=0.7,
        ops_metrics={"quality_grade": "A"},
    )
    assert with_ops["ros"]["empty"] is False
    assert "grade A" in with_ops["ros"]["display"]
    assert "no ML" in with_ops["ros"]["display"]
    assert with_ops["ml"]["is_ros"] is False

    with_ros = build_split_conf_view(
        confidence_pred=0.5,
        ops_metrics={"ros_confidence": 0.8},
    )
    assert with_ros["ros"]["ros_confidence"] == 0.8
    assert "80%" in with_ros["ros"]["display"]
    assert with_ros["invents_scores"] is False


def test_decision_log_empty_no_invented_id():
    """Without work_dir / without jsonl: honest stub — no invented decision_id."""
    stub = load_decision_log_surface(
        work_dir=None, decision_card={"decision": "HOLD", "event_id": "E1"}
    )
    assert stub["mode"] == "stub"
    assert stub["go_q_met"] is False
    assert stub["ack_ui_only"] is True
    assert stub["field_ops_ml_live_fusion"] == "ON"
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
    from wildfire_front.product.decide_service import decide_from_request
    from wildfire_front.product.decision_log import append_decision

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
    assert side["field_ops_ml_live_fusion"] == "ON"
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


def test_vv_scorecard_empty_no_invented_field_scores():
    """Mes3 W1-A: no work_dir / missing file → honest empty, null field metrics."""
    stub = load_vv_scorecard_surface(work_dir=None)
    assert stub["marker"] == "vv-scorecard"
    assert stub["mode"] == "sin_sidecar"
    assert stub["go_q_met"] is False
    assert stub["field_ops_ml_live_fusion"] == "ON"
    assert stub["field_iou"] is None
    assert stub["field_ros"] is None
    assert stub["field_grade"] is None
    assert stub["metrics_field_null"] is True
    assert stub["invents_field_scores"] is False
    assert "sin sidecar" in stub["note"].lower()


def test_vv_scorecard_reads_real_sidecar(tmp_path: Path):
    """Drive shipped write_vv_scorecard → SPA surface is read-only eng_stub."""
    from wildfire_front.product.vv_sidecar import write_vv_scorecard

    work = tmp_path / "inc_vv"
    work.mkdir()
    write_vv_scorecard(work, base=tmp_path, include_repo_root=False, event_id="IF_VV")
    side = load_vv_scorecard_surface(
        work_dir=work, base=tmp_path, include_repo_root=False
    )
    assert side["mode"] == "sidecar_read"
    assert side["path_rel"] == "vv_scorecard.json"
    assert side["eng_stub"] is True
    assert side["event_id"] == "IF_VV"
    assert side["go_q_met"] is False
    assert side["go_q"] == "partial"
    assert side["field_ops_fusion"] == "ON"
    assert side["field_iou"] is None
    assert side["field_ros"] is None
    assert side["field_grade"] is None
    assert side["invents_field_scores"] is False

    empty_wd = tmp_path / "inc_no_vv"
    empty_wd.mkdir()
    missing = load_vv_scorecard_surface(
        work_dir=empty_wd, base=tmp_path, include_repo_root=False
    )
    assert missing["mode"] == "sin_sidecar"
    assert missing["field_iou"] is None


def test_payload_embeds_uncertainty_bar_and_a6_a7_a8_html_markers():
    payload = build_product_app_payload(live=False, scan=False)
    ub = payload["uncertainty_bar"]
    assert ub["marker"] == "uncertainty-bar"
    assert ub["field_ops_ml_live_fusion"] == "ON"
    assert ub["go_q_invent_forbidden"] is True
    assert ub["invents_scores"] is False
    assert ub["is_ros"] is False
    assert "no es ROS" in ub["note"]
    assert ub["source"] == "existing_confidence_pred_only"

    assert payload["h1_eng_rehearsal"]["go_q_met"] is False
    assert payload["h1_eng_rehearsal"]["marker"] == "h1-rehearsal"
    assert payload["h1_eng_rehearsal"]["not_third_party_acta"] is True
    sc = payload["split_conf"]
    assert sc["marker"] == "split-conf"
    assert sc["ml_neq_ros"] is True
    assert sc["field_ops_ml_live_fusion"] == "ON"
    assert sc["go_q_met"] is False
    assert "Conf. ML ≠ Conf. ROS" in sc["banner"]
    assert payload["sr_ladder"]["marker"] == "sr-ladder"
    assert payload["sr_ladder"]["field_ops_ml_live_fusion"] == "ON"
    assert payload["decision_log"]["go_q_met"] is False
    assert payload["decision_log"]["marker"] == "decision-log"
    vv = payload["vv_scorecard"]
    assert vv["marker"] == "vv-scorecard"
    assert vv["go_q_met"] is False
    assert vv["field_iou"] is None
    assert vv["field_ros"] is None
    assert vv["invents_field_scores"] is False
    assert str(payload["rails"]["field_ops_ml_live_fusion"]).upper() == "ON"
    assert payload["rails"]["go_q_invent_forbidden"] is True
    assert payload["live_ops"]["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    assert payload["live_ops"]["honesty_rails"]["go_q_met"] is False
    assert "Fusion OFF" not in (payload["live_ops"].get("note") or "")

    html = render_product_app_html(payload)
    assert 'id="uncertainty-bar"' in html or 'data-marker="uncertainty-bar"' in html
    assert "no es ROS" in html
    assert "IoU" in html and "ROS" in html
    assert 'data-marker="uncertainty-no-ros"' in html
    assert "uncertainty_bar" in html or "uncertaintyBar" in html
    assert 'data-marker="h1-rehearsal"' in html
    assert "no es acta H1" in html
    assert "btn-h1-copy-cmd" in html
    assert 'data-marker="sr-ladder"' in html
    assert 'data-marker="decision-log"' in html
    assert 'data-marker="vv-scorecard"' in html
    assert "paintVvScorecard" in html
    assert 'data-marker="weakness-board"' in html
    assert "paintWeaknessBoard" in html
    assert payload["weakness_board"]["marker"] == "weakness-board"
    assert payload["weakness_board"]["go_q_met"] is False
    assert payload["weakness_board"]["invents_counts"] is False
    assert "eng_stub" in html
    assert 'data-marker="split-conf"' in html
    assert 'data-marker="split-conf-ml"' in html
    assert 'data-marker="split-conf-ros"' in html
    assert "Conf. ML ≠ Conf. ROS" in html
    assert "no es despacho táctico" in html
    assert "runDlogAck" in html or "ack_decision" in html
    assert "go_q_met" in html
    assert "Claims Guardian" in html or "sr-claims" in html
    assert "fusion ON" in html
    assert "fusion ON ≠ GO_Q" in html
    assert "addTop('Fusion OFF'" not in html
    assert "fusionRailOn" in html
    assert "orientación de card" in html
    assert "no es GO_Q" in html
    assert "decision-honest" in html
    assert '"field_ops_ml_live_fusion": "ON"' in html
    assert "go_q_invent_forbidden" in html
    assert "liveUnavailableFallback" in html


def test_payload_reads_real_sidecar_and_html_marker(tmp_path: Path):
    """Product payload path: real append → build_product_app_payload decision_log."""
    from wildfire_front.product.decide_service import decide_from_request
    from wildfire_front.product.decision_log import append_decision

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
