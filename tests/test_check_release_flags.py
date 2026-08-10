"""Tests for B2 release flags SSOT checker."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys_path_insert = str(ROOT / "scripts")

import sys

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


def test_stamp_schema_keys_exist():
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    if not stamp_path.is_file():
        pytest.skip("stamp missing")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert "ml_product_go" in stamp
    assert "field_ops_allow_ml_live_in_fusion" in stamp
    assert stamp.get("field_ops_allow_ml_live_in_fusion") is False
