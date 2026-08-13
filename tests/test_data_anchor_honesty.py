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
    assert doc.get("grade_a_requires_confirmed_anchor") is True


def test_confirmed_with_h1_zero_or_null_fields_cannot_promote():
    from wildfire_front.open_if.anchor_guard import can_promote_to_confirmed

    ok, reasons = can_promote_to_confirmed(
        {
            "fire_id": "hellin_2024",
            "vp_m_min": 50.0,
            "area_ha": 200.0,
            "source": "INFOCAM 2024 parte operativo",
            "H1": 0,
        }
    )
    assert ok is False
    assert any("h1_zero_no_cite" in r for r in reasons)

    ok_null, reasons_null = can_promote_to_confirmed(
        {
            "fire_id": "hellin_2024",
            "vp_m_min": None,
            "area_ha": None,
            "source": None,
        }
    )
    assert ok_null is False
    assert any("missing_vp_m_min" in r for r in reasons_null)
    assert any("missing_area_ha" in r for r in reasons_null)
    assert any("missing_source" in r for r in reasons_null)


def test_confirmed_anchors_require_numeric_and_source():
    """Schema honesty: confirmed rows must carry Vp/ha/source (no empty promote)."""
    doc = _anchors()
    for fid, row in doc["anchors"].items():
        if str(row.get("status", "")).lower() != "confirmed":
            continue
        assert isinstance(row.get("vp_m_min"), (int, float)), f"{fid} missing vp"
        assert isinstance(row.get("area_ha"), (int, float)), f"{fid} missing ha"
        assert float(row["vp_m_min"]) > 0, f"{fid} vp must be positive"
        assert float(row["area_ha"]) > 0, f"{fid} ha must be positive"
        assert str(row.get("source") or "").strip(), f"{fid} missing source"


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
    assert "FREEZE_ML" in text or "No ML retrain" in text


def test_data_intake_and_current_state_keep_hellin_pending_narrative():
    intake = INTAKE_MD.read_text(encoding="utf-8")
    assert "pending_external" in intake
    assert "Hellín" in intake or "hellin" in intake.lower()
    # Must not claim Hellín confirmed in the honesty banner era
    assert "Hellín confirmed" not in intake
    assert "cite" in intake.lower() or "DATA_ANCHOR_SSOT" in intake
    cs = CURRENT_STATE.read_text(encoding="utf-8")
    assert "pending_external" in cs or "Hellín" in cs
    assert "| **GO_Q** | **partial** |" in cs
