"""Tests for release flags SSOT checker (Agent B owns)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys_path_insert = str(ROOT / "scripts")

if sys_path_insert not in sys.path:
    sys.path.insert(0, sys_path_insert)

from check_release_flags import _go_q_stamp_ok, evaluate  # noqa: E402


def test_live_repo_flags_pass():
    """Live authority files must be self-consistent after B alignment."""
    report = evaluate()
    assert report.get("exit_code") == 0, report
    assert report["status"] == "PASS"
    assert report["n_fail"] == 0
    by_id = {c["id"]: c for c in report["checks"]}
    for required in (
        "field_ops_fusion_on",
        "go_q_stamp_not_complete",
        "go_q_current_state_partial",
        "go_mes_plus_false",
        "tobarra_keep_reopen_false",
        "no_cite_no_promote",
    ):
        assert required in by_id, required
        assert by_id[required]["ok"], by_id[required]


def test_stamp_schema_keys_exist():
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    if not stamp_path.is_file():
        pytest.skip("stamp missing")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert "ml_product_go" in stamp
    assert "field_ops_allow_ml_live_in_fusion" in stamp
    assert stamp.get("field_ops_allow_ml_live_in_fusion") is True
    assert stamp.get("GO_Q") == "partial"
    assert stamp.get("GO_MES") is True
    assert stamp.get("GO_MES_plus") is False
    assert (stamp.get("rails") or {}).get("tobarra_keep_reopen") is False


def test_current_state_go_q_partial_token():
    md = (ROOT / "docs" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    assert "| **GO_Q** | **partial** |" in md
    assert "| **field_ops ML fusion** | **ON** |" in md
    assert "| **GO_MES+** | **false** |" in md


def test_go_q_stamp_helper_rejects_complete():
    assert _go_q_stamp_ok("partial") is True
    assert _go_q_stamp_ok(False) is True
    assert _go_q_stamp_ok("true") is False
    assert _go_q_stamp_ok(True) is False
    assert _go_q_stamp_ok("complete") is False
    assert _go_q_stamp_ok("full") is False


def test_evaluate_fails_when_go_q_true(tmp_path: Path):
    """Synthetic stamp with GO_Q true must hard-fail (never invent complete)."""
    stamp = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    stamp["GO_Q"] = "true"
    st = tmp_path / "stamp.json"
    st.write_text(json.dumps(stamp), encoding="utf-8")
    cs = ROOT / "docs" / "CURRENT_STATE.md"
    report = evaluate(current_state_path=cs, stamp_path=st)
    assert report["exit_code"] == 1
    assert report["status"] == "FAIL"
    goq = next(c for c in report["checks"] if c["id"] == "go_q_stamp_not_complete")
    assert goq["ok"] is False


def test_evaluate_fails_when_fusion_off(tmp_path: Path):
    stamp = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    stamp["field_ops_allow_ml_live_in_fusion"] = False
    stamp["rails"] = {**(stamp.get("rails") or {}), "field_ops_fusion": "OFF"}
    st = tmp_path / "stamp.json"
    st.write_text(json.dumps(stamp), encoding="utf-8")
    report = evaluate(current_state_path=ROOT / "docs" / "CURRENT_STATE.md", stamp_path=st)
    assert report["exit_code"] == 1
    fusion = next(c for c in report["checks"] if c["id"] == "field_ops_fusion_on")
    assert fusion["ok"] is False
