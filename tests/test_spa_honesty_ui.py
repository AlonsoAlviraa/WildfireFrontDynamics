"""Agent A honesty UI: H1 eng rehearsal, SR ladder, decision-log read path."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.spa_honesty_ui import (
    SR_NON_CLAIMS,
    build_h1_eng_rehearsal,
    build_sr_ladder,
    load_decision_log_surface,
)

ROOT = Path(__file__).resolve().parents[1]


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


def test_decision_log_stub_and_sidecar(tmp_path: Path):
    stub = load_decision_log_surface(
        work_dir=None, decision_card={"decision": "HOLD", "event_id": "E1"}
    )
    assert stub["mode"] == "stub"
    assert stub["go_q_met"] is False
    assert stub["ack_ui_only"] is True
    assert stub["field_ops_ml_live_fusion"] == "OFF"
    assert stub["id"] == "E1"

    wd = tmp_path / "inc"
    out = wd / "outbox"
    out.mkdir(parents=True)
    (out / "decision_log.json").write_text(
        json.dumps({"id": "log-99", "decision": "ABSTAIN", "ack": "pending"}),
        encoding="utf-8",
    )
    side = load_decision_log_surface(
        work_dir=wd,
        decision_card={"decision": "HOLD", "event_id": "E1"},
    )
    assert side["mode"] == "sidecar_read"
    assert side["id"] == "log-99"
    assert side["go_q_met"] is False
    assert side["path_rel"] == "outbox/decision_log.json"


def test_payload_embeds_a6_a7_a8_and_html_markers():
    payload = build_product_app_payload(live=False, scan=False)
    assert payload["h1_eng_rehearsal"]["go_q_met"] is False
    assert payload["h1_eng_rehearsal"]["marker"] == "h1-rehearsal"
    assert payload["sr_ladder"]["marker"] == "sr-ladder"
    assert payload["sr_ladder"]["field_ops_ml_live_fusion"] == "OFF"
    assert payload["decision_log"]["go_q_met"] is False
    assert str(payload["rails"]["field_ops_ml_live_fusion"]).upper() == "OFF"
    assert payload["rails"]["go_q_invent_forbidden"] is True

    html = render_product_app_html(payload)
    assert 'data-marker="h1-rehearsal"' in html
    assert 'data-marker="sr-ladder"' in html
    assert "go_q_met" in html
    assert "Claims Guardian" in html or "sr-claims" in html
    assert "fusion OFF" in html
    assert "liveUnavailableFallback" in html
