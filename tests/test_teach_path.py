"""Teach-path snapshot + decide --explain honesty (stamp fallback; no GO_Q flip)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.product.operator_ux import build_operator_brief
from wildfire_front.product.teach_path import (
    format_decide_explain,
    load_field_ops_ml_fusion_rail,
    load_gate_snapshot,
    load_ml_go_stamp,
    ssot_field_ops_fusion,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
VERDICT = ROOT / "docs" / "GO_MES_VERDICT.json"
PLAN = ROOT / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"


def _write_stamp(tmp_path: Path, **overrides: object) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "schema": "wfd_ml_product_go_stamp_v1",
        "GO_MES": True,
        "GO_MES_plus": False,
        "GO_Q": "partial",
        "field_ops_allow_ml_live_in_fusion": True,
        "rails": {"field_ops_fusion": "ON", "tobarra_keep_reopen": False},
    }
    payload.update(overrides)
    path = docs / "ML_PRODUCT_GO_STATUS.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_live_verdict_and_plan_json_absent():
    """Main leftover: verdict/plan JSON do not exist; living stamp does."""
    assert not VERDICT.is_file()
    assert not PLAN.is_file()
    assert STAMP.is_file()


def test_load_gate_snapshot_stamp_fallback_not_unknown():
    """SPA KPI Producto/Demo reads this snapshot via operator brief.gates."""
    assert STAMP.is_file()
    stamp = load_ml_go_stamp(ROOT)
    assert stamp is not None
    snap = load_gate_snapshot(ROOT)
    gates = snap["gates"]
    assert gates["GO_MES"] is True or str(gates["GO_MES"]).lower() == "true"
    assert gates["GO_MES"] != "unknown"
    assert gates["GO_Q"] == "partial"
    assert gates["GO_Q"] is not True
    assert gates["GO_Q"] != "unknown"
    assert gates["GO_MES_plus"] is False


def test_load_gate_snapshot_stamp_present_verdict_plan_absent(tmp_path: Path):
    _write_stamp(tmp_path)
    assert not (tmp_path / "docs" / "GO_MES_VERDICT.json").is_file()
    assert not (tmp_path / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json").is_file()
    snap = load_gate_snapshot(tmp_path)
    gates = snap["gates"]
    assert gates["GO_MES"] is True
    assert gates["GO_Q"] == "partial"
    assert gates["GO_Q"] is not True
    assert gates["GO_Q"] != "unknown"
    assert gates["GO_MES"] != "unknown"
    assert gates["GO_MES_plus"] is False
    assert snap["sources_status"].get("ml_product_stamp") == "ok"


def test_load_gate_snapshot_unknown_when_stamp_also_missing(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    snap = load_gate_snapshot(tmp_path)
    assert snap["gates"]["GO_MES"] == "unknown"
    assert snap["gates"]["GO_Q"] == "unknown"
    assert snap["gates"]["GO_Q"] is not True


@pytest.mark.parametrize("bad_go_q", [True, "true", "complete", "full", "True"])
def test_load_gate_snapshot_stamp_go_q_never_coerced_true(tmp_path: Path, bad_go_q):
    _write_stamp(tmp_path, GO_Q=bad_go_q)
    snap = load_gate_snapshot(tmp_path)
    assert snap["gates"]["GO_Q"] == "partial"
    assert snap["gates"]["GO_Q"] is not True


def test_operator_brief_producto_demo_gates_from_stamp():
    """Display path: SPA KPI Producto/Demo = brief.gates.GO_MES / GO_Q."""
    brief = build_operator_brief(ROOT)
    gates = brief["gates"]
    assert gates["GO_MES"] is True or str(gates["GO_MES"]).lower() == "true"
    assert gates["GO_MES"] != "unknown"
    assert gates["GO_Q"] == "partial"
    assert gates["GO_Q"] is not True
    assert gates["GO_Q"] != "unknown"


def test_load_field_ops_ml_fusion_rail_prefers_stamp_when_catalog_missing(tmp_path: Path):
    _write_stamp(tmp_path)
    assert not (tmp_path / "config" / "decision_policies.json").is_file()
    assert load_field_ops_ml_fusion_rail(tmp_path) == "ON"
    assert ssot_field_ops_fusion(tmp_path) == "ON"


def test_format_decide_explain_footnote_not_remains_off_when_stamp_on():
    assert ssot_field_ops_fusion(ROOT) == "ON"
    text = format_decide_explain({"decision": "ABSTAIN"}, repo=ROOT)
    assert "remains OFF" not in text
    assert "field_ops ML live fusion ON" in text
    assert "GO_Q complete" in text
    assert "despacho" in text.lower()


def test_format_decide_explain_footnote_off_wording_when_rail_off():
    text = format_decide_explain(
        {"decision": "ABSTAIN"},
        field_ops_fusion_rail="OFF",
    )
    assert "field_ops ML live fusion remains OFF until explicit policy change" in text


def test_format_decide_explain_does_not_copy_this_run_fusion_onto_field_ops():
    card = {
        "decision": "ABSTAIN",
        "policy_id": "research_open",
        "metrics": {"allow_ml_live_in_fusion": True},
    }
    text = format_decide_explain(card, field_ops_fusion_rail="OFF")
    assert "this_run policy allow_ml_live: ON" in text
    assert "field_ops ML live fusion: OFF" in text
    assert "remains OFF until explicit policy change" in text
