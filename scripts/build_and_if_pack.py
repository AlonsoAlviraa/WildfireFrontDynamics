#!/usr/bin/env python3
"""Build industrial open_if pack for Andalucía REDIAM (Pista B+).

Pack layout (outputs/open_if/and_<codigo>_<fecha>/):
  manifest.json
  vectors/perimeter_rediam.geojson   (EPSG:4326)
  vectors/firms_hotspots.geojson     (or empty + SKIP note)
  vectors/firms_hull_proxy.geojson
  timeline_perimeters.geojson
  metrics_o2.json
  scorecard_and_industrial.json
  map.html
  operator_brief_open_if.md
  provenance.json
  dnbr_status.json

Honest gates: no invented Vp; FIRMS hull ≠ burned area; attribute REDIAM/Junta.

Examples:
  python scripts/build_and_if_pack.py --selection data/open_if/rediam_andalucia/inventory/selection_gold.json
  python scripts/build_and_if_pack.py --codigo 2024040011 --feature-geojson path.geojson --feature-index 0
  python scripts/build_and_if_pack.py --fixture tests/fixtures/rediam_and/sample_perim_3042.geojson --skip-firms --skip-dnbr
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from shapely.geometry import MultiPoint, mapping, shape
    from shapely.ops import transform
except ImportError:  # pragma: no cover
    print("shapely required: pip install shapely", file=sys.stderr)
    raise

try:
    from pyproj import Transformer
except ImportError:  # pragma: no cover
    Transformer = None  # type: ignore

ATTRIBUTION = (
    "Fuente: REDIAM — Junta de Andalucía. Uso libre con mención de autores y propietarios."
)
NATIVE_CRS = "EPSG:3042"
UA = "WildfireFrontDynamics/1.0 (research; AND open pack)"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _relpath(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _tf(src: str, dst: str):
    if Transformer is None:
        return None
    return Transformer.from_crs(src, dst, always_xy=True)


def parse_crs_from_geojson(fc: dict[str, Any] | None) -> str | None:
    """Extract EPSG code from GeoJSON crs member or properties.crs_native."""
    if not fc:
        return None
    props = fc.get("properties") or {}
    for key in ("crs_native", "crs", "CRS"):
        v = props.get(key)
        if isinstance(v, str) and "EPSG" in v.upper():
            # normalize EPSG:3042
            import re

            m = re.search(r"EPSG[:\s]*:?(\d+)", v, re.I)
            if m:
                return f"EPSG:{m.group(1)}"
            return v
    crs = fc.get("crs")
    if isinstance(crs, dict):
        name = (crs.get("properties") or {}).get("name") or ""
        # urn:ogc:def:crs:EPSG::3042
        import re

        m = re.search(r"EPSG[:\s]*:?(\d+)", str(name), re.I)
        if m:
            return f"EPSG:{m.group(1)}"
    return None


def reproject_geom(geom: Any, src: str, dst: str) -> Any:
    tf = _tf(src, dst)
    if tf is None:
        raise RuntimeError("pyproj required for CRS transform")

    def _proj(x, y, z=None):
        return tf.transform(x, y)

    return transform(_proj, geom)


def area_ha_wgs84(geom: Any) -> float:
    """Equal-area ha from WGS84 geometry."""
    if geom is None or geom.is_empty:
        return 0.0
    tf = _tf("EPSG:4326", "EPSG:6933")
    if tf is None:
        minx, miny, maxx, maxy = geom.bounds
        lat = (miny + maxy) / 2.0
        m_lat = 111_320.0
        m_lon = 111_320.0 * math.cos(math.radians(lat))

        def _to_m(x, y, z=None):
            return (x * m_lon, y * m_lat)

        return float(transform(_to_m, geom).area) / 10_000.0

    def _proj(x, y, z=None):
        return tf.transform(x, y)

    return float(transform(_proj, geom).area) / 10_000.0


def area_ha_native(geom: Any) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    return float(geom.area) / 10_000.0


def pack_id(codigo: str, fecha: str) -> str:
    f = (fecha or "nodate").replace("-", "")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(codigo))
    return f"and_{safe}_{f}".lower()


def load_feature_from_selection(sel_item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (feature, meta) from selection entry."""
    path = Path(sel_item["source_path"])
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"source geojson missing: {path}")
    fc = json.loads(path.read_text(encoding="utf-8"))
    feats = fc.get("features") or []
    idx = int(sel_item.get("feature_index") or 0)
    if idx < 0 or idx >= len(feats):
        # try match by CODIGO
        cod = str(sel_item.get("codigo") or "")
        found = None
        for i, f in enumerate(feats):
            p = f.get("properties") or {}
            if str(p.get("CODIGO") or p.get("codigo") or "") == cod:
                found = f
                idx = i
                break
        if found is None:
            raise IndexError(f"feature_index {idx} out of range and codigo {cod} not found")
        feat = found
    else:
        feat = feats[idx]
    meta = {
        "source_path": _relpath(path),
        "feature_index": idx,
        "layer_properties": fc.get("properties"),
        "source_crs": parse_crs_from_geojson(fc),
        "fc_crs": fc.get("crs"),
    }
    return feat, meta


def load_feature_from_geojson(
    path: Path, *, codigo: str | None, index: int | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    fc = json.loads(path.read_text(encoding="utf-8"))
    feats = fc.get("features") or []
    if not feats:
        raise ValueError(f"no features in {path}")
    src_crs = parse_crs_from_geojson(fc)
    if codigo:
        for i, f in enumerate(feats):
            p = f.get("properties") or {}
            if str(p.get("CODIGO") or p.get("codigo") or "") == str(codigo):
                return f, {
                    "source_path": _relpath(path),
                    "feature_index": i,
                    "source_crs": src_crs,
                    "fc_crs": fc.get("crs"),
                }
        raise ValueError(f"codigo {codigo} not in {path}")
    idx = 0 if index is None else index
    return feats[idx], {
        "source_path": _relpath(path),
        "feature_index": idx,
        "source_crs": src_crs,
        "fc_crs": fc.get("crs"),
    }


def parse_fecha(props: dict[str, Any], fallback: str | None = None) -> str:
    raw = props.get("FECHA_INC") or props.get("fecha_inc") or fallback
    if raw is None:
        return ""
    s = str(raw).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    return s


def detect_crs_and_to_wgs84(
    geom: Any,
    *,
    declared_crs: str | None = None,
) -> tuple[Any, str, float]:
    """Return (geom_wgs84, source_crs, area_ha_from_native_or_equal).

    Uses declared GeoJSON CRS when present. Projected coords without a known
    CRS raise RuntimeError (no silent wrong reproject).
    """
    minx, miny, maxx, maxy = geom.bounds
    projected = abs(minx) > 180 or abs(miny) > 90 or abs(maxx) > 180 or abs(maxy) > 90
    if projected:
        src = declared_crs or NATIVE_CRS
        if declared_crs is None:
            # Only allow implicit 3042 for REDIAM-shaped UTM30N-ish bounds
            # (easting ~100k–800k, northing ~3.9e6–4.4e6 for Andalucía)
            if not (50_000 < minx < 900_000 and 3_500_000 < miny < 4_600_000):
                raise RuntimeError(
                    f"projected coords without declared CRS and outside REDIAM "
                    f"EPSG:3042 sanity box: bounds=({minx},{miny},{maxx},{maxy})"
                )
            src = NATIVE_CRS
        ha_native = area_ha_native(geom)
        g_wgs = reproject_geom(geom, src, "EPSG:4326")
        return g_wgs, src, ha_native
    ha = area_ha_wgs84(geom)
    return geom, declared_crs or "EPSG:4326", ha


def fetch_firms_for_event(
    *,
    event_date: str,
    bbox: tuple[float, float, float, float],
    pad_days: int = 2,
    timeout: int = 120,
) -> dict[str, Any]:
    """Fetch FIRMS VIIRS Spain year archive filtered to bbox and date±pad."""
    out: dict[str, Any] = {
        "status": "SKIP",
        "n_hotspots": 0,
        "features": [],
        "source": None,
        "reasons": [],
        "bbox": list(bbox),
        "event_date": event_date,
        "pad_days": pad_days,
        "note": "NASA FIRMS hotspots are ~375m pixels, NOT official burned area.",
    }
    if not event_date or len(event_date) < 10:
        out["reasons"].append("missing_event_date")
        return out
    year = int(event_date[:4])
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/"
        f"{year}/viirs-snpp_{year}_Spain.csv"
    )
    out["source"] = url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        out["reasons"].append(f"download_failed:{type(exc).__name__}:{exc}")
        return out

    try:
        d0 = date.fromisoformat(event_date)
    except ValueError:
        out["reasons"].append("bad_event_date")
        return out
    dates = {(d0 + timedelta(days=k)).isoformat() for k in range(-pad_days, pad_days + 1)}
    lon0, lat0, lon1, lat1 = bbox
    feats = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        try:
            if (r.get("acq_date") or "") not in dates:
                continue
            lon = float(r["longitude"])
            lat = float(r["latitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (lon0 <= lon <= lon1 and lat0 <= lat <= lat1):
            continue
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
                    "not_official_perimeter": True,
                    "source": f"FIRMS/viirs-snpp/{year}",
                    "note": "Hotspot pixel, not fire perimeter",
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    out["features"] = feats
    out["n_hotspots"] = len(feats)
    out["status"] = "GO" if feats else "SKIP"
    if not feats:
        out["reasons"].append("zero_hotspots_in_window")
    return out


def firms_hull_metrics(
    pts: list[tuple[float, float]], rediam_geom: Any
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Convex hull of FIRMS points vs REDIAM perimeter. Hull is PROXY only."""
    result: dict[str, Any] = {
        "n_points": len(pts),
        "area_firms_hull_ha": None,
        "ratio_hull_vs_rediam": None,
        "iou_firms_buffer_vs_rediam": None,
        "hausdorff_m": None,
        "hausdorff_status": "SKIP",
        "disclaimer": (
            "FIRMS convex hull is a thermal-pixel proxy footprint, "
            "NOT official burned area. Do not report as ha quemadas."
        ),
    }
    if len(pts) < 3:
        result["hausdorff_status"] = "SKIP"
        result["hausdorff_reason"] = "need_ge3_points_for_hull"
        return result, None

    mp = MultiPoint(pts)
    hull = mp.convex_hull
    hull_ha = area_ha_wgs84(hull)
    result["area_firms_hull_ha"] = round(hull_ha, 2)

    rediam_ha = area_ha_wgs84(rediam_geom) if rediam_geom is not None else 0.0
    if rediam_ha > 0:
        result["ratio_hull_vs_rediam"] = round(hull_ha / rediam_ha, 3)

    # Buffer hotspots ~375m as crude footprint for IoU
    try:
        # work in equal-area meters
        tf = _tf("EPSG:4326", "EPSG:6933")
        if tf is not None and rediam_geom is not None:

            def _proj(x, y, z=None):
                return tf.transform(x, y)

            hull_m = transform(_proj, hull)
            red_m = transform(_proj, rediam_geom)
            # 375m pixel buffer on multipoint
            pts_m = transform(_proj, mp)
            buf = pts_m.buffer(375.0)
            inter = buf.intersection(red_m).area
            union = buf.union(red_m).area
            if union > 0:
                result["iou_firms_buffer_vs_rediam"] = round(inter / union, 4)
            if len(pts) >= 5:
                result["hausdorff_m"] = round(float(hull_m.hausdorff_distance(red_m)), 1)
                result["hausdorff_status"] = "GO"
                result["hausdorff_note"] = (
                    "Hausdorff hull_proxy vs REDIAM official perimeter (method O2). "
                    "Not national cadastre CLM; AND institutional perimeter."
                )
            else:
                result["hausdorff_status"] = "SKIP"
                result["hausdorff_reason"] = "few_points_lt5"
        else:
            result["hausdorff_status"] = "SKIP"
            result["hausdorff_reason"] = "pyproj_or_geom_missing"
    except Exception as exc:
        result["hausdorff_status"] = "SKIP"
        result["hausdorff_reason"] = f"error:{type(exc).__name__}"

    hull_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer": "firms_convex_hull",
                    "not_official_perimeter": True,
                    "not_official_burned_area": True,
                    "approx_area_ha": result["area_firms_hull_ha"],
                    "n_hotspots": len(pts),
                    "disclaimer": result["disclaimer"],
                },
                "geometry": mapping(hull),
            }
        ],
        "properties": {
            "not_official_perimeter": True,
            "attribution_firms": "NASA FIRMS VIIRS",
        },
    }
    return result, hull_fc


def try_dnbr(pack_dir: Path, *, event_date: str, skip: bool) -> dict[str, Any]:
    if skip:
        status = {
            "schema": "open_if_dnbr_status_v1",
            "status": "SKIP",
            "reasons": ["skip_dnbr_flag"],
            "product": "dnbr_stac_s2_l2a",
            "built_at_utc": _utc(),
            "disclaimer": "Not official perimeter. Severity proxy only.",
            "pack_dir": str(pack_dir),
        }
        _write_json(pack_dir / "dnbr_status.json", status)
        return status
    # Reuse build_open_if_dnbr if timeline exists
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_open_if_dnbr", ROOT / "scripts" / "build_open_if_dnbr.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load build_open_if_dnbr")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.run_for_pack(pack_dir, event_date=event_date or None)
    except Exception as exc:
        status = {
            "schema": "open_if_dnbr_status_v1",
            "status": "SKIP",
            "reasons": [f"dnbr_failed:{type(exc).__name__}:{exc}"],
            "product": "dnbr_stac_s2_l2a",
            "built_at_utc": _utc(),
            "disclaimer": "Not official perimeter. Severity proxy only.",
            "pack_dir": str(pack_dir),
        }
        _write_json(pack_dir / "dnbr_status.json", status)
        return status


def render_brief(
    manifest: dict[str, Any], scorecard: dict[str, Any], metrics: dict[str, Any]
) -> str:
    m = manifest
    sc = scorecard
    lines = [
        f"# Brief open-data — {m.get('pack_id')} (Pista B+ AND REDIAM)",
        "",
        f"_Generado: {m.get('built_at_utc')}_",
        "",
        "## Qué es",
        f"- Incendio **REDIAM / Junta de Andalucía** código `{m.get('codigo')}`",
        f"- Fecha IF: **{m.get('fecha_inc')}** · {m.get('municipio')}/{m.get('provincia')}",
        f"- Área perímetro oficial (geom): **{m.get('area_rediam_ha')} ha**",
        f"- Atribución: **{ATTRIBUTION}**",
        "- **No** usa LWIR Heligrafics · **No** inventa Vp/ROS táctico",
        "",
        "## Capas",
        f"- O2 REDIAM perímetro: **{sc.get('gates', {}).get('O2_REDIAM')}**",
        f"- FIRMS open sat: **{sc.get('gates', {}).get('OPEN_FIRMS')}** (n={metrics.get('n_firms_hotspots', 0)})",
        f"- dNBR STAC: **{sc.get('gates', {}).get('OPEN_DNBR')}**",
        f"- Hausdorff method: **{sc.get('gates', {}).get('O2_METHOD_HAUSDORFF')}**",
        "",
        "## Métricas O2 (honesto)",
        f"- area_rediam_ha: {metrics.get('area_rediam_ha')}",
        f"- area_firms_hull_ha (proxy): {metrics.get('area_firms_hull_ha')}",
        f"- ratio_hull_vs_rediam: {metrics.get('ratio_hull_vs_rediam')}",
        f"- iou_firms_buffer_vs_rediam: {metrics.get('iou_firms_buffer_vs_rediam')}",
        f"- hausdorff_m: {metrics.get('hausdorff_m')}",
        "",
        "> El hull FIRMS **no** es superficie quemada oficial.",
        "",
        "## Veredicto pack",
        f"- **{sc.get('verdict')}**",
        f"- Decision open-only: **{sc.get('decision_open')}** (HOLD sin ancla ASEMA)",
        "",
        "## No usar como",
        "- ROS táctico / orden de extinción",
        "- Sustituto de Tobarra OPS gold (LWIR + Vp)",
        "- Ha quemadas a partir del convex hull FIRMS",
        "",
        "## Provenance",
        f"- {ATTRIBUTION}",
        f"- WFS: `{m.get('wfs_layer')}`",
        f"- Pack: `{m.get('pack_dir')}`",
        "",
    ]
    return "\n".join(lines)


def map_html(
    *,
    pack_id: str,
    rediam_fc: dict[str, Any],
    firms_fc: dict[str, Any] | None,
    hull_fc: dict[str, Any] | None,
    area_ha: float,
    center: tuple[float, float],
) -> str:
    rediam_js = json.dumps(rediam_fc, ensure_ascii=False, separators=(",", ":"))
    firms_js = json.dumps(
        firms_fc or {"type": "FeatureCollection", "features": []},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    hull_js = json.dumps(
        hull_fc or {"type": "FeatureCollection", "features": []},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    lat, lon = center[1], center[0]
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<title>{pack_id} · REDIAM AND</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#map{{height:100%;margin:0}}
.banner{{padding:8px 12px;font-family:system-ui,sans-serif;background:#1a1a1a;color:#eee;font-size:13px}}
.banner b{{color:#f5a623}}
.legend{{position:absolute;bottom:20px;right:12px;z-index:1000;background:rgba(255,255,255,.92);
padding:8px 10px;font:12px system-ui,sans-serif;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.3)}}
.sw{{display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:middle;border:1px solid #333}}
</style>
</head><body>
<div class="banner">
  <b>{pack_id}</b> · perímetro oficial REDIAM · {area_ha:.1f} ha ·
  Fuente: REDIAM — Junta de Andalucía · FIRMS hull = proxy (no ha oficiales) · no Vp táctico
</div>
<div id="map"></div>
<div class="legend">
  <div><span class="sw" style="background:#e74c3c;opacity:.35"></span>REDIAM perímetro (O2)</div>
  <div><span class="sw" style="background:#f39c12;opacity:.25"></span>FIRMS hull proxy</div>
  <div><span class="sw" style="background:#e67e22;border-radius:50%"></span>FIRMS hotspots</div>
</div>
<script>
const rediam = {rediam_js};
const firms = {firms_js};
const hull = {hull_js};
const map = L.map('map').setView([{lat}, {lon}], 11);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18, attribution: '&copy; OpenStreetMap'
}}).addTo(map);
const rediamLayer = L.geoJSON(rediam, {{
  style: {{color:'#c0392b', weight:2, fillColor:'#e74c3c', fillOpacity:0.25}}
}}).addTo(map);
const hullLayer = L.geoJSON(hull, {{
  style: {{color:'#d35400', weight:1, dashArray:'4 4', fillColor:'#f39c12', fillOpacity:0.12}}
}}).addTo(map);
L.geoJSON(firms, {{
  pointToLayer: (f, latlng) => L.circleMarker(latlng, {{
    radius: 4, color:'#e67e22', fillColor:'#f5b041', fillOpacity:0.85, weight:1
  }})
}}).addTo(map);
try {{ map.fitBounds(rediamLayer.getBounds().pad(0.15)); }} catch (e) {{}}
</script>
</body></html>
"""


def build_scorecard(
    *,
    pack_id: str,
    has_perimeter: bool,
    attribution_ok: bool,
    firms_status: str,
    n_firms: int,
    haus_status: str,
    dnbr_status: str,
    repro_status: str = "SKIP",
    decision_open: str = "HOLD",
) -> dict[str, Any]:
    """Industrial scorecard. GO only when every gate is PASS or justified SKIP."""
    no_false = decision_open in {"HOLD", "ABSTAIN", "open_demo"}
    gates = {
        "O2_REDIAM": "PASS" if has_perimeter and attribution_ok else "FAIL",
        "O2_METHOD_HAUSDORFF": (
            "PASS" if haus_status == "GO" else ("SKIP" if haus_status == "SKIP" else "FAIL")
        ),
        "OPEN_FIRMS": (
            "PASS"
            if firms_status == "GO" and n_firms >= 1
            else ("SKIP" if firms_status == "SKIP" else "FAIL")
        ),
        "OPEN_DNBR": (
            "PASS"
            if dnbr_status in {"GO", "OK"}
            else ("SKIP" if dnbr_status in {"SKIP", "BLOCKED"} else "FAIL")
        ),
        "NO_FALSE_DISPATCH": "PASS" if no_false else "FAIL",
        # REPRO not demonstrated at pack-build time → SKIP (verify may promote)
        "REPRO": (
            "PASS" if repro_status == "PASS" else ("SKIP" if repro_status == "SKIP" else "FAIL")
        ),
        "PROVENANCE": "PASS" if attribution_ok else "FAIL",
    }
    hard_fail_keys = {"O2_REDIAM", "PROVENANCE", "NO_FALSE_DISPATCH"}
    any_hard_fail = any(gates[k] == "FAIL" for k in hard_fail_keys)
    any_fail = any(g == "FAIL" for g in gates.values())
    all_pass_or_skip = all(g in {"PASS", "SKIP"} for g in gates.values())

    if any_hard_fail:
        verdict = "NO_GO"
    elif any_fail:
        # Non-hard FAIL (e.g. REPRO=FAIL if ever set) → at best PARTIAL
        verdict = "PARTIAL"
    elif all_pass_or_skip:
        if gates["OPEN_FIRMS"] == "SKIP" and gates["OPEN_DNBR"] == "SKIP":
            verdict = "PARTIAL"
        else:
            verdict = "GO_OPEN_AND_O2"
    else:
        verdict = "PARTIAL"

    return {
        "schema": "scorecard_and_industrial_v1",
        "track": "Pista_B_plus_AND_REDIAM",
        "pack_id": pack_id,
        "gates": gates,
        "verdict": verdict,
        "decision_open": decision_open,
        "decision_note": (
            "Open-only industrial demo. HOLD for field_ops without ASEMA Vp/ha anchor. "
            "No tactical dispatch."
        ),
        "lwir_heligraphics": False,
        "vp_invented": False,
        "firms_hull_is_official_burned_area": False,
        "attribution": ATTRIBUTION,
        "built_at_utc": _utc(),
    }


def attribution_ok_from_text(*parts: str) -> bool:
    """True only if the joined *parts* contain both REDIAM and Junta.

    Callers must pass strings that appear on written artifacts (perimeter
    props, provenance JSON, brief body). Do **not** inject the module
    ATTRIBUTION constant or bare \"REDIAM\"/\"Junta\" literals here to force PASS.
    """
    blob = " ".join(p for p in parts if p)
    return "REDIAM" in blob and "Junta" in blob


def attribution_ok_from_written(
    *,
    perimeter_feature_props: dict[str, Any] | None,
    perimeter_fc_props: dict[str, Any] | None,
    provenance_obj: dict[str, Any] | None,
    brief_text: str,
    perimeter_file_text: str | None = None,
) -> bool:
    """Derive PROVENANCE from content that is (or will be) on disk."""
    parts: list[str] = []
    for props in (perimeter_feature_props, perimeter_fc_props):
        if not props:
            continue
        for key in ("attribution", "source", "owner"):
            v = props.get(key)
            if v:
                parts.append(str(v))
    if provenance_obj:
        if provenance_obj.get("attribution"):
            parts.append(str(provenance_obj["attribution"]))
        for src in provenance_obj.get("sources") or []:
            if isinstance(src, dict):
                for key in ("owner", "id", "access"):
                    if src.get(key):
                        parts.append(str(src[key]))
    if brief_text:
        parts.append(brief_text)
    if perimeter_file_text:
        parts.append(perimeter_file_text)
    return attribution_ok_from_text(*parts)


def build_pack_from_feature(
    feat: dict[str, Any],
    *,
    out_root: Path,
    meta: dict[str, Any],
    skip_firms: bool = False,
    skip_dnbr: bool = False,
    firms_timeout: int = 120,
    codigo_override: str | None = None,
    fecha_override: str | None = None,
) -> dict[str, Any]:
    props = dict(feat.get("properties") or {})
    codigo = str(codigo_override or props.get("CODIGO") or props.get("codigo") or "unknown")
    fecha = parse_fecha(props, fecha_override)
    pid = pack_id(codigo, fecha)
    pack_dir = out_root / pid
    vec_dir = pack_dir / "vectors"
    pack_dir.mkdir(parents=True, exist_ok=True)
    vec_dir.mkdir(exist_ok=True)

    raw_geom = feat.get("geometry")
    if raw_geom is None:
        raise ValueError(f"missing/null geometry for codigo={codigo}; cannot build pack")
    try:
        geom = shape(raw_geom)
    except Exception as exc:
        raise ValueError(
            f"invalid geometry for codigo={codigo}: {type(exc).__name__}:{exc}"
        ) from exc
    if geom.is_empty:
        raise ValueError(f"empty geometry for codigo={codigo}; cannot build pack")
    if not geom.is_valid:
        geom = geom.buffer(0)
        if geom.is_empty or not geom.is_valid:
            raise ValueError(f"unrepairable geometry for codigo={codigo}")

    declared_crs = meta.get("source_crs")
    geom_native = geom  # keep original coords before reproject
    geom_wgs, src_crs, ha_native = detect_crs_and_to_wgs84(geom, declared_crs=declared_crs)
    ha_wgs = area_ha_wgs84(geom_wgs)
    area_rediam_ha = round(ha_wgs if ha_wgs > 0 else ha_native, 2)

    mun = props.get("Municipio") or props.get("municipio") or ""
    prov = props.get("Provincia") or props.get("provincia") or ""

    # Perimeter GeoJSON 4326
    rediam_feat = {
        "type": "Feature",
        "properties": {
            **{k: props.get(k) for k in props},
            "CODIGO": codigo,
            "fecha_inc": fecha,
            "source": "REDIAM",
            "owner": "Junta de Andalucía",
            "attribution": ATTRIBUTION,
            "crs_source": src_crs,
            "area_ha_geom": area_rediam_ha,
            "layer": "perimeter_rediam_official",
            "official_perimeter_and": True,
            "not_tactical_ros": True,
        },
        "geometry": mapping(geom_wgs),
    }
    rediam_fc = {
        "type": "FeatureCollection",
        "features": [rediam_feat],
        "properties": {
            "attribution": ATTRIBUTION,
            "crs": "EPSG:4326",
            "crs_native": src_crs,
        },
    }
    (vec_dir / "perimeter_rediam.geojson").write_text(
        json.dumps(rediam_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Original CRS copy for audit (plan C3)
    native_fc = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:{src_crs.replace(':', '::')}"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "CODIGO": codigo,
                    "fecha_inc": fecha,
                    "attribution": ATTRIBUTION,
                    "crs": src_crs,
                    "layer": "perimeter_rediam_native",
                },
                "geometry": mapping(geom_native),
            }
        ],
        "properties": {
            "attribution": ATTRIBUTION,
            "crs": src_crs,
            "note": "Native coordinates as ingested; not WGS84",
        },
    }
    native_name = f"perimeter_rediam_native_{src_crs.replace(':', '').lower()}.geojson"
    (vec_dir / native_name).write_text(
        json.dumps(native_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Keep timeline for dNBR helper compatibility
    (pack_dir / "timeline_perimeters.geojson").write_text(
        json.dumps(rediam_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    minx, miny, maxx, maxy = geom_wgs.bounds
    pad = 0.2
    bbox = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    c = geom_wgs.centroid
    center = (float(c.x), float(c.y))

    # FIRMS
    firms_meta: dict[str, Any]
    if skip_firms:
        firms_meta = {
            "status": "SKIP",
            "n_hotspots": 0,
            "features": [],
            "reasons": ["skip_firms_flag"],
            "note": "NASA FIRMS hotspots are ~375m pixels, NOT official burned area.",
        }
    else:
        firms_meta = fetch_firms_for_event(event_date=fecha, bbox=bbox, timeout=firms_timeout)

    firms_fc = {
        "type": "FeatureCollection",
        "features": firms_meta.get("features") or [],
        "properties": {
            "status": firms_meta.get("status"),
            "n_hotspots": firms_meta.get("n_hotspots"),
            "source": firms_meta.get("source"),
            "reasons": firms_meta.get("reasons"),
            "not_official_perimeter": True,
            "not_official_burned_area": True,
            "note": firms_meta.get("note"),
        },
    }
    (vec_dir / "firms_hotspots.geojson").write_text(
        json.dumps(firms_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (pack_dir / "firms_hotspots.geojson").write_text(
        json.dumps(firms_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pts = [
        (float(f["geometry"]["coordinates"][0]), float(f["geometry"]["coordinates"][1]))
        for f in firms_fc["features"]
        if f.get("geometry")
    ]
    hull_metrics, hull_fc = firms_hull_metrics(pts, geom_wgs)
    if hull_fc is None:
        hull_fc = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"status": "SKIP", "not_official_perimeter": True},
        }
    (vec_dir / "firms_hull_proxy.geojson").write_text(
        json.dumps(hull_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # dNBR
    dnbr = try_dnbr(pack_dir, event_date=fecha, skip=skip_dnbr)
    dnbr_st = str(dnbr.get("status") or "SKIP")

    metrics = {
        "schema": "metrics_o2_and_rediam_v1",
        "pack_id": pid,
        "codigo": codigo,
        "fecha_inc": fecha,
        "area_rediam_ha": area_rediam_ha,
        "area_rediam_source": "geom_equal_area_epsg6933_from_wgs84",
        "area_attr_sup": {
            "SUP_ARBOLA": props.get("SUP_ARBOLA"),
            "SUP_MATORR": props.get("SUP_MATORR"),
            "SUP_PASTIZ": props.get("SUP_PASTIZ"),
        },
        "n_firms_hotspots": firms_meta.get("n_hotspots") or 0,
        "firms_status": firms_meta.get("status"),
        "area_firms_hull_ha": hull_metrics.get("area_firms_hull_ha"),
        "ratio_hull_vs_rediam": hull_metrics.get("ratio_hull_vs_rediam"),
        "iou_firms_buffer_vs_rediam": hull_metrics.get("iou_firms_buffer_vs_rediam"),
        "hausdorff_m": hull_metrics.get("hausdorff_m"),
        "hausdorff_status": hull_metrics.get("hausdorff_status"),
        "dnbr_status": dnbr_st,
        "honest_notes": [
            "FIRMS hull is proxy only — not official burned area",
            "No tactical Vp/ROS without ASEMA",
            "REDIAM perimeter is institutional AND O2, not CLM cadastre",
        ],
        "built_at_utc": _utc(),
    }
    _write_json(pack_dir / "metrics_o2.json", metrics)

    decision_open = "HOLD"
    pack_dir_rel = _relpath(pack_dir)
    wfs_layer = f"ms:perim_incendios_{fecha[:4]}" if fecha else None

    provenance = {
        "schema": "provenance_and_rediam_v1",
        "attribution": ATTRIBUTION,
        "sources": [
            {
                "id": "rediam_perimeters",
                "owner": "Junta de Andalucía / REDIAM",
                "access": (
                    "https://www.juntadeandalucia.es/medioambiente/mapwms/"
                    "REDIAM_perimetros_incendios_forestales"
                ),
                "layer": wfs_layer,
                "role": "official_perimeter_o2_and",
            },
            {
                "id": "nasa_firms",
                "owner": "NASA FIRMS",
                "role": "active_fire_hotspots_proxy",
                "not_official_burned_area": True,
                "status": firms_meta.get("status"),
            },
            {
                "id": "sentinel2_stac",
                "role": "dnbr_severity_proxy",
                "status": dnbr_st,
            },
        ],
        "built_at_utc": _utc(),
        "policy": [
            "Cite REDIAM / Junta de Andalucía on all artifacts",
            "Do not invent Vp",
            "Do not claim FIRMS hull as burned area",
            "Decision field_ops remains HOLD without ASEMA",
        ],
    }
    _write_json(pack_dir / "provenance.json", provenance)

    # Draft manifest for brief (scorecard_verdict filled after attr check)
    manifest = {
        "product": "and_rediam_open_if_pack_v1",
        "track": "Pista_B_plus_AND_REDIAM",
        "pack_id": pid,
        "codigo": codigo,
        "fecha_inc": fecha,
        "municipio": mun,
        "provincia": prov,
        "area_rediam_ha": area_rediam_ha,
        "built_at_utc": _utc(),
        "requires_lwir_heligraphics": False,
        "vp_tactical": None,
        "vp_note": "Not available in REDIAM perimeter layer; request ASEMA for O1 anchor",
        "attribution": ATTRIBUTION,
        "wfs_layer": wfs_layer,
        "crs_native": src_crs,
        "crs_pack": "EPSG:4326",
        "pack_dir": pack_dir_rel,
        "artifacts": {
            "perimeter": "vectors/perimeter_rediam.geojson",
            "perimeter_native": f"vectors/{native_name}",
            "firms": "vectors/firms_hotspots.geojson",
            "firms_hull_proxy": "vectors/firms_hull_proxy.geojson",
            "metrics_o2": "metrics_o2.json",
            "scorecard": "scorecard_and_industrial.json",
            "map": "map.html",
            "brief": "operator_brief_open_if.md",
            "provenance": "provenance.json",
            "dnbr_status": "dnbr_status.json",
        },
        "source_feature": {
            "path": meta.get("source_path"),
            "feature_index": meta.get("feature_index"),
        },
        "centroid_lonlat": [center[0], center[1]],
        "bbox_wgs84": [minx, miny, maxx, maxy],
        "scorecard_verdict": None,
        "firms_status": firms_meta.get("status"),
        "dnbr_status": dnbr_st,
    }

    # Placeholder scorecard for brief gates display; rebuilt with real attr_ok below
    scorecard_draft = build_scorecard(
        pack_id=pid,
        has_perimeter=area_rediam_ha > 0,
        attribution_ok=True,  # temporary for brief text only
        firms_status=str(firms_meta.get("status") or "SKIP"),
        n_firms=int(firms_meta.get("n_hotspots") or 0),
        haus_status=str(hull_metrics.get("hausdorff_status") or "SKIP"),
        dnbr_status=dnbr_st,
        repro_status="SKIP",
        decision_open=decision_open,
    )
    brief = render_brief(manifest, scorecard_draft, metrics)
    (pack_dir / "operator_brief_open_if.md").write_text(brief, encoding="utf-8")

    # PROVENANCE / attr_ok: only from written artifact content (no constant injection)
    perim_path = vec_dir / "perimeter_rediam.geojson"
    perim_on_disk = perim_path.read_text(encoding="utf-8") if perim_path.is_file() else ""
    attr_ok = attribution_ok_from_written(
        perimeter_feature_props=rediam_feat.get("properties"),
        perimeter_fc_props=rediam_fc.get("properties"),
        provenance_obj=provenance,
        brief_text=brief,
        perimeter_file_text=perim_on_disk,
    )
    scorecard = build_scorecard(
        pack_id=pid,
        has_perimeter=area_rediam_ha > 0,
        attribution_ok=attr_ok,
        firms_status=str(firms_meta.get("status") or "SKIP"),
        n_firms=int(firms_meta.get("n_hotspots") or 0),
        haus_status=str(hull_metrics.get("hausdorff_status") or "SKIP"),
        dnbr_status=dnbr_st,
        repro_status="SKIP",  # not demonstrated at pack build
        decision_open=decision_open,
    )
    _write_json(pack_dir / "scorecard_and_industrial.json", scorecard)
    manifest["scorecard_verdict"] = scorecard.get("verdict")
    _write_json(pack_dir / "manifest.json", manifest)

    # If brief was built with draft gates that differ, refresh brief once
    if scorecard.get("verdict") != scorecard_draft.get("verdict") or not attr_ok:
        brief = render_brief(manifest, scorecard, metrics)
        (pack_dir / "operator_brief_open_if.md").write_text(brief, encoding="utf-8")

    html = map_html(
        pack_id=pid,
        rediam_fc=rediam_fc,
        firms_fc=firms_fc,
        hull_fc=hull_fc,
        area_ha=area_rediam_ha,
        center=center,
    )
    (pack_dir / "map.html").write_text(html, encoding="utf-8")

    print(
        json.dumps(
            {
                "pack_id": pid,
                "verdict": scorecard.get("verdict"),
                "area_rediam_ha": area_rediam_ha,
                "n_firms": metrics.get("n_firms_hotspots"),
                "dnbr": dnbr_st,
                "attribution_ok": attr_ok,
                "pack_dir": manifest["pack_dir"],
            },
            indent=2,
        )
    )
    return {"manifest": manifest, "scorecard": scorecard, "metrics": metrics, "pack_dir": pack_dir}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build AND REDIAM open_if pack")
    ap.add_argument(
        "--selection",
        type=Path,
        default=None,
        help="selection_gold.json (builds gold + silver)",
    )
    ap.add_argument("--tier", default="all", choices=["all", "gold", "silver", "gold_only"])
    ap.add_argument("--codigo", default=None)
    ap.add_argument("--feature-geojson", type=Path, default=None)
    ap.add_argument("--feature-index", type=int, default=None)
    ap.add_argument("--fixture", type=Path, default=None, help="Synthetic/offline GeoJSON")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "open_if")
    ap.add_argument("--skip-firms", action="store_true")
    ap.add_argument("--skip-dnbr", action="store_true")
    ap.add_argument("--firms-timeout", type=int, default=120)
    args = ap.parse_args()

    out_root = args.out if args.out.is_absolute() else ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    built: list[dict[str, Any]] = []

    if args.fixture:
        path = args.fixture if args.fixture.is_absolute() else ROOT / args.fixture
        feat, meta = load_feature_from_geojson(path, codigo=args.codigo, index=args.feature_index)
        built.append(
            build_pack_from_feature(
                feat,
                out_root=out_root,
                meta=meta,
                skip_firms=args.skip_firms,
                skip_dnbr=args.skip_dnbr,
                firms_timeout=args.firms_timeout,
                codigo_override=args.codigo,
            )
        )
    elif args.feature_geojson:
        path = (
            args.feature_geojson
            if args.feature_geojson.is_absolute()
            else ROOT / args.feature_geojson
        )
        feat, meta = load_feature_from_geojson(path, codigo=args.codigo, index=args.feature_index)
        built.append(
            build_pack_from_feature(
                feat,
                out_root=out_root,
                meta=meta,
                skip_firms=args.skip_firms,
                skip_dnbr=args.skip_dnbr,
                firms_timeout=args.firms_timeout,
                codigo_override=args.codigo,
            )
        )
    elif args.selection:
        sel_path = args.selection if args.selection.is_absolute() else ROOT / args.selection
        sel = json.loads(sel_path.read_text(encoding="utf-8"))
        items: list[dict[str, Any]] = []
        if args.tier in {"all", "gold", "gold_only"}:
            items.extend(sel.get("gold") or [])
        if args.tier in {"all", "silver"}:
            items.extend(sel.get("silver") or [])
        if args.codigo:
            items = [i for i in items if str(i.get("codigo")) == str(args.codigo)]
            if not items:
                # search full selection
                items = [
                    i
                    for i in (sel.get("gold") or []) + (sel.get("silver") or [])
                    if str(i.get("codigo")) == str(args.codigo)
                ]
        if not items:
            print("No selection items to build", file=sys.stderr)
            return 2
        for item in items:
            feat, meta = load_feature_from_selection(item)
            built.append(
                build_pack_from_feature(
                    feat,
                    out_root=out_root,
                    meta=meta,
                    skip_firms=args.skip_firms,
                    skip_dnbr=args.skip_dnbr,
                    firms_timeout=args.firms_timeout,
                    codigo_override=str(item.get("codigo") or ""),
                    fecha_override=item.get("fecha_inc"),
                )
            )
    else:
        ap.error("Provide --selection, --feature-geojson, or --fixture")

    return 0 if built else 1


if __name__ == "__main__":
    raise SystemExit(main())
