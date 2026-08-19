"""Snapshot + compare: shipped surface functions, no re-implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.product.decide_service import REPO_ROOT
from wildfire_front.product.surface_api import (
    SNAPSHOT_BASENAME,
    SOURCE_BOARD_KEYS,
    cited_delta,
    cited_instant,
    compare_from_request,
    snapshot_from_card,
    surface_compare,
    surface_snapshot,
)

SLA = REPO_ROOT / "outputs" / "incidents" / "_sla_measure"
TOBARRA_FO = (
    REPO_ROOT
    / "outputs"
    / "pilot_honesty_card"
    / "sites"
    / "tobarra"
    / "decision_card_field_ops.json"
)


def _forbidden_text(payload: dict) -> str:
    return json.dumps(payload, default=str).lower()


def test_snapshot_sla_work_dir_has_board_rails_hashes() -> None:
    if not SLA.is_dir():
        pytest.skip("_sla_measure missing")
    snap = surface_snapshot(SLA)
    assert snap["ok"] is True
    assert snap["act"] == "snapshot"
    assert snap["decision"] in {"GO", "HOLD", "ABSTAIN"}
    board = snap["source_board"]
    for key in SOURCE_BOARD_KEYS:
        assert key in board
        assert board[key]["status"] in {"present", "missing"}
        assert board[key]["present"] is (board[key]["status"] == "present")
    rails = snap["rails"]
    assert rails["not_tactical_dispatch"] is True
    assert rails["fusion_on_is_not_dispatch"] is True
    assert rails["go_q_partial"] is True
    assert rails["go_q_complete"] is False
    assert str(rails["go_q"]).lower() == "partial"
    assert snap["not_tactical_dispatch"] is True
    assert snap["hashes"]["input_hash"]
    assert snap["hashes"]["output_hash"]
    cited = snap["cited"]
    ops = json.loads((SLA / "outbox" / "operational_metrics.json").read_text(encoding="utf-8"))
    card = json.loads((SLA / "outbox" / "fire_decision_card.json").read_text(encoding="utf-8"))
    ops_m = (card.get("metrics") or {}).get("ops") or {}
    assert cited["invented"] is False
    assert cited["not_tactical"] is True
    assert cited["ros_m_min"] == ops_m.get("primary_ros_m_min")
    assert cited["ros_source"] == "metrics.ops.primary_ros_m_min"
    assert "iou" not in str(cited["ros_source"]).lower()
    assert cited["interval_s"] == ops.get("interval_s_median")
    assert cited["area_ha"] == ops_m.get("area_ha_max")
    assert cited["quality_grade"] == ops_m.get("quality_grade") or ops.get("quality_grade")
    blob = _forbidden_text(snap)
    assert "despacho táctico" not in blob or "not_tactical_dispatch" in blob
    assert "go_q_complete\": true" not in blob
    assert "signed acta" not in blob
    assert "hellín" not in blob and "hellin" not in blob
    assert "cardoso" not in blob
    assert "0.308" not in blob
    assert "rcda" not in blob
    assert "caldor" not in blob


def test_snapshot_tobarra_field_ops_reliability_driver() -> None:
    if not TOBARRA_FO.is_file():
        pytest.skip("honesty tobarra field_ops card missing")
    card = json.loads(TOBARRA_FO.read_text(encoding="utf-8"))
    snap = snapshot_from_card(card)
    assert snap["decision"] == "ABSTAIN"
    assert snap["source_board"]["ops"]["present"] is True
    assert snap["source_board"]["ml_live"]["present"] is True
    assert snap["source_board"]["open"]["present"] is False
    assert snap["source_board"]["reliability"]["present"] is False
    assert snap["source_board"]["reliability"]["driver"] == "reliability_unverified"
    assert "reliability" in snap["drivers"]
    assert snap["cited"]["ros_m_min"] == (card.get("metrics") or {}).get("ops", {}).get(
        "primary_ros_m_min"
    )
    assert snap["cited"]["ros_source"] == "metrics.ops.primary_ros_m_min"
    assert snap["cited"]["invented"] is False
    assert snap["rails"]["go_q_complete"] is False
    assert snap["not_tactical_dispatch"] is True


def test_compare_flip_and_identity() -> None:
    left = {
        "event_id": "cmp",
        "decision": "GO",
        "confidence_pred": 0.7,
        "system_reliability_pass": True,
        "sources": [
            {"id": "ops_thermal_front", "available": True},
            {"id": "open_cems", "available": False},
            {"id": "ml_live_reliability", "available": True},
        ],
        "reasons": ["ops_thermal_front:conf=0.70"],
        "audit": {"input_hash": "aaa", "output_hash": "out-a", "policy_id": "field_ops"},
    }
    right = {
        "event_id": "cmp",
        "decision": "ABSTAIN",
        "confidence_pred": 0.5,
        "system_reliability_pass": False,
        "sources": [
            {"id": "ops_thermal_front", "available": True},
            {"id": "open_cems", "available": False},
            {"id": "ml_live_reliability", "available": False},
        ],
        "reasons": ["field_ops_fail_closed_reliability_unverified"],
        "audit": {"input_hash": "bbb", "output_hash": "out-b", "policy_id": "field_ops"},
    }
    flip = surface_compare(left, right)
    assert flip["ok"] is True
    assert flip["flipped"] is True
    assert flip["from"] == "GO"
    assert flip["to"] == "ABSTAIN"
    assert flip["same_input"] is False
    assert "ml_live" in flip["source_delta"]["disappeared"]
    alert = flip["alert"]
    assert alert["kind"] == "decision_flip"
    assert alert["delivered"] is False
    assert alert["channel"] == "local_payload"
    assert alert["not_sms"] is True
    assert alert["not_whatsapp"] is True
    assert alert["not_email"] is True
    assert alert["not_tactical_dispatch"] is True
    assert flip["rails"]["go_q_complete"] is False
    assert flip["not_tactical_dispatch"] is True

    same = surface_compare(left, left)
    assert same["ok"] is True
    assert same["flipped"] is False
    assert same["same_input"] is True
    assert same["alert"]["kind"] == "identity"
    assert same["alert"]["delivered"] is False
    assert same["from"] == same["to"] == "GO"


def test_compare_same_input_hash_is_identity_even_if_decision_text_differs() -> None:
    a = {
        "decision": "HOLD",
        "system_reliability_pass": False,
        "sources": [],
        "audit": {"input_hash": "same-in", "output_hash": "h1"},
    }
    b = {
        "decision": "GO",
        "system_reliability_pass": False,
        "sources": [],
        "audit": {"input_hash": "same-in", "output_hash": "h2"},
    }
    out = surface_compare(a, b)
    assert out["flipped"] is False
    assert out["same_input"] is True
    assert out["alert"]["kind"] == "identity"


def test_compare_real_snapshots_preserve_ops_and_empty_delta(tmp_path: Path) -> None:
    """Same-incident identity must reuse snapshot source_board (not rebuild from slim card)."""
    if not SLA.is_dir():
        pytest.skip("_sla_measure missing")
    snap = surface_snapshot(SLA)
    assert snap["ok"] is True
    assert snap["source_board"]["ops"]["present"] is True
    saved = tmp_path / "snapshot.json"
    saved.write_text(json.dumps(snap), encoding="utf-8")

    vs_dir = surface_compare(snap, SLA)
    vs_self = surface_compare(snap, snap)
    vs_file = surface_compare(saved, SLA)
    vs_file_file = surface_compare(saved, saved)

    for payload in (vs_dir, vs_self, vs_file, vs_file_file):
        assert payload["ok"] is True
        assert payload["flipped"] is False
        assert payload["alert"]["kind"] == "identity"
        assert payload["source_delta"]["appeared"] == []
        assert payload["source_delta"]["disappeared"] == []
        assert payload["left"]["source_board"]["ops"]["present"] is True
        assert payload["right"]["source_board"]["ops"]["present"] is True
        assert payload["left"]["source_board"]["ops"]["status"] == "present"
        assert payload["right"]["source_board"]["ops"]["status"] == "present"
        assert payload["not_tactical_dispatch"] is True
        assert payload["rails"]["go_q_complete"] is False


def test_persist_snapshot_and_compare_evolution(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    first = {
        "event_id": "evo",
        "decision": "GO",
        "confidence_pred": 0.72,
        "system_reliability_pass": True,
        "sources": [
            {"id": "ops_thermal_front", "available": True},
            {"id": "ml_live_reliability", "available": True},
        ],
        "reasons": ["ops_thermal_front:conf=0.72"],
        "audit": {"input_hash": "in-go", "output_hash": "out-go"},
    }
    (outbox / "fire_decision_card.json").write_text(json.dumps(first), encoding="utf-8")
    dry = surface_snapshot(tmp_path, persist=False)
    assert dry["saved"] is False
    assert not (outbox / SNAPSHOT_BASENAME).is_file()
    saved = surface_snapshot(tmp_path, persist=True)
    assert saved["saved"] is True
    assert (outbox / SNAPSHOT_BASENAME).is_file()
    assert saved["source_board"]["ops"]["present"] is True

    second = {
        "event_id": "evo",
        "decision": "ABSTAIN",
        "confidence_pred": 0.41,
        "system_reliability_pass": False,
        "sources": [{"id": "ops_thermal_front", "available": True}],
        "reasons": ["field_ops_fail_closed_reliability_unverified"],
        "audit": {"input_hash": "in-abs", "output_hash": "out-abs"},
    }
    (outbox / "fire_decision_card.json").write_text(json.dumps(second), encoding="utf-8")
    evo = compare_from_request({"work_dir": str(tmp_path)}, resolve_work_dir=lambda raw: Path(raw))
    assert evo["ok"] is True
    assert evo["against"] == "saved_snapshot"
    assert evo["flipped"] is True
    assert evo["from"] == "GO"
    assert evo["to"] == "ABSTAIN"
    assert evo["left"]["source_board"]["ops"]["present"] is True
    assert "ml_live" in evo["source_delta"]["disappeared"]
    assert evo["confidence_delta"] == pytest.approx(0.41 - 0.72)
    assert evo["output_hash_changed"] is True
    assert evo["alert"]["delivered"] is False
    assert evo["not_tactical_dispatch"] is True
    assert evo["rails"]["go_q_complete"] is False


def test_cited_null_without_ops_does_not_invent_ros() -> None:
    snap = snapshot_from_card(
        {
            "event_id": "open_only",
            "decision": "HOLD",
            "confidence_pred": 0.61,
            "system_reliability_pass": False,
            "sources": [{"id": "open_cems", "available": True}],
            "metrics": {"ops": None, "open_cems": {"area_ha": 2169.34}},
            "reasons": ["missing:ops_thermal_front"],
            "audit": {"input_hash": "o1", "output_hash": "o2"},
        }
    )
    cited = snap["cited"]
    assert cited["ros_m_min"] is None
    assert cited["ros_source"] is None
    assert cited["area_ha"] == pytest.approx(2169.34)
    assert cited["area_source"] == "metrics.open_cems.area_ha"
    assert cited["interval_s"] is None
    assert cited["invented"] is False
    assert cited["not_tactical"] is True
    built = cited_instant(
        {"metrics": {"open_cems": {"area_ha": 2169.34}}, "sources": []}
    )
    assert built["ros_m_min"] is None


def test_cited_delta_numeric_and_null() -> None:
    left = snapshot_from_card(
        {
            "decision": "GO",
            "confidence_pred": 0.7,
            "system_reliability_pass": True,
            "sources": [{"id": "ops_thermal_front", "available": True}],
            "metrics": {
                "ops": {
                    "primary_ros_m_min": 6.0,
                    "area_ha_max": 10.0,
                    "n_frames": 4,
                    "interval_s_median": 60.0,
                    "quality_grade": "B",
                    "observed_at": "2024-08-02T16:19:14Z",
                }
            },
            "audit": {"input_hash": "c1", "output_hash": "d1"},
        }
    )
    right = snapshot_from_card(
        {
            "decision": "GO",
            "confidence_pred": 0.7,
            "system_reliability_pass": True,
            "sources": [{"id": "ops_thermal_front", "available": True}],
            "metrics": {
                "ops": {
                    "primary_ros_m_min": 7.5,
                    "area_ha_max": 12.0,
                    "n_frames": 5,
                    "interval_s_median": 60.0,
                    "quality_grade": "B",
                    "observed_at": "2024-08-02T16:24:14Z",
                }
            },
            "audit": {"input_hash": "c2", "output_hash": "d2"},
        }
    )
    cmp = surface_compare(left, right)
    delta = cmp["cited_delta"]
    assert delta["ros_m_min"] == pytest.approx(1.5)
    assert delta["area_ha"] == pytest.approx(2.0)
    assert delta["n_frames"] == pytest.approx(1.0)
    assert delta["delta_t_s"] == pytest.approx(300.0)
    assert delta["invented"] is False
    assert delta["not_tactical"] is True
    empty = snapshot_from_card({"decision": "ABSTAIN", "sources": [], "metrics": {}})
    missing = surface_compare(left, empty)
    assert missing["cited_delta"]["ros_m_min"] is None
    assert missing["cited_delta"]["area_ha"] is None
    assert missing["cited_delta"]["invented"] is False
    unit = cited_delta(left["cited"], empty["cited"])
    assert unit["ros_m_min"] is None


def test_snapshot_missing_work_dir(tmp_path: Path) -> None:
    miss = surface_snapshot(tmp_path)
    assert miss["ok"] is False
    assert miss["error"] == "card_missing"
    assert miss["not_tactical_dispatch"] is True
    assert miss["rails"]["go_q_complete"] is False
