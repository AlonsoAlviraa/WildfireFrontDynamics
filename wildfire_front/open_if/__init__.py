"""Open-data IF helpers (Pista B): CEMS packs, optional STAC dNBR, La Mierla cadence."""

from .anchor_guard import (
    assert_not_fake_confirmed,
    can_promote_to_confirmed,
    promote_anchor_to_confirmed,
)
from .dnbr import classify_dnbr, compute_dnbr, compute_nbr, severity_fractions
from .regional import CWFISAdapter, INPEFireEventsAdapter, RegionalQuery, WFIGSAdapter

__all__ = [
    "compute_nbr",
    "compute_dnbr",
    "classify_dnbr",
    "severity_fractions",
    "can_promote_to_confirmed",
    "promote_anchor_to_confirmed",
    "assert_not_fake_confirmed",
    "WFIGSAdapter",
    "CWFISAdapter",
    "INPEFireEventsAdapter",
    "RegionalQuery",
]
