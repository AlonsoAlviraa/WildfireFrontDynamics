"""Build fire-status map payload from local GeoJSON + optional FIRMS NRT."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wildfire_front.geo_crs import geojson_to_wgs84, looks_projected_meters
from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

from .firms_client import fetch_firms_hotspots

# Common outbox / product filenames (relative to work-dir or outbox)
_DEFAULT_LOCAL_CANDIDATES = (
    "main_front.geojson",
    "fronts.geojson",
    "fronts_wgs84.geojson",
    "emergency_envelope_guidance.geojson",
    "emergency_envelope.geojson",
    "outbox/main_front.geojson",
    "outbox/fronts.geojson",
    "outbox/emergency_envelope_guidance.geojson",
)

_DEFAULT_BBOX_SPAIN_CENTER = (-3.8, 39.5, -2.8, 40.5)  # west,south,east,north


def _load_fc(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("type") == "FeatureCollection":
        return data
    if data.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    return None


def _coords_iter(geom: dict[str, Any] | None):
    if not geom:
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        yield c
    elif t in ("MultiPoint", "LineString"):
        for p in c or []:
            yield p
    elif t in ("MultiLineString", "Polygon"):
        for ring in c or []:
            for p in ring:
                yield p
    elif t == "MultiPolygon":
        for poly in c or []:
            for ring in poly:
                for p in ring:
                    yield p


def _first_xy(fc: dict[str, Any]) -> tuple[float, float] | None:
    for f in fc.get("features") or []:
        for p in _coords_iter((f or {}).get("geometry")):
            if not p or len(p) < 2:
                continue
            try:
                return float(p[0]), float(p[1])
            except (TypeError, ValueError):
                continue
    return None


def _infer_utm_zone(fc: dict[str, Any]) -> tuple[int, bool]:
    """Infer UTM zone/hemisphere from GeoJSON crs / feature props (default 30N)."""
    zone, northern = 30, True
    names: list[str] = []
    crs = fc.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties") or {}
        if isinstance(props, dict) and props.get("name"):
            names.append(str(props["name"]))
    for f in fc.get("features") or []:
        p = (f or {}).get("properties") or {}
        if isinstance(p, dict) and p.get("crs"):
            names.append(str(p["crs"]))
    for name in names:
        m = re.search(r"326(\d{2})", name)
        if m:
            return int(m.group(1)), True
        m = re.search(r"327(\d{2})", name)
        if m:
            return int(m.group(1)), False
        m = re.search(r"UTM[_\s-]?(\d{1,2})N", name, re.I)
        if m:
            return int(m.group(1)), True
    return zone, northern


def ensure_wgs84_geojson(fc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (geojson_wgs84, meta) — reproject UTM meters when needed for Leaflet/OSM."""
    meta: dict[str, Any] = {
        "crs_output": "EPSG:4326",
        "reprojected": False,
        "source_crs": None,
        "utm_zone": None,
    }
    xy = _first_xy(fc)
    if xy is None:
        return fc, meta
    x, y = xy
    if not looks_projected_meters(x, y):
        meta["source_crs"] = "EPSG:4326_or_geographic"
        # still drop obsolete crs member for RFC 7946 consumers
        out = dict(fc)
        out.pop("crs", None)
        return out, meta

    zone, northern = _infer_utm_zone(fc)
    meta["reprojected"] = True
    meta["utm_zone"] = zone
    meta["source_crs"] = f"EPSG:326{zone:02d}" if northern else f"EPSG:327{zone:02d}"
    wgs = geojson_to_wgs84(fc, zone=zone, northern=northern)
    return wgs, meta


def _bbox_from_features(features: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for f in features:
        for p in _coords_iter((f or {}).get("geometry")):
            if not p or len(p) < 2:
                continue
            try:
                x, y = float(p[0]), float(p[1])
            except (TypeError, ValueError):
                continue
            # only geographic lon/lat after ensure_wgs84
            if abs(x) > 180 or abs(y) > 90:
                continue
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    pad = 0.15
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def load_local_geojson_layers(
    *,
    work_dir: Path | str | None = None,
    geojson_paths: list[Path | str] | None = None,
) -> list[dict[str, Any]]:
    """Load local layers and reproject to WGS84 lon/lat for Leaflet basemaps."""
    layers: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(path: Path, name: str | None = None) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            return
        if not path.is_file():
            return
        fc = _load_fc(path)
        if not fc:
            return
        seen.add(key)
        wgs, crs_meta = ensure_wgs84_geojson(fc)
        feats = list(wgs.get("features") or [])
        layers.append(
            {
                "id": name or path.stem,
                "name": name or path.name,
                "path": str(path),
                "source": "local",
                "n_features": len(feats),
                "geojson": wgs,
                "crs": crs_meta,
            }
        )

    for raw in geojson_paths or []:
        _add(Path(raw))

    if work_dir is not None:
        root = Path(work_dir)
        for rel in _DEFAULT_LOCAL_CANDIDATES:
            _add(root / rel, name=Path(rel).name)

    return layers


def build_fire_status_map_payload(
    *,
    work_dir: Path | str | None = None,
    geojson_paths: list[Path | str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    center: tuple[float, float] | None = None,
    live: bool = True,
    map_key: str | None = None,
    day_range: int = 1,
    fixture_csv: Path | str | None = None,
    timeout: float = 60.0,
    title: str = "WFD · estado del incendio (mapa)",
) -> dict[str, Any]:
    """Compose map model: local layers + optional FIRMS NRT + honesty rails."""
    layers = load_local_geojson_layers(work_dir=work_dir, geojson_paths=geojson_paths)

    all_feats: list[dict[str, Any]] = []
    for lyr in layers:
        all_feats.extend((lyr.get("geojson") or {}).get("features") or [])

    resolved_bbox = bbox or _bbox_from_features(all_feats) or _DEFAULT_BBOX_SPAIN_CENTER
    if center is None:
        w, s, e, n = resolved_bbox
        center = ((w + e) / 2.0, (s + n) / 2.0)

    firms = fetch_firms_hotspots(
        bbox=resolved_bbox,
        map_key=map_key,
        day_range=day_range,
        timeout=timeout,
        fixture_csv=fixture_csv,
        allow_network=bool(live) and fixture_csv is None,
    )

    if firms.get("features"):
        layers.append(
            {
                "id": "firms_nrt_hotspots",
                "name": "FIRMS NRT hotspots",
                "path": firms.get("source_url"),
                "source": firms.get("source_mode") or "firms",
                "connectivity": firms.get("connectivity"),
                "n_features": firms.get("n_hotspots", 0),
                "geojson": {
                    "type": "FeatureCollection",
                    "features": firms.get("features") or [],
                },
            }
        )

    connectivity = str(firms.get("connectivity") or "skipped")
    local_n = sum(int(L.get("n_features") or 0) for L in layers if L.get("source") == "local")

    return {
        "schema": "wfd_fire_status_map_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "title": title,
        "center": {"lon": center[0], "lat": center[1]},
        "bbox": {
            "west": resolved_bbox[0],
            "south": resolved_bbox[1],
            "east": resolved_bbox[2],
            "north": resolved_bbox[3],
        },
        "zoom": 10 if local_n or firms.get("n_hotspots") else 6,
        "layers": layers,
        "layer_summary": [
            {
                "id": L.get("id"),
                "name": L.get("name"),
                "source": L.get("source"),
                "n_features": L.get("n_features"),
                "connectivity": L.get("connectivity"),
                "reprojected": bool((L.get("crs") or {}).get("reprojected")),
                "source_crs": (L.get("crs") or {}).get("source_crs"),
            }
            for L in layers
        ],
        "firms": {
            "connectivity": firms.get("connectivity"),
            "source_mode": firms.get("source_mode"),
            "source_url": firms.get("source_url"),
            "n_hotspots": firms.get("n_hotspots"),
            "reasons": firms.get("reasons") or [],
            "honesty": firms.get("honesty") or {},
        },
        "connectivity": {
            "status": connectivity,
            "live_requested": bool(live),
            "local_layers": len([L for L in layers if L.get("source") == "local"]),
            "external_hotspots": int(firms.get("n_hotspots") or 0),
        },
        "rails": {
            "field_ops_ml_live_fusion": field_ops_ml_live_fusion_rail(),
            "not_tactical_dispatch": True,
            "nrt_not_official_perimeter": True,
            "hotspots_not_burned_area": True,
            "go_q_invent_forbidden": True,
            "iou_is_not_ros": True,
        },
        "disclaimer": (
            "Mapa de estado / NRT. NO despacho táctico. "
            "Hotspots FIRMS ≠ área quemada oficial ni perímetro de extinción. "
            "Capas locales = productos WFD (frente/envelope) con sus limitaciones. "
            "field_ops ML fusion = ON (≠ despacho)."
        ),
        "work_dir": str(work_dir) if work_dir else None,
    }
