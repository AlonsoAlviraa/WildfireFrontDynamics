"""W1-A / W3-A: SPA read-only weakness board — no invented counts / 2nd grade-A."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.spa_honesty_ui import (
    load_weakness_board_surface,
    second_anchor_surface,
)

ROOT = Path(__file__).resolve().parents[1]


def _board(*, grade_a: int, fires: list[dict]) -> dict:
    return {
        "schema": "wfd_if_weakness_board_v1",
        "rails": {
            "go_q": "partial",
            "field_ops_ml_fusion": "ON",
            "hellin_status_ssot": "pending_external",
            "freeze_ml": True,
            "invented_vp_ha": False,
        },
        "summary": {
            "n_fires": len(fires),
            "n_confirmed": sum(1 for f in fires if f.get("status") == "confirmed"),
            "n_ml_strong": 0,
            "n_no_use": sum(1 for f in fires if f.get("status") == "NO_USE"),
            "grade_a_ops_anchors": grade_a,
        },
        "fires": fires,
    }


def test_empty_missing_json_does_not_invent_counts(tmp_path: Path) -> None:
    missing = load_weakness_board_surface(
        repo_root=tmp_path, board_path=tmp_path / "nope.json", base=tmp_path
    )
    assert missing["marker"] == "weakness-board"
    assert missing["empty"] is True
    assert missing["mode"] == "sin_board"
    assert missing["n_fires"] is None
    assert missing["n_confirmed"] is None
    assert missing["n_ml_strong"] is None
    assert missing["grade_a_ops_anchors"] is None
    assert missing["grade_a_ops_anchors"] != 2
    assert missing["go_q_met"] is False
    assert missing["go_q"] == "partial"
    assert missing["invents_counts"] is False
    assert missing["invents_vp_ha"] is False
    assert missing["second_anchor"]["visible"] is False
    assert missing["fires"] == []
    assert missing["field_ops_ml_live_fusion"] == "ON"

    bad = tmp_path / "docs" / "WEAKNESS_BOARD.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not-json", encoding="utf-8")
    unreadable = load_weakness_board_surface(
        repo_root=tmp_path, board_path=bad, base=tmp_path
    )
    assert unreadable["empty"] is True
    assert unreadable["grade_a_ops_anchors"] is None
    assert unreadable["n_ml_strong"] is None
    assert unreadable["go_q_met"] is False


def test_real_json_pins_tobarra_only_cited_vp(tmp_path: Path) -> None:
    path = tmp_path / "docs" / "WEAKNESS_BOARD.json"
    path.parent.mkdir(parents=True)
    payload = _board(
        grade_a=1,
        fires=[
            {
                "fire_id": "tobarra_20240802",
                "status": "confirmed",
                "anchor_status": "confirmed",
                "honesty_class": "ml_weak",
                "use_flag": "review",
                "blocking_gap": "rights",
                "vp_m_min_cited": 7.0,
                "area_ha_cited": 39.0,
            },
            {
                "fire_id": "hellin_2024",
                "status": "pending_external",
                "anchor_status": "pending_external",
                "honesty_class": "ml_weak",
                "use_flag": "review",
                "blocking_gap": "cite",
                "vp_m_min_cited": None,
                "area_ha_cited": None,
            },
            {
                "fire_id": "cardoso_2025",
                "status": "pending_external",
                "anchor_status": "pending_external",
                "honesty_class": "ml_weak",
                "use_flag": "review",
                "blocking_gap": "cite",
                "vp_m_min_cited": None,
                "area_ha_cited": None,
            },
        ],
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    surface = load_weakness_board_surface(
        repo_root=tmp_path, board_path=path, base=tmp_path
    )
    assert surface["empty"] is False
    assert surface["n_confirmed"] == 1
    assert surface["n_ml_strong"] == 0
    assert surface["grade_a_ops_anchors"] == 1
    assert surface["go_q_met"] is False
    assert surface["hellin_status"] == "pending_external"
    by_id = {row["fire_id"]: row for row in surface["fires"]}
    assert by_id["tobarra_20240802"]["vp_m_min_cited"] == 7.0
    assert by_id["tobarra_20240802"]["area_ha_cited"] == 39.0
    assert by_id["hellin_2024"]["vp_m_min_cited"] is None
    assert by_id["cardoso_2025"]["vp_m_min_cited"] is None
    assert surface["second_anchor"]["visible"] is False
    assert "no inventar 2ª" in surface["second_anchor"]["copy"]


def test_second_anchor_hidden_unless_two_confirmed_cited() -> None:
    one = _board(
        grade_a=1,
        fires=[
            {
                "fire_id": "tobarra_20240802",
                "status": "confirmed",
                "anchor_status": "confirmed",
                "vp_m_min_cited": 7.0,
                "area_ha_cited": 39.0,
            }
        ],
    )
    hidden = second_anchor_surface(one)
    assert hidden["visible"] is False
    assert hidden["n_confirmed_cited"] == 1
    assert hidden["grade_a_ops_anchors"] == 1
    assert "no inventar 2ª" in hidden["copy"]

    two = _board(
        grade_a=2,
        fires=[
            {
                "fire_id": "tobarra_20240802",
                "status": "confirmed",
                "anchor_status": "confirmed",
                "vp_m_min_cited": 7.0,
                "area_ha_cited": 39.0,
            },
            {
                "fire_id": "hellin_2024",
                "status": "confirmed",
                "anchor_status": "confirmed",
                "vp_m_min_cited": 4.0,
                "area_ha_cited": 120.0,
            },
        ],
    )
    shown = second_anchor_surface(two)
    assert shown["visible"] is True
    assert shown["n_confirmed_cited"] == 2
    assert shown["grade_a_ops_anchors"] == 2
    ids = {row["fire_id"] for row in shown["fires"]}
    assert ids == {"tobarra_20240802", "hellin_2024"}

    lying = _board(
        grade_a=2,
        fires=[
            {
                "fire_id": "tobarra_20240802",
                "status": "confirmed",
                "anchor_status": "confirmed",
                "vp_m_min_cited": 7.0,
                "area_ha_cited": 39.0,
            },
            {
                "fire_id": "hellin_2024",
                "status": "pending_external",
                "anchor_status": "pending_external",
                "vp_m_min_cited": None,
                "area_ha_cited": None,
            },
        ],
    )
    fail_closed = second_anchor_surface(lying)
    assert fail_closed["visible"] is False
    assert fail_closed["n_confirmed_cited"] == 1
    assert fail_closed["grade_a_ops_anchors"] == 2
    assert fail_closed["invents_second_anchor"] is False


def test_payload_embeds_weakness_board_marker() -> None:
    payload = build_product_app_payload(live=False, scan=False, repo=ROOT)
    wb = payload["weakness_board"]
    assert wb["marker"] == "weakness-board"
    assert wb["go_q_met"] is False
    assert wb["go_q"] == "partial"
    assert wb["invents_counts"] is False
    assert wb["invents_vp_ha"] is False
    if not wb["empty"]:
        assert wb["n_confirmed"] == 1
        assert wb["n_ml_strong"] == 0
        assert wb["grade_a_ops_anchors"] == 1
        assert wb["hellin_status"] == "pending_external"
        by_id = {row["fire_id"]: row for row in wb["fires"]}
        assert by_id["tobarra_20240802"]["vp_m_min_cited"] == 7.0
        assert by_id["hellin_2024"]["vp_m_min_cited"] is None
        assert wb["second_anchor"]["visible"] is False
    html = render_product_app_html(payload)
    assert 'data-marker="weakness-board"' in html
    assert 'id="weakness-board"' in html
    assert "paintWeaknessBoard" in html
    assert "no inventar 2ª" in html
    assert "no POST" in html or "no promote" in html
    assert "go_q_met" in html
