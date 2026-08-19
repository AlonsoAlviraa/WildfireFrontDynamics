"""Constellation desk: real satellite chips, not a hotspot counter.

Backends (first that works):
  1. NASA GIBS / Worldview Snapshots — VIIRS true-color, SWIR false-color, thermal
  2. FIRMS Europe 24h CSV — live VIIRS points (no MAP_KEY)
  3. Earth Engine (optional) — same contract, GOES-FDC + Sentinel-2 + WeatherNext

Chips are *evidence*. FIRMS / thermal anomalies ≠ official burned area.
No language model. No invented ROS or hectares.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .board import query_hash
from .maps_grounding import AOIS, ground_place

GIBS_SNAPSHOT = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
FIRMS_EUROPE_24H = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Europe_24h.csv"
)
UA = "WildfireFrontDynamics-Relator/0.1 (hackathon constellation desk)"

# Historical fire dates we can replay without a live season.
AOI_SKY: dict[str, dict[str, Any]] = {
    "nijar": {
        "dates": ("2024-06-05", "2024-06-07"),
        "bbox": [-2.40, 36.82, -2.05, 37.08],
        "label": "Níjar, Almería — June 2024",
    },
    "tobarra": {
        "dates": ("2024-08-01", "2024-08-03"),
        "bbox": [-1.88, 38.46, -1.50, 38.76],
        "label": "Tobarra, Albacete — August 2024",
    },
}

# Three complementary looks at the same bbox. WRAP must match layer count.
LAYERS = (
    {
        "role": "true_color",
        "sensor": "VIIRS SNPP",
        "layers": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
        "wrap": "day",
        "why": "What the peninsula looked like in visible light that morning.",
    },
    {
        "role": "swir_false",
        "sensor": "VIIRS SNPP M11-I2-I1",
        "layers": "VIIRS_SNPP_CorrectedReflectance_BandsM11-I2-I1",
        "wrap": "day",
        "why": "SWIR false color: heat/burn scar pops; not a hectare figure.",
    },
    {
        "role": "thermal",
        "sensor": "VIIRS SNPP thermal anomalies + true color",
        "layers": (
            "VIIRS_SNPP_CorrectedReflectance_TrueColor,"
            "VIIRS_SNPP_Thermal_Anomalies_375m_All"
        ),
        "wrap": "day,none",
        "why": "Active thermal detections over true color. FIRMS-class, not CEMS ha.",
    },
)


def _aoi_key(name: str) -> str:
    raw = (name or "").strip().lower()
    for key, rec in AOIS.items():
        if raw == key or raw == rec["incident_id"] or raw in rec["aliases"]:
            return key
    return raw if raw in AOI_SKY else "nijar"


def sky_spec(aoi: str) -> dict[str, Any]:
    key = _aoi_key(aoi)
    spec = dict(AOI_SKY[key])
    place = ground_place(key)
    spec["aoi"] = key
    spec["place"] = place
    spec["bbox"] = list(spec.get("bbox") or place.get("bbox") or [])
    return spec


def snapshot_url(
    *,
    bbox: list[float],
    time: str,
    layers: str,
    wrap: str,
    width: int = 768,
    height: int = 768,
) -> str:
    west, south, east, north = (float(x) for x in bbox)
    q = urlencode(
        {
            "REQUEST": "GetSnapshot",
            "TIME": time,
            "BBOX": f"{west},{south},{east},{north}",
            "CRS": "EPSG:4326",
            "LAYERS": layers,
            "WRAP": wrap,
            "FORMAT": "image/jpeg",
            "WIDTH": str(width),
            "HEIGHT": str(height),
        }
    )
    return f"{GIBS_SNAPSHOT}?{q}"


def _http_get(url: str, *, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def pull_chip(
    dest: Path,
    *,
    bbox: list[float],
    time: str,
    layer: dict[str, Any],
) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = snapshot_url(bbox=bbox, time=time, layers=layer["layers"], wrap=layer["wrap"])
    blob = _http_get(url)
    if len(blob) < 800 or blob[:2] != b"\xff\xd8":
        raise RuntimeError(f"gibs_not_jpeg role={layer['role']} bytes={len(blob)}")
    dest.write_bytes(blob)
    return {
        "role": layer["role"],
        "sensor": layer["sensor"],
        "date": time,
        "path": str(dest),
        "url": url,
        "bytes": len(blob),
        "cite": f"nasa_gibs:{layer['layers']}:{time}",
        "why": layer["why"],
        "not_official_burned": True,
    }


def pull_constellation(
    aoi: str,
    dest_dir: Path,
    *,
    dates: tuple[str, ...] | None = None,
    timeout_ok: bool = True,
) -> dict[str, Any]:
    """Download true-color + SWIR + thermal chips for one or two dates."""
    spec = sky_spec(aoi)
    days = tuple(dates or spec["dates"])
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    chips: list[dict[str, Any]] = []
    errors: list[str] = []
    for day in days:
        for layer in LAYERS:
            name = f"{spec['aoi']}_{day}_{layer['role']}.jpg"
            try:
                chips.append(
                    pull_chip(
                        dest_dir / name,
                        bbox=list(spec["bbox"]),
                        time=day,
                        layer=layer,
                    )
                )
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
                errors.append(f"{name}: {type(exc).__name__}")
                if not timeout_ok:
                    raise
    try:
        from .sentinel import pull_sentinel_previews

        s2 = pull_sentinel_previews(spec["aoi"], dest_dir)
        chips.extend(s2.get("chips") or [])
        errors.extend(s2.get("errors") or [])
    except Exception as exc:
        errors.append(f"sentinel2: {type(exc).__name__}")

    qh = query_hash(
        {
            "aoi": spec["aoi"],
            "bbox": spec["bbox"],
            "dates": list(days),
            "layers": [L["role"] for L in LAYERS],
        }
    )
    return {
        "ok": bool(chips),
        "aoi": spec["aoi"],
        "label": spec["label"],
        "place": spec["place"],
        "bbox": spec["bbox"],
        "dates": list(days),
        "chips": chips,
        "errors": errors,
        "query_hash": qh,
        "source": "nasa_gibs_worldview",
        "not_official_burned": True,
        "not_tactical_dispatch": True,
        "cite": f"nasa_gibs:worldview:{spec['aoi']}:{','.join(days)}",
    }


def parse_firms_csv(text: str, bbox: list[float] | None = None) -> list[dict[str, Any]]:
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    west = south = east = north = None
    if bbox and len(bbox) == 4:
        west, south, east, north = (float(x) for x in bbox)
    for rec in reader:
        try:
            lat = float(rec["latitude"])
            lon = float(rec["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if west is not None and not (west <= lon <= east and south <= lat <= north):
            continue
        rows.append(
            {
                "lat": lat,
                "lon": lon,
                "frp": _opt_float(rec.get("frp")),
                "confidence": rec.get("confidence"),
                "acq_date": rec.get("acq_date"),
                "acq_time": rec.get("acq_time"),
                "daynight": rec.get("daynight"),
                "satellite": rec.get("satellite"),
            }
        )
    return rows


def _opt_float(raw: Any) -> float | None:
    try:
        return float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def pull_firms_europe_24h(*, bbox: list[float] | None = None) -> dict[str, Any]:
    raw = _http_get(FIRMS_EUROPE_24H, timeout=60).decode("utf-8", errors="replace")
    points = parse_firms_csv(raw, bbox=bbox)
    frps = [p["frp"] for p in points if p.get("frp") is not None]
    return {
        "ok": True,
        "source": "firms_viirs_snpp_europe_24h",
        "cite": "nasa_firms:SUOMI_VIIRS_C2_Europe_24h",
        "n_hotspots": len(points),
        "frp_sum_mw": round(sum(frps), 2) if frps else None,
        "points": points[:400],
        "not_official_burned": True,
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def densest_cluster(points: list[dict[str, Any]], *, cell: float = 0.35) -> dict[str, Any] | None:
    """Pick a live AOI from today's VIIRS without inventing a fire name."""
    if not points:
        return None
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for p in points:
        key = (int(p["lat"] / cell), int(p["lon"] / cell))
        buckets.setdefault(key, []).append(p)
    cluster = max(buckets.values(), key=len)
    lats = [p["lat"] for p in cluster]
    lons = [p["lon"] for p in cluster]
    pad = 0.18
    return {
        "n": len(cluster),
        "bbox": [
            min(lons) - pad,
            min(lats) - pad,
            max(lons) + pad,
            max(lats) + pad,
        ],
        "centroid": [sum(lats) / len(lats), sum(lons) / len(lons)],
        "cite": "nasa_firms:cluster_24h",
        "not_official_burned": True,
    }


def today_utc() -> str:
    return date.today().isoformat()


def yesterday_utc() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def write_manifest(pack: dict[str, Any], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    slim = dict(pack)
    dest.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    return dest
