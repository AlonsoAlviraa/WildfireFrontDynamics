"""Source board: the living expediente. Cells are cited or they do not exist."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from . import NOT_CLAIMS, SCHEMA

CELL_IDS = ("open_sat", "ops_thermal", "open_official_ha", "ops_ros")
STATUSES = ("missing", "present", "cited", "struck")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def query_hash(payload: dict[str, Any]) -> str:
    blob = repr(sorted((str(k), repr(payload[k])) for k in payload)).encode("utf-8")
    return sha256(blob).hexdigest()[:16]


def _cell(*, status: str = "missing", **extra: Any) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"bad cell status: {status}")
    cell = {
        "status": status,
        "value": extra.get("value"),
        "unit": extra.get("unit"),
        "cite": extra.get("cite"),
        "source": extra.get("source"),
        "note": extra.get("note") or "",
        "query_hash": extra.get("query_hash"),
    }
    if status == "cited" and not cell["cite"]:
        raise ValueError("cited cell requires cite")
    return cell


def empty_board(*, incident_id: str = "nijar_demo", place: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "incident_id": incident_id,
        "updated_at": utc_now(),
        "place": place
        or {
            "label": None,
            "cite": None,
            "note": "No Maps grounding yet.",
        },
        "cells": {cid: _cell() for cid in CELL_IDS},
        "decision": "ABSTAIN",
        "decision_reason": "0/4 sources. Relator does not decide.",
        "judge": None,
        "fiscal": {"struck": [], "forced_abstain": False, "ok": True},
        "rails": dict.fromkeys(NOT_CLAIMS, True) | {"go_q_met": False},
        "events": [],
        "briefing": "",
        "not_tactical_dispatch": True,
    }


def set_cell(board: dict[str, Any], cell_id: str, **kwargs: Any) -> dict[str, Any]:
    if cell_id not in CELL_IDS:
        raise KeyError(cell_id)
    out = deepcopy(board)
    out["cells"][cell_id] = _cell(**kwargs)
    out["updated_at"] = utc_now()
    return out


def append_event(board: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(board)
    rec = {
        "at": utc_now(),
        "type": event.get("type"),
        "actor": event.get("actor"),
        "summary": event.get("summary"),
    }
    out.setdefault("events", []).append(rec)
    out["updated_at"] = rec["at"]
    return out


def cell_status(board: dict[str, Any], cell_id: str) -> str:
    cell = (board.get("cells") or {}).get(cell_id) or {}
    return str(cell.get("status") or "missing")


def cited_value(board: dict[str, Any], cell_id: str) -> Any:
    cell = (board.get("cells") or {}).get(cell_id) or {}
    if cell.get("status") != "cited":
        return None
    return cell.get("value")


def quorum(board: dict[str, Any]) -> dict[str, Any]:
    cells = board.get("cells") or {}
    present = [c for c, cell in cells.items() if cell.get("status") in ("present", "cited")]
    cited = [c for c, cell in cells.items() if cell.get("status") == "cited"]
    thermal_ok = cell_status(board, "ops_thermal") in ("present", "cited")
    # Scout-only (FIRMS) is never a quorum. Official ha without thermal is not ops.
    ready_for_judge = thermal_ok
    return {
        "needed": list(CELL_IDS),
        "present": present,
        "cited": cited,
        "n_present": len(present),
        "n_cited": len(cited),
        "n_total": len(CELL_IDS),
        "ready_for_judge": ready_for_judge,
        "allow_go": False,  # Relator never lifts this; only sealed decide + fiscal
        "firms_alone_is_not_quorum": True,
    }


def render_grid(board: dict[str, Any]) -> str:
    lines = [
        f"Relator · {board.get('incident_id')} · {board.get('decision')}",
        f"place: {(board.get('place') or {}).get('label') or '—'}",
    ]
    for cid in CELL_IDS:
        cell = (board.get("cells") or {}).get(cid) or {}
        val = cell.get("value")
        cite = cell.get("cite") or ""
        tail = f" = {val}" if val is not None else ""
        extra = f"  cite:{cite}" if cite else ""
        lines.append(f"  [{cell.get('status','?'):7}] {cid}{tail}{extra}")
    q = quorum(board)
    lines.append(f"quorum {q['n_present']}/{q['n_total']} present · cited {q['n_cited']}")
    lines.append(f"reason: {board.get('decision_reason')}")
    return "\n".join(lines)
