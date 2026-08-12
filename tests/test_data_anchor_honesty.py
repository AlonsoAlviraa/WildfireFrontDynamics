"""Agent B — data anchor honesty (Hellín pending, no silent promote)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHORS = ROOT / "data" / "infocam_anchors.json"
SSOT_MD = ROOT / "docs" / "DATA_ANCHOR_SSOT.md"
INTAKE_MD = ROOT / "docs" / "DATA_INTAKE_STATUS.md"
CURRENT_STATE = ROOT / "docs" / "CURRENT_STATE.md"


def _anchors() -> dict:
    assert ANCHORS.is_file(), "data/infocam_anchors.json missing"
    return json.loads(ANCHORS.read_text(encoding="utf-8"))


def test_only_tobarra_confirmed_for_o1():
    doc = _anchors()
    confirmed = [
        fid
        for fid, row in doc["anchors"].items()
        if str(row.get("status", "")).lower() == "confirmed"
    ]
    assert confirmed == ["tobarra_20240802"], confirmed
    tb = doc["anchors"]["tobarra_20240802"]
    assert tb.get("vp_m_min") == 7.0
    assert tb.get("area_ha") == 39.0
    assert tb.get("source")


def test_hellin_stays_pending_external_without_vp():
    doc = _anchors()
    h = doc["anchors"]["hellin_2024"]
    assert h["status"] == "pending_external"
    assert h.get("vp_m_min") is None
    assert h.get("area_ha") is None
    assert not h.get("source")


def test_pending_anchors_have_no_numeric_go_values():
    doc = _anchors()
    for fid, row in doc["anchors"].items():
        if str(row.get("status", "")).lower() != "pending_external":
            continue
        assert row.get("vp_m_min") in (None, ""), f"{fid} has vp while pending"
        assert row.get("area_ha") in (None, ""), f"{fid} has ha while pending"


def test_ssot_doc_blocks_silent_hellin_promote():
    text = SSOT_MD.read_text(encoding="utf-8")
    assert "pending_external" in text
    assert "hellin_2024" in text.lower() or "Hellín" in text
    assert "cite" in text.lower()
    assert "promote" in text.lower()
    # Checklist gates must be explicit
    assert "Literal cite" in text or "literal cite" in text.lower()
    assert "Do not invent" in text or "do not invent" in text.lower()


def test_data_intake_and_current_state_keep_hellin_pending_narrative():
    intake = INTAKE_MD.read_text(encoding="utf-8")
    assert "pending_external" in intake
    assert "Hellín" in intake or "hellin" in intake.lower()
    # Must not claim Hellín confirmed in the honesty banner era
    assert "Hellín confirmed" not in intake
    cs = CURRENT_STATE.read_text(encoding="utf-8")
    assert "pending_external" in cs or "Hellín" in cs
    assert "**GO_Q** | **partial**" in cs or "GO_Q partial" in cs
