"""Render Leaflet fire-status map HTML from payload (inline GeoJSON for file://)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_fire_status_map_html(payload: dict[str, Any]) -> str:
    """Return a self-contained HTML string (Leaflet via CDN + inline layers)."""
    data_js = json.dumps(payload, ensure_ascii=False)
    title = str(payload.get("title") or "WFD fire status map")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {{ --bg:#0b1220; --panel:#121a2b; --text:#e8f0ff; --muted:#8aa0bc; --line:#243049; --hot:#ff5a3d; --loc:#3de7ff; --warn:#ffb020; }}
  * {{ box-sizing: border-box; }}
  html, body {{ height:100%; margin:0; font-family: "Segoe UI", system-ui, sans-serif; background:var(--bg); color:var(--text); }}
  #app {{ display:grid; grid-template-rows:auto 1fr; height:100%; }}
  header {{ padding:.65rem 1rem; background:linear-gradient(180deg,#121a2b,#0b1220); border-bottom:1px solid var(--line); }}
  header h1 {{ margin:0; font-size:1.05rem; font-weight:650; letter-spacing:.02em; }}
  header .meta {{ margin-top:.35rem; color:var(--muted); font-size:.82rem; line-height:1.35; }}
  .badge {{ display:inline-block; padding:.1rem .45rem; border-radius:999px; border:1px solid var(--line); margin-right:.35rem; font-size:.75rem; }}
  .badge.ok {{ border-color:#1f8f5f; color:#5dffb0; }}
  .badge.skip {{ border-color:#8a7020; color:var(--warn); }}
  .badge.err {{ border-color:#a33; color:#ff8d8d; }}
  #map {{ height:100%; width:100%; background:#0a101a; }}
  .legend {{ position:absolute; z-index:1000; right:12px; bottom:24px; background:rgba(12,18,30,.9); border:1px solid var(--line); border-radius:10px; padding:.6rem .75rem; font-size:.78rem; max-width:280px; color:var(--text); }}
  .legend b {{ display:block; margin-bottom:.3rem; }}
  .swatch {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:.35rem; }}
</style>
</head>
<body>
<div id="app">
  <header>
    <h1 id="title"></h1>
    <div class="meta" id="meta"></div>
  </header>
  <div id="map"></div>
</div>
<script>
const P = {data_js};
const conn = (P.connectivity && P.connectivity.status) || (P.firms && P.firms.connectivity) || 'skipped';
const badgeClass = conn === 'connected' || conn === 'fixture' ? 'ok' : (conn === 'error' ? 'err' : 'skip');
document.getElementById('title').textContent = P.title || 'WFD fire status map';
document.getElementById('meta').innerHTML =
  '<span class="badge ' + badgeClass + '">connectivity: ' + conn + '</span>' +
  '<span class="badge">field_ops fusion: ' + ((P.rails||{{}}).field_ops_ml_live_fusion || 'OFF') + '</span>' +
  '<span class="badge">layers: ' + ((P.layers||[]).length) + '</span>' +
  '<div style="margin-top:.4rem">' + (P.disclaimer || '') + '</div>';

const center = P.center || {{lon: -3.7, lat: 40.4}};
const map = L.map('map').setView([center.lat, center.lon], P.zoom || 8);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap'
}}).addTo(map);

const bounds = [];
function touchBounds(layer) {{
  try {{
    const b = layer.getBounds && layer.getBounds();
    if (b && b.isValid && b.isValid()) bounds.push(b);
  }} catch (e) {{}}
}}

(P.layers || []).forEach((Lyr, idx) => {{
  const gj = Lyr.geojson;
  if (!gj) return;
  const isFirms = (Lyr.id || '').indexOf('firms') >= 0 || (Lyr.source || '').indexOf('firms') >= 0
    || (Lyr.source_mode || '').indexOf('firms') >= 0 || (Lyr.name || '').indexOf('FIRMS') >= 0
    || (Lyr.source || '') === 'public_europe_csv' || (Lyr.source || '') === 'area_api' || (Lyr.source || '') === 'fixture_csv';
  const style = isFirms
    ? {{ color: '#ff5a3d', weight: 1, fillColor: '#ff5a3d', fillOpacity: 0.85, radius: 5 }}
    : {{ color: '#3de7ff', weight: 3, fillColor: '#3de7ff', fillOpacity: 0.15 }};
  const layer = L.geoJSON(gj, {{
    style: () => style,
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {{
      radius: isFirms ? 5 : 4,
      color: isFirms ? '#ff5a3d' : '#3de7ff',
      fillColor: isFirms ? '#ff5a3d' : '#3de7ff',
      fillOpacity: 0.85,
      weight: 1
    }}),
    onEachFeature: (f, l) => {{
      const p = f.properties || {{}};
      const lines = Object.keys(p).slice(0, 12).map(k => '<b>' + k + '</b>: ' + p[k]);
      l.bindPopup('<div style="font-size:12px"><b>' + (Lyr.name || Lyr.id) + '</b><br/>' + lines.join('<br/>') + '</div>');
    }}
  }}).addTo(map);
  touchBounds(layer);
}});

if (bounds.length) {{
  const b = bounds[0];
  bounds.slice(1).forEach(x => b.extend(x));
  map.fitBounds(b.pad(0.2));
}}

const legend = L.control({{position: 'bottomright'}});
legend.onAdd = function() {{
  const d = L.DomUtil.create('div', 'legend');
  d.innerHTML = '<b>Leyenda</b>'
    + '<div><span class="swatch" style="background:#3de7ff"></span>Local (frente / envelope WFD)</div>'
    + '<div><span class="swatch" style="background:#ff5a3d"></span>FIRMS NRT hotspot (≠ perímetro)</div>'
    + '<div style="margin-top:.35rem;color:#8aa0bc">NO despacho táctico · NRT ≠ tiempo real ops</div>';
  return d;
}};
legend.addTo(map);
</script>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_fire_status_map(
    payload: dict[str, Any],
    output_dir: Path | str,
    *,
    html_name: str = "fire_status_map.html",
    json_name: str = "fire_status_map.json",
) -> dict[str, Path]:
    """Write HTML + JSON payload; return paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / html_name
    json_path = out / json_name
    html_path.write_text(render_fire_status_map_html(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"html": html_path, "json": json_path}
