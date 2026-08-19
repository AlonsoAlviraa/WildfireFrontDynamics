"""Deterministic Maps-style place labels for demo AOIs.

Live Cloud Run can swap this for Grounding with Google Maps.
Labels are geography only — never an evacuation or dispatch order.
"""

from __future__ import annotations

from typing import Any

AOIS: dict[str, dict[str, Any]] = {
    "nijar": {
        "incident_id": "nijar_demo",
        "label": "Níjar, Almería, Spain",
        "cite": "maps_grounding:place/nijar-almeria",
        "note": "A-7 roughly 3 km east of the demo bbox. Geography only — not an evacuation order.",
        "bbox": [-2.22, 36.94, -2.10, 37.06],
        "aliases": ("nijar", "níjar", "almeria", "almería"),
    },
    "tobarra": {
        "incident_id": "tobarra_demo",
        "label": "Tobarra, Albacete, Spain",
        "cite": "maps_grounding:place/tobarra-albacete",
        "note": "CM-412 corridor. Geography only — not an evacuation order.",
        "bbox": [-1.72, 38.55, -1.64, 38.63],
        "aliases": ("tobarra", "albacete"),
    },
}


def ground_place(name_or_id: str) -> dict[str, Any]:
    key = (name_or_id or "").strip().lower()
    for rec in AOIS.values():
        if key == rec["incident_id"] or key in rec["aliases"]:
            return {
                "label": rec["label"],
                "cite": rec["cite"],
                "note": rec["note"],
                "bbox": list(rec["bbox"]),
                "not_tactical_dispatch": True,
            }
    return {
        "label": None,
        "cite": None,
        "note": "Unknown AOI — Relator will not invent a toponym.",
        "bbox": None,
        "not_tactical_dispatch": True,
    }
