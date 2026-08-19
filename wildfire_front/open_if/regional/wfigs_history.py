"""Resumable year/GACC harvest for WFIGS daily fire perimeters."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .base import (
    ADAPTER_VERSION,
    AdapterError,
    FetchPayload,
    NormalizationResult,
    RegionalQuery,
    _atomic_write_bytes,
    _atomic_write_json,
    canonical_json,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .wfigs import WFIGS_FIELDS, WFIGSAdapter

WFIGS_DAILY_LAYER_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/"
    "WFIGS_Daily_Perimeters_Public/FeatureServer/0"
)
HARVEST_SCHEMA = "wfd_wfigs_history_harvest_v1"
PARTITION_SCHEMA = "wfd_wfigs_history_partition_v1"

GACC_REGIONS: dict[str, str] = {
    "alaska": "AICC",
    "eastern": "EACC",
    "great_basin": "GBCC",
    "northern_california": "ONCC",
    "northern_rockies": "NRCC",
    "northwest": "NWCC",
    "rocky_mountain": "RMCC",
    "southern": "SACC",
    "southern_california": "OSCC",
    "southwest": "SWCC",
}


class WFIGSDailyPerimetersAdapter(WFIGSAdapter):
    """Normalizer identity for the WFIGS daily/progression service."""

    source_id = "us_wfigs_daily_perimeters"
    provider = "National Interagency Fire Center / WFIGS Daily Perimeters"

    @property
    def honesty(self) -> dict[str, Any]:
        return {
            "daily_perimeters_are_candidate_progression_not_ground_truth": True,
            "duplicate_same_event_timestamps_require_resolution": True,
            "future_or_incident_year_mismatched_timestamps_rejected": True,
            "same_event_temporal_pair_and_leakage_audit_required": True,
            "not_validated_tactical_dispatch": True,
        }


@dataclass(frozen=True)
class HarvestPartition:
    year: int
    region: str
    gacc: str

    @property
    def key(self) -> str:
        return f"{self.year}/{self.region}"


def _year_bounds(year: int, *, as_of: date) -> tuple[str, str]:
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), as_of)
    return start.isoformat(), end.isoformat()


def _partition_where(partition: HarvestPartition, *, as_of: date) -> str:
    start, end = _year_bounds(partition.year, as_of=as_of)
    escaped_gacc = partition.gacc.replace("'", "''")
    incident_prefix = f"{partition.year}-%"
    return " AND ".join(
        [
            "poly_FeatureCategory = 'Wildfire Daily Fire Perimeter'",
            "attr_IncidentTypeCategory = 'WF'",
            "(poly_DeleteThis IS NULL OR poly_DeleteThis <> 'Yes')",
            "(poly_FeatureAccess IS NULL OR poly_FeatureAccess = 'Public')",
            "(poly_IsVisible IS NULL OR poly_IsVisible = 'Yes')",
            f"attr_GACC = '{escaped_gacc}'",
            f"attr_UniqueFireIdentifier LIKE '{incident_prefix}'",
            f"poly_PolygonDateTime >= TIMESTAMP '{start} 00:00:00'",
            f"poly_PolygonDateTime <= TIMESTAMP '{end} 23:59:59'",
        ]
    )


def _partition_url(
    partition: HarvestPartition,
    *,
    as_of: date,
    count_only: bool = False,
    offset: int = 0,
    page_size: int = 2000,
) -> str:
    params: dict[str, str | int] = {
        "where": _partition_where(partition, as_of=as_of),
        "f": "json" if count_only else "geojson",
    }
    if count_only:
        params["returnCountOnly"] = "true"
    else:
        params.update(
            {
                "outFields": WFIGS_FIELDS,
                "returnGeometry": "true",
                "outSR": "4326",
                "geometryPrecision": "6",
                "orderByFields": "poly_PolygonDateTime ASC,OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
        )
    return f"{WFIGS_DAILY_LAYER_URL}/query?{urlencode(params)}"


class WFIGSHistoricalHarvester:
    """Download WFIGS daily perimeters into resumable year/GACC partitions."""

    def __init__(
        self,
        *,
        output_root: Path,
        timeout: float = 120.0,
        max_bytes: int = 64 * 1024 * 1024,
        page_size: int = 250,
        as_of: date | None = None,
    ) -> None:
        if page_size <= 0 or page_size > 2000:
            raise ValueError("page_size must be in 1..2000")
        self.output_root = Path(output_root)
        self.page_size = int(page_size)
        self.as_of = as_of or datetime.now(UTC).date()
        self.adapter = WFIGSDailyPerimetersAdapter(timeout=timeout, max_bytes=max_bytes)

    def partitions(self, years: list[int], regions: list[str]) -> list[HarvestPartition]:
        unknown = sorted(set(regions) - set(GACC_REGIONS))
        if unknown:
            raise ValueError(f"unknown WFIGS regions: {', '.join(unknown)}")
        current_year = self.as_of.year
        for year in years:
            if year < 2014 or year > current_year:
                raise ValueError(f"WFIGS year must be in 2014..{current_year}: {year}")
        return [
            HarvestPartition(year=year, region=region, gacc=GACC_REGIONS[region])
            for year in sorted(set(years))
            for region in regions
        ]

    def _partition_dir(self, partition: HarvestPartition) -> Path:
        return self.output_root / "partitions" / str(partition.year) / partition.region

    def _count(self, partition: HarvestPartition) -> int:
        url = _partition_url(partition, as_of=self.as_of, count_only=True)
        payload = self.adapter.request(url, name="count.json", accept="application/json")
        try:
            document = json.loads(payload.body.decode("utf-8"))
            return int(document["count"])
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError(f"invalid WFIGS count response for {partition.key}") from exc

    def harvest_partition(
        self, partition: HarvestPartition, *, resume: bool = True
    ) -> dict[str, Any]:
        partition_dir = self._partition_dir(partition)
        manifest_path = partition_dir / "manifest.json"
        if resume and manifest_path.is_file():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("schema") == PARTITION_SCHEMA and existing.get("status") == "complete":
                return {**existing, "resumed": True, "manifest": str(manifest_path)}

        raw_dir = partition_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        retrieved_at = utc_now()
        expected = self._count(partition)
        start, end = _year_bounds(partition.year, as_of=self.as_of)
        query = RegionalQuery(start=start, end=end, limit=max(1, min(100_000, expected + 1)))
        aggregate = NormalizationResult()
        raw_records: list[dict[str, Any]] = []
        offset = 0
        effective_page_size = self.page_size
        while offset < expected:
            count = min(effective_page_size, expected - offset)
            url = _partition_url(
                partition,
                as_of=self.as_of,
                offset=offset,
                page_size=count,
            )
            page_name = f"page_{offset:08d}.geojson"
            raw_path = raw_dir / page_name
            payload: FetchPayload | None = None
            reused = False
            if resume and raw_path.is_file():
                try:
                    existing_body = raw_path.read_bytes()
                    existing_document = json.loads(existing_body.decode("utf-8"))
                    existing_features = existing_document.get("features")
                    if not isinstance(existing_features, list) or not existing_features:
                        raise ValueError("page has no features")
                    payload = FetchPayload(
                        name=page_name,
                        url=url,
                        body=existing_body,
                        content_type="application/geo+json",
                    )
                    raw_document = existing_document
                    reused = True
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    payload = None

            retry_count = 0
            while payload is None:
                try:
                    payload = self.adapter.request(
                        url,
                        name=page_name,
                        accept="application/geo+json,application/json",
                    )
                    raw_document = json.loads(payload.body.decode("utf-8"))
                    if not isinstance(raw_document.get("features"), list):
                        raise AdapterError("WFIGS response has no GeoJSON features array")
                except (AdapterError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    payload = None
                    retry_count += 1
                    if count > 25:
                        effective_page_size = max(25, count // 2)
                        break
                    if retry_count >= 4:
                        raise AdapterError(
                            f"WFIGS page failed after {retry_count} attempts for "
                            f"{partition.key} offset={offset}: {exc}"
                        ) from exc
                    time.sleep(min(10, 2**retry_count))
            if payload is None:
                continue

            received = len(raw_document.get("features") or [])
            raw_path = raw_dir / payload.name
            if not reused:
                _atomic_write_bytes(raw_path, payload.body)
            raw_records.append(
                {
                    "file": str(raw_path.relative_to(partition_dir)).replace("\\", "/"),
                    "url": payload.url,
                    "requested_records": count,
                    "received_records": received,
                    "bytes": len(payload.body),
                    "sha256": sha256_bytes(payload.body),
                    "etag": payload.etag,
                    "last_modified": payload.last_modified,
                    "reused": reused,
                    "retry_count": retry_count,
                }
            )
            page_result = self.adapter.normalize([payload], query, retrieved_at=retrieved_at)
            aggregate.features.extend(page_result.features)
            aggregate.rejected.extend(page_result.rejected)
            if received <= 0:
                break
            offset += received

        by_id: dict[str, dict[str, Any]] = {}
        for feature in aggregate.features:
            observation_id = str((feature.get("properties") or {}).get("observation_id") or "")
            if observation_id:
                by_id[observation_id] = feature
        features = sorted(
            by_id.values(),
            key=lambda feature: (
                str((feature.get("properties") or {}).get("event_id") or ""),
                str((feature.get("properties") or {}).get("observed_at") or ""),
                str((feature.get("properties") or {}).get("observation_id") or ""),
            ),
        )
        normalized = {
            "type": "FeatureCollection",
            "schema": "wfd_fire_observation_v1",
            "source_id": self.adapter.source_id,
            "partition": {
                "year": partition.year,
                "region": partition.region,
                "gacc": partition.gacc,
            },
            "retrieved_at": retrieved_at,
            "features": features,
        }
        normalized_path = partition_dir / "normalized.geojson"
        _atomic_write_json(normalized_path, normalized)
        event_ids = {
            str((feature.get("properties") or {}).get("event_id")) for feature in features
        }
        manifest = {
            "schema": PARTITION_SCHEMA,
            "status": "complete",
            "source_id": self.adapter.source_id,
            "adapter_version": ADAPTER_VERSION,
            "partition": {
                "year": partition.year,
                "region": partition.region,
                "gacc": partition.gacc,
                "start": start,
                "end": end,
            },
            "retrieved_at": retrieved_at,
            "where_sha256": sha256_bytes(
                _partition_where(partition, as_of=self.as_of).encode("utf-8")
            ),
            "counts": {
                "server_count": expected,
                "raw_received": offset,
                "normalized": len(features),
                "rejected": len(aggregate.rejected),
                "events": len(event_ids),
                "effective_page_size": effective_page_size,
            },
            "raw": raw_records,
            "normalized": {
                "file": "normalized.geojson",
            "sha256": sha256_file(normalized_path),
            },
            "rejected": aggregate.rejected[:1000],
            "honesty": self.adapter.honesty,
        }
        _atomic_write_json(manifest_path, manifest)
        return {**manifest, "resumed": False, "manifest": str(manifest_path)}

    def harvest(
        self,
        *,
        years: list[int],
        regions: list[str],
        resume: bool = True,
        continue_on_error: bool = True,
        workers: int = 1,
    ) -> dict[str, Any]:
        if workers <= 0 or workers > 8:
            raise ValueError("workers must be in 1..8")
        started_at = utc_now()
        partition_results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        partitions = self.partitions(years, regions)
        if workers == 1:
            for partition in partitions:
                try:
                    result = self.harvest_partition(partition, resume=resume)
                    partition_results.append(result)
                except (AdapterError, OSError, ValueError) as exc:
                    failures.append({"partition": partition.key, "reason": str(exc)})
                    if not continue_on_error:
                        raise
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_partition = {
                    executor.submit(self.harvest_partition, partition, resume=resume): partition
                    for partition in partitions
                }
                for future in as_completed(future_to_partition):
                    partition = future_to_partition[future]
                    try:
                        partition_results.append(future.result())
                    except (AdapterError, OSError, ValueError) as exc:
                        failures.append({"partition": partition.key, "reason": str(exc)})
                        if not continue_on_error:
                            for pending in future_to_partition:
                                pending.cancel()
                            raise
        partition_results.sort(
            key=lambda result: (
                int((result.get("partition") or {}).get("year") or 0),
                str((result.get("partition") or {}).get("region") or ""),
            )
        )

        self.output_root.mkdir(parents=True, exist_ok=True)
        observations_path = self.output_root / "observations.geojson"
        temporary_path = observations_path.with_name(
            f".{observations_path.name}.{os.getpid()}.tmp"
        )
        observation_ids: set[str] = set()
        event_ids: set[str] = set()
        first_feature = True
        header = {
            "type": "FeatureCollection",
            "schema": "wfd_fire_observation_v1",
            "source_id": self.adapter.source_id,
            "generated_at": utc_now(),
        }
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(header, ensure_ascii=False, separators=(",", ":"))[:-1])
            handle.write(',"features":[')
            for result in partition_results:
                manifest_path = Path(result["manifest"])
                normalized_path = manifest_path.parent / "normalized.geojson"
                try:
                    document = json.loads(normalized_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    failures.append(
                        {
                            "partition": str(result.get("partition")),
                            "reason": "normalized_unreadable",
                        }
                    )
                    continue
                for feature in document.get("features") or []:
                    properties = feature.get("properties") or {}
                    observation_id = str(properties.get("observation_id") or "")
                    if not observation_id or observation_id in observation_ids:
                        continue
                    observation_ids.add(observation_id)
                    event_id = str(properties.get("event_id") or "")
                    if event_id:
                        event_ids.add(event_id)
                    if not first_feature:
                        handle.write(",")
                    handle.write(
                        json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
                    )
                    first_feature = False
            handle.write("]}\n")
        temporary_path.replace(observations_path)
        report = {
            "schema": HARVEST_SCHEMA,
            "ok": not failures,
            "started_at": started_at,
            "completed_at": utc_now(),
            "as_of": self.as_of.isoformat(),
            "source_url": WFIGS_DAILY_LAYER_URL,
            "years": sorted(set(years)),
            "regions": regions,
            "counts": {
                "partitions_requested": len(years) * len(regions),
                "partitions_complete": len(partition_results),
                "partitions_failed": len(failures),
                "observations": len(observation_ids),
                "events": len(event_ids),
                "downloaded_bytes": sum(
                    int(raw.get("bytes") or 0)
                    for result in partition_results
                    for raw in result.get("raw") or []
                ),
            },
            "failures": failures,
            "partitions": [
                {
                    "partition": result.get("partition"),
                    "counts": result.get("counts"),
                    "resumed": result.get("resumed"),
                    "manifest": result.get("manifest"),
                }
                for result in partition_results
            ],
            "observations": {
                "file": str(observations_path),
                "sha256": sha256_file(observations_path),
            },
            "request_fingerprint": sha256_bytes(
                canonical_json(
                    {
                        "years": sorted(set(years)),
                        "regions": regions,
                        "as_of": self.as_of.isoformat(),
                    }
                )
            ),
            "honesty": self.adapter.honesty,
        }
        _atomic_write_json(self.output_root / "HARVEST_REPORT.json", report)
        return report


__all__ = [
    "GACC_REGIONS",
    "HARVEST_SCHEMA",
    "PARTITION_SCHEMA",
    "WFIGS_DAILY_LAYER_URL",
    "HarvestPartition",
    "WFIGSDailyPerimetersAdapter",
    "WFIGSHistoricalHarvester",
]
