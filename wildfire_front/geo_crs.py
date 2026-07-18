"""Minimal CRS helpers for web-friendly GeoJSON (UTM 30N ↔ WGS84).

Used so geojson.io / Leaflet see lon/lat, not projected meters.
"""

from __future__ import annotations

import math
from typing import Any


def utm_to_wgs84(
    easting: float,
    northing: float,
    *,
    zone: int = 30,
    northern: bool = True,
) -> tuple[float, float]:
    """Convert UTM to WGS84 lon/lat degrees. Returns (lon, lat)."""
    # Karney / USGS reverse formulas (WGS84)
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    x = float(easting) - 500000.0
    y = float(northing)
    if not northern:
        y -= 10000000.0

    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))

    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_phi = math.sin(phi1)
    cos_phi = math.cos(phi1)
    tan_phi = math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * sin_phi**2)
    t1 = tan_phi**2
    c1 = ep2 * cos_phi**2
    r1 = a * (1 - e2) / (1 - e2 * sin_phi**2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * tan_phi / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    lon = (
        lon0
        + (
            d
            - (1 + 2 * t1 + c1) * d**3 / 6
            + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
        )
        / cos_phi
    )

    return math.degrees(lon), math.degrees(lat)


def looks_projected_meters(x: float, y: float) -> bool:
    """Heuristic: UTM-style eastings/northings vs lon/lat."""
    return abs(x) > 180.0 or abs(y) > 90.0


def transform_coords(
    coords: Any,
    *,
    zone: int = 30,
    northern: bool = True,
) -> Any:
    """Recursively transform coordinate arrays [x,y] or [x,y,z] if projected."""
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        x, y = float(coords[0]), float(coords[1])
        if looks_projected_meters(x, y):
            lon, lat = utm_to_wgs84(x, y, zone=zone, northern=northern)
            out = [round(lon, 7), round(lat, 7)]
            if len(coords) > 2:
                out.append(coords[2])
            return out
        return list(coords)
    return [transform_coords(c, zone=zone, northern=northern) for c in coords]


def geojson_to_wgs84(
    data: dict[str, Any],
    *,
    zone: int = 30,
    northern: bool = True,
) -> dict[str, Any]:
    """Return a copy of a GeoJSON FeatureCollection in WGS84 lon/lat."""
    import copy

    out = copy.deepcopy(data)
    # Drop obsolete crs member (RFC 7946)
    out.pop("crs", None)
    for feat in out.get("features") or []:
        geom = feat.get("geometry")
        if not geom:
            continue
        if "coordinates" in geom:
            geom["coordinates"] = transform_coords(
                geom["coordinates"], zone=zone, northern=northern
            )
    props = out.get("properties")
    if isinstance(props, dict):
        props = dict(props)
        props["crs"] = "EPSG:4326"
        props["source_crs_assumed"] = f"EPSG:326{zone:02d}" if northern else f"EPSG:327{zone:02d}"
        out["properties"] = props
    else:
        out["properties"] = {"crs": "EPSG:4326"}
    return out
