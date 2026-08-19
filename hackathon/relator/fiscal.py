"""Prosecutor: unsourced ROS / ha / GO claims are struck. No LLM.

This is the Model Armor stand-in that runs without GCP. Same rules can be
ported to a Model Armor custom filter on Cloud Run.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .board import append_event, cell_status, cited_value

# Decision-verb GO, not product flags GO_Q / GO_MES / GO_TOTAL.
_GO_VERB = re.compile(
    r"(?<![A-Z_])\bGO\b(?!_)",
    re.IGNORECASE,
)
_ROS = re.compile(
    r"(?:ROS|rate of spread|velocidad(?: del frente)?)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:m\s*/\s*min|m·min|m per min)?",
    re.IGNORECASE,
)
_MMIN = re.compile(r"(\d+(?:[.,]\d+)?)\s*m\s*/\s*min", re.IGNORECASE)
_HA = re.compile(r"(\d+(?:[.,]\d+)?)\s*ha\b", re.IGNORECASE)

_SAFE_GO_CONTEXT = (
    "go_q",
    "go_mes",
    "go_total",
    "not go",
    "≠ go",
    "!= go",
    "fusion on ≠",
    "never go",
    "no go",
)


def _num(raw: str) -> float:
    return float(raw.replace(",", "."))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6


def _go_is_flag_talk(text: str, match: re.Match[str]) -> bool:
    window = text[max(0, match.start() - 24) : match.end() + 16].lower()
    return any(tok in window for tok in _SAFE_GO_CONTEXT)


def scan_text(text: str, board: dict[str, Any]) -> list[dict[str, Any]]:
    """Return strike records for unsourced quantitative / GO claims."""
    strikes: list[dict[str, Any]] = []
    blob = text or ""
    ros_cited = cited_value(board, "ops_ros")
    ha_cited = cited_value(board, "open_official_ha")

    for rx, kind in ((_ROS, "ros"), (_MMIN, "ros")):
        for m in rx.finditer(blob):
            val = _num(m.group(1))
            if ros_cited is not None and _close(val, float(ros_cited)):
                continue
            strikes.append(
                {
                    "kind": kind,
                    "span": m.group(0),
                    "value": val,
                    "why": "ROS / m/min without a matching cited ops_ros cell",
                }
            )

    for m in _HA.finditer(blob):
        val = _num(m.group(1))
        if ha_cited is not None and _close(val, float(ha_cited)):
            continue
        # "0 ha cited" / "0/4" style — still a number+ha; only allow if cited.
        strikes.append(
            {
                "kind": "ha",
                "span": m.group(0),
                "value": val,
                "why": "hectare figure without a matching cited open_official_ha cell",
            }
        )

    for m in _GO_VERB.finditer(blob):
        if _go_is_flag_talk(blob, m):
            continue
        # A GO verb is only legal if the sealed judge already said GO *and*
        # fiscal is not looking at an injected hallucination. We never let
        # prose invent GO ahead of the judge.
        judge = board.get("judge") or {}
        if str(judge.get("decision") or "").upper() == "GO" and not judge.get("forced"):
            continue
        strikes.append(
            {
                "kind": "go_verb",
                "span": m.group(0),
                "value": None,
                "why": "GO as a decision verb is reserved for the sealed judge",
            }
        )
    return strikes


def redact(text: str, strikes: list[dict[str, Any]]) -> str:
    out = text or ""
    for s in strikes:
        span = str(s.get("span") or "")
        if span:
            out = out.replace(span, "⟦STRUCK:uncited⟧")
    return out


def prosecute(
    board: dict[str, Any],
    *,
    briefing: str | None = None,
    actor: str = "fiscal",
) -> dict[str, Any]:
    """Strike unsourced claims. Any strike force-ABSTAINs the board."""
    text = briefing if briefing is not None else str(board.get("briefing") or "")
    strikes = scan_text(text, board)
    out = deepcopy(board)
    out["briefing"] = redact(text, strikes) if strikes else text
    fiscal = {
        "ok": not strikes,
        "forced_abstain": bool(strikes),
        "struck": strikes,
        "engine": "relator_fiscal_v1",
    }
    out["fiscal"] = fiscal
    if strikes:
        out["decision"] = "ABSTAIN"
        kinds = sorted({str(s["kind"]) for s in strikes})
        out["decision_reason"] = (
            "Fiscal struck uncited claim(s): " + ", ".join(kinds) + ". Relator refuses to carry them."
        )
        # Mark quantitative cells struck if the prose invented them.
        cells = out.setdefault("cells", {})
        if any(s["kind"] == "ros" for s in strikes) and cell_status(out, "ops_ros") != "cited":
            prev = cells.get("ops_ros") or {}
            cells["ops_ros"] = {
                **prev,
                "status": "struck",
                "note": "Uncited ROS in briefing — struck by fiscal.",
            }
        if any(s["kind"] == "ha" for s in strikes) and cell_status(out, "open_official_ha") != "cited":
            prev = cells.get("open_official_ha") or {}
            cells["open_official_ha"] = {
                **prev,
                "status": "struck",
                "note": "Uncited ha in briefing — struck by fiscal.",
            }
        out = append_event(
            out,
            {
                "type": "card.challenged",
                "actor": actor,
                "summary": out["decision_reason"],
            },
        )
    return out


def compose_briefing(board: dict[str, Any]) -> str:
    """Plain-language dossier line. Only cited numbers are printed."""
    place = (board.get("place") or {}).get("label") or "unlocated AOI"
    q = board.get("decision") or "ABSTAIN"
    bits = [f"Relator {q} at {place}."]
    ros = cited_value(board, "ops_ros")
    ha = cited_value(board, "open_official_ha")
    if ros is not None:
        cite = ((board.get("cells") or {}).get("ops_ros") or {}).get("cite")
        bits.append(f"Cited front speed {ros} m/min (cite:{cite}).")
    else:
        bits.append("No cited front speed.")
    if ha is not None:
        cite = ((board.get("cells") or {}).get("open_official_ha") or {}).get("cite")
        bits.append(f"Cited official area {ha} ha (cite:{cite}).")
    else:
        bits.append("No cited official area. FIRMS hull is not burned area.")
    if cell_status(board, "open_sat") in ("present", "cited"):
        bits.append("Open satellite hotspots are present and not an official perimeter.")
    if cell_status(board, "ops_thermal") in ("present", "cited"):
        bits.append("Operator thermal GeoTIFF accepted.")
    bits.append("Not tactical dispatch. GO_Q remains partial. No language model.")
    return " ".join(bits)
