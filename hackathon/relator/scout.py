"""Scout: constellation desk → open_sat cell + sky chips.

Prefer real NASA GIBS chips (VIIRS true-color / SWIR / thermal). A numeric
FIRMS pulse is only a fallback when the sky pack is not attached.
Does not compute ROS. Does not promote FIRMS to official burned area.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .board import append_event, query_hash, set_cell
from .eyes import local_look
from .maps_grounding import ground_place


def ingest_sky_pack(board: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Attach a constellation pull (chips + optional hotspot count) to the board."""
    place = pack.get("place") or ground_place(str(pack.get("aoi") or board.get("incident_id") or "nijar"))
    n = pack.get("n_hotspots")
    chips = list(pack.get("chips") or [])
    qh = pack.get("query_hash") or query_hash({"aoi": pack.get("aoi"), "dates": pack.get("dates")})
    n_chips = len(chips)
    present = n_chips > 0 or (n is not None and int(n) > 0)
    note = (
        f"Sky desk: {n_chips} satellite chip(s)"
        + (f", {int(n)} FIRMS-class hotspots" if n is not None else "")
        + f". {pack.get('source') or 'constellation'}. FIRMS/thermal ≠ official burned area. hash={qh}."
    )
    look = local_look(pack)
    out = set_cell(
        board,
        "open_sat",
        status="present" if present else "missing",
        value=int(n) if n is not None else (n_chips or None),
        unit="hotspots" if n is not None else "chips",
        source=str(pack.get("source") or "nasa_gibs_worldview"),
        query_hash=str(qh),
        cite=pack.get("cite"),
        note=note,
    )
    out["place"] = {
        "label": place.get("label") or pack.get("label"),
        "cite": place.get("cite"),
        "note": place.get("note"),
        "bbox": pack.get("bbox") or place.get("bbox"),
        "not_tactical_dispatch": True,
    }
    out["sky"] = {
        "chips": chips,
        "dates": pack.get("dates"),
        "source": pack.get("source"),
        "cite": pack.get("cite"),
        "query_hash": qh,
        "look": look,
        "not_official_burned": True,
    }
    return append_event(out, {"type": "source.arrived", "actor": "scout", "summary": note})


def ingest_firms_pulse(
    board: dict[str, Any],
    *,
    n_hotspots: int,
    bbox: list[float] | None = None,
    source: str = "firms_ee_or_bq",
    aoi: str | None = None,
    sky: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if sky:
        pack = dict(sky)
        if pack.get("n_hotspots") is None and n_hotspots:
            pack["n_hotspots"] = n_hotspots
        pack.setdefault("aoi", aoi)
        pack.setdefault("source", source)
        return ingest_sky_pack(board, pack)

    place = ground_place(aoi or str(board.get("incident_id") or "nijar"))
    qh = query_hash(
        {
            "n_hotspots": int(n_hotspots),
            "bbox": list(bbox or place.get("bbox") or []),
            "source": source,
            "incident": board.get("incident_id"),
        }
    )
    note = (
        f"{int(n_hotspots)} FIRMS hotspot(s), no chip attached. "
        f"FIRMS hull ≠ official burned area. query_hash={qh}."
    )
    out = set_cell(
        board,
        "open_sat",
        status="present" if int(n_hotspots) > 0 else "missing",
        value=int(n_hotspots) if int(n_hotspots) > 0 else None,
        unit="hotspots",
        source=source,
        query_hash=qh,
        note=note,
        cite=None,
    )
    out["place"] = {
        "label": place.get("label"),
        "cite": place.get("cite"),
        "note": place.get("note"),
        "bbox": place.get("bbox"),
        "not_tactical_dispatch": True,
    }
    return append_event(
        out,
        {
            "type": "source.arrived",
            "actor": "scout",
            "summary": note,
        },
    )


def pull_and_ingest(
    board: dict[str, Any],
    *,
    aoi: str,
    dest_dir: Path,
) -> dict[str, Any]:
    from .satellites import pull_constellation

    pack = pull_constellation(aoi, dest_dir)
    return ingest_sky_pack(board, pack)
