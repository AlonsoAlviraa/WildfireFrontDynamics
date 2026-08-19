"""Clerk: classify a messy operator drop. JPG dies. Only cited ha from text/PDF."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .board import append_event, set_cell

_TIFF = {".tif", ".tiff"}
_PHONE = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
# Official area only when the document itself carries a cite token.
_CITED_HA = re.compile(
    r"(?:cite\s*:\s*\S+).{0,80}?(\d+(?:[.,]\d+)?)\s*ha"
    r"|(\d+(?:[.,]\d+)?)\s*ha.{0,80}?cite\s*:\s*(\S+)",
    re.IGNORECASE | re.DOTALL,
)
_CITE_TOKEN = re.compile(r"cite\s*:\s*(\S+)", re.IGNORECASE)


def classify_name(name: str) -> str:
    suf = Path(name).suffix.lower()
    if suf in _TIFF:
        return "ops_thermal"
    if suf in _PHONE:
        return "reject_phone"
    if suf == ".pdf" or suf == ".txt" or suf == ".md":
        return "open_document"
    return "unknown"


def extract_cited_ha(text: str) -> dict[str, Any] | None:
    """Return {value, cite} only if the document states both ha and a cite."""
    blob = text or ""
    m = _CITED_HA.search(blob)
    if not m:
        return None
    if m.group(1):
        cite_m = _CITE_TOKEN.search(blob)
        if not cite_m:
            return None
        return {"value": float(m.group(1).replace(",", ".")), "cite": cite_m.group(1)}
    if m.group(2) and m.group(3):
        return {"value": float(m.group(2).replace(",", ".")), "cite": m.group(3)}
    return None


def ingest_drop(
    board: dict[str, Any],
    files: list[dict[str, Any]],
    *,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """``files`` items: {name, text?, content_b64?}."""
    accepted_tif: list[str] = []
    rejected: list[dict[str, str]] = []
    cited_ha: dict[str, Any] | None = None
    out = board

    for item in files or []:
        name = str(item.get("name") or "file")
        kind = classify_name(name)
        if kind == "reject_phone":
            rejected.append(
                {
                    "name": name,
                    "why": "Phone JPG/PNG is not a georeferenced thermal. Relator refuses it.",
                }
            )
            continue
        if kind == "ops_thermal":
            accepted_tif.append(name)
            continue
        if kind == "open_document":
            extracted = extract_cited_ha(str(item.get("text") or ""))
            if extracted:
                cited_ha = extracted
            else:
                rejected.append(
                    {
                        "name": name,
                        "why": "Document has no cited hectare (need '<n> ha' and 'cite:<id>').",
                    }
                )
            continue
        rejected.append({"name": name, "why": "Unknown type — clerk will not guess."})

    if work_dir is not None:
        try:
            from wildfire_front.product.operator_intake import receive_files

            payload = []
            for item in files or []:
                if classify_name(str(item.get("name") or "")) == "ops_thermal":
                    payload.append(item)
            if payload:
                receive_files(Path(work_dir), payload)
        except Exception:
            # Prior-art intake is optional in the hackathon slice.
            pass

    if accepted_tif:
        out = set_cell(
            out,
            "ops_thermal",
            status="present",
            value=len(accepted_tif),
            unit="geotiff",
            source="operator_inbox",
            note=f"Accepted {len(accepted_tif)} GeoTIFF(s): {', '.join(accepted_tif[:6])}.",
        )
    if cited_ha:
        out = set_cell(
            out,
            "open_official_ha",
            status="cited",
            value=cited_ha["value"],
            unit="ha",
            cite=cited_ha["cite"],
            source="open_document",
            note="Hectares copied from a cited official document. Not a FIRMS hull.",
        )

    summary = (
        f"Clerk: {len(accepted_tif)} GeoTIFF accepted, {len(rejected)} refused"
        + (f", official ha cited={cited_ha['value']}" if cited_ha else ", no official ha")
    )
    out = append_event(out, {"type": "source.arrived", "actor": "clerk", "summary": summary})
    out = dict(out)
    out["clerk"] = {
        "accepted_tif": accepted_tif,
        "rejected": rejected,
        "cited_ha": cited_ha,
        "jpg_not_enough": any(r["name"].lower().endswith((".jpg", ".jpeg", ".png")) for r in rejected),
    }
    return out
