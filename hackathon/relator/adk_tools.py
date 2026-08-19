"""In-process helpers for Cloud Run / Pub/Sub. No language model."""

from __future__ import annotations

from typing import Any

from .agent import handle_event
from .board import empty_board, render_grid
from .fiscal import scan_text

_SESSIONS: dict[str, dict[str, Any]] = {}


def _board(incident_id: str) -> dict[str, Any]:
    return _SESSIONS.get(incident_id) or empty_board(incident_id=incident_id)


def _put(incident_id: str, board: dict[str, Any]) -> dict[str, Any]:
    _SESSIONS[incident_id] = board
    return board


def tool_scout_firms(incident_id: str, n_hotspots: int, aoi: str = "nijar") -> str:
    """Ingest a FIRMS pulse. Does not compute ROS. FIRMS ≠ burned area."""
    b = handle_event(
        _board(incident_id),
        {"type": "firms_pulse", "n_hotspots": int(n_hotspots), "aoi": aoi, "incident_id": incident_id},
    )
    _put(incident_id, b)
    return render_grid(b)


def tool_pull_sky(incident_id: str, aoi: str = "nijar") -> str:
    """Pull VIIRS / Sentinel-2 chips and attach them to the board."""
    from pathlib import Path

    from .scout import pull_and_ingest

    dest = Path("outputs") / "relator_demo" / "chips"
    b = pull_and_ingest(_board(incident_id), aoi=aoi, dest_dir=dest)
    _put(incident_id, b)
    look = ((b.get("sky") or {}).get("look") or {}).get("text") or ""
    return render_grid(b) + "\n" + look


def tool_clerk_drop(incident_id: str, files_json: str) -> str:
    """Classify a messy drop. JSON list of {name, text?}. JPG is refused."""
    import json

    files = json.loads(files_json)
    b = handle_event(
        _board(incident_id),
        {"type": "operator_drop", "files": files, "incident_id": incident_id},
    )
    _put(incident_id, b)
    return render_grid(b)


def tool_read_board(incident_id: str) -> str:
    return render_grid(_board(incident_id))


def tool_prosecute_brief(incident_id: str, briefing: str) -> str:
    b = handle_event(
        _board(incident_id),
        {"type": "hallucinated_brief", "text": briefing, "incident_id": incident_id},
    )
    _put(incident_id, b)
    return render_grid(b)


def tool_scan_only(incident_id: str, briefing: str) -> str:
    hits = scan_text(briefing, _board(incident_id))
    if not hits:
        return "fiscal_ok"
    return "fiscal_would_strike: " + "; ".join(h["why"] for h in hits)
