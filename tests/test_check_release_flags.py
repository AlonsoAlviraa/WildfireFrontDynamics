"""Tests for B2 release flags SSOT checker (+ SPA industrial gate PR10)."""

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
        assert any(c["id"] == "field_ops_fusion_off" and c["ok"] for c in report["checks"])
        # SPA industrial markers on source (PR10)
        assert any(
            c["id"] == "spa_industrial_markers_source" and c["ok"] for c in report["checks"]
        )
        # GO_Q not invented true
        assert any(c["id"] == "go_q_not_true_without_h1" and c["ok"] for c in report["checks"])


def test_stamp_schema_keys_exist():
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    if not stamp_path.is_file():
        pytest.skip("stamp missing")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert "ml_product_go" in stamp
    assert "field_ops_allow_ml_live_in_fusion" in stamp
    assert stamp.get("field_ops_allow_ml_live_in_fusion") is False


def test_spa_markers_in_source_module():
    """Dual marker lists: evaluate() SPA_MARKERS subset + PR04/05/07 extended set.

    evaluate()/spa_industrial_markers_source only gates SPA_MARKERS (4 industrial
    tokens). role-seg / last-act / bridge are intentional product tests — not
    claimed as release-flags SSOT coverage.
    """
    from check_release_flags import SPA_MARKERS

    src = ROOT / "wildfire_front" / "product" / "app_spa_html.py"
    assert src.is_file()
    text = src.read_text(encoding="utf-8")
    # SSOT subset used by evaluate()
    assert SPA_MARKERS == ("#0B1220", "primary-acts", "mode-toggle", "btn-act-decide")
    for marker in SPA_MARKERS:
        assert marker in text, f"missing evaluate() SPA_MARKERS item {marker}"
    # Extended product markers (PR04 role, PR05 last-act, PR07 bridge, Live Ops)
    extended = (
        "role-seg", "last-act", "Último acto", "/bridge/v1/decide",
        "/live/v1/decide", "runLiveAct",
    )
    for marker in extended:
        assert marker in text, f"missing extended SPA marker {marker}"
    # Drift guard: evaluate() detail must reference the SSOT list, not extended
    report = evaluate()
    if report.get("exit_code") != 2:
        by_id = {c["id"]: c for c in (report.get("checks") or [])}
        src_check = by_id.get("spa_industrial_markers_source") or {}
        detail = str(src_check.get("detail") or "")
        assert "primary-acts" in detail or "app_spa_html" in detail
        assert src_check.get("ok") is True
        live_check = by_id.get("live_ops_spa_markers") or {}
        assert live_check.get("ok") is True, live_check
        core_check = by_id.get("live_ops_core_module") or {}
        assert core_check.get("ok") is True, core_check
        dd_check = by_id.get("app_demo_day_flag") or {}
        assert dd_check.get("ok") is True, dd_check


def test_invariants_include_spa_and_go_q():
    report = evaluate()
    if report.get("exit_code") == 2:
        pytest.skip(report.get("error") or "authority missing")
    inv = report.get("invariants") or {}
    assert inv.get("field_ops_fusion") == "OFF"
    assert inv.get("go_q_invent_forbidden") is True
    assert inv.get("spa_industrial_c2") is True
    assert inv.get("live_ops_demo_kernel") is True
    # Named checks present with concrete ok flags (not vacuous)
    by_id = {c["id"]: c for c in (report.get("checks") or [])}
    assert by_id["field_ops_fusion_off"]["ok"] is True
    assert by_id["go_q_not_true_without_h1"]["ok"] is True
    assert by_id["spa_industrial_markers_source"]["ok"] is True
    # evaluate() exit_code is real status signal
    assert report["exit_code"] in (0, 1)
    if report["exit_code"] == 0:
        assert report["status"] == "PASS"
        assert report["n_fail"] == 0


def test_evaluate_report_exit_code_contract():
    """evaluate() always returns a structured report with exit_code int."""
    report = evaluate()
    assert isinstance(report, dict)
    assert isinstance(report.get("exit_code"), int)
    assert report["exit_code"] in (0, 1, 2)
    if report["exit_code"] == 2:
        assert report.get("error")
        return
    assert "checks" in report
    assert isinstance(report["checks"], list)
    assert len(report["checks"]) >= 3
