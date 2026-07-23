"""CEMS activation WATCH status for open IF packs (La Mierla honesty)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

CEMS_SCHEMA = "open_if_cems_watch_v1"

# EMSR896 is Orés (Aragón) — must never be treated as La Mierla.
EMSR896_NOTE = (
    "EMSR896 is Aragon (Orés / Cinco Villas path), NOT La Mierla "
    "(Sierra Norte de Guadalajara / CLM). Keep CEMS status WATCH until a "
    "dedicated EMSR activation for Sierra Norte GU is published on "
    "mapping.emergency.copernicus.eu."
)

DEFAULT_RELATED = (
    "https://mapping.emergency.copernicus.eu/news/wildfire-in-aragon-spain-emsr896/"
)
DEFAULT_PORTAL = "https://mapping.emergency.copernicus.eu/"


def build_cems_watch(
    *,
    status: str = "WATCH",
    note: str | None = None,
    checked_at: str | None = None,
    related_news: str | None = None,
    portal: str | None = None,
    activation_codes_seen: list[str] | None = None,
    la_mierla_emsr: str | None = None,
    fetch_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ``cems_watch.json`` payload with mandatory EMSR896 disclaimer."""
    note_text = note or EMSR896_NOTE
    if "EMSR896" not in note_text:
        note_text = f"{note_text} | {EMSR896_NOTE}"
    return {
        "schema": CEMS_SCHEMA,
        "status": status,
        "note": note_text,
        "checked_at": checked_at or datetime.now(UTC).isoformat(),
        "related_news": related_news or DEFAULT_RELATED,
        "portal": portal or DEFAULT_PORTAL,
        "emsr896_is_not_la_mierla": True,
        "la_mierla_emsr_code": la_mierla_emsr,  # null until real activation
        "activation_codes_seen": list(activation_codes_seen or []),
        "fetch_result": fetch_result,
        "honesty": {
            "not_official_perimeter": True,
            "do_not_merge_emsr896_as_la_mierla": True,
        },
    }


def assert_emsr896_disclaimer(doc: dict[str, Any]) -> None:
    """Raise AssertionError if EMSR896 / Orés disclaimer is missing."""
    note = str(doc.get("note") or "")
    if "EMSR896" not in note:
        raise AssertionError("cems_watch note must mention EMSR896")
    if not doc.get("emsr896_is_not_la_mierla", False):
        raise AssertionError("cems_watch must set emsr896_is_not_la_mierla=true")
