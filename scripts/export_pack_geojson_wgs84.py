#!/usr/bin/env python3
"""Reproject pack GeoJSON (UTM) to WGS84 for web viewers + build Leaflet map HTML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.geo_crs import geojson_to_wgs84  # noqa: E402

DEFAULT_FILES = (
    "main_front.geojson",
    "fronts.geojson",
    "emergency_envelope_guidance.geojson",
)


def convert_file(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    data = json.loads(src.read_text(encoding="utf-8"))
    if not data.get("features"):
        return False
    out = geojson_to_wgs84(data, zone=30, northern=True)
    dst.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return True


def build_map_html(pack: Path, fire_id: str) -> Path:
    """Self-contained Leaflet map embedding WGS84 layers."""
    layers = []
    for name, label, color, weight in (
        ("main_front_wgs84.geojson", "Frente principal", "#ff6b35", 3),
        ("emergency_envelope_guidance.geojson", "Envelope 15/30/60 (guía)", "#4cc9f0", 2),
        ("fronts_wgs84.geojson", "Todos los frentes", "#f72585", 1.5),
    ):
        p = pack / name
        # envelope may already be WGS84 after re-export
        if name == "emergency_envelope_guidance.geojson" and not p.is_file():
            continue
        if not p.is_file():
            continue
        layers.append(
            {
                "name": label,
                "color": color,
                "weight": weight,
                "data": json.loads(p.read_text(encoding="utf-8")),
            }
        )

    # If envelope still missing wgs84, try convert from utm sibling
    env_utm = pack / "emergency_envelope_guidance_utm.geojson"
    env_wgs = pack / "emergency_envelope_guidance.geojson"
    if env_utm.is_file() and env_wgs.is_file():
        # already have wgs in list
        pass

    html_path = pack / "map_viewer.html"
    layers_js = json.dumps(layers)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Mapa — {fire_id}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body {{ margin:0; height:100%; font-family: system-ui, sans-serif; }}
    #map {{ position:absolute; inset:0; }}
    .banner {{
      position:absolute; z-index:1000; left:10px; right:10px; top:10px;
      background:rgba(15,20,25,.92); color:#e7ecf1; padding:10px 14px;
      border-radius:8px; font-size:13px; line-height:1.4;
      border:1px solid #2a3a4f; max-width:520px;
    }}
    .banner b {{ color:#fff; }}
    .banner .warn {{ color:#ffb703; }}
  </style>
</head>
<body>
  <div class="banner">
    <b>{fire_id}</b> — capas en WGS84 (lon/lat)<br/>
    <span class="warn">El envelope es GUÍA extrapolada, NO perímetro oficial ni despacho táctico.</span>
  </div>
  <div id="map"></div>
  <script>
    const layersData = {layers_js};
    const map = L.map('map');
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    const bounds = L.latLngBounds([]);
    const overlays = {{}};
    layersData.forEach((layer) => {{
      const gj = L.geoJSON(layer.data, {{
        style: (feat) => {{
          const sector = (feat.properties && feat.properties.sector) || '';
          let color = layer.color;
          if (sector === 'head') color = '#ff4d4d';
          if (sector === 'rear') color = '#90be6d';
          if (sector === 'flank_isotropic') color = '#4cc9f0';
          const h = (feat.properties && feat.properties.horizon_min) || 0;
          return {{
            color: color,
            weight: layer.weight,
            fillOpacity: sector ? 0.12 : 0.08,
            opacity: h === 60 ? 0.45 : (h === 30 ? 0.7 : 0.95)
          }};
        }},
        onEachFeature: (feat, lyr) => {{
          const p = feat.properties || {{}};
          const lines = Object.keys(p).slice(0, 12).map(k => `<b>${{k}}</b>: ${{p[k]}}`);
          lyr.bindPopup(lines.join('<br/>'));
        }}
      }});
      gj.addTo(map);
      overlays[layer.name] = gj;
      try {{ bounds.extend(gj.getBounds()); }} catch (e) {{}}
    }});
    L.control.layers(null, overlays, {{ collapsed: false }}).addTo(map);
    if (bounds.isValid()) {{
      map.fitBounds(bounds.pad(0.2));
    }} else {{
      map.setView([39.0, -1.8], 8);
    }}
  </script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return html_path


def process_pack(pack: Path) -> dict:
    fire_id = pack.name
    out: dict = {"fire_id": fire_id, "converted": [], "map": None}
    for fn in DEFAULT_FILES:
        src = pack / fn
        if fn == "emergency_envelope_guidance.geojson":
            # may already be WGS84; also convert utm sibling if present
            utm = pack / "emergency_envelope_guidance_utm.geojson"
            if utm.is_file():
                convert_file(utm, pack / "emergency_envelope_guidance.geojson")
                out["converted"].append("emergency_envelope_guidance.geojson (from utm)")
            elif src.is_file():
                # re-run convert in case still UTM
                convert_file(src, pack / "emergency_envelope_guidance.geojson")
                out["converted"].append("emergency_envelope_guidance.geojson")
            continue
        if not src.is_file():
            continue
        dst = pack / fn.replace(".geojson", "_wgs84.geojson")
        if convert_file(src, dst):
            out["converted"].append(dst.name)
    # Prefer main_front_wgs84 + envelope for map
    map_path = build_map_html(pack, fire_id)
    out["map"] = str(map_path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fires",
        default="tobarra_20240802,cardoso_2025,hellin_2024,brazatortas_2025",
    )
    ap.add_argument("--root", type=Path, default=ROOT / "outputs" / "observatorio")
    args = ap.parse_args()
    for fid in [x.strip() for x in args.fires.split(",") if x.strip()]:
        pack = args.root / fid
        if not pack.is_dir():
            print("skip", fid)
            continue
        r = process_pack(pack)
        print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
