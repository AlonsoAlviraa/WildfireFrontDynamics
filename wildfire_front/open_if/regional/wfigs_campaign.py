"""Stratified, resumable WFIGS tensor pilot across CONUS regions."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .base import _atomic_write_json, utc_now
from .pair_enrichment import _inside_hrrr_conus
from .wfigs_materialize import WFIGSEOMaterializer
from .wfigs_rights import wfigs_rights_summary

CAMPAIGN_SCHEMA = "wfd_wfigs_tensor_campaign_v1"
REGION_DIRECTORIES = {
    "AICC": "alaska",
    "EACC": "eastern",
    "GBCC": "great_basin",
    "NRCC": "northern_rockies",
    "NWCC": "northwest",
    "ONCC": "northern_california",
    "OSCC": "southern_california",
    "RMCC": "rocky_mountain",
    "SACC": "southern",
    "SWCC": "southwest",
}


def _eligible_scene(enriched: dict[str, Any]) -> dict[str, Any] | None:
    sentinel = ((enriched.get("eo") or {}).get("sentinel2") or {})
    for candidate in sentinel.get("candidates") or []:
        if candidate.get("stac_created_at_or_before_t0") is True:
            return candidate
    return None


def select_campaign_pairs(
    pairs: list[dict[str, Any]],
    enrichment: dict[str, dict[str, Any]],
    *,
    split: str,
    events_per_region: int,
    grid_span_m: float = 15_360.0,
) -> list[dict[str, Any]]:
    """Select one pair per event, balanced by GACC, without target-derived ranking."""

    candidates: list[tuple[str, float, str, dict[str, Any]]] = []
    for pair in pairs:
        if pair.get("approved") is not True or pair.get("split") != split:
            continue
        enriched = enrichment.get(str(pair.get("pair_id")))
        if enriched is None or not _inside_hrrr_conus(enriched.get("t0_bbox")):
            continue
        west, south, east, north = (
            float(value) for value in enriched["t0_bbox"]
        )
        latitude = (south + north) / 2.0
        width_m = (east - west) * 111_320.0 * max(math.cos(math.radians(latitude)), 0.1)
        height_m = (north - south) * 110_540.0
        # Input-only eligibility: reserve 10% context around t0. Future t1 is
        # still used solely as a post-selection truncation QA check.
        if max(width_m, height_m) > grid_span_m * 0.9:
            continue
        weather = enriched.get("weather") or {}
        if weather.get("status") != "resolved" or weather.get("available_by_t0_verified") is not True:
            continue
        scene = _eligible_scene(enriched)
        if scene is None:
            continue
        # Cloud is an input-availability property. Growth, t1 area and overlap
        # are intentionally absent from this selection score.
        cloud = float(scene.get("cloud_cover_pct") or 100.0)
        candidates.append((str(pair.get("region")), cloud, str(pair["pair_id"]), pair))

    selected: list[dict[str, Any]] = []
    region_events: dict[str, set[str]] = defaultdict(set)
    for region, _cloud, _pair_id, pair in sorted(candidates):
        if region not in REGION_DIRECTORIES or len(region_events[region]) >= events_per_region:
            continue
        event_id = str(pair["event_id"])
        if event_id in region_events[region]:
            continue
        region_events[region].add(event_id)
        selected.append(pair)
    return selected


class WFIGSTensorCampaign:
    """Run small materialization groups and merge their auditable manifests."""

    def __init__(
        self,
        *,
        history_root: Path,
        output_root: Path,
        split: str = "train",
        events_per_region: int = 2,
        size: int = 256,
        resolution_m: float = 60.0,
        min_valid_fraction: float = 0.70,
    ) -> None:
        if events_per_region <= 0:
            raise ValueError("events_per_region must be positive")
        self.history_root = Path(history_root)
        self.output_root = Path(output_root)
        self.split = split
        self.events_per_region = events_per_region
        self.size = size
        self.resolution_m = resolution_m
        self.min_valid_fraction = min_valid_fraction

    def run(self) -> dict[str, Any]:
        pairs_path = self.history_root / "temporal_pairs/PAIRS.json"
        enrichment_path = self.history_root / "enrichment/PAIR_ENRICHMENT.json"
        pairs = json.loads(pairs_path.read_text(encoding="utf-8")).get("pairs") or []
        enriched_rows = json.loads(enrichment_path.read_text(encoding="utf-8")).get("pairs") or []
        enrichment = {str(row["pair_id"]): row for row in enriched_rows}
        selected = select_campaign_pairs(
            pairs,
            enrichment,
            split=self.split,
            events_per_region=self.events_per_region,
            grid_span_m=self.size * self.resolution_m,
        )
        groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
        for pair in selected:
            groups[(int(pair["year"]), str(pair["region"]))].append(pair)

        all_rows: list[dict[str, Any]] = []
        group_rows: list[dict[str, Any]] = []
        self.output_root.mkdir(parents=True, exist_ok=True)
        for (year, region), group in sorted(groups.items()):
            directory = REGION_DIRECTORIES[region]
            observations = self.history_root / f"partitions/{year}/{directory}/normalized.geojson"
            group_root = self.output_root / f"groups/{year}/{directory}"
            if not observations.is_file():
                group_rows.append(
                    {
                        "year": year,
                        "region": region,
                        "status": "failed",
                        "reason": "partition_missing",
                    }
                )
                continue
            pair_ids = tuple(str(pair["pair_id"]) for pair in group)
            try:
                inventory = WFIGSEOMaterializer(
                    pairs_path=pairs_path,
                    enrichment_path=enrichment_path,
                    observations_path=observations,
                    output_root=group_root,
                    limit=len(pair_ids),
                    splits=(self.split,),
                    pair_ids=pair_ids,
                    size=self.size,
                    resolution_m=self.resolution_m,
                    min_valid_fraction=self.min_valid_fraction,
                ).build()
                rows = inventory["rows"]
                for row in rows:
                    if row.get("relative_path"):
                        row["campaign_relative_path"] = (
                            Path(f"groups/{year}/{directory}") / row["relative_path"]
                        ).as_posix()
                all_rows.extend(rows)
                group_rows.append(
                    {
                        "year": year,
                        "region": region,
                        "status": "complete",
                        "counts": inventory["counts"],
                    }
                )
            except Exception as exc:
                group_rows.append(
                    {
                        "year": year,
                        "region": region,
                        "status": "failed",
                        "reason": type(exc).__name__,
                    }
                )
            _atomic_write_json(
                self.output_root / "STATE.json",
                {
                    "schema": CAMPAIGN_SCHEMA,
                    "updated_at": utc_now(),
                    "groups_complete": len(group_rows),
                    "groups_total": len(groups),
                    "rows": group_rows,
                },
            )

        reasons = Counter(str(row.get("reason")) for row in all_rows if row["status"] != "materialized")
        inventory = {
            "schema": CAMPAIGN_SCHEMA,
            "generated_at": utc_now(),
            "configuration": {
                "split": self.split,
                "events_per_region": self.events_per_region,
                "one_pair_per_event": True,
                "selection_uses_t1_or_growth": False,
                "size": self.size,
                "resolution_m": self.resolution_m,
                "min_valid_fraction": self.min_valid_fraction,
            },
            "counts": {
                "pairs_selected": len(selected),
                "events_selected": len({str(pair["event_id"]) for pair in selected}),
                "pairs_materialized": sum(row["status"] == "materialized" for row in all_rows),
                "pairs_rejected": sum(row["status"] != "materialized" for row in all_rows),
                "pairs_training_ready": sum(row.get("training_ready") is True for row in all_rows),
                "rejection_reasons": dict(sorted(reasons.items())),
                "regions_selected": dict(sorted(Counter(str(pair["region"]) for pair in selected).items())),
            },
            "groups": group_rows,
            "rows": all_rows,
            "rights": wfigs_rights_summary(),
            "claims": {
                "internal_noncommercial_training_allowed": True,
                "raw_or_derived_tensor_publication_allowed": False,
                "external_test_evaluated": False,
            },
        }
        _atomic_write_json(self.output_root / "INVENTORY.json", inventory)
        return inventory


__all__ = ["CAMPAIGN_SCHEMA", "REGION_DIRECTORIES", "WFIGSTensorCampaign", "select_campaign_pairs"]
