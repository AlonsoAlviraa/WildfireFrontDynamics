"""Audit WFIGS daily observations into event-disjoint temporal pairs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pyproj import Geod
from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .base import _atomic_write_json, parse_time, sha256_bytes, utc_now, validated_geometry
from .wfigs_rights import wfigs_rights_summary

PAIR_SCHEMA = "wfd_regional_temporal_pairs_v1"
INVENTORY_SCHEMA = "wfd_wfigs_pair_inventory_v1"
SPLIT_SCHEMA = "wfd_event_disjoint_splits_v1"
STRICT_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
EVENT_YEAR_RE = re.compile(r"^(\d{4})-")
GEOD = Geod(ellps="WGS84")
FEATURES_ARRAY_RE = re.compile(r'"features"\s*:\s*\[')


def _iter_geojson_features(path: Path, *, chunk_size: int = 4 * 1024 * 1024):
    """Yield a FeatureCollection incrementally without loading its geometries twice."""

    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                raise ValueError(f"GeoJSON features array not found: {path}")
            buffer += chunk
            match = FEATURES_ARRAY_RE.search(buffer)
            if match is not None:
                buffer = buffer[match.end() :]
                break
            if len(buffer) > chunk_size * 2:
                buffer = buffer[-chunk_size:]

        while True:
            buffer = buffer.lstrip()
            if buffer.startswith(","):
                buffer = buffer[1:].lstrip()
            if buffer.startswith("]"):
                return
            try:
                feature, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError as exc:
                chunk = handle.read(chunk_size)
                if not chunk:
                    raise ValueError(f"truncated GeoJSON feature in {path}") from exc
                buffer += chunk
                continue
            buffer = buffer[end:]
            if isinstance(feature, dict):
                yield feature


def _area_ha(geometry: BaseGeometry) -> float:
    area_m2, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(float(area_m2)) / 10_000.0


def _centroid_distance_km(first: BaseGeometry, second: BaseGeometry) -> float:
    c0 = first.centroid
    c1 = second.centroid
    _, _, distance_m = GEOD.inv(c0.x, c0.y, c1.x, c1.y)
    return abs(float(distance_m)) / 1000.0


def _strict_time(value: Any) -> datetime | None:
    raw = str(value or "")
    if not STRICT_UTC_RE.fullmatch(raw):
        return None
    return parse_time(raw)


def _event_year(event_id: str) -> int | None:
    match = EVENT_YEAR_RE.match(event_id)
    return int(match.group(1)) if match else None


def _bucket(delta_hours: float) -> str | None:
    if 6.0 <= delta_hours < 12.0:
        return "6_12h"
    if 12.0 <= delta_hours < 24.0:
        return "12_24h"
    if 24.0 <= delta_hours <= 48.0:
        return "24_48h"
    return None


def _split_for_event(event_id: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{event_id}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / float(2**64)
    if fraction < 0.70:
        return "train"
    if fraction < 0.85:
        return "validation"
    return "test"


def _observation_rejection(feature: dict[str, Any], *, as_of: datetime) -> str | None:
    props = feature.get("properties") or {}
    if props.get("source_id") != "us_wfigs_daily_perimeters":
        return "source_not_wfigs_daily"
    if props.get("geometry_semantics") != "wildfire_daily_perimeter":
        semantic = str(props.get("geometry_semantics") or "unknown")
        if "scar" in semantic:
            return "final_scar_rejected"
        if "m3" in semantic or "buffer" in semantic:
            return "m3_proxy_rejected"
        if "hotspot" in semantic or "thermal" in semantic:
            return "hotspot_rejected"
        return "not_daily_perimeter"
    if props.get("candidate_progression_label") is not True:
        return "not_progression_candidate"
    event_id = str(props.get("event_id") or "")
    year = _event_year(event_id)
    if year is None:
        return "event_id_without_year"
    observed = _strict_time(props.get("observed_at"))
    if observed is None:
        return "timestamp_ambiguous_or_not_utc"
    if observed > as_of + timedelta(days=1):
        return "timestamp_in_future"
    if observed.year != year:
        return "timestamp_incident_year_mismatch"
    upstream = props.get("upstream_properties") or {}
    if str(upstream.get("poly_FeatureCategory") or "") != "Wildfire Daily Fire Perimeter":
        return "upstream_category_not_daily"
    if str(upstream.get("attr_IncidentTypeCategory") or "WF") != "WF":
        return "incident_not_wildfire"
    geometry, _ = validated_geometry(feature.get("geometry"))
    if geometry is None or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        return "invalid_or_non_polygon_geometry"
    try:
        if _area_ha(shape(geometry)) < 1.0:
            return "area_lt_1ha"
    except (TypeError, ValueError):
        return "geometry_area_failed"
    return None


def _observation_record(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") or {}
    checked_geometry, _ = validated_geometry(feature.get("geometry"))
    if checked_geometry is None:
        raise ValueError("observation geometry was not valid after validation")
    geometry = shape(checked_geometry)
    upstream = props.get("upstream_properties") or {}
    return {
        "observation_id": str(props["observation_id"]),
        "event_id": str(props["event_id"]),
        "observed_at": str(props["observed_at"]),
        "observed_dt": _strict_time(props["observed_at"]),
        "geometry": geometry,
        "area_ha": _area_ha(geometry),
        "region": str(upstream.get("attr_GACC") or "UNKNOWN"),
        "state": str(upstream.get("attr_POOState") or "UNKNOWN"),
        "incident_name": upstream.get("poly_IncidentName") or upstream.get("attr_IncidentName"),
        "map_method": upstream.get("poly_MapMethod"),
        "source_acres": upstream.get("poly_GISAcres") or upstream.get("poly_Acres_AutoCalc"),
    }


def _pair_metrics(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    geometry0: BaseGeometry = first["geometry"]
    geometry1: BaseGeometry = second["geometry"]
    intersection = geometry0.intersection(geometry1)
    union = geometry0.union(geometry1)
    intersection_ha = _area_ha(intersection) if not intersection.is_empty else 0.0
    union_ha = _area_ha(union) if not union.is_empty else 0.0
    area0 = float(first["area_ha"])
    area1 = float(second["area_ha"])
    delta_hours = (second["observed_dt"] - first["observed_dt"]).total_seconds() / 3600.0
    growth = area1 - area0
    equivalent_radius_km = math.sqrt(max(area1, 0.0) * 10_000.0 / math.pi) / 1000.0
    centroid_limit_km = max(25.0, 4.0 * equivalent_radius_km)
    centroid_shift_km = _centroid_distance_km(geometry0, geometry1)
    return {
        "delta_hours": round(delta_hours, 6),
        "delta_bucket": _bucket(delta_hours),
        "area_t0_ha": round(area0, 6),
        "area_t1_ha": round(area1, 6),
        "growth_ha": round(growth, 6),
        "growth_pct_t0": round(100.0 * growth / area0, 6) if area0 else None,
        "intersection_ha": round(intersection_ha, 6),
        "union_ha": round(union_ha, 6),
        "iou": round(intersection_ha / union_ha, 8) if union_ha else None,
        "containment_t0": round(intersection_ha / area0, 8) if area0 else None,
        "area_ratio_t1_t0": round(area1 / area0, 8) if area0 else None,
        "centroid_shift_km": round(centroid_shift_km, 6),
        "centroid_limit_km": round(centroid_limit_km, 6),
    }


def _pair_reasons(metrics: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    delta = float(metrics["delta_hours"])
    if delta <= 0:
        reasons.append("non_positive_delta")
    elif delta < 6.0:
        reasons.append("delta_lt_6h")
    elif delta > 48.0:
        reasons.append("delta_gt_48h")
    if float(metrics.get("intersection_ha") or 0.0) <= 0:
        reasons.append("no_spatial_overlap")
    containment = float(metrics.get("containment_t0") or 0.0)
    if containment < 0.75:
        reasons.append("t0_containment_lt_75pct")
    area_ratio = float(metrics.get("area_ratio_t1_t0") or 0.0)
    if area_ratio < 0.90:
        reasons.append("area_shrink_gt_10pct")
    if float(metrics.get("centroid_shift_km") or 0.0) > float(
        metrics.get("centroid_limit_km") or 25.0
    ):
        reasons.append("centroid_shift_inconsistent")
    return sorted(set(reasons))


class RegionalTemporalPairBuilder:
    """Build honest WFIGS temporal pairs and deterministic event splits."""

    def __init__(
        self,
        *,
        observations_path: Path,
        output_root: Path,
        as_of: datetime | None = None,
        split_salt: str = "wfd-wfigs-event-split-v1",
    ) -> None:
        self.observations_path = Path(observations_path)
        self.output_root = Path(output_root)
        self.as_of = as_of or datetime.now(UTC)
        if self.as_of.tzinfo is None:
            self.as_of = self.as_of.replace(tzinfo=UTC)
        self.split_salt = split_salt

    def build(self) -> dict[str, Any]:
        all_event_ids: set[str] = set()
        observation_count = 0
        observation_rejections: list[dict[str, str]] = []
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for feature in _iter_geojson_features(self.observations_path):
            observation_count += 1
            props = feature.get("properties") or {}
            event_id = str(props.get("event_id") or "")
            if event_id:
                all_event_ids.add(event_id)
            reason = _observation_rejection(feature, as_of=self.as_of)
            if reason:
                observation_rejections.append(
                    {
                        "observation_id": str(props.get("observation_id") or ""),
                        "event_id": str(props.get("event_id") or ""),
                        "reason": reason,
                    }
                )
                continue
            record = _observation_record(feature)
            grouped[record["event_id"]].append(record)

        valid_by_event: dict[str, list[dict[str, Any]]] = {}
        for event_id, records in grouped.items():
            by_time: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for record in records:
                by_time[record["observed_at"]].append(record)
            selected: list[dict[str, Any]] = []
            for observed_at, duplicates in by_time.items():
                ordered = sorted(
                    duplicates,
                    key=lambda record: (record["area_ha"], record["observation_id"]),
                    reverse=True,
                )
                selected.append(ordered[0])
                for duplicate in ordered[1:]:
                    observation_rejections.append(
                        {
                            "observation_id": duplicate["observation_id"],
                            "event_id": event_id,
                            "reason": "duplicate_event_timestamp",
                            "kept_observation_id": ordered[0]["observation_id"],
                            "observed_at": observed_at,
                        }
                    )
            valid_by_event[event_id] = sorted(selected, key=lambda record: record["observed_dt"])

        approved_pairs: list[dict[str, Any]] = []
        rejected_pairs: list[dict[str, Any]] = []
        for event_id, records in sorted(valid_by_event.items()):
            for first, second in zip(records, records[1:], strict=False):
                identity = {
                    "event_id": event_id,
                    "t0": first["observation_id"],
                    "t1": second["observation_id"],
                }
                pair_id = f"wfigs-pair-{sha256_bytes(json.dumps(identity, sort_keys=True).encode())[:20]}"
                try:
                    metrics = _pair_metrics(first, second)
                    reasons = _pair_reasons(metrics)
                except (GEOSException, TypeError, ValueError, OverflowError):
                    delta_hours = (
                        second["observed_dt"] - first["observed_dt"]
                    ).total_seconds() / 3600.0
                    metrics = {
                        "delta_hours": round(delta_hours, 6),
                        "delta_bucket": _bucket(delta_hours),
                    }
                    reasons = ["geometry_operation_failed"]
                pair = {
                    "pair_id": pair_id,
                    "event_id": event_id,
                    "year": _event_year(event_id),
                    "region": first["region"] if first["region"] == second["region"] else "MIXED",
                    "state": first["state"] if first["state"] == second["state"] else "MIXED",
                    "incident_name": first["incident_name"] or second["incident_name"],
                    "t0_observation_id": first["observation_id"],
                    "t1_observation_id": second["observation_id"],
                    "t0": first["observed_at"],
                    "t1": second["observed_at"],
                    "metrics": metrics,
                    "map_methods": [first["map_method"], second["map_method"]],
                    "rejection_reasons": reasons,
                    "approved": not reasons,
                }
                if reasons:
                    rejected_pairs.append(pair)
                else:
                    approved_pairs.append(pair)

        accepted_event_ids = sorted({pair["event_id"] for pair in approved_pairs})
        split_by_event = {
            event_id: _split_for_event(event_id, self.split_salt)
            for event_id in accepted_event_ids
        }
        for pair in approved_pairs:
            pair["split"] = split_by_event[pair["event_id"]]
        split_sets = {
            split: sorted(event for event, assigned in split_by_event.items() if assigned == split)
            for split in ("train", "validation", "test")
        }
        assert not (set(split_sets["train"]) & set(split_sets["validation"]))
        assert not (set(split_sets["train"]) & set(split_sets["test"]))
        assert not (set(split_sets["validation"]) & set(split_sets["test"]))

        pair_rejection_counts = Counter(
            reason for pair in rejected_pairs for reason in pair["rejection_reasons"]
        )
        observation_rejection_counts = Counter(row["reason"] for row in observation_rejections)
        bucket_counts = Counter(pair["metrics"]["delta_bucket"] for pair in approved_pairs)
        distribution: dict[str, dict[str, dict[str, int]]] = {}
        for dimension in ("region", "state", "year"):
            event_values: dict[str, set[str]] = defaultdict(set)
            pair_counts: Counter[str] = Counter()
            for pair in approved_pairs:
                key = str(pair.get(dimension) or "UNKNOWN")
                event_values[key].add(pair["event_id"])
                pair_counts[key] += 1
            distribution[dimension] = {
                key: {
                    "events": len(event_values[key]),
                    "approved_pairs": pair_counts[key],
                }
                for key in sorted(event_values)
            }

        rights = wfigs_rights_summary(event_count=len(all_event_ids))
        inventory = {
            "schema": INVENTORY_SCHEMA,
            "generated_at": utc_now(),
            "source": "WFIGS Daily Perimeters Public",
            "source_item_id": rights["source_item_id"],
            "observations_file": str(self.observations_path),
            "n_eventos_descargados": len(all_event_ids),
            "n_observaciones_descargadas": observation_count,
            "n_observaciones_validas_deduplicadas": sum(len(v) for v in valid_by_event.values()),
            "n_eventos_con_2_mas_perimetros": sum(
                len(records) >= 2 for records in valid_by_event.values()
            ),
            "n_eventos_con_pares_aprobados": len(accepted_event_ids),
            "n_pares_aprobados": len(approved_pairs),
            "n_pares_6_12h": bucket_counts["6_12h"],
            "n_pares_12_24h": bucket_counts["12_24h"],
            "n_pares_24_48h": bucket_counts["24_48h"],
            "n_pares_rechazados": len(rejected_pairs),
            "n_pares_rechazados_y_motivo": dict(sorted(pair_rejection_counts.items())),
            "n_observaciones_rechazadas_y_motivo": dict(
                sorted(observation_rejection_counts.items())
            ),
            "distribucion_geografica": distribution,
            "derechos_resueltos": rights,
            "criterios": {
                "delta_buckets_hours": {
                    "6_12h": "[6,12)",
                    "12_24h": "[12,24)",
                    "24_48h": "[24,48]",
                },
                "minimum_t0_containment": 0.75,
                "minimum_area_ratio_t1_t0": 0.90,
                "minimum_area_ha": 1.0,
                "strict_utc_timestamp": True,
                "adjacent_pairs_only": True,
                "final_scars_m3_hotspots_rejected": True,
            },
            "split_counts": {
                split: {
                    "events": len(events),
                    "pairs": sum(pair.get("split") == split for pair in approved_pairs),
                }
                for split, events in split_sets.items()
            },
            "claims": {
                "pairs_are_candidate_progression_labels": True,
                "pairs_are_ground_truth": False,
                "event_disjoint_splits": True,
                "tile_disjoint_only": False,
                "training_allowed_for_internal_noncommercial_research": True,
                "training_blocked_until_rights_resolved": False,
                "raw_or_derived_data_publication_blocked": True,
            },
        }

        self.output_root.mkdir(parents=True, exist_ok=True)
        pairs_document = {
            "schema": PAIR_SCHEMA,
            "generated_at": inventory["generated_at"],
            "pairs": approved_pairs,
        }
        rejected_document = {
            "schema": PAIR_SCHEMA,
            "generated_at": inventory["generated_at"],
            "pairs": rejected_pairs,
            "observation_rejections": observation_rejections,
        }
        splits_document = {
            "schema": SPLIT_SCHEMA,
            "generated_at": inventory["generated_at"],
            "salt_sha256": sha256_bytes(self.split_salt.encode()),
            "ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
            "events": split_sets,
            "event_to_split": split_by_event,
            "assertions": {
                "pair_event_single_split": True,
                "train_validation_overlap": 0,
                "train_test_overlap": 0,
                "validation_test_overlap": 0,
            },
        }
        _atomic_write_json(self.output_root / "INVENTORY.json", inventory)
        _atomic_write_json(self.output_root / "RIGHTS_POLICY.json", rights)
        _atomic_write_json(self.output_root / "PAIRS.json", pairs_document)
        _atomic_write_json(self.output_root / "REJECTED.json", rejected_document)
        _atomic_write_json(self.output_root / "SPLITS.json", splits_document)
        return inventory


__all__ = [
    "INVENTORY_SCHEMA",
    "PAIR_SCHEMA",
    "SPLIT_SCHEMA",
    "RegionalTemporalPairBuilder",
]
