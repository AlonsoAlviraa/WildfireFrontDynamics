"""Leakage-aware EO and HRRR metadata enrichment for approved WFIGS pairs."""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .base import _atomic_write_json, parse_time, utc_now
from .temporal_pairs import _iter_geojson_features
from .wfigs_rights import wfigs_rights_summary

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
HRRR_BASE_URL = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
ENRICHMENT_SCHEMA = "wfd_wfigs_pair_enrichment_v1"
ENRICHMENT_INVENTORY_SCHEMA = "wfd_wfigs_pair_enrichment_inventory_v1"
USER_AGENT = "WildfireFrontDynamics/1.0 (auditable historical enrichment)"
EO_COLLECTIONS = {
    "sentinel2": "sentinel-2-l2a",
    "landsat": "landsat-c2-l2",
}
EO_LOOKBACK_DAYS = {"sentinel2": 45, "landsat": 64}
EO_ASSETS = {
    "sentinel2": ("blue", "green", "red", "nir", "swir16", "swir22", "scl"),
    "landsat": ("blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"),
}


def _bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    values: list[tuple[float, float]] = []

    def visit(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            values.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, list):
            for child in value:
                visit(child)

    visit(geometry.get("coordinates"))
    if not values:
        return None
    xs = [value[0] for value in values]
    ys = [value[1] for value in values]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_intersects(first: list[float], second: list[float]) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def _merge_bbox(
    first: tuple[float, float, float, float] | None,
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if first is None:
        return second
    return (
        min(first[0], second[0]),
        min(first[1], second[1]),
        max(first[2], second[2]),
        max(first[3], second[3]),
    )


def _parse_datetime(value: Any) -> datetime | None:
    parsed = parse_time(str(value or ""))
    return parsed.astimezone(UTC) if parsed is not None else None


def _event_cache_name(event_id: str) -> str:
    digest = hashlib.sha256(event_id.encode()).hexdigest()[:12]
    safe = "".join(character if character.isalnum() else "_" for character in event_id)
    return f"{safe[:72]}_{digest}.json"


def _summarize_item(item: dict[str, Any], sensor: str) -> dict[str, Any]:
    properties = item.get("properties") or {}
    assets = item.get("assets") or {}
    wanted_assets = {}
    for name in EO_ASSETS[sensor]:
        asset = assets.get(name)
        if isinstance(asset, dict) and asset.get("href"):
            wanted_assets[name] = {
                key: asset.get(key)
                for key in ("href", "type", "title")
                if asset.get(key) is not None
            }
    return {
        "id": item.get("id"),
        "collection": item.get("collection"),
        "datetime": properties.get("datetime"),
        "created": properties.get("created"),
        "updated": properties.get("updated"),
        "cloud_cover_pct": properties.get("eo:cloud_cover"),
        "platform": properties.get("platform"),
        "bbox": item.get("bbox"),
        "assets": wanted_assets,
    }


class EarthSearchClient:
    """Small retrying Earth Search client with bounded pagination."""

    def __init__(self, *, timeout: float = 90.0, page_limit: int = 200) -> None:
        self.timeout = timeout
        self.page_limit = page_limit

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            EARTH_SEARCH_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/geo+json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(min(8, 2**attempt))
        raise OSError(f"Earth Search failed after retries: {last_error}")

    def search(
        self,
        *,
        collection: str,
        bbox: list[float],
        start: datetime,
        end: datetime,
        max_items: int = 600,
    ) -> tuple[list[dict[str, Any]], bool]:
        body: dict[str, Any] = {
            "collections": [collection],
            "bbox": bbox,
            "datetime": (
                f"{start.isoformat().replace('+00:00', 'Z')}/"
                f"{end.isoformat().replace('+00:00', 'Z')}"
            ),
            "limit": min(self.page_limit, max_items),
            "query": {"eo:cloud_cover": {"lt": 95}},
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        }
        items: list[dict[str, Any]] = []
        truncated = False
        while len(items) < max_items:
            document = self._post(body)
            page = list(document.get("features") or [])
            items.extend(page[: max_items - len(items)])
            next_link = next(
                (link for link in document.get("links") or [] if link.get("rel") == "next"),
                None,
            )
            if next_link is None:
                break
            if len(items) >= max_items:
                truncated = True
                break
            next_body = next_link.get("body")
            if not isinstance(next_body, dict):
                truncated = True
                break
            body = next_body
        return items, truncated


def _floor_cycle(moment: datetime) -> datetime:
    return moment.replace(hour=(moment.hour // 6) * 6, minute=0, second=0, microsecond=0)


def _ceil_lead(cycle: datetime, moment: datetime) -> int:
    return int(math.ceil((moment - cycle).total_seconds() / 3600.0))


def _hrrr_index_url(cycle: datetime, lead: int) -> str:
    stamp = cycle.strftime("%Y%m%d")
    hour = cycle.strftime("%H")
    return (
        f"{HRRR_BASE_URL}/hrrr.{stamp}/conus/"
        f"hrrr.t{hour}z.wrfsfcf{lead:02d}.grib2.idx"
    )


# Conservative inner envelope for the NOAA HRRR CONUS Lambert grid.  A bbox
# outside this envelope must not be called weather-resolved merely because the
# S3 object exists (notably Alaska, Hawaii and Puerto Rico).
HRRR_CONUS_BOUNDS = (-134.0, 20.0, -60.0, 55.0)


def _inside_hrrr_conus(bbox: list[float] | None) -> bool:
    if bbox is None or len(bbox) != 4:
        return False
    west, south, east, north = (float(value) for value in bbox)
    domain_west, domain_south, domain_east, domain_north = HRRR_CONUS_BOUNDS
    return (
        domain_west <= west <= east <= domain_east
        and domain_south <= south <= north <= domain_north
    )


def _weather_candidates(
    pair: dict[str, Any], bbox: list[float] | None = None
) -> list[dict[str, Any]]:
    if not _inside_hrrr_conus(bbox):
        return []
    t0 = _parse_datetime(pair.get("t0"))
    t1 = _parse_datetime(pair.get("t1"))
    if t0 is None or t1 is None:
        return []
    latest = _floor_cycle(t0)
    candidates: list[dict[str, Any]] = []
    for back in range(4):
        cycle = latest - timedelta(hours=6 * back)
        first_lead = max(0, _ceil_lead(cycle, t0))
        last_lead = _ceil_lead(cycle, t1)
        if first_lead > last_lead or last_lead > 48:
            continue
        candidates.append(
            {
                "cycle": cycle.isoformat().replace("+00:00", "Z"),
                "first_lead": first_lead,
                "last_lead": last_lead,
                "last_index_url": _hrrr_index_url(cycle, last_lead),
            }
        )
    return candidates


def _probe_head(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                modified_raw = response.headers.get("Last-Modified")
                modified = (
                    parsedate_to_datetime(modified_raw).astimezone(UTC)
                    if modified_raw
                    else None
                )
                return {
                    "status": int(response.status),
                    "content_length": int(response.headers.get("Content-Length") or 0),
                    "last_modified": (
                        modified.isoformat().replace("+00:00", "Z") if modified else None
                    ),
                }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"status": 404, "error": "not_found"}
            last_error = exc
        except OSError as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(min(4, 2**attempt))
    return {"status": "error", "error": str(last_error)}


def _select_eo(
    items: list[dict[str, Any]],
    *,
    sensor: str,
    t0: datetime,
    bbox: list[float],
    limit: int = 3,
) -> list[dict[str, Any]]:
    eligible: list[tuple[float, float, float, str, dict[str, Any]]] = []
    lookback = t0 - timedelta(days=EO_LOOKBACK_DAYS[sensor])
    for item in items:
        acquired = _parse_datetime(item.get("datetime"))
        item_bbox = item.get("bbox")
        if acquired is None or acquired > t0 or acquired < lookback:
            continue
        if not isinstance(item_bbox, list) or len(item_bbox) != 4:
            continue
        if not _bbox_intersects(bbox, [float(value) for value in item_bbox]):
            continue
        try:
            cloud = float(item.get("cloud_cover_pct") or 100.0)
        except (TypeError, ValueError):
            cloud = 100.0
        age_days = (t0 - acquired).total_seconds() / 86400.0
        score = age_days + cloud / 20.0
        eligible.append((score, age_days, cloud, str(item.get("id") or ""), item))
    output: list[dict[str, Any]] = []
    for score, age_days, cloud, _item_id, item in sorted(eligible)[:limit]:
        created = _parse_datetime(item.get("created"))
        output.append(
            {
                **item,
                "age_days_at_t0": round(age_days, 6),
                "selection_score": round(score, 6),
                "cloud_cover_pct": round(cloud, 6),
                "stac_created_time_present": created is not None,
                "stac_created_at_or_before_t0": created is not None and created <= t0,
            }
        )
    return output


class WFIGSPairEnricher:
    """Resolve pre-t0 EO candidates and provably available HRRR runs."""

    def __init__(
        self,
        *,
        pairs_path: Path,
        observations_path: Path,
        output_root: Path,
        workers: int = 8,
        earth_search: EarthSearchClient | None = None,
    ) -> None:
        if workers <= 0 or workers > 32:
            raise ValueError("workers must be in 1..32")
        self.pairs_path = Path(pairs_path)
        self.observations_path = Path(observations_path)
        self.output_root = Path(output_root)
        self.workers = workers
        self.earth_search = earth_search or EarthSearchClient()

    def _load_pairs(self) -> list[dict[str, Any]]:
        document = json.loads(self.pairs_path.read_text(encoding="utf-8"))
        pairs = list(document.get("pairs") or [])
        if not pairs:
            raise ValueError("approved pairs file contains no pairs")
        return pairs

    def _pair_bboxes(self, pairs: list[dict[str, Any]]) -> dict[str, list[float]]:
        wanted = {str(pair["t0_observation_id"]) for pair in pairs}
        by_observation: dict[str, list[float]] = {}
        for feature in _iter_geojson_features(self.observations_path):
            properties = feature.get("properties") or {}
            observation_id = str(properties.get("observation_id") or "")
            if observation_id not in wanted:
                continue
            bounds = _bounds(feature.get("geometry") or {})
            if bounds is not None:
                by_observation[observation_id] = list(bounds)
            if len(by_observation) == len(wanted):
                break
        return by_observation

    def _event_specs(
        self, pairs: list[dict[str, Any]], pair_bboxes: dict[str, list[float]]
    ) -> dict[str, dict[str, Any]]:
        specs: dict[str, dict[str, Any]] = {}
        for pair in pairs:
            bbox = pair_bboxes.get(str(pair["t0_observation_id"]))
            t0 = _parse_datetime(pair.get("t0"))
            if bbox is None or t0 is None:
                continue
            event_id = str(pair["event_id"])
            spec = specs.setdefault(
                event_id,
                {"bbox": None, "first_t0": t0, "last_t0": t0},
            )
            spec["bbox"] = _merge_bbox(
                spec["bbox"], (bbox[0], bbox[1], bbox[2], bbox[3])
            )
            spec["first_t0"] = min(spec["first_t0"], t0)
            spec["last_t0"] = max(spec["last_t0"], t0)
        return specs

    def _fetch_event(self, event_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        cache_dir = self.output_root / "event_cache"
        cache_path = cache_dir / _event_cache_name(event_id)
        if cache_path.is_file():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("status") == "complete":
                    return cached
            except (OSError, json.JSONDecodeError):
                pass
        bbox = [float(value) for value in spec["bbox"]]
        first_t0: datetime = spec["first_t0"]
        last_t0: datetime = spec["last_t0"]
        result: dict[str, Any] = {
            "event_id": event_id,
            "status": "complete",
            "bbox": bbox,
            "first_t0": first_t0.isoformat().replace("+00:00", "Z"),
            "last_t0": last_t0.isoformat().replace("+00:00", "Z"),
            "sensors": {},
        }
        for sensor, collection in EO_COLLECTIONS.items():
            try:
                items, truncated = self.earth_search.search(
                    collection=collection,
                    bbox=bbox,
                    start=first_t0 - timedelta(days=EO_LOOKBACK_DAYS[sensor]),
                    end=last_t0,
                )
                result["sensors"][sensor] = {
                    "status": "ok",
                    "collection": collection,
                    "truncated_at_600": truncated,
                    "items": [_summarize_item(item, sensor) for item in items],
                }
            except (OSError, ValueError) as exc:
                result["status"] = "partial"
                result["sensors"][sensor] = {
                    "status": "error",
                    "collection": collection,
                    "error": str(exc),
                    "items": [],
                }
        _atomic_write_json(cache_path, result)
        return result

    def build(self) -> dict[str, Any]:
        generated_at = utc_now()
        pairs = self._load_pairs()
        pair_bboxes = self._pair_bboxes(pairs)
        event_specs = self._event_specs(pairs, pair_bboxes)
        events: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_event = {
                executor.submit(self._fetch_event, event_id, spec): event_id
                for event_id, spec in event_specs.items()
            }
            for future in as_completed(future_to_event):
                event_id = future_to_event[future]
                try:
                    events[event_id] = future.result()
                except (OSError, ValueError) as exc:
                    events[event_id] = {
                        "event_id": event_id,
                        "status": "error",
                        "error": str(exc),
                        "sensors": {},
                    }

        weather_candidates = {
            str(pair["pair_id"]): _weather_candidates(
                pair, pair_bboxes.get(str(pair["t0_observation_id"]))
            )
            for pair in pairs
        }
        urls = sorted(
            {
                str(candidate["last_index_url"])
                for candidates in weather_candidates.values()
                for candidate in candidates
            }
        )
        probe_cache_path = self.output_root / "HRRR_PROBES.json"
        probes: dict[str, dict[str, Any]] = {}
        if probe_cache_path.is_file():
            try:
                existing = json.loads(probe_cache_path.read_text(encoding="utf-8"))
                probes.update(existing.get("probes") or {})
            except (OSError, json.JSONDecodeError):
                pass
        missing_urls = [url for url in urls if url not in probes]
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_url = {
                executor.submit(_probe_head, url): url for url in missing_urls
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                probes[url] = future.result()
        _atomic_write_json(
            probe_cache_path,
            {
                "schema": "wfd_hrrr_archive_probes_v1",
                "generated_at": generated_at,
                "probes": probes,
            },
        )

        enriched: list[dict[str, Any]] = []
        missing_bbox = 0
        for pair in pairs:
            pair_id = str(pair["pair_id"])
            t0 = _parse_datetime(pair.get("t0"))
            bbox = pair_bboxes.get(str(pair["t0_observation_id"]))
            event = events.get(str(pair["event_id"]), {"sensors": {}})
            eo: dict[str, Any] = {}
            if t0 is None or bbox is None:
                missing_bbox += 1
                for sensor in EO_COLLECTIONS:
                    eo[sensor] = {"status": "missing_t0_or_bbox", "candidates": []}
            else:
                for sensor in EO_COLLECTIONS:
                    sensor_result = (event.get("sensors") or {}).get(sensor) or {}
                    selected = _select_eo(
                        list(sensor_result.get("items") or []),
                        sensor=sensor,
                        t0=t0,
                        bbox=bbox,
                    )
                    eo[sensor] = {
                        "status": "resolved" if selected else "no_pre_t0_candidate",
                        "event_query_status": sensor_result.get("status"),
                        "event_query_truncated": sensor_result.get("truncated_at_600", False),
                        "lookback_days": EO_LOOKBACK_DAYS[sensor],
                        "candidates": selected,
                    }

            weather: dict[str, Any] = {
                "status": (
                    "no_verified_full_window_run"
                    if _inside_hrrr_conus(bbox)
                    else "outside_hrrr_conus_domain"
                ),
                "provider": "NOAA HRRR AWS Open Data",
                "available_by_t0_verified": False,
                "spatial_domain_verified": _inside_hrrr_conus(bbox),
            }
            if t0 is not None:
                for candidate in weather_candidates[pair_id]:
                    probe = probes.get(str(candidate["last_index_url"])) or {}
                    modified = _parse_datetime(probe.get("last_modified"))
                    if probe.get("status") == 200 and modified is not None and modified <= t0:
                        weather = {
                            "status": "resolved",
                            "provider": "NOAA HRRR AWS Open Data",
                            **candidate,
                            "n_hourly_leads": (
                                int(candidate["last_lead"])
                                - int(candidate["first_lead"])
                                + 1
                            ),
                            "archive_probe": probe,
                            "available_by_t0_verified": True,
                            "spatial_domain_verified": True,
                            "availability_evidence": (
                                "S3 index object Last-Modified is at or before t0; "
                                "the probed object is the maximum lead required by the pair."
                            ),
                        }
                        break
            enriched.append(
                {
                    "pair_id": pair_id,
                    "event_id": pair["event_id"],
                    "split": pair["split"],
                    "t0": pair["t0"],
                    "t1": pair["t1"],
                    "delta_hours": pair["metrics"]["delta_hours"],
                    "t0_bbox": bbox,
                    "eo": eo,
                    "weather": weather,
                }
            )

        counts = {
            "pairs": len(enriched),
            "pairs_missing_t0_bbox": missing_bbox,
            "events_queried": len(events),
            "events_query_complete": sum(event.get("status") == "complete" for event in events.values()),
            "events_query_partial_or_error": sum(event.get("status") != "complete" for event in events.values()),
            "pairs_sentinel2_pre_t0": sum(
                row["eo"]["sentinel2"]["status"] == "resolved" for row in enriched
            ),
            "pairs_landsat_pre_t0": sum(
                row["eo"]["landsat"]["status"] == "resolved" for row in enriched
            ),
            "pairs_both_eo_pre_t0": sum(
                row["eo"]["sentinel2"]["status"] == "resolved"
                and row["eo"]["landsat"]["status"] == "resolved"
                for row in enriched
            ),
            "pairs_any_eo_pre_t0": sum(
                row["eo"]["sentinel2"]["status"] == "resolved"
                or row["eo"]["landsat"]["status"] == "resolved"
                for row in enriched
            ),
            "pairs_sentinel2_top_candidate_stac_created_by_t0": sum(
                bool(row["eo"]["sentinel2"]["candidates"])
                and row["eo"]["sentinel2"]["candidates"][0][
                    "stac_created_at_or_before_t0"
                ]
                for row in enriched
            ),
            "pairs_landsat_top_candidate_stac_created_by_t0": sum(
                bool(row["eo"]["landsat"]["candidates"])
                and row["eo"]["landsat"]["candidates"][0][
                    "stac_created_at_or_before_t0"
                ]
                for row in enriched
            ),
            "pairs_both_top_candidates_stac_created_by_t0": sum(
                bool(row["eo"]["sentinel2"]["candidates"])
                and bool(row["eo"]["landsat"]["candidates"])
                and row["eo"]["sentinel2"]["candidates"][0][
                    "stac_created_at_or_before_t0"
                ]
                and row["eo"]["landsat"]["candidates"][0][
                    "stac_created_at_or_before_t0"
                ]
                for row in enriched
            ),
            "pairs_hrrr_available_by_t0_and_full_window": sum(
                row["weather"]["status"] == "resolved" for row in enriched
            ),
            "pairs_hrrr_unresolved": sum(
                row["weather"]["status"] != "resolved" for row in enriched
            ),
            "pairs_outside_hrrr_conus_domain": sum(
                row["weather"]["status"] == "outside_hrrr_conus_domain"
                for row in enriched
            ),
            "hrrr_archive_urls_probed": len(urls),
        }
        inventory = {
            "schema": ENRICHMENT_INVENTORY_SCHEMA,
            "generated_at": generated_at,
            "counts": counts,
            "contracts": {
                "eo_acquisition_at_or_before_t0": True,
                "eo_operational_publication_time_verified": False,
                "eo_historical_reprocessing_possible": True,
                "eo_selection": "top 3 by age_days + cloud_cover_pct/20 within sensor lookback",
                "eo_scene_full_perimeter_coverage_verified": False,
                "hrrr_max_forecast_lead_hours": 48,
                "hrrr_run_available_by_t0_verified_from_s3_last_modified": True,
                "hrrr_spatial_domain_verified_from_t0_bbox": True,
                "t1_or_post_t0_observations_used_as_inputs": False,
                "event_disjoint_splits_preserved": True,
            },
            "rights": {
                **wfigs_rights_summary(),
                "training_blocked_by_wfigs_rights": False,
                "current_artifact_contains_metadata_only": True,
            },
        }
        self.output_root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.output_root / "INVENTORY.json", inventory)
        _atomic_write_json(
            self.output_root / "PAIR_ENRICHMENT.json",
            {
                "schema": ENRICHMENT_SCHEMA,
                "generated_at": generated_at,
                "pairs": enriched,
            },
        )
        return inventory


__all__ = [
    "EARTH_SEARCH_URL",
    "ENRICHMENT_INVENTORY_SCHEMA",
    "ENRICHMENT_SCHEMA",
    "EarthSearchClient",
    "WFIGSPairEnricher",
]
