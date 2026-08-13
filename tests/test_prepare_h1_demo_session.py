"""H1 session prepare must snapshot stamp fusion; never close GO_Q."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prepare_h1_demo_session as prep  # noqa: E402

STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"


def _stamp_fusion() -> str | None:
    if not STAMP.is_file():
        return None
    stamp = json.loads(STAMP.read_text(encoding="utf-8"))
    if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
        return "ON"
    rails = stamp.get("rails") or {}
    raw = rails.get("field_ops_fusion")
    return str(raw).upper() if raw is not None else "OFF"


def test_skip_dry_run_snapshots_stamp_fusion_not_hardcoded_off(tmp_path: Path, monkeypatch):
    """--skip-dry-run must write stamp fusion (ON), not a hardcoded OFF."""
    expected = _stamp_fusion()
    if expected is None:
        pytest.skip("ML product stamp missing — cannot snapshot fusion")

    out_json = tmp_path / "H1_DEMO_SESSION_READY.json"
    invite = tmp_path / "H1_CALENDAR_INVITE.md"
    monkeypatch.setattr(prep, "OUT_JSON", out_json)
    monkeypatch.setattr(prep, "INVITE_MD", invite)

    code = prep.main(["--skip-dry-run"])
    assert code in (0, 1)
    assert out_json.is_file()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["go_q_met"] is False
    assert payload.get("product_unlock") is False
    rails = payload.get("rails") or {}
    assert rails.get("field_ops_fusion") == expected
    assert rails.get("GO_Q") == "partial"
    assert rails.get("field_ops_fusion") != "OFF" or expected == "OFF"
    if expected == "ON":
        assert "OFF" not in str(rails.get("field_ops_fusion"))

    assert invite.is_file()
    text = invite.read_text(encoding="utf-8")
    assert "No field_ops ML live fusion ON" not in text
    if expected == "ON":
        assert "fusion OFF" not in text
        assert "fusion **OFF**" not in text
        assert "fusion ON" in text or "fusion **ON**" in text
    assert "go_q_met" not in text.lower() or "false" in text.lower()


def test_invite_builder_uses_stamp_fusion_rail():
    expected = _stamp_fusion()
    if expected is None:
        pytest.skip("ML product stamp missing")
    md = prep.build_invite_md(when_hint="test-slot", fusion=expected)
    assert "No field_ops ML live fusion ON" not in md
    if expected == "ON":
        assert "fusion **OFF**" not in md
        assert "fusion **ON**" in md or "fusion ON" in md
        assert "GO_Q" in md
        assert "despacho" in md.lower() or "GO_Q" in md
