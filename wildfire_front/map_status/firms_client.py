"""NASA FIRMS NRT hotspot client (open CSV + optional MAP_KEY area API).

Never invents detections. Offline/fixture path is first-class for CI.
Hotspots are ~375 m satellite pixels — NOT official burned area / perimeter.
"""

from __future__ import annotations

import csv
import io
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Public regional NRT CSV (no MAP_KEY). Large; always filter by bbox after download.
FIRMS_EUROPE_VIIRS_24H = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv"
)

# Area API (requires free MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/map_key/)
FIRMS_AREA_API_TMPL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    "{map_key}/{source}/{west},{south},{east},{north}/{day_range}"
)

DEFAULT_SOURCE = "VIIRS_SNPP_NRT"
UA = "WildfireFrontDynamics/0.1 (+fire-status-map; research NRT; not dispatch)"


def parse_firms_csv(
    text: str,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    source_label: str = "FIRMS",
) -> list[dict[str, Any]]:
    """Parse FIRMS CSV text → GeoJSON Point features (optionally clipped to bbox)."""
    west = south = east = north = None
    if bbox is not None:
        west, south, east, north = bbox
    feats: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            lon = float(row["longitude"])
            lat = float(row["latitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if west is not None and not (west <= lon <= east and south <= lat <= north):  # type: ignore[operator]
            continue
        props = {
            "acq_date": row.get("acq_date"),
            "acq_time": row.get("acq_time"),
            "confidence": row.get("confidence"),
            "frp": row.get("frp"),
            "bright_ti4": row.get("bright_ti4") or row.get("brightness"),
            "satellite": row.get("satellite"),
            "daynight": row.get("daynight"),
            "not_official_perimeter": True,
            "not_burned_area": True,
            "source": source_label,
            "note": "FIRMS hotspot pixel (~375m) — not fire front / official perimeter",
        }
        feats.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    return feats


def _download_text(url: str, *, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_firms_hotspots(
    *,
    bbox: tuple[float, float, float, float],
    map_key: str | None = None,
    day_range: int = 1,
    source: str = DEFAULT_SOURCE,
    timeout: float = 60.0,
    fixture_csv: Path | str | None = None,
    allow_network: bool = True,
    prefer_area_api: bool = True,
) -> dict[str, Any]:
    """Fetch FIRMS hotspots for a bbox.

    Connectivity status values:
      - connected: live HTTP success (area API or public Europe CSV)
      - fixture: loaded from local CSV (tests / offline demos)
      - skipped: allow_network=False or empty key path without open fallback
      - error: network/parse failure

    Never fabricates points when fetch fails.
    """
    west, south, east, north = (float(x) for x in bbox)
    if west > east:
        west, east = east, west
    if south > north:
        south, north = north, south
    bbox_t = (west, south, east, north)

    out: dict[str, Any] = {
        "schema": "wfd_firms_fetch_v1",
        "connectivity": "skipped",
        "source_mode": None,
        "source_url": None,
        "n_hotspots": 0,
        "features": [],
        "bbox": list(bbox_t),
        "day_range": int(day_range),
        "reasons": [],
        "honesty": {
            "not_official_perimeter": True,
            "not_burned_area": True,
            "nrt_not_realtime_ops": True,
            "latency_note": "FIRMS NRT latency is typically hours, not second-by-second ops CAD",
            "not_tactical_dispatch": True,
        },
    }

    # 1) Fixture / offline file (always preferred when provided)
    if fixture_csv is not None:
        path = Path(fixture_csv)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            out["connectivity"] = "error"
            out["reasons"].append(f"fixture_read_failed:{exc}")
            return out
        feats = parse_firms_csv(text, bbox=bbox_t, source_label=f"FIRMS/fixture:{path.name}")
        out["connectivity"] = "fixture"
        out["source_mode"] = "fixture_csv"
        out["source_url"] = str(path)
        out["features"] = feats
        out["n_hotspots"] = len(feats)
        if not feats:
            out["reasons"].append("zero_hotspots_in_fixture_bbox")
        return out

    if not allow_network:
        out["connectivity"] = "skipped"
        out["source_mode"] = "offline"
        out["reasons"].append("allow_network_false")
        return out

    key = (map_key if map_key is not None else os.environ.get("FIRMS_MAP_KEY") or "").strip()

    # 2) Area API with MAP_KEY (precise bbox, smaller payload)
    if prefer_area_api and key:
        url = FIRMS_AREA_API_TMPL.format(
            map_key=key,
            source=source,
            west=west,
            south=south,
            east=east,
            north=north,
            day_range=max(1, min(int(day_range), 10)),
        )
        out["source_url"] = url.replace(key, "***")
        try:
            text = _download_text(url, timeout=timeout)
            feats = parse_firms_csv(text, bbox=bbox_t, source_label=f"FIRMS/area/{source}")
            out["connectivity"] = "connected"
            out["source_mode"] = "area_api"
            out["features"] = feats
            out["n_hotspots"] = len(feats)
            if not feats:
                out["reasons"].append("zero_hotspots_in_area")
            return out
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            out["reasons"].append(f"area_api_failed:{type(exc).__name__}:{exc}")
            # fall through to public Europe CSV

    # 3) Public Europe 24h CSV (no key) + client-side bbox filter
    url = FIRMS_EUROPE_VIIRS_24H
    out["source_url"] = url
    try:
        text = _download_text(url, timeout=timeout)
        feats = parse_firms_csv(text, bbox=bbox_t, source_label="FIRMS/Europe_VIIRS_24h")
        out["connectivity"] = "connected"
        out["source_mode"] = "public_europe_csv"
        out["features"] = feats
        out["n_hotspots"] = len(feats)
        if not key:
            out["reasons"].append("no_FIRMS_MAP_KEY_used_public_europe_csv")
        if not feats:
            out["reasons"].append("zero_hotspots_in_bbox_after_public_csv")
        return out
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        out["connectivity"] = "error"
        out["source_mode"] = "public_europe_csv"
        out["reasons"].append(f"public_csv_failed:{type(exc).__name__}:{exc}")
        out["features"] = []
        out["n_hotspots"] = 0
        return out
