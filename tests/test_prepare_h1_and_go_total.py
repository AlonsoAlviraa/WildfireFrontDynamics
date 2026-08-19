"""H1 session prep + GO_TOTAL: eng-ready, GO_Q stays partial without acta."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_h1_demo_session import (  # noqa: E402
    _pack_ok,
    write_go_total_status,
)


def test_live_pack_and_reliability_exist():
    ok, missing = _pack_ok()
    if not ok:
        pytest.skip(f"generated H1 pack is not distributed: {missing}")
    rel = ROOT / "docs" / "RELIABILITY_GATE_REPORT_THIRD_PARTY.md"
    assert rel.is_file()
    assert "does **not** close go_q" in rel.read_text(encoding="utf-8").lower()


def test_live_stamp_has_no_forged_h1_acta():
    stamp = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    assert stamp.get("GO_Q") == "partial"
    assert not stamp.get("h1_acta")
    actas = ROOT / "docs" / "actas"
    real = [p for p in actas.glob("ACTA_DEMO_*.md") if "PENDING" not in p.name.upper()]
    assert real == []


def test_write_go_total_status_met_false_without_acta(tmp_path: Path, monkeypatch):
    dest = tmp_path / "GO_TOTAL_STATUS.json"
    import prepare_h1_demo_session as prep

    monkeypatch.setattr(prep, "GO_TOTAL", dest)
    from datetime import UTC, datetime

    payload = write_go_total_status(
        now=datetime.now(UTC),
        eng_ready=True,
        pack_step={"ok": True},
        rel_step={"ok": True},
        refuse_verified=True,
    )
    assert dest.is_file()
    assert payload["met"] is False
    assert payload["go_total"] is False
    assert payload["go_q"]["met"] is False
    assert payload["go_q"]["status"] == "partial"
    assert payload["remaining_human_steps"]
    assert all(s.get("owner") == "human" for s in payload["remaining_human_steps"])
    cmds = "\n".join(payload["human_commands"])
    assert "record_h1_demo_complete.py" in cmds
    assert "ACTA_DEMO_YYYYMMDD_<org>.md" in cmds
    assert payload["eng_closable"]["prepare_h1_demo_session"] is True
    assert payload["eng_closable"]["check_release_flags_complete_only_with_h1_acta"] is True
    blockers = payload["inventory"]["blockers"]
    human_go_total = [
        b for b in blockers if b.get("owner") == "human" and "GO_TOTAL" in (b.get("blocks") or [])
    ]
    assert human_go_total
    assert all(b["status"] == "open" for b in human_go_total)
    stretch = [b for b in blockers if b.get("blocks_go_total") is False]
    assert stretch


def test_live_go_total_status_honest_if_present():
    path = ROOT / "docs" / "GO_TOTAL_STATUS.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("met") is False
    assert data.get("go_total") is False
    assert data.get("go_q", {}).get("met") is False
    assert data.get("go_q", {}).get("status") == "partial"
    assert data.get("remaining_human_steps")
    assert all(s.get("owner") == "human" for s in data["remaining_human_steps"])
    assert data.get("gates", {}).get("field_ops_fusion") == "ON"
    assert data.get("gates", {}).get("GO_MES_plus") is False
    h1 = data.get("h1_slot") or {}
    assert h1.get("status") in {"not_booked", "booked_human_open", "done"}
    # Eng default truth until Alonso books: not inventing booked without human
    if h1.get("status") == "done":
        assert data.get("go_q", {}).get("h1_acta")  # done only with evidence path


def test_live_session_go_q_met_false_fusion_on():
    path = ROOT / "docs" / "H1_DEMO_SESSION_READY.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("go_q_met") is False
    assert data.get("product_unlock") is False
    assert data.get("rails", {}).get("field_ops_fusion") == "ON"
    assert data.get("rails", {}).get("GO_Q") == "partial"
    assert data.get("h1_slot") in {"not_booked", "booked_human_open", "done"}


def test_write_go_total_never_sets_met_true_without_acta_field(tmp_path: Path, monkeypatch):
    """Anti-invent: writer always leaves met/go_total false (record_h1 owns complete)."""
    dest = tmp_path / "GO_TOTAL_STATUS.json"
    import prepare_h1_demo_session as prep

    monkeypatch.setattr(prep, "GO_TOTAL", dest)
    from datetime import UTC, datetime

    payload = write_go_total_status(
        now=datetime.now(UTC),
        eng_ready=True,
        pack_step={"ok": True},
        rel_step={"ok": True},
        refuse_verified=True,
        h1_slot="not_booked",
    )
    assert payload["met"] is False
    assert payload["go_total"] is False
    assert payload["go_q"]["h1_acta"] is None
    assert payload["h1_slot"]["status"] == "not_booked"
    assert payload["gates"]["GO_Q"] == "partial"
    assert "prepare_h1_demo_session" in payload["eng_closable"]


def test_pack_ok_missing_dir(tmp_path: Path, monkeypatch):
    import prepare_h1_demo_session as prep

    monkeypatch.setattr(prep, "DEMO_PACK", tmp_path / "missing_pack")
    ok, missing = _pack_ok()
    assert ok is False
    assert missing
