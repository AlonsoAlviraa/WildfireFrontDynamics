#!/usr/bin/env python3
"""Enrich La Mierla open pack with multi-sensor FIRMS + STAC S2 + viewer deep-links.

Honest limits:
  - Google Maps / Earth satellite *tiles* are not scraped (ToS / anti-bot).
  - We emit deep-links to Maps/Earth/Worldview/FIRMS for human inspection.
  - Esri World Imagery basemap is used in map_satellite.html (public tile URL).
  - Sentinel-2 via Element84 Earth Search STAC (metadata + asset hrefs).
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EVENT = "guadalajara_la_mierla_20260717"
PACK = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
FIRMS_DIR = ROOT / "outputs" / "firms" / EVENT
SAT_DIR = PACK / "satellite_enrichment"

# Observed fire core (from prior FIRMS extent) + pad
LAT0, LAT1 = 40.85, 41.40
LON0, LON1 = -3.35, -2.75

UA = "WildfireFrontDynamics/1.0 (open emergency research)"

FIRMS_SOURCES = {
    "viirs_n20_24h": (
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
        "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv"
    ),
    "viirs_n21_24h": (
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
        "noaa-21-viirs-c2/csv/J2_VIIRS_C2_Europe_24h.csv"
    ),
    "viirs_snpp_24h": (
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
        "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Europe_24h.csv"
    ),
    "modis_24h": (
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
        "modis-c6.1/csv/MODIS_C6_1_Europe_24h.csv"
    ),
    "viirs_n20_7d": (
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
        "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_7d.csv"
    ),
}

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1/search"


def download(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def filter_rows(text: str) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(text)))
    out: list[dict[str, str]] = []
    for r in rows:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if LAT0 <= lat <= LAT1 and LON0 <= lon <= LON1:
            out.append(r)
    return out


def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts_u = sorted(set(points))
    if len(pts_u) <= 2:
        return pts_u
    lower: list[tuple[float, float]] = []
    for p in pts_u:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts_u):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def ring_area_ha(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    lat0 = mean(p[1] for p in ring) * math.pi / 180
    m_lat = 111320.0
    m_lon = 111320.0 * math.cos(lat0)
    xy = [(p[0] * m_lon, p[1] * m_lat) for p in ring]
    a = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5 / 10000.0


def rows_to_geojson(rows: list[dict[str, str]], sensor: str) -> dict[str, Any]:
    feats = []
    for r in rows:
        lat, lon = float(r["latitude"]), float(r["longitude"])
        frp = r.get("frp") or r.get("FRP") or ""
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "sensor": sensor,
                    "acq_date": r.get("acq_date"),
                    "acq_time": r.get("acq_time"),
                    "confidence": r.get("confidence") or r.get("confidence"),
                    "frp": frp,
                    "bright_ti4": r.get("bright_ti4") or r.get("brightness"),
                    "satellite": r.get("satellite"),
                    "instrument": r.get("instrument"),
                    "fire_id": EVENT,
                    "not_official_perimeter": True,
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    return {
        "type": "FeatureCollection",
        "features": feats,
        "properties": {
            "sensor": sensor,
            "n": len(feats),
            "event_id": EVENT,
            "not_official_perimeter": True,
        },
    }


def metrics_from_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    lats = [float(r["latitude"]) for r in rows]
    lons = [float(r["longitude"]) for r in rows]
    frps: list[float] = []
    for r in rows:
        try:
            frps.append(float(r.get("frp") or r.get("FRP") or 0))
        except ValueError:
            frps.append(0.0)
    pts = list(zip(lons, lats, strict=False))
    hull = convex_hull(pts)
    ring = hull + [hull[0]] if len(hull) >= 3 else []
    dates = sorted({r.get("acq_date", "") for r in rows if r.get("acq_date")})
    by_date: dict[str, int] = {}
    for r in rows:
        d = r.get("acq_date") or "?"
        by_date[d] = by_date.get(d, 0) + 1
    return {
        "n": len(rows),
        "acq_dates": dates,
        "counts_by_date": dict(sorted(by_date.items())),
        "extent": {
            "lat_min": min(lats),
            "lat_max": max(lats),
            "lon_min": min(lons),
            "lon_max": max(lons),
        },
        "frp_mw": {
            "mean": round(mean(frps), 2) if frps else None,
            "max": round(max(frps), 2) if frps else None,
            "sum": round(sum(frps), 2) if frps else None,
        },
        "hull_area_ha_approx": round(ring_area_ha(ring), 1) if ring else 0.0,
    }


def stac_search_s2(
    bbox: list[float],
    datetime_range: str,
    max_cloud: float = 80.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": datetime_range,
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    req = urllib.request.Request(
        EARTH_SEARCH,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
            "User-Agent": UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return list(payload.get("features") or [])


def summarize_stac(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for it in items:
        props = it.get("properties") or {}
        assets = it.get("assets") or {}
        visual = None
        for key in ("visual", "thumbnail", "overview", "rendered_preview"):
            if key in assets and isinstance(assets[key], dict):
                visual = assets[key].get("href")
                break
        out.append(
            {
                "id": it.get("id"),
                "datetime": props.get("datetime"),
                "eo:cloud_cover": props.get("eo:cloud_cover"),
                "platform": props.get("platform"),
                "bbox": it.get("bbox"),
                "visual_href": visual,
                "stac_self": (it.get("links") or [{}])[0].get("href")
                if it.get("links")
                else None,
            }
        )
    return out


def viewer_links(lat: float, lon: float, zoom: int = 11) -> dict[str, str]:
    """Deep-links for human inspection (not scraped tile dumps)."""
    # Worldview uses lat,lon,zoom and layer list
    wv_layers = (
        "VIIRS_NOAA20_Thermal_Anomalies_375m_Day,"
        "VIIRS_NOAA20_Thermal_Anomalies_375m_Night,"
        "MODIS_Aqua_Thermal_Anomalies_All,"
        "MODIS_Terra_Thermal_Anomalies_All,"
        "VIIRS_SNPP_CorrectedReflectance_TrueColor,"
        "Reference_Labels_15m"
    )
    # FIRMS advanced map center
    firms = (
        f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@"
        f"{lon:.4f},{lat:.4f},{zoom}z"
    )
    worldview = (
        f"https://worldview.earthdata.nasa.gov/?v="
        f"{lon - 0.55},{lat - 0.35},{lon + 0.55},{lat + 0.35}"
        f"&l={wv_layers}&t=2026-07-20"
    )
    gmaps_sat = (
        f"https://www.google.com/maps/@{lat:.5f},{lon:.5f},{zoom}z/data=!3m1!1e3"
    )
    gmaps_search = (
        f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"
    )
    gearth = (
        f"https://earth.google.com/web/search/{lat:.5f},{lon:.5f}/"
        f"@{lat:.5f},{lon:.5f},2500a,12000d,35y,0h,0t,0r"
    )
    osm = f"https://www.openstreetmap.org/#map={zoom}/{lat:.5f}/{lon:.5f}"
    # Esri satellite viewer via ArcGIS
    esri = (
        "https://www.arcgis.com/home/webmap/viewer.html?"
        f"center={lon:.5f},{lat:.5f}&level={zoom}&basemapUrl="
        "https://services.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer"
    )
    # Sentinel Hub EO Browser
    eob = (
        "https://apps.sentinel-hub.com/eo-browser/?"
        f"lat={lat:.5f}&lng={lon:.5f}&zoom={zoom}"
        f"&datasetId=S2L2A&fromTime=2026-07-14T00%3A00%3A00.000Z"
        f"&toTime=2026-07-21T23%3A59%3A59.999Z"
    )
    return {
        "google_maps_satellite": gmaps_sat,
        "google_maps_search": gmaps_search,
        "google_earth_web": gearth,
        "nasa_worldview": worldview,
        "nasa_firms_map": firms,
        "sentinel_hub_eo_browser": eob,
        "esri_world_imagery_viewer": esri,
        "openstreetmap": osm,
    }


def write_satellite_map(
    path: Path,
    multi_geo: dict[str, Any],
    hull_geo: dict[str, Any],
    center: tuple[float, float],
    n: int,
    links: dict[str, str],
) -> None:
    _ = (n, links)  # kept for call-site API; not shown on map UI
    multi_js = json.dumps(multi_geo, ensure_ascii=False, separators=(",", ":"))
    hull_js = json.dumps(hull_geo, ensure_ascii=False, separators=(",", ":"))
    lat, lon = center
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>La Mierla — FIRMS multi-sensor</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body {{ margin:0; font-family: system-ui,sans-serif; background:#0b0b0b; color:#eee; }}
#map {{ height:100vh; width:100%; }}
.legend {{ position:absolute; z-index:1000; bottom:28px; left:12px;
  background:rgba(12,12,14,0.88); padding:8px 12px; border-radius:8px; font-size:12px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }}
</style>
</head>
<body>
<div class="legend">
  <div><span class="dot" style="background:#ff3300"></span>VIIRS N20</div>
  <div><span class="dot" style="background:#ff8800"></span>VIIRS N21</div>
  <div><span class="dot" style="background:#ffcc00"></span>VIIRS SNPP</div>
  <div><span class="dot" style="background:#cc66ff"></span>MODIS</div>
  <div><span class="dot" style="background:#ffff66;border-radius:2px;width:14px;height:3px"></span>Hull</div>
</div>
<div id="map"></div>
<script>
const MULTI = {multi_js};
const HULL = {hull_js};
const colors = {{
  viirs_n20_24h:'#ff3300', viirs_n20_7d:'#ff5522',
  viirs_n21_24h:'#ff8800', viirs_snpp_24h:'#ffcc00', modis_24h:'#cc66ff'
}};
const map = L.map('map').setView([{lat:.5}, {lon:.5}], 10);
const esri = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{ maxZoom: 18, attribution: 'Tiles &copy; Esri' }}
).addTo(map);
const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18, attribution: '&copy; OSM'
}});
L.control.layers({{ 'Esri satélite': esri, 'OpenStreetMap': osm }}, null, {{collapsed:true}}).addTo(map);

const bounds = [];
L.geoJSON(HULL, {{
  style: {{ color:'#ffff66', weight:2.5, fillColor:'#ffaa00', fillOpacity:0.08 }},
  onEachFeature: (f, layer) => {{ if (layer.getBounds) bounds.push(layer.getBounds()); }}
}}).addTo(map);

L.geoJSON(MULTI, {{
  pointToLayer: (f, latlng) => {{
    const s = (f.properties && f.properties.sensor) || 'viirs_n20_24h';
    const frp = parseFloat((f.properties && f.properties.frp) || 0) || 0;
    const r = Math.max(3, Math.min(12, 2.5 + Math.sqrt(frp) * 0.85));
    return L.circleMarker(latlng, {{
      radius: r,
      color: colors[s] || '#ff4400',
      fillColor: colors[s] || '#ff6600',
      fillOpacity: 0.8,
      weight: 0.8
    }});
  }},
  onEachFeature: (f, layer) => {{
    bounds.push(L.latLngBounds([layer.getLatLng()]));
    const p = f.properties || {{}};
    layer.bindPopup(
      '<b>' + (p.sensor||'') + '</b><br/>' +
      (p.acq_date||'') + ' ' + (p.acq_time||'') + '<br/>' +
      'FRP ' + (p.frp||'?') + ' · conf ' + (p.confidence||'?')
    );
  }}
}}).addTo(map);

if (bounds.length) {{
  let u = bounds[0];
  for (let i=1;i<bounds.length;i++) u.extend(bounds[i]);
  map.fitBounds(u.pad(0.1));
}}
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main() -> int:
    SAT_DIR.mkdir(parents=True, exist_ok=True)
    FIRMS_DIR.mkdir(parents=True, exist_ok=True)
    PACK.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()

    sensor_stats: dict[str, Any] = {}
    all_feats: list[dict[str, Any]] = []
    all_pts: list[tuple[float, float]] = []
    errors: list[str] = []

    for key, url in FIRMS_SOURCES.items():
        try:
            text = download(url)
            rows = filter_rows(text)
            m = metrics_from_rows(rows)
            m["url"] = url
            sensor_stats[key] = m
            gj = rows_to_geojson(rows, key)
            (SAT_DIR / f"firms_{key}.geojson").write_text(
                json.dumps(gj, indent=2), encoding="utf-8"
            )
            # also store 7d as timeline-friendly
            if key == "viirs_n20_7d":
                (PACK / "firms_hotspots_7d.geojson").write_text(
                    json.dumps(gj, indent=2), encoding="utf-8"
                )
                (FIRMS_DIR / "firms_viirs_n20_7d_filtered.csv").write_text(
                    # rewrite filtered csv
                    "",
                    encoding="utf-8",
                )
                if rows:
                    with (FIRMS_DIR / "firms_viirs_n20_7d_filtered.csv").open(
                        "w", encoding="utf-8", newline=""
                    ) as f:
                        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        w.writeheader()
                        w.writerows(rows)
            for ft in gj["features"]:
                # tag for multi layer
                all_feats.append(ft)
                c = ft["geometry"]["coordinates"]
                all_pts.append((c[0], c[1]))
            print(f"  {key}: n={m['n']} dates={m.get('acq_dates')}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{key}: {type(e).__name__}: {e}")
            sensor_stats[key] = {"n": 0, "error": str(e), "url": url}
            print(f"  FAIL {key}: {e}")

    # Dedup roughly by rounded lon/lat/date for multi layer display (keep all for raw sensors)
    multi = {
        "type": "FeatureCollection",
        "features": all_feats,
        "properties": {
            "event_id": EVENT,
            "n": len(all_feats),
            "sensors": list(FIRMS_SOURCES.keys()),
            "generated_at_utc": now,
            "not_official_perimeter": True,
        },
    }
    (SAT_DIR / "firms_multi_sensor_union.geojson").write_text(
        json.dumps(multi, indent=2), encoding="utf-8"
    )

    hull = convex_hull(all_pts) if all_pts else []
    ring = hull + [hull[0]] if len(hull) >= 3 else []
    hull_ha = ring_area_ha(ring) if ring else 0.0
    hull_geo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer": "multi_sensor_hull",
                    "approx_area_ha_from_hull": round(hull_ha, 1),
                    "n_points": len(all_pts),
                    "not_official_perimeter": True,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(p) for p in ring]] if ring else [],
                },
            }
        ],
    }
    (SAT_DIR / "firms_multi_hull.geojson").write_text(
        json.dumps(hull_geo, indent=2), encoding="utf-8"
    )

    # Center from extent
    if all_pts:
        lat_c = mean(p[1] for p in all_pts)
        lon_c = mean(p[0] for p in all_pts)
        ext = {
            "lat_min": min(p[1] for p in all_pts),
            "lat_max": max(p[1] for p in all_pts),
            "lon_min": min(p[0] for p in all_pts),
            "lon_max": max(p[0] for p in all_pts),
        }
    else:
        lat_c, lon_c = 41.10, -3.05
        ext = {"lat_min": LAT0, "lat_max": LAT1, "lon_min": LON0, "lon_max": LON1}

    links = viewer_links(lat_c, lon_c, zoom=11)

    # STAC Sentinel-2: fire window 14–21 jul 2026 + pre-fire for dNBR later
    bbox = [ext["lon_min"] - 0.05, ext["lat_min"] - 0.05, ext["lon_max"] + 0.05, ext["lat_max"] + 0.05]
    stac_meta: dict[str, Any] = {"bbox": bbox, "searches": {}}
    for label, dt_range, cloud in (
        ("during_fire_14_21_jul", "2026-07-14T00:00:00Z/2026-07-21T23:59:59Z", 90.0),
        ("pre_fire_01_15_jul", "2026-07-01T00:00:00Z/2026-07-15T23:59:59Z", 60.0),
        ("strict_clear_during", "2026-07-16T00:00:00Z/2026-07-21T23:59:59Z", 40.0),
    ):
        try:
            items = stac_search_s2(bbox, dt_range, max_cloud=cloud, limit=15)
            summaries = summarize_stac(items)
            stac_meta["searches"][label] = {
                "datetime": dt_range,
                "max_cloud": cloud,
                "n_items": len(summaries),
                "items": summaries,
            }
            print(f"  STAC {label}: {len(summaries)} items")
        except Exception as e:  # noqa: BLE001
            stac_meta["searches"][label] = {"error": str(e), "datetime": dt_range}
            errors.append(f"stac {label}: {e}")
            print(f"  STAC FAIL {label}: {e}")

    (SAT_DIR / "sentinel2_stac_search.json").write_text(
        json.dumps(stac_meta, indent=2), encoding="utf-8"
    )

    # Timeline counts from 7d if available
    timeline = sensor_stats.get("viirs_n20_7d", {}).get("counts_by_date") or {}

    report = {
        "event_id": EVENT,
        "generated_at_utc": now,
        "bbox_filter": {
            "lat_min": LAT0,
            "lat_max": LAT1,
            "lon_min": LON0,
            "lon_max": LON1,
        },
        "extent_union": ext,
        "center": {"lat": round(lat_c, 5), "lon": round(lon_c, 5)},
        "multi_sensor_n_points": len(all_feats),
        "multi_hull_ha_approx": round(hull_ha, 1),
        "sensors": sensor_stats,
        "timeline_viirs_n20_7d": timeline,
        "viewer_deep_links": links,
        "google_maps_note": (
            "Google Maps/Earth satellite raster tiles are NOT downloaded or scraped "
            "(violates ToS / CAPTCHA). Deep-links open the official viewers at fire centroid. "
            "For basemap imagery in-repo we use Esri World Imagery public tiles + NASA FIRMS/GIBS."
        ),
        "sentinel2_stac": {
            k: {
                "n_items": v.get("n_items"),
                "error": v.get("error"),
                "clearest": (v.get("items") or [None])[0],
            }
            for k, v in stac_meta.get("searches", {}).items()
        },
        "errors": errors,
        "artifacts": {
            "map_satellite": "map_satellite.html",
            "multi_geojson": "satellite_enrichment/firms_multi_sensor_union.geojson",
            "stac": "satellite_enrichment/sentinel2_stac_search.json",
            "report": "satellite_enrichment/enrichment_report.json",
            "brief": "satellite_enrichment/SATELLITE_BRIEF.md",
        },
    }
    (SAT_DIR / "enrichment_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (PACK / "satellite_enrichment_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    write_satellite_map(
        PACK / "map_satellite.html",
        multi,
        hull_geo,
        (lat_c, lon_c),
        len(all_feats),
        links,
    )

    # Markdown brief
    s2_lines = []
    for label, block in stac_meta.get("searches", {}).items():
        n_it = block.get("n_items")
        if block.get("error"):
            s2_lines.append(f"- **{label}**: ERROR {block['error']}")
            continue
        items = block.get("items") or []
        top = items[0] if items else None
        if top:
            s2_lines.append(
                f"- **{label}**: {n_it} escenas · top `{top.get('id')}` "
                f"cloud={top.get('eo:cloud_cover')} · {top.get('datetime')}"
            )
        else:
            s2_lines.append(f"- **{label}**: 0 escenas (nubes / gap STAC)")

    sensor_lines = []
    for k, m in sensor_stats.items():
        if m.get("error"):
            sensor_lines.append(f"| {k} | ERROR | — | — |")
        else:
            sensor_lines.append(
                f"| {k} | {m.get('n')} | {m.get('frp_mw', {}).get('max')} | "
                f"{m.get('hull_area_ha_approx')} |"
            )

    brief = f"""# Satellite enrichment — La Mierla ({EVENT})

**Generated:** {now}

## Qué se hizo (y qué no)

| Fuente | Acción | ¿Scraping de tiles? |
|--------|--------|---------------------|
| NASA FIRMS multi-sensor | Descarga CSV NRT filtrado bbox | No (datos abiertos CSV) |
| Sentinel-2 L2A STAC | Búsqueda Element84 Earth Search | No (metadatos + href COG) |
| Esri World Imagery | Basemap en `map_satellite.html` | Tiles públicos de visualización |
| Google Maps / Earth | **Solo deep-links** al centroide | **No** — ToS prohíbe scrape de tiles |
| NASA Worldview / FIRMS map | Deep-links | No |

## FIRMS multi-sensor (bbox Sierra Norte GU)

| Sensor | n hotspots | FRP max (MW) | Hull ~ha |
|--------|------------|--------------|----------|
{chr(10).join(sensor_lines)}

**Unión puntos (con solapes entre sensores):** {len(all_feats)}  
**Hull multi-sensor ~ha:** {hull_ha:.0f} (proxy térmico, no área quemada oficial)

### Timeline VIIRS N20 7 días (conteos por fecha)

```json
{json.dumps(timeline, indent=2)}
```

## Sentinel-2 (STAC)

Bbox búsqueda: `{bbox}`

{chr(10).join(s2_lines)}

Si `strict_clear_during` tiene nubes altas, el dNBR open habrá que esperar post-fuego o usar HLS/Worldview true-color.

## Enlaces viewers (clic en navegador)

- [Google Maps satélite]({links["google_maps_satellite"]})
- [Google Earth web]({links["google_earth_web"]})
- [NASA Worldview (anomalías térmicas)]({links["nasa_worldview"]})
- [NASA FIRMS map]({links["nasa_firms_map"]})
- [Sentinel Hub EO Browser]({links["sentinel_hub_eo_browser"]})
- [Esri World Imagery]({links["esri_world_imagery_viewer"]})
- [OpenStreetMap]({links["openstreetmap"]})

## Artefactos locales

- [map_satellite.html](../map_satellite.html) — mapa con basemap satélite + multi-sensor
- [firms_multi_sensor_union.geojson](firms_multi_sensor_union.geojson)
- [sentinel2_stac_search.json](sentinel2_stac_search.json)
- [enrichment_report.json](enrichment_report.json)

## Lectura operativa (honesta)

1. Multi-sensor confirma núcleo activo Sierra Norte GU (lat ~{lat_c:.2f}, lon ~{lon_c:.2f}).
2. Hull y FRP miden **actividad térmica satélite**, no perímetro EGIF ni ROS.
3. Google Maps sirve para contexto orográfico/urbanizaciones; **no** sustituye LWIR/INFOCAM.
4. Siguiente salto de valor: dNBR cuando haya S2/HLS claro post-frente.
"""
    (SAT_DIR / "SATELLITE_BRIEF.md").write_text(brief, encoding="utf-8")

    # Update pack manifest if exists
    man_path = PACK / "manifest.json"
    if man_path.is_file():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        layers = man.setdefault("layers", {})
        layers["map_satellite"] = "map_satellite.html"
        layers["satellite_enrichment"] = "satellite_enrichment/"
        layers["firms_hotspots_7d"] = "firms_hotspots_7d.geojson"
        man["satellite_enrichment_at_utc"] = now
        man_path.write_text(json.dumps(man, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "multi_n": len(all_feats),
                "hull_ha": round(hull_ha, 1),
                "map": str(PACK / "map_satellite.html"),
                "brief": str(SAT_DIR / "SATELLITE_BRIEF.md"),
                "errors": errors,
            },
            indent=2,
        )
    )
    return 0 if not errors or len(all_feats) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
