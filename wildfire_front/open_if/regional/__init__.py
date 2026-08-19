"""Operational regional fire-data adapters."""

from __future__ import annotations

from .base import (
    ADAPTER_VERSION,
    INDEX_SCHEMA,
    OBSERVATION_SCHEMA,
    SNAPSHOT_SCHEMA,
    STATE_SCHEMA,
    AdapterError,
    BaseRegionalFireAdapter,
    FetchPayload,
    NormalizationResult,
    RegionalQuery,
)
from .cwfis import CWFIS_LAYERS, CWFISAdapter
from .inpe import INPEFireEventsAdapter
from .wfigs import WFIGSAdapter
from .wfigs_rights import (
    WFIGSPublicationBlocked,
    assert_wfigs_publication_allowed,
    refresh_wfigs_rights_artifacts,
    wfigs_rights_summary,
)

ADAPTERS: dict[str, type[BaseRegionalFireAdapter]] = {
    "wfigs": WFIGSAdapter,
    "cwfis": CWFISAdapter,
    "inpe": INPEFireEventsAdapter,
}


def build_adapter(
    provider: str, *, timeout: float = 60.0, max_bytes: int = 64 * 1024 * 1024
) -> BaseRegionalFireAdapter:
    try:
        adapter_type = ADAPTERS[provider]
    except KeyError as exc:
        allowed = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unknown provider {provider!r}; choose: {allowed}") from exc
    return adapter_type(timeout=timeout, max_bytes=max_bytes)


__all__ = [
    "ADAPTERS",
    "ADAPTER_VERSION",
    "CWFIS_LAYERS",
    "INDEX_SCHEMA",
    "OBSERVATION_SCHEMA",
    "SNAPSHOT_SCHEMA",
    "STATE_SCHEMA",
    "AdapterError",
    "BaseRegionalFireAdapter",
    "CWFISAdapter",
    "FetchPayload",
    "INPEFireEventsAdapter",
    "NormalizationResult",
    "RegionalQuery",
    "WFIGSAdapter",
    "WFIGSPublicationBlocked",
    "assert_wfigs_publication_allowed",
    "build_adapter",
    "refresh_wfigs_rights_artifacts",
    "wfigs_rights_summary",
]
