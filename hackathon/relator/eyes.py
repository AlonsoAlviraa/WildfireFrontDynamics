"""Chip ledger — no LLM. Numbers come from the pack, never from a model."""

from __future__ import annotations

from typing import Any


def local_look(pack: dict[str, Any]) -> dict[str, Any]:
    """Describe what is on file. Does not call any model. Does not invent physics."""
    chips = pack.get("chips") or []
    dates = pack.get("dates") or []
    roles = sorted({str(c.get("role")) for c in chips})
    n = pack.get("n_hotspots")
    lines = [
        f"Constellation desk pulled {len(chips)} chip(s) for {pack.get('label') or pack.get('aoi')}.",
        f"Sensors on the board: {', '.join(roles) or 'none'}. Dates: {', '.join(dates) or 'n/a'}.",
    ]
    if n is not None:
        cite = pack.get("cite") or "nasa_firms"
        lines.append(f"Hotspot count on file: {n} (cite:{cite}). Not official burned area.")
    else:
        lines.append("No hotspot count on file — clerk will not invent one from the pixels.")
    if len(dates) >= 2:
        lines.append(
            f"Two-date stack ({dates[0]} → {dates[1]}). "
            "Visual change is for a human to confirm; this look does not measure spread."
        )
    lines.append("No language model called. No rate-of-spread. No hectares. Not dispatch.")
    return {
        "engine": "local_look",
        "model": None,
        "text": " ".join(lines),
        "not_tactical_dispatch": True,
        "invented_numbers": False,
        "llm": False,
    }
