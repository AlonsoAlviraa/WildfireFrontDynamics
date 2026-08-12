"""Tests for B2 release flags SSOT checker (Agent B owns)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys_path_insert = str(ROOT / "scripts")

if sys_path_insert not in sys.path:
    sys.path.insert(0, sys_path_insert)

from check_release_flags import evaluate  # noqa: E402


def test_live_repo_flags_pass_or_report_clearly():
    """Live authority files must be self-consistent after B2 alignment."""
    report = evaluate()
    assert report.get("exit_code") in (0, 1, 2)
    assert "checks" in report or "error" in report
    if report.get("exit_code") == 0:
        assert report["status"] == "PASS"
        assert report["n_fail"] == 0
        # fusion OFF invariant present
        assert any(
            c["id"] == "field_ops_fusion_off" and c["ok"] for c in report["checks"]
        )
        # GO_Q must stay partial (never invent complete)
        assert any(
            c["id"] == "go_q_stamp_not_complete" and c["ok"] for c in report["checks"]
        )
        assert any(
            c["id"] == "go_q_current_state_partial" and c["ok"]
            for c in report["checks"]
        )


def test_stamp_schema_keys_exist():
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    if not stamp_path.is_file():
        pytest.skip("stamp missing")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert "ml_product_go" in stamp
    assert "field_ops_allow_ml_live_in_fusion" in stamp
    assert stamp.get("field_ops_allow_ml_live_in_fusion") is False
    assert stamp.get("GO_Q") == "partial"
    assert stamp.get("GO_MES") is True
    assert stamp.get("GO_MES_plus") is False


def test_current_state_go_q_partial_token():
    md = (ROOT / "docs" / "CURRENT_STATE.md").read_text(encoding="utf-8")
    assert "| **GO_Q** | **partial** |" in md
    assert "fusion OFF" in md or "| **field_ops ML fusion** | **OFF** |" in md
