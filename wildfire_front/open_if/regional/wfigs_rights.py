"""Documented research-use policy and publication guard for WFIGS data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import _atomic_write_json, utc_now

WFIGS_RIGHTS_SCHEMA = "wfd_wfigs_rights_policy_v1"
WFIGS_RIGHTS_POLICY_ID = "nifc-wfigs-public-research-no-redistribution-v1"
WFIGS_ITEM_ID = "7fa2437e625d49f7af1017c8617b68c1"
WFIGS_ITEM_URL = f"https://www.arcgis.com/sharing/rest/content/items/{WFIGS_ITEM_ID}"
WFIGS_DOI_COPYRIGHT_URL = "https://www.doi.gov/copyright"

PUBLICATION_ALLOWED = frozenset(
    {
        "aggregate_metrics",
        "code",
        "configuration",
        "methodology",
        "plots",
    }
)
PUBLICATION_BLOCKED = frozenset(
    {
        "checkpoint",
        "derived_dataset",
        "geometry",
        "raw_data",
        "tensor",
        "tile",
    }
)


class WFIGSPublicationBlocked(PermissionError):
    """Raised when an artifact is outside the approved research publication policy."""


def wfigs_rights_summary(*, event_count: int | None = None) -> dict[str, Any]:
    """Return the auditable policy used by local, non-commercial WFIGS research."""

    summary: dict[str, Any] = {
        "schema": WFIGS_RIGHTS_SCHEMA,
        "policy_id": WFIGS_RIGHTS_POLICY_ID,
        "policy_checked_at": "2026-08-19",
        "source_item_id": WFIGS_ITEM_ID,
        "source_item_url": WFIGS_ITEM_URL,
        "owner": "NIFC_Authoritative",
        "access": "public",
        "explicit_reuse_licence": None,
        "license_info_is_disclaimer": True,
        "internal_noncommercial_research_allowed": True,
        "internal_noncommercial_training_allowed": True,
        "commercial_use_authorized": False,
        "raw_data_redistribution_allowed": False,
        "derived_dataset_redistribution_allowed": False,
        "checkpoint_publication_allowed": False,
        "rights_resolved_for_internal_noncommercial_training": True,
        "rights_resolved_for_training_and_redistribution": False,
        "publication_allowed": sorted(PUBLICATION_ALLOWED),
        "publication_blocked": sorted(PUBLICATION_BLOCKED),
        "evidence": {
            "arcgis_item": WFIGS_ITEM_URL,
            "doi_copyright_policy": WFIGS_DOI_COPYRIGHT_URL,
            "arcgis_access_public": True,
            "scientific_use_addressed_by_disclaimer": True,
            "arcgis_terms_of_use_present": False,
        },
        "basis": (
            "Project policy permits internal non-commercial scientific use because the "
            "NIFC item is public and its disclaimer expressly addresses scientific and "
            "aggregate use. No affirmative redistribution licence was found, so public "
            "release of source data, derived datasets, tensors, or checkpoints remains blocked."
        ),
        "not_legal_advice": True,
    }
    if event_count is not None:
        summary.update(
            {
                "n_eventos_habilitados_investigacion_interna": int(event_count),
                "n_eventos_pendientes_revision_redistribucion": int(event_count),
            }
        )
    return summary


def assert_wfigs_publication_allowed(artifact_kind: str) -> None:
    """Fail closed unless an artifact kind is approved for public release."""

    normalized = str(artifact_kind).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in PUBLICATION_ALLOWED:
        return
    if normalized in PUBLICATION_BLOCKED:
        reason = "explicitly blocked until redistribution/publication rights are confirmed"
    else:
        reason = "not present in the allow-list"
    raise WFIGSPublicationBlocked(
        f"WFIGS artifact kind {artifact_kind!r} is {reason}; "
        f"allowed kinds: {', '.join(sorted(PUBLICATION_ALLOWED))}"
    )


def refresh_wfigs_rights_artifacts(root: Path) -> dict[str, Any]:
    """Migrate existing WFIGS manifests without recomputing geometry or network data."""

    root = Path(root)
    inventory_path = root / "temporal_pairs" / "INVENTORY.json"
    if not inventory_path.is_file():
        raise FileNotFoundError(f"WFIGS temporal-pair inventory not found: {inventory_path}")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    event_count = int(inventory.get("n_eventos_descargados") or 0)
    rights = wfigs_rights_summary(event_count=event_count)
    inventory["source_item_id"] = WFIGS_ITEM_ID
    inventory["derechos_resueltos"] = rights
    inventory.setdefault("claims", {}).update(
        {
            "training_allowed_for_internal_noncommercial_research": True,
            "training_blocked_until_rights_resolved": False,
            "raw_or_derived_data_publication_blocked": True,
        }
    )
    inventory["rights_policy_refreshed_at"] = utc_now()
    _atomic_write_json(inventory_path, inventory)
    _atomic_write_json(root / "RIGHTS_POLICY.json", rights)
    _atomic_write_json(root / "temporal_pairs" / "RIGHTS_POLICY.json", rights)

    updated: list[str] = [
        str(inventory_path),
        str(root / "RIGHTS_POLICY.json"),
        str(root / "temporal_pairs" / "RIGHTS_POLICY.json"),
    ]
    enrichment_path = root / "enrichment" / "INVENTORY.json"
    if enrichment_path.is_file():
        enrichment = json.loads(enrichment_path.read_text(encoding="utf-8"))
        enrichment["rights"] = {
            **wfigs_rights_summary(),
            "training_blocked_by_wfigs_rights": False,
            "current_artifact_contains_metadata_only": True,
        }
        enrichment["rights_policy_refreshed_at"] = utc_now()
        _atomic_write_json(enrichment_path, enrichment)
        updated.append(str(enrichment_path))

    baseline_path = root / "ml" / "GEOMETRY_BASELINE.json"
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        claims = baseline.setdefault("claims", {})
        claims.pop("wfigs_training_rights_resolved", None)
        claims.update(
            {
                "wfigs_internal_noncommercial_training_allowed": True,
                "wfigs_raw_or_derived_data_publication_blocked": True,
            }
        )
        baseline["rights_policy_refreshed_at"] = utc_now()
        _atomic_write_json(baseline_path, baseline)
        updated.append(str(baseline_path))

    return {
        "schema": "wfd_wfigs_rights_refresh_v1",
        "root": str(root),
        "event_count": event_count,
        "updated": updated,
        "geometry_pairs_or_splits_recomputed": False,
        "policy": rights,
    }


__all__ = [
    "PUBLICATION_ALLOWED",
    "PUBLICATION_BLOCKED",
    "WFIGS_ITEM_ID",
    "WFIGS_ITEM_URL",
    "WFIGSPublicationBlocked",
    "WFIGS_RIGHTS_POLICY_ID",
    "WFIGS_RIGHTS_SCHEMA",
    "assert_wfigs_publication_allowed",
    "refresh_wfigs_rights_artifacts",
    "wfigs_rights_summary",
]
