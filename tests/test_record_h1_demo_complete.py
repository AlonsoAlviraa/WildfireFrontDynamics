"""record_h1_demo_complete — refuse PENDING; SSOT only after valid acta."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from record_h1_demo_complete import record, validate_acta_fields  # noqa: E402


def _valid_acta_text() -> str:
    return "\n".join(
        [
            "# Acta demo",
            "",
            "| Campo | Valor |",
            "|-------|--------|",
            "| **Fecha** | 2026-08-10 |",
            "",
            "| Rol | Nombre | Organización |",
            "|-----|--------|--------------|",
            "| **Presentador** | Test Presenter | WFD |",
            "| **Tercero (externo)** | Test University Reviewer | Uni |",
            "",
        ]
    )


def test_validate_pending_draft_fails():
    draft = ROOT / "docs" / "actas" / "ACTA_DEMO_PENDING_HUMAN.md"
    if not draft.is_file():
        return
    parsed = validate_acta_fields(draft.read_text(encoding="utf-8"))
    assert parsed["ok"] is False


def test_record_refuses_pending_draft_no_mutation():
    draft = ROOT / "docs" / "actas" / "ACTA_DEMO_PENDING_HUMAN.md"
    stamp_before = (ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8")
    code, payload = record(acta_path=draft, status_path=ROOT / "docs" / "missing_plan.json")
    assert code == 2
    assert payload.get("go_q_met") is False
    stamp_after = (ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8")
    assert stamp_after == stamp_before
    assert json.loads(stamp_after).get("GO_Q") == "partial"


def test_record_updates_stamp_and_current_state_on_valid_acta(tmp_path: Path):
    acta = tmp_path / "ACTA_DEMO_20260810_uni.md"
    acta.write_text(_valid_acta_text(), encoding="utf-8")
    stamp_src = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    stamp_src["GO_Q"] = "partial"
    stamp_path = tmp_path / "ML_PRODUCT_GO_STATUS.json"
    stamp_path.write_text(json.dumps(stamp_src, indent=2), encoding="utf-8")
    cs_src = (ROOT / "docs" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    cs_path = tmp_path / "CURRENT_STATE.md"
    cs_path.write_text(cs_src, encoding="utf-8")
    sess_path = tmp_path / "H1_DEMO_SESSION_READY.json"
    sess_path.write_text(json.dumps({"go_q_met": False, "rails": {"GO_Q": "partial"}}), encoding="utf-8")
    status_path = tmp_path / "PLAN_1_MES_GRAPH_V6_STATUS.json"
    status_path.write_text(json.dumps({"gates": {}, "rails": {}, "tracks": {}}), encoding="utf-8")
    go_total_path = tmp_path / "GO_TOTAL_STATUS.json"
    go_total_path.write_text(
        json.dumps({"schema": "wfd_go_total_status_v1", "met": False, "go_q": {"met": False}}),
        encoding="utf-8",
    )
    live_go_total_before = None
    live_gt = ROOT / "docs" / "GO_TOTAL_STATUS.json"
    if live_gt.is_file():
        live_go_total_before = live_gt.read_text(encoding="utf-8")

    code, payload = record(
        acta_path=acta,
        status_path=status_path,
        stamp_path=stamp_path,
        current_state_path=cs_path,
        session_path=sess_path,
        go_total_path=go_total_path,
    )
    assert code == 0, payload
    assert payload.get("go_q_met") is True
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert stamp["GO_Q"] == "complete"
    assert stamp["h1_acta"]["tercero"] == "Test University Reviewer"
    assert stamp["h1_acta"]["fecha"] == "2026-08-10"
    assert stamp["h1_acta"]["presentador"] == "Test Presenter"
    md = cs_path.read_text(encoding="utf-8")
    assert "| **GO_Q** | **complete** |" in md
    sess = json.loads(sess_path.read_text(encoding="utf-8"))
    assert sess["go_q_met"] is True
    assert sess["product_unlock"] is False
    assert sess.get("go_total_met") is True
    plan = json.loads(status_path.read_text(encoding="utf-8"))
    assert plan["gates"]["GO_Q"]["met"] is True
    gt = json.loads(go_total_path.read_text(encoding="utf-8"))
    assert gt["met"] is True
    assert gt["go_q"]["met"] is True
    assert gt["remaining_human_steps"] == []
    assert gt["go_q"]["h1_acta"]["tercero"] == "Test University Reviewer"

    # Live repo must remain partial (tmp only).
    live = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    assert live.get("GO_Q") == "partial"
    if live_go_total_before is not None:
        assert live_gt.read_text(encoding="utf-8") == live_go_total_before


def test_record_dry_run_does_not_write(tmp_path: Path):
    acta = tmp_path / "ACTA_DEMO_20260810_uni.md"
    acta.write_text(_valid_acta_text(), encoding="utf-8")
    stamp_path = tmp_path / "ML_PRODUCT_GO_STATUS.json"
    stamp_path.write_text(
        (ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    before = stamp_path.read_text(encoding="utf-8")
    code, payload = record(
        acta_path=acta,
        status_path=tmp_path / "missing.json",
        dry_run=True,
        stamp_path=stamp_path,
        current_state_path=tmp_path / "no_cs.md",
        session_path=tmp_path / "no_sess.json",
    )
    assert code == 0
    assert payload.get("go_q_met") is True
    assert stamp_path.read_text(encoding="utf-8") == before


def test_record_missing_acta_exit2_no_mutation(tmp_path: Path):
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    stamp_before = stamp_path.read_text(encoding="utf-8")
    missing = tmp_path / "no_such_acta.md"
    code, payload = record(
        acta_path=missing,
        status_path=tmp_path / "plan.json",
        stamp_path=tmp_path / "stamp.json",
        current_state_path=tmp_path / "cs.md",
        session_path=tmp_path / "sess.json",
        go_total_path=tmp_path / "gt.json",
    )
    assert code == 2
    assert payload.get("go_q_met") is False
    assert "not found" in str(payload.get("error") or "").lower()
    assert stamp_path.read_text(encoding="utf-8") == stamp_before
    assert json.loads(stamp_before).get("GO_Q") == "partial"


def test_record_go_mes_false_go_q_complete_but_go_total_not_met(tmp_path: Path):
    """GO_TOTAL = GO_MES AND GO_Q complete — do not invent met when GO_MES false."""
    acta = tmp_path / "ACTA_DEMO_20260810_uni.md"
    acta.write_text(_valid_acta_text(), encoding="utf-8")
    stamp_src = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    stamp_src["GO_MES"] = False
    stamp_src["GO_Q"] = "partial"
    stamp_path = tmp_path / "ML_PRODUCT_GO_STATUS.json"
    stamp_path.write_text(json.dumps(stamp_src, indent=2), encoding="utf-8")
    go_total_path = tmp_path / "GO_TOTAL_STATUS.json"
    go_total_path.write_text(
        json.dumps({"schema": "wfd_go_total_status_v1", "met": False, "go_q": {"met": False}}),
        encoding="utf-8",
    )
    sess_path = tmp_path / "H1_DEMO_SESSION_READY.json"
    sess_path.write_text(json.dumps({"go_q_met": False}), encoding="utf-8")
    code, payload = record(
        acta_path=acta,
        status_path=tmp_path / "plan.json",
        stamp_path=stamp_path,
        current_state_path=tmp_path / "no_cs.md",
        session_path=sess_path,
        go_total_path=go_total_path,
    )
    assert code == 0, payload
    assert payload.get("go_q_met") is True
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert stamp["GO_Q"] == "complete"
    gt = json.loads(go_total_path.read_text(encoding="utf-8"))
    assert gt["go_q"]["met"] is True
    assert gt["met"] is False
    assert gt["go_total"] is False
    assert gt["gates"]["GO_MES"] is False
    assert gt["remaining_human_steps"]
    sess = json.loads(sess_path.read_text(encoding="utf-8"))
    assert sess["go_q_met"] is True
    assert sess.get("go_total_met") is False
