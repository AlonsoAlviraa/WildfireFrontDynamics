"""ML LEAP D0/E1 docs — request pack + Hellín H1–H7 + no silent promote."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "docs" / "ML_LEAP_REQUEST_DATA.md"
EVAL = ROOT / "docs" / "ML_LEAP_EVAL_ONESHOT.md"
ANCHORS = ROOT / "data" / "infocam_anchors.json"
SSOT = ROOT / "docs" / "DATA_ANCHOR_SSOT.md"


def test_request_data_pack_lists_p0_and_h_gates():
    assert REQ.is_file()
    text = REQ.read_text(encoding="utf-8")
    assert "P0-1" in text and "P0-2" in text and "P0-3" in text
    assert "P1-1" in text
    for hid in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        assert hid in text, hid
    assert "hellin_2024" in text
    assert "pending_external" in text
    assert "FREEZE" in text or "retrain" in text.lower()
    assert "confirmed" in text.lower()


def test_hellin_still_pending_after_d0_docs():
    doc = json.loads(ANCHORS.read_text(encoding="utf-8"))
    h = doc["anchors"]["hellin_2024"]
    assert h["status"] == "pending_external"
    assert h.get("vp_m_min") is None
    confirmed = [k for k, v in doc["anchors"].items() if v.get("status") == "confirmed"]
    assert confirmed == ["tobarra_20240802"]


def test_ssot_has_h1_h7_ids():
    text = SSOT.read_text(encoding="utf-8")
    for hid in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        assert hid in text, hid


def test_eval_oneshot_forbids_test_cal_overwrite():
    assert EVAL.is_file()
    text = EVAL.read_text(encoding="utf-8")
    assert "eval_ml_uncertainty_u1" in text
    assert "--split test" in text
    assert "uncertainty_calibration_v1.json" in text
    assert "validate_ml_scorecard" in text
    assert "Do not overwrite" in text or "do not overwrite" in text.lower()
    assert "SKIP" in text
    assert "fusion" in text.lower()
