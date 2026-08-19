"""Shared contracts and durable materialization for regional fire adapters."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping, shape
from shapely.validation import make_valid

OBSERVATION_SCHEMA = "wfd_fire_observation_v1"
SNAPSHOT_SCHEMA = "wfd_regional_fire_snapshot_v1"
STATE_SCHEMA = "wfd_regional_fire_state_v1"
INDEX_SCHEMA = "wfd_regional_fire_index_v1"
ADAPTER_VERSION = "1.0.0"
USER_AGENT = "WildfireFrontDynamics-regional-ingest/1.0 (+bounded; auditable)"


class AdapterError(ValueError):
    """Provider, parsing, or materialization failure."""


@dataclass(frozen=True)
class RegionalQuery:
    """Provider-neutral, bounded query."""

    bbox: tuple[float, float, float, float] | None = None
    start: str | None = None
    end: str | None = None
    limit: int = 1000
    cwfis_layer: str = "activefires"
    inpe_status: str = "active"

    def validate(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.limit > 100_000:
            raise ValueError("limit cannot exceed 100000")
        if self.bbox is not None:
            west, south, east, north = self.bbox
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError("bbox must be west,south,east,north in EPSG:4326")
        start = parse_time(self.start)
        end = parse_time(self.end, end_of_day=True)
        if self.start is not None and start is None:
            raise ValueError("start must be an ISO-8601 date or date-time")
        if self.end is not None and end is None:
            raise ValueError("end must be an ISO-8601 date or date-time")
        if start is not None and end is not None and start > end:
            raise ValueError("start must be earlier than or equal to end")
        if self.inpe_status not in {"active", "observation", "both"}:
            raise ValueError("inpe_status must be active, observation, or both")

    def as_dict(self) -> dict[str, Any]:
        return {
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "start": self.start,
            "end": self.end,
            "limit": self.limit,
            "cwfis_layer": self.cwfis_layer,
            "inpe_status": self.inpe_status,
        }


@dataclass(frozen=True)
class FetchPayload:
    """A single immutable upstream response or offline fixture."""

    name: str
    url: str
    body: bytes
    content_type: str
    status: int = 200
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class NormalizationResult:
    features: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raw += "T23:59:59.999999" if end_of_day else "T00:00:00"
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def epoch_ms_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return normalize_iso(value)
    try:
        return datetime.fromtimestamp(numeric / 1000.0, tz=UTC).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def normalize_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    parsed = parse_time(raw)
    if parsed is None:
        return raw
    if "T" not in raw and len(raw) == 10:
        return raw
    return parsed.isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "payload.bin"


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def query_accepts(feature: dict[str, Any], query: RegionalQuery) -> bool:
    props = feature.get("properties") or {}
    observed = parse_time(props.get("observed_at"))
    start = parse_time(query.start)
    end = parse_time(query.end, end_of_day=True)
    if start is not None and observed is not None and observed < start:
        return False
    if end is not None and observed is not None and observed > end:
        return False
    if query.bbox is not None:
        try:
            if not shape(feature["geometry"]).intersects(box(*query.bbox)):
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def validated_geometry(
    geometry: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(geometry, dict):
        return None, ["missing_geometry"]
    try:
        geom = shape(geometry)
    except (TypeError, ValueError) as exc:
        return None, [f"invalid_geometry:{type(exc).__name__}"]
    if geom.is_empty:
        return None, ["empty_geometry"]
    flags: list[str] = []
    if not geom.is_valid:
        geom = make_valid(geom)
        flags.append("geometry_repaired_make_valid")
    if geom.is_empty:
        return None, ["empty_geometry_after_repair"]
    return mapping(geom), flags


def make_observation_feature(
    *,
    source_id: str,
    upstream_item_id: str,
    event_id: str,
    geometry: dict[str, Any],
    observation_kind: str,
    geometry_semantics: str,
    role: str,
    observed_at: str | None,
    published_at: str | None,
    source_updated_at: str | None,
    retrieved_at: str,
    source_url: str,
    licence_id: str,
    provisional: bool,
    candidate_progression_label: bool,
    quality_flags: list[str] | None = None,
    upstream_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checked_geometry, geometry_flags = validated_geometry(geometry)
    if checked_geometry is None:
        raise ValueError(",".join(geometry_flags))
    flags = sorted({*(quality_flags or []), *geometry_flags})
    identity = {
        "source_id": source_id,
        "upstream_item_id": str(upstream_item_id),
        "event_id": str(event_id),
        "observed_at": observed_at,
        "geometry_semantics": geometry_semantics,
        "geometry": checked_geometry,
    }
    observation_id = f"{source_id}:{sha256_bytes(canonical_json(identity))[:24]}"
    return {
        "type": "Feature",
        "id": observation_id,
        "geometry": checked_geometry,
        "properties": {
            "schema": OBSERVATION_SCHEMA,
            "observation_id": observation_id,
            "source_id": source_id,
            "upstream_item_id": str(upstream_item_id),
            "event_id": str(event_id),
            "observation_kind": observation_kind,
            "geometry_semantics": geometry_semantics,
            "role": role,
            "observed_at": observed_at,
            "published_at": published_at,
            "source_updated_at": source_updated_at,
            "retrieved_at": retrieved_at,
            "first_seen_at": retrieved_at,
            "last_seen_at": retrieved_at,
            "crs": "EPSG:4326",
            "licence_id": licence_id,
            "provisional": bool(provisional),
            "candidate_progression_label": bool(candidate_progression_label),
            "requires_temporal_pair_audit": bool(candidate_progression_label),
            "source_url": source_url,
            "quality_flags": flags,
            "upstream_properties": {
                str(key): value
                for key, value in (upstream_properties or {}).items()
                if value is not None
            },
        },
    }


class BaseRegionalFireAdapter(ABC):
    """Provider adapter with bounded HTTP and offline-fixture support."""

    source_id: str
    provider: str
    licence_id: str
    raw_extension: str

    def __init__(self, *, timeout: float = 60.0, max_bytes: int = 64 * 1024 * 1024) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)

    def request(self, url: str, *, name: str, accept: str = "*/*") -> FetchPayload:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": accept},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise AdapterError(
                        f"{self.source_id} response exceeded max_bytes={self.max_bytes}: {url}"
                    )
                return FetchPayload(
                    name=name,
                    url=response.geturl(),
                    body=body,
                    content_type=str(response.headers.get("Content-Type") or "application/octet-stream"),
                    status=int(response.status),
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                )
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"{self.source_id} HTTP {exc.code}: {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AdapterError(f"{self.source_id} fetch failed: {exc}") from exc

    def fixture_payloads(self, paths: list[Path]) -> list[FetchPayload]:
        if not paths:
            raise ValueError("at least one fixture path is required")
        payloads: list[FetchPayload] = []
        for index, path in enumerate(paths):
            if not path.is_file():
                raise FileNotFoundError(path)
            body = path.read_bytes()
            if len(body) > self.max_bytes:
                raise AdapterError(f"fixture exceeds max_bytes={self.max_bytes}: {path}")
            suffix = path.suffix.lower()
            content_type = {
                ".json": "application/json",
                ".geojson": "application/geo+json",
                ".kml": "application/vnd.google-earth.kml+xml",
                ".xml": "application/xml",
            }.get(suffix, "application/octet-stream")
            payloads.append(
                FetchPayload(
                    name=f"fixture_{index:04d}_{path.name}",
                    url=f"fixture:{path.resolve()}",
                    body=body,
                    content_type=content_type,
                )
            )
        return payloads

    @abstractmethod
    def fetch(self, query: RegionalQuery) -> list[FetchPayload]:
        """Fetch one or more bounded provider payloads."""

    @abstractmethod
    def normalize(
        self,
        payloads: list[FetchPayload],
        query: RegionalQuery,
        *,
        retrieved_at: str,
    ) -> NormalizationResult:
        """Convert provider payloads to the WFD observation contract."""

    @property
    @abstractmethod
    def honesty(self) -> dict[str, Any]:
        """Provider-specific non-claims persisted in every manifest."""

    def ingest(
        self,
        *,
        output_root: Path,
        query: RegionalQuery,
        fixtures: list[Path] | None = None,
        retrieved_at: str | None = None,
    ) -> dict[str, Any]:
        query.validate()
        stamp = retrieved_at or utc_now()
        payloads = self.fixture_payloads(fixtures) if fixtures else self.fetch(query)
        result = self.normalize(payloads, query, retrieved_at=stamp)
        if len(result.features) > query.limit:
            result.features = result.features[: query.limit]
        return materialize_batch(
            adapter=self,
            output_root=Path(output_root),
            query=query,
            payloads=payloads,
            result=result,
            retrieved_at=stamp,
            fixture_mode=bool(fixtures),
        )


def _feature_sort_key(feature: dict[str, Any]) -> tuple[str, str, str]:
    props = feature.get("properties") or {}
    return (
        str(props.get("event_id") or ""),
        str(props.get("observed_at") or ""),
        str(props.get("observation_id") or ""),
    )


def _merge_index(
    existing: dict[str, Any], new_features: list[dict[str, Any]], *, retrieved_at: str
) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for feature in existing.get("features") or []:
        props = feature.get("properties") or {}
        observation_id = str(props.get("observation_id") or feature.get("id") or "")
        if observation_id:
            by_id[observation_id] = feature
    for feature in new_features:
        props = feature.get("properties") or {}
        observation_id = str(props.get("observation_id") or feature.get("id") or "")
        if not observation_id:
            continue
        previous = by_id.get(observation_id)
        if previous is not None:
            previous_props = previous.get("properties") or {}
            props["first_seen_at"] = previous_props.get("first_seen_at") or props.get(
                "first_seen_at"
            )
        props["last_seen_at"] = retrieved_at
        by_id[observation_id] = feature
    features = sorted(by_id.values(), key=_feature_sort_key)
    return {
        "type": "FeatureCollection",
        "schema": INDEX_SCHEMA,
        "updated_at": retrieved_at,
        "n_features": len(features),
        "features": features,
    }


def materialize_batch(
    *,
    adapter: BaseRegionalFireAdapter,
    output_root: Path,
    query: RegionalQuery,
    payloads: list[FetchPayload],
    result: NormalizationResult,
    retrieved_at: str,
    fixture_mode: bool,
) -> dict[str, Any]:
    provider_root = output_root / adapter.source_id
    provider_root.mkdir(parents=True, exist_ok=True)
    compact = re.sub(r"[^0-9]", "", retrieved_at)[:20]
    suffix = sha256_bytes(canonical_json([p.url for p in payloads]))[:8]
    snapshot_dir = provider_root / "snapshots" / f"{compact}_{suffix}"
    if snapshot_dir.exists():
        counter = 1
        while snapshot_dir.with_name(f"{snapshot_dir.name}_{counter}").exists():
            counter += 1
        snapshot_dir = snapshot_dir.with_name(f"{snapshot_dir.name}_{counter}")
    raw_dir = snapshot_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=False)

    raw_records: list[dict[str, Any]] = []
    for payload in payloads:
        name = _safe_name(payload.name)
        raw_path = raw_dir / name
        raw_path.write_bytes(payload.body)
        raw_records.append(
            {
                "file": str(raw_path.relative_to(provider_root)).replace("\\", "/"),
                "url": payload.url,
                "http_status": payload.status,
                "content_type": payload.content_type,
                "bytes": len(payload.body),
                "sha256": sha256_bytes(payload.body),
                "etag": payload.etag,
                "last_modified": payload.last_modified,
            }
        )

    normalized = {
        "type": "FeatureCollection",
        "schema": OBSERVATION_SCHEMA,
        "source_id": adapter.source_id,
        "retrieved_at": retrieved_at,
        "features": sorted(result.features, key=_feature_sort_key),
    }
    normalized_path = snapshot_dir / "normalized.geojson"
    _atomic_write_json(normalized_path, normalized)

    index_path = provider_root / "index.geojson"
    existing_index = _load_json(index_path, {"type": "FeatureCollection", "features": []})
    merged = _merge_index(existing_index, result.features, retrieved_at=retrieved_at)
    _atomic_write_json(index_path, merged)
    _atomic_write_json(provider_root / "latest.geojson", normalized)

    semantics: dict[str, int] = {}
    events: set[str] = set()
    candidate_count = 0
    observed_values: list[str] = []
    for feature in result.features:
        props = feature.get("properties") or {}
        semantic = str(props.get("geometry_semantics") or "unknown")
        semantics[semantic] = semantics.get(semantic, 0) + 1
        if props.get("event_id"):
            events.add(str(props["event_id"]))
        if props.get("candidate_progression_label") is True:
            candidate_count += 1
        if props.get("observed_at"):
            observed_values.append(str(props["observed_at"]))

    manifest = {
        "schema": SNAPSHOT_SCHEMA,
        "adapter": {
            "class": type(adapter).__name__,
            "version": ADAPTER_VERSION,
            "source_id": adapter.source_id,
            "provider": adapter.provider,
            "licence_id": adapter.licence_id,
        },
        "retrieved_at": retrieved_at,
        "fixture_mode": fixture_mode,
        "query": query.as_dict(),
        "counts": {
            "payloads": len(payloads),
            "normalized": len(result.features),
            "rejected": len(result.rejected),
            "events": len(events),
            "candidate_progression_labels": candidate_count,
            "index_total": len(merged["features"]),
        },
        "observed_range": {
            "min": min(observed_values) if observed_values else None,
            "max": max(observed_values) if observed_values else None,
        },
        "semantics": dict(sorted(semantics.items())),
        "honesty": adapter.honesty,
        "raw": raw_records,
        "rejected": result.rejected[:1000],
        "files": {
            "normalized": {
                "file": str(normalized_path.relative_to(provider_root)).replace("\\", "/"),
                "sha256": sha256_file(normalized_path),
            },
            "index": {"file": "index.geojson", "sha256": sha256_file(index_path)},
            "latest": "latest.geojson",
        },
    }
    manifest_path = snapshot_dir / "manifest.json"
    _atomic_write_json(manifest_path, manifest)
    _atomic_write_json(provider_root / "latest.json", manifest)

    state_path = provider_root / "state.json"
    previous_state = _load_json(state_path, {})
    snapshots = list(previous_state.get("snapshots") or [])
    manifest_rel = str(manifest_path.relative_to(provider_root)).replace("\\", "/")
    snapshots.append(
        {
            "retrieved_at": retrieved_at,
            "manifest": manifest_rel,
            "normalized": len(result.features),
            "index_total": len(merged["features"]),
        }
    )
    state = {
        "schema": STATE_SCHEMA,
        "source_id": adapter.source_id,
        "last_success_at": retrieved_at,
        "last_manifest": manifest_rel,
        "n_snapshots": len(snapshots),
        "n_index_features": len(merged["features"]),
        "snapshots": snapshots,
    }
    _atomic_write_json(state_path, state)

    return {
        "ok": True,
        "schema": SNAPSHOT_SCHEMA,
        "source_id": adapter.source_id,
        "snapshot_dir": str(snapshot_dir),
        "manifest": str(manifest_path),
        "index": str(index_path),
        "state": str(state_path),
        "counts": manifest["counts"],
        "semantics": manifest["semantics"],
        "honesty": adapter.honesty,
    }
