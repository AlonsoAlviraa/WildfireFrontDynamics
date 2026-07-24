#!/usr/bin/env python3
"""Build open-only pack for IF La Mierla (Guadalajara) from FIRMS NRT + scrape metadata.

Does NOT produce official perimeter, LWIR ROS, or confirmed anchors.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
EVENT = "guadalajara_la_mierla_20260717"
URL = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv"
)
LAT0, LAT1 = 40.70, 41.40
LON0, LON1 = -3.40, -2.70


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


def main() -> int:
    pack = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
    firms_dir = ROOT / "outputs" / "firms" / EVENT
    pack.mkdir(parents=True, exist_ok=True)
    firms_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()

    scrape = {
        "scraped_at_utc": now,
        "press": [
            {
                "as_of": "2026-07-20",
                "ha": 26000,
                "perimeter_km": 120,
                "evacuated_people": 1200,
                "evacuated_municipalities": 33,
                "source": "elpais.com",
                "url": (
                    "https://elpais.com/espana/2026-07-20/"
                    "las-llamas-no-dan-tregua-en-la-mierla-32-pueblos-evacuados-"
                    "y-26000-hectareas-afectadas.html"
                ),
                "notes": "PMA Tamajon; nivel 2; amenaza Soria; ~400 efectivos",
            },
            {
                "as_of": "2026-07-21",
                "ha": 29000,
                "evacuated_municipalities": 34,
                "confined_municipalities": 14,
                "evacuated_people": 1200,
                "source": "europapress / INFOCAM X",
                "url": (
                    "https://www.europapress.es/castilla-lamancha/noticia-sucesos-"
                    "incendio-mierla-guadalajara-frena-avance-soria-afecta-ya-29000-"
                    "hectareas-20260721105632.html"
                ),
                "notes": (
                    "frena avance Soria; Page luz mas alla del humo; "
                    "campamento ~100 ninos; BRIF reconocimiento; "
                    "evac Barcones + residencia Retortillo (Soria)"
                ),
            },
        ],
        "x_official": [
            {
                "handle": "@Plan_INFOCAM",
                "post_id": "2079484888751710377",
                "when_utc": "2026-07-21T08:33:27Z",
                "text_summary": (
                    "Nivel 2; 29.000 ha estimadas; 34 municipios evacuados + 14 "
                    "confinados; >1.200 personas; 72 terrestres / 394 efectivos; "
                    "fuego tecnico + maquinaria noche"
                ),
                "confidence": "primary_official",
            },
            {
                "handle": "@Plan_INFOCAM",
                "post_id": "2079512599058592198",
                "when_utc": "2026-07-21T10:23:33Z",
                "text_summary": (
                    "Viceconsejero Almodovar PMA Guadalajara: Nivel 2 moviliza "
                    "todos recursos; Nivel 3 = cambio direccion, no mas medios"
                ),
                "confidence": "primary_official",
            },
            {
                "handle": "@AT_Brif",
                "post_id": "2079513423402893431",
                "when_utc": "2026-07-21T10:26:50Z",
                "text_summary": "BRIF Tabuyo reconocimiento aereo #IFLaMierla",
            },
            {
                "handle": "@europapress",
                "post_id": "2079516083950612662",
                "when_utc": "2026-07-21T10:37:24Z",
                "text_summary": "29.000 ha; campamento 100 ninos; situacion muy complicada",
            },
            {
                "handle": "@Plan_INFOCAM",
                "post_id": "2079310609129124093",
                "when_utc": "2026-07-20T21:00:55Z",
                "text_summary": (
                    "Noche 20 jul: Nivel 2; 34+14; 74 terrestres / 424 efectivos; "
                    "CECOPI ataque cabeza con bajada temp"
                ),
            },
        ],
        "infocam_latest": {
            "as_of_utc": "2026-07-21T08:33:27Z",
            "level": 2,
            "ha_estimated": 29000,
            "evacuated_municipalities": 34,
            "confined_municipalities": 14,
            "people_affected": 1200,
            "terrestrial_means": 72,
            "personnel": 394,
            "source_post_id": "2079484888751710377",
            "note": "Official INFOCAM X update; ha still provisional estimate",
        },
        "cems": {
            "status": "WATCH",
            "note": (
                "EMSR896 is Aragon (Ores path). No confirmed EMSR for La Mierla "
                "in this scrape; recheck mapping.emergency.copernicus.eu"
            ),
            "related_news": (
                "https://mapping.emergency.copernicus.eu/news/wildfire-in-aragon-spain-emsr896/"
            ),
        },
    }

    req = urllib.request.Request(URL, headers={"User-Agent": "WildfireFrontDynamics/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    sel: list[dict] = []
    for r in rows:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if LAT0 <= lat <= LAT1 and LON0 <= lon <= LON1:
            sel.append(r)

    csv_path = firms_dir / "firms_viirs_nrt_24h_filtered.csv"
    if sel:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sel[0].keys()))
            w.writeheader()
            w.writerows(sel)

    feats = []
    pts: list[tuple[float, float]] = []
    frps: list[float] = []
    for r in sel:
        lat, lon = float(r["latitude"]), float(r["longitude"])
        pts.append((lon, lat))
        try:
            frps.append(float(r.get("frp") or 0))
        except ValueError:
            frps.append(0.0)
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "acq_date": r.get("acq_date"),
                    "acq_time": r.get("acq_time"),
                    "confidence": r.get("confidence"),
                    "frp": r.get("frp"),
                    "bright_ti4": r.get("bright_ti4"),
                    "satellite": r.get("satellite"),
                    "fire_id": EVENT,
                    "not_official_perimeter": True,
                    "note": "NASA FIRMS VIIRS hotspot pixel ~375m, not fire front",
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    firms_gj = {
        "type": "FeatureCollection",
        "features": feats,
        "properties": {
            "source": URL,
            "n": len(feats),
            "generated_at_utc": now,
            "not_official_perimeter": True,
            "event_id": EVENT,
        },
    }
    for p in (firms_dir / "firms_hotspots_wgs84.geojson", pack / "firms_hotspots.geojson"):
        p.write_text(json.dumps(firms_gj, indent=2), encoding="utf-8")

    hull = convex_hull(pts) if pts else []
    hull_ring = hull + [hull[0]] if len(hull) >= 3 else []
    hull_ha = ring_area_ha(hull_ring) if hull_ring else 0.0
    if hull:
        pad = 0.02
        aoi = [
            [min(p[0] for p in hull) - pad, min(p[1] for p in hull) - pad],
            [max(p[0] for p in hull) + pad, min(p[1] for p in hull) - pad],
            [max(p[0] for p in hull) + pad, max(p[1] for p in hull) + pad],
            [min(p[0] for p in hull) - pad, max(p[1] for p in hull) + pad],
        ]
        aoi.append(aoi[0])
    else:
        aoi = [
            [LON0, LAT0],
            [LON1, LAT0],
            [LON1, LAT1],
            [LON0, LAT1],
            [LON0, LAT0],
        ]

    footprint = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer": "firms_convex_hull",
                    "not_official_perimeter": True,
                    "method": "convex_hull_of_viirs_hotspots_24h",
                    "approx_area_ha_from_hull": round(hull_ha, 1),
                    "n_hotspots": len(pts),
                    "disclaimer": (
                        "Proxy footprint only. Press ha ~26-29k; "
                        "hull is lower bound of active thermal pixels."
                    ),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(p) for p in hull_ring]] if hull_ring else [],
                },
            },
            {
                "type": "Feature",
                "properties": {"layer": "aoi_bbox", "not_official_perimeter": True},
                "geometry": {"type": "Polygon", "coordinates": [aoi]},
            },
        ],
    }
    for name in ("firms_footprint_proxy.geojson", "timeline_perimeters.geojson"):
        (pack / name).write_text(json.dumps(footprint, indent=2), encoding="utf-8")

    lats = [p[1] for p in pts]
    lons = [p[0] for p in pts]
    dates = sorted({r.get("acq_date", "") for r in sel})
    firms_metrics = {
        "event_id": EVENT,
        "source": URL,
        "n_hotspots": len(sel),
        "acq_dates": dates,
        "bbox_filter": {
            "lat_min": LAT0,
            "lat_max": LAT1,
            "lon_min": LON0,
            "lon_max": LON1,
        },
        "extent_observed": {
            "lat_min": min(lats) if lats else None,
            "lat_max": max(lats) if lats else None,
            "lon_min": min(lons) if lons else None,
            "lon_max": max(lons) if lons else None,
        },
        "frp_mw": {
            "mean": round(mean(frps), 2) if frps else None,
            "max": round(max(frps), 2) if frps else None,
            "sum": round(sum(frps), 2) if frps else None,
        },
        "hull_area_ha_approx": round(hull_ha, 1),
        "generated_at_utc": now,
    }
    (pack / "firms_metrics.json").write_text(json.dumps(firms_metrics, indent=2), encoding="utf-8")
    (firms_dir / "firms_summary.json").write_text(
        json.dumps(firms_metrics, indent=2), encoding="utf-8"
    )

    ha_press = 29000
    scorecard = {
        "activation": EVENT,
        "track": "open_firms_only",
        "O2_cems_delineation": "NOT_ACTIVATED_OR_UNKNOWN",
        "O2_national_official": "BLOCKED",
        "max_area_ha": ha_press,
        "max_area_ha_source": "infocam_x_estimate_2026-07-21T08:33Z",
        "firms_hull_area_ha_approx": round(hull_ha, 1),
        "n_timeline_steps": 1,
        "n_hotspots_24h": len(sel),
        "civil_protection_level": 2,
        "evacuated_municipalities_reported": 34,
        "confined_municipalities_reported": 14,
        "people_affected_reported": 1200,
        "terrestrial_means_reported": 72,
        "personnel_reported": 394,
        "pma": "Tamajon / Guadalajara",
        "domain": "CLM_Guadalajara",
        "not_official_perimeter": True,
        "not_tactical_dispatch": True,
        "generated_at_utc": now,
        "notes": [
            "Open track only: FIRMS + INFOCAM X + press metadata",
            "29k ha is INFOCAM estimated surface (not EGIF final)",
            "Hull area is NOT burned area (convex hull of thermal pixels)",
            "No LWIR / no confirmed Vp/ha anchor for O1",
        ],
    }
    (pack / "scorecard_pista_b.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")

    manifest = {
        "event_id": EVENT,
        "name": "La Mierla / Sierra Norte de Guadalajara",
        "ccaa": "Castilla-La Mancha",
        "created_at_utc": now,
        "layers": {
            "firms_hotspots": "firms_hotspots.geojson",
            "firms_footprint_proxy": "firms_footprint_proxy.geojson",
            "timeline_perimeters": "timeline_perimeters.geojson",
            "scorecard": "scorecard_pista_b.json",
            "firms_metrics": "firms_metrics.json",
            "scrape": "scrape_latest.json",
            "operator_brief": "operator_brief_open_if.md",
            "map": "map.html",
            "open_metrics_for_decide": "open_metrics_for_decide.json",
        },
        "status": "open_firms_partial",
        "blocked": ["lwir", "official_perimeter", "confirmed_anchor"],
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (pack / "scrape_latest.json").write_text(json.dumps(scrape, indent=2), encoding="utf-8")

    brief = f"""# Operator brief OPEN — La Mierla (GU) {EVENT}

**Generated:** {now}
**Track:** open FIRMS only (no LWIR)
**NOT** official perimeter · **NOT** tactical dispatch

## Situation (open sources, provisional)

| Metric | Value | Source |
|--------|-------|--------|
| Start | 2026-07-16 ~13:55 | COR/Infocam via press |
| ha estimada | **~26,000 (20 jul) → ~29,000 (21 jul)** | INFOCAM X 08:33Z / prensa |
| Perimetro press | ~120 km | El País 20 jul |
| Nivel | **2** | INFOCAM (primary) |
| Evacuados | **>1.200** pers.; **34** mun. evacuados; **14** confinados | INFOCAM X 21 jul 08:33Z |
| Medios 21 jul AM | 72 terrestres / 394 efectivos | INFOCAM X |
| PMA | Tamajón / Guadalajara | El País / INFOCAM |
| FIRMS 24h | **{len(sel)}** hotspots | NASA VIIRS NRT |
| Hull FIRMS ~ha | **{hull_ha:.0f}** (proxy only) | convex hull of pixels |
| FRP mean/max | {firms_metrics["frp_mw"]["mean"]} / {firms_metrics["frp_mw"]["max"]} MW | FIRMS |

## Evolution note (21 jul, scrape)

- **INFOCAM (primary):** Nivel 2; 29.000 ha estimadas; fuego técnico + maquinaria noche; Nivel 3 ≠ más medios.
- **BRIF (@AT_Brif):** reconocimiento aéreo Tabuyo en órbita #IFLaMierla.
- **Prensa:** frena avance a Soria; evacuado Barcones + residencia Retortillo; Page "luz más allá del humo".
- **Orés (contraste Aragón):** estabilizado nivel 1 (no confundir EMSR896).

## WFD product status

| Product | Status |
|---------|--------|
| FIRMS overlay | READY |
| Footprint proxy | READY (hull, not official) |
| CEMS delineation | WATCH (EMSR896 is Aragon) |
| Incident ROS / field GO | BLOCKED (no LWIR + no confirmed anchor) |
| ML CLM v34 on this IF | N/A (no patches) |

## Files

See `manifest.json` in this pack.
"""
    (pack / "operator_brief_open_if.md").write_text(brief, encoding="utf-8")

    # Inline GeoJSON so map works via file:// (fetch of local files is blocked by browsers).
    hotspots_js = json.dumps(firms_gj, ensure_ascii=False, separators=(",", ":"))
    footprint_js = json.dumps(footprint, ensure_ascii=False, separators=(",", ":"))
    lat_c = (
        (firms_metrics["extent_observed"]["lat_min"] + firms_metrics["extent_observed"]["lat_max"])
        / 2
        if pts
        else 41.1
    )
    lon_c = (
        (firms_metrics["extent_observed"]["lon_min"] + firms_metrics["extent_observed"]["lon_max"])
        / 2
        if pts
        else -3.05
    )
    map_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>La Mierla open FIRMS — {EVENT}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body {{ margin:0; font-family: system-ui, sans-serif; background:#111; }}
#map {{ height: 100vh; }}
.banner {{ position:absolute; z-index:1000; top:10px; left:50px; right:10px;
  background:rgba(20,20,20,0.9); color:#fff; padding:10px 14px; border-radius:8px;
  max-width:560px; font-size:13px; line-height:1.35; }}
.banner strong {{ color:#f5a623; }}
.legend {{ position:absolute; z-index:1000; bottom:24px; left:12px;
  background:rgba(20,20,20,0.88); color:#eee; padding:8px 12px; border-radius:8px;
  font-size:12px; }}
.legend span {{ display:inline-block; width:10px; height:10px; border-radius:50%;
  margin-right:6px; vertical-align:middle; }}
</style>
</head>
<body>
<div class="banner">
  <strong>OPEN track only</strong> — FIRMS ≠ perímetro oficial · no despacho táctico<br/>
  {EVENT} · <b id="ncount">{len(sel)}</b> hotspots · press/INFOCAM ~{ha_press} ha · hull~{hull_ha:.0f} ha<br/>
  <span style="opacity:.85">Datos embebidos (funciona abriendo el HTML local). Tiles OSM necesitan red.</span>
</div>
<div class="legend">
  <div><span style="background:#ff6600"></span>Hotspot VIIRS (FRP↑ = mayor)</div>
  <div><span style="background:#ffcc00;border-radius:2px;width:14px;height:3px"></span>Hull proxy (no oficial)</div>
  <div><span style="background:#4488ff;border-radius:2px;width:14px;height:3px"></span>AOI bbox</div>
</div>
<div id="map"></div>
<script>
// Embedded layers (no fetch / no file:// CORS issues)
const HOTSPOTS = {hotspots_js};
const FOOTPRINT = {footprint_js};

const map = L.map('map').setView([{lat_c:.5}, {lon_c:.5}], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18, attribution: '&copy; OpenStreetMap'
}}).addTo(map);

const bounds = [];

const hullLayer = L.geoJSON(FOOTPRINT, {{
  style: f => (f.properties && f.properties.layer === 'firms_convex_hull')
    ? {{color:'#ffcc00', weight:3, fillColor:'#ffaa00', fillOpacity:0.12}}
    : {{color:'#4488ff', weight:1.5, dashArray:'6 4', fillOpacity:0.03}},
  onEachFeature: (f, layer) => {{
    if (layer.getBounds) bounds.push(layer.getBounds());
    const p = f.properties || {{}};
    layer.bindPopup(
      '<b>' + (p.layer || 'polygon') + '</b><br/>' +
      (p.approx_area_ha_from_hull != null ? ('hull ~' + p.approx_area_ha_from_hull + ' ha<br/>') : '') +
      '<i>not_official_perimeter</i>'
    );
  }}
}}).addTo(map);

const hotLayer = L.geoJSON(HOTSPOTS, {{
  pointToLayer: (f, latlng) => {{
    const frp = parseFloat((f.properties && f.properties.frp) || 0) || 0;
    const r = Math.max(4, Math.min(14, 3 + Math.sqrt(frp) * 0.9));
    const fill = frp > 80 ? '#ff2200' : (frp > 20 ? '#ff6600' : '#ffaa33');
    return L.circleMarker(latlng, {{
      radius: r,
      color: '#ff2200',
      fillColor: fill,
      fillOpacity: 0.85,
      weight: 1,
      opacity: 0.95
    }});
  }},
  onEachFeature: (f, layer) => {{
    bounds.push(L.latLngBounds([layer.getLatLng()]));
    const p = f.properties || {{}};
    layer.bindPopup(
      '<b>FIRMS hotspot</b><br/>' +
      (p.acq_date || '') + ' ' + (p.acq_time || '') + '<br/>' +
      'FRP: ' + (p.frp || '?') + ' MW<br/>' +
      'conf: ' + (p.confidence || '?') + '<br/>' +
      '<i>~375 m pixel · no es frente de fuego</i>'
    );
  }}
}}).addTo(map);

const n = (HOTSPOTS.features || []).length;
document.getElementById('ncount').textContent = String(n);
if (bounds.length) {{
  const u = bounds[0];
  for (let i = 1; i < bounds.length; i++) u.extend(bounds[i]);
  map.fitBounds(u.pad(0.12));
}}
if (!n) {{
  L.popup().setLatLng([{lat_c:.5}, {lon_c:.5}])
    .setContent('Sin hotspots embebidos — regenera el pack')
    .openOn(map);
}}
</script>
</body>
</html>
"""
    (pack / "map.html").write_text(map_html, encoding="utf-8")

    open_metrics = {
        "max_area_ha": ha_press,
        "n_timeline_steps": 1,
        "activation": EVENT,
        "O2_cems_delineation": "NOT_ACTIVATED_OR_UNKNOWN",
        "n_hotspots_24h": len(sel),
        "track": "open_firms_only",
    }
    (pack / "open_metrics_for_decide.json").write_text(
        json.dumps(open_metrics, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "pack": str(pack),
                "n_hotspots": len(sel),
                "hull_ha": round(hull_ha, 1),
                "dates": dates,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
