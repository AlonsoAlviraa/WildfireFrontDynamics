"""Shared Decision Card surface: flags, catalog, last card."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.surface_api import (
    dumps_compact,
    surface_card,
    surface_catalog,
    surface_compare,
    surface_flags,
    surface_health,
    surface_snapshot,
)


def test_surface_health_and_compact_json() -> None:
    payload = surface_health()
    assert payload["ok"] is True
    raw = dumps_compact(payload)
    assert b"\n" not in raw
    assert json.loads(raw)["product"]


def test_surface_flags_do_not_flip_go_q() -> None:
    payload = surface_flags()
    assert payload["ok"] is True
    assert str(payload.get("GO_Q")).lower() == "partial"
    assert payload.get("GO_MES_plus") is False
    assert payload.get("ml_product_go_scope") == "lab_only"
    assert payload.get("field_ops_fusion") == "ON"


def test_surface_catalog_keeps_rcda_holdout() -> None:
    payload = surface_catalog()
    ids = {row["id"] for row in payload["holdout_only"]}
    assert "rcda_net" in ids
    assert "caldor_clean17_physical_v1" in ids
    ready_ids = {row["id"] for row in payload["products"]}
    assert "rcda_net" not in ready_ids


def test_surface_card_missing_and_present(tmp_path: Path) -> None:
    missing = surface_card(tmp_path)
    assert missing["ok"] is False
    assert missing["error"] == "card_missing"
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    card = {
        "event_id": "surf",
        "decision": "ABSTAIN",
        "confidence_pred": 0.2,
        "system_reliability_pass": False,
        "audit": {"policy_id": "field_ops"},
    }
    (outbox / "fire_decision_card.json").write_text(json.dumps(card), encoding="utf-8")
    found = surface_card(tmp_path)
    assert found["ok"] is True
    assert found["summary"]["decision"] == "ABSTAIN"
    assert found["summary"]["policy_id"] == "field_ops"
    assert found["result"]["decision"] == "ABSTAIN"


def test_surface_snapshot_and_compare_on_tmp_card(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    card = {
        "event_id": "surf2",
        "decision": "HOLD",
        "confidence_pred": 0.4,
        "system_reliability_pass": False,
        "sources": [{"id": "ops_thermal_front", "available": True}],
        "reasons": ["missing:open_cems"],
        "audit": {"input_hash": "in1", "output_hash": "out1", "policy_id": "field_ops"},
    }
    (outbox / "fire_decision_card.json").write_text(json.dumps(card), encoding="utf-8")
    snap = surface_snapshot(tmp_path)
    assert snap["ok"] is True
    assert snap["decision"] == "HOLD"
    assert snap["source_board"]["ops"]["present"] is True
    assert snap["source_board"]["open"]["present"] is False
    assert snap["rails"]["not_tactical_dispatch"] is True
    ident = surface_compare(tmp_path, tmp_path)
    assert ident["flipped"] is False
    assert ident["alert"]["kind"] == "identity"
