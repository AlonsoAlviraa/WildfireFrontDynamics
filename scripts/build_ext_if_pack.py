#!/usr/bin/env python3
"""Build industrial open_if packs for Extremadura RAI official perimeters.

Examples:
  python scripts/inventory_ext_rai.py
  python scripts/build_ext_if_pack.py --tier all
  python scripts/build_ext_if_pack.py --id 2025100393 --skip-dnbr
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util

import shapefile  # pyshp
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

# Reuse AND industrial helpers
_spec = importlib.util.spec_from_file_location(
    "build_and_if_pack", ROOT / "scripts" / "build_and_if_pack.py"
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load build_and_if_pack")
andp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(andp)

ATTRIBUTION = (
    "Fuente: Registro de Áreas Incendiadas (RAI) — Junta de Extremadura / INFOEX. "
    "Uso no comercial de validación; no redistribuir crudos sin acuerdo."
)
DEFAULT_SELECTION = (
    ROOT / "data" / "open_if" / "extremadura_rai_2025" / "inventory" / "selection_gold.json"
)
OUT_ROOT = ROOT / "outputs" / "open_if"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def load_shp_feature(shp_path: Path) -> tuple[dict[str, Any], Any, str, float]:
    """Return (props, geom_wgs84, crs_native, area_ha_geom)."""
    r = shapefile.Reader(str(shp_path))
    field_names = [f[0] for f in r.fields[1:]]
    prj = shp_path.with_suffix(".prj")
    crs_str = "EPSG:25829"
    if prj.exists():
        try:
            crs_str = CRS.from_wkt(prj.read_text(encoding="utf-8", errors="ignore")).to_epsg()
            crs_str = f"EPSG:{crs_str}" if crs_str else "EPSG:25829"
        except Exception:
            crs_str = "EPSG:25829"
    crs = CRS.from_user_input(crs_str)
    sr = next(r.iterShapeRecords())
    props = dict(zip(field_names, sr.record, strict=False))
    g = shape(sr.shape.__geo_interface__)
    if not crs.is_geographic:
        tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        g_wgs = transform(lambda x, y, z=None: tf.transform(x, y), g)
    else:
        g_wgs = g
    ha = andp.area_ha_wgs84(g_wgs)
    return props, g_wgs, crs_str, ha


def build_scorecard_ext(
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
    no_false = decision_open in {"HOLD", "ABSTAIN", "open_demo"}
    gates = {
        "O2_RAI": "PASS" if has_perimeter and attribution_ok else "FAIL",
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
        "REPRO": "PASS"
        if repro_status == "PASS"
        else ("SKIP" if repro_status == "SKIP" else "FAIL"),
        "PROVENANCE": "PASS" if attribution_ok else "FAIL",
        "FECHAS_DET_EXT": "PASS",  # always for RAI delivery with fields
    }
    hard = {"O2_RAI", "PROVENANCE", "NO_FALSE_DISPATCH"}
    any_hard = any(gates[k] == "FAIL" for k in hard)
    any_fail = any(g == "FAIL" for g in gates.values())
    if any_hard:
        verdict = "NO_GO"
    elif any_fail or gates["OPEN_FIRMS"] == "SKIP" and gates["OPEN_DNBR"] == "SKIP":
        verdict = "PARTIAL"
    else:
        verdict = "GO_OPEN_EXT_O2"
    return {
        "schema": "scorecard_ext_industrial_v1",
        "track": "Pista_B_plus_EXT_RAI",
        "pack_id": pack_id,
        "gates": gates,
        "verdict": verdict,
        "decision_open": decision_open,
        "decision_note": (
            "Open industrial demo EXT. HOLD for field_ops without RAI/INFOEX Vp/ha. "
            "No tactical dispatch. FIRMS hull ≠ burned area."
        ),
        "lwir_heligraphics": False,
        "vp_invented": False,
        "firms_hull_is_official_burned_area": False,
        "attribution": ATTRIBUTION,
        "built_at_utc": _utc(),
    }


def firms_window(fecha_det: str | None, fecha_ext: str | None) -> tuple[str, int]:
    """Return (anchor_date, pad_days) covering det..ext ±1d."""
    if not fecha_det:
        return "2025-08-14", 2
    try:
        d0 = date.fromisoformat(fecha_det)
    except ValueError:
        return fecha_det, 2
    if fecha_ext:
        try:
            d1 = date.fromisoformat(fecha_ext)
            pad = max(2, (d1 - d0).days + 1)
            # fetch_firms uses event_date ± pad_days; center mid window
            mid = d0 + timedelta(days=(d1 - d0).days // 2)
            return mid.isoformat(), min(pad, 20)
        except ValueError:
            pass
    return fecha_det, 3


def build_one(
    event: dict[str, Any],
    *,
    skip_firms: bool,
    skip_dnbr: bool,
) -> Path:
    shp_raw = Path(event["shp_path"])
    shp = shp_raw if shp_raw.is_absolute() else (ROOT / shp_raw)
    props, geom, crs_native, ha = load_shp_feature(shp)
    id_incen = event["id_incen"]
    fecha_det = event.get("fecha_det") or ""
    fecha_ext = event.get("fecha_ext") or ""
    fecha_key = (fecha_det or "unknown").replace("-", "")
    pack_id = f"ext_{id_incen}_{fecha_key}"
    pack_dir = OUT_ROOT / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "vectors").mkdir(exist_ok=True)

    minx, miny, maxx, maxy = geom.bounds
    pad = 0.05
    bbox = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    center = (geom.centroid.x, geom.centroid.y)

    feat_props = {
        "id_incen": id_incen,
        "municipio": event.get("municipio"),
        "fecha_det": fecha_det,
        "fecha_ext": fecha_ext,
        "hectareas_attr": event.get("hectareas_attr"),
        "area_geom_ha": round(ha, 2),
        "medicion": props.get("MEDICION"),
        "crs_native": crs_native,
        "source": "RAI Junta de Extremadura / INFOEX",
        "attribution": ATTRIBUTION,
        "not_lwir": True,
        "vp_tactical": None,
    }
    fc4326 = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": feat_props,
                "geometry": mapping(geom),
            }
        ],
        "properties": {
            "attribution": ATTRIBUTION,
            "crs": "EPSG:4326",
            "layer": "perimeter_rai_official",
        },
    }
    _write_json(pack_dir / "vectors" / "perimeter_rai.geojson", fc4326)

    # native copy (re-read original coords)
    r = shapefile.Reader(str(shp))
    field_names = [f[0] for f in r.fields[1:]]
    sr = next(r.iterShapeRecords())
    g_nat = shape(sr.shape.__geo_interface__)
    props_n = dict(zip(field_names, sr.record, strict=False))
    fc_nat = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {**props_n, "crs_native": crs_native, "attribution": ATTRIBUTION},
                "geometry": mapping(g_nat),
            }
        ],
        "properties": {"crs": crs_native, "attribution": ATTRIBUTION},
    }
    epsg = crs_native.replace("EPSG:", "").replace(":", "")
    _write_json(pack_dir / "vectors" / f"perimeter_rai_native_epsg{epsg}.geojson", fc_nat)

    # timeline for dNBR reuse
    _write_json(pack_dir / "timeline_perimeters.geojson", fc4326)

    # FIRMS
    firms_status = "SKIP"
    n_firms = 0
    firms_fc: dict[str, Any] | None = None
    hull_fc: dict[str, Any] | None = None
    metrics_extra: dict[str, Any] = {}
    if not skip_firms:
        anchor, pad_days = firms_window(fecha_det, fecha_ext)
        firms = andp.fetch_firms_for_event(event_date=anchor, bbox=bbox, pad_days=pad_days)
        # If mid-window fails, also try fecha_det
        if firms.get("n_hotspots", 0) == 0 and fecha_det and fecha_det != anchor:
            firms2 = andp.fetch_firms_for_event(event_date=fecha_det, bbox=bbox, pad_days=pad_days)
            if firms2.get("n_hotspots", 0) > firms.get("n_hotspots", 0):
                firms = firms2
        firms_status = firms.get("status", "SKIP")
        n_firms = int(firms.get("n_hotspots") or 0)
        firms_fc = {
            "type": "FeatureCollection",
            "features": firms.get("features") or [],
            "properties": {
                "status": firms_status,
                "n_hotspots": n_firms,
                "not_official_burned_area": True,
                "source": firms.get("source"),
                "reasons": firms.get("reasons"),
                "window_anchor": firms.get("event_date"),
                "pad_days": firms.get("pad_days"),
            },
        }
        _write_json(pack_dir / "vectors" / "firms_hotspots.geojson", firms_fc)
        pts = [
            (f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])
            for f in firms_fc["features"]
            if f.get("geometry", {}).get("type") == "Point"
        ]
        metrics_extra, hull_fc = andp.firms_hull_metrics(pts, geom)
        if hull_fc:
            # reword disclaimer for EXT
            for ft in hull_fc.get("features") or []:
                ft.setdefault("properties", {})["disclaimer"] = metrics_extra.get("disclaimer")
            _write_json(pack_dir / "vectors" / "firms_hull_proxy.geojson", hull_fc)
    else:
        _write_json(
            pack_dir / "vectors" / "firms_hotspots.geojson",
            {
                "type": "FeatureCollection",
                "features": [],
                "properties": {"status": "SKIP", "reasons": ["skip_firms"]},
            },
        )

    metrics = {
        "schema": "metrics_o2_ext_rai_v1",
        "pack_id": pack_id,
        "area_rai_ha": round(ha, 2),
        "area_attr_ha": event.get("hectareas_attr"),
        "area_firms_hull_ha": metrics_extra.get("area_firms_hull_ha"),
        "ratio_hull_vs_rai": metrics_extra.get("ratio_hull_vs_rediam"),
        "iou_firms_buffer_vs_rai": metrics_extra.get("iou_firms_buffer_vs_rediam"),
        "hausdorff_m": metrics_extra.get("hausdorff_m"),
        "hausdorff_status": metrics_extra.get("hausdorff_status", "SKIP"),
        "n_firms_hotspots": n_firms,
        "firms_status": firms_status,
        "fecha_det": fecha_det,
        "fecha_ext": fecha_ext,
        "disclaimer": (
            "FIRMS convex hull is a thermal-pixel proxy footprint, NOT official burned area. "
            "Official perimeter: RAI Extremadura."
        ),
        "vp_tactical": None,
        "vp_invented": False,
        "built_at_utc": _utc(),
    }
    _write_json(pack_dir / "metrics_o2.json", metrics)

    # dNBR
    dnbr = andp.try_dnbr(pack_dir, event_date=fecha_det or "2025-08-01", skip=skip_dnbr)
    dnbr_status = str(dnbr.get("status") or "SKIP")

    # brief draft then scorecard with written attribution
    manifest = {
        "schema": "open_if_pack_ext_rai_v1",
        "pack_id": pack_id,
        "track": "Pista_B_plus_EXT_RAI",
        "id_incen": id_incen,
        "municipio": event.get("municipio"),
        "fecha_det": fecha_det,
        "fecha_ext": fecha_ext,
        "area_rai_ha": round(ha, 2),
        "hectareas_attr": event.get("hectareas_attr"),
        "crs_native": crs_native,
        "built_at_utc": _utc(),
        "pack_dir": str(pack_dir.relative_to(ROOT)).replace("\\", "/"),
        "attribution": ATTRIBUTION,
        "source_agency": "RAI / INFOEX / Junta de Extremadura",
        "lwir": False,
        "vp_tactical": None,
    }
    scorecard = build_scorecard_ext(
        pack_id=pack_id,
        has_perimeter=True,
        attribution_ok=True,  # provisional; recheck after write
        firms_status=firms_status,
        n_firms=n_firms,
        haus_status=str(metrics.get("hausdorff_status") or "SKIP"),
        dnbr_status=dnbr_status,
        repro_status="SKIP",
        decision_open="HOLD",
    )
    brief = "\n".join(
        [
            f"# Brief open-data — {pack_id} (EXT RAI / INFOEX)",
            "",
            f"_Generado: {manifest['built_at_utc']}_",
            "",
            "## Qué es",
            f"- Incendio **oficial RAI Extremadura** id `{id_incen}` · {event.get('municipio')}",
            f"- Detección: **{fecha_det}** · Extinción: **{fecha_ext}**",
            f"- Área perímetro (geom): **{ha:.1f} ha** (attr: {event.get('hectareas_attr')})",
            f"- Atribución: **{ATTRIBUTION}**",
            "- Sin LWIR · sin Vp inventado · no despacho táctico",
            "",
            "## Capas",
            f"- O2 RAI: **{scorecard['gates']['O2_RAI']}**",
            f"- FIRMS: **{scorecard['gates']['OPEN_FIRMS']}** (n={n_firms})",
            f"- dNBR: **{scorecard['gates']['OPEN_DNBR']}**",
            f"- Hausdorff: **{scorecard['gates']['O2_METHOD_HAUSDORFF']}**",
            "",
            "## Métricas",
            f"- area_rai_ha: {metrics.get('area_rai_ha')}",
            f"- area_firms_hull_ha (proxy): {metrics.get('area_firms_hull_ha')}",
            f"- ratio_hull_vs_rai: {metrics.get('ratio_hull_vs_rai')}",
            f"- hausdorff_m: {metrics.get('hausdorff_m')}",
            "",
            "> Hull FIRMS **no** es ha quemadas oficiales.",
            "",
            f"## Veredicto: **{scorecard['verdict']}** · decision **{scorecard['decision_open']}**",
            "",
            f"Fuente: {ATTRIBUTION}",
            "",
        ]
    )
    (pack_dir / "operator_brief_open_if.md").write_text(brief, encoding="utf-8")

    provenance = {
        "schema": "provenance_ext_rai_v1",
        "attribution": ATTRIBUTION,
        "sources": [
            {
                "id": "rai_shp",
                "owner": "Registro de Áreas Incendiadas — Junta de Extremadura / INFOEX",
                "contact": "rai@juntaex.es",
                "path": event.get("shp_path"),
                "crs": crs_native,
            },
            {"id": "nasa_firms", "owner": "NASA FIRMS", "access": "open"},
        ],
        "use": "non_commercial_validation",
        "restrictions": "No raw redistribution without agreement; no tactical dispatch claims",
        "built_at_utc": _utc(),
    }
    _write_json(pack_dir / "provenance.json", provenance)

    perim_text = (pack_dir / "vectors" / "perimeter_rai.geojson").read_text(encoding="utf-8")
    attr_ok = andp.attribution_ok_from_written(
        perimeter_feature_props=feat_props,
        perimeter_fc_props=fc4326.get("properties"),
        provenance_obj=provenance,
        brief_text=brief,
        perimeter_file_text=perim_text,
    )
    # EXT-specific tokens
    if not attr_ok:
        blob = perim_text + brief + json.dumps(provenance)
        attr_ok = ("RAI" in blob or "Extremadura" in blob) and "Junta" in blob

    scorecard = build_scorecard_ext(
        pack_id=pack_id,
        has_perimeter=True,
        attribution_ok=attr_ok,
        firms_status=firms_status,
        n_firms=n_firms,
        haus_status=str(metrics.get("hausdorff_status") or "SKIP"),
        dnbr_status=dnbr_status,
        repro_status="SKIP",
        decision_open="HOLD",
    )
    scorecard["gates"]["FECHAS_DET_EXT"] = "PASS" if fecha_det and fecha_ext else "SKIP"
    _write_json(pack_dir / "scorecard_ext_industrial.json", scorecard)

    manifest["verdict"] = scorecard["verdict"]
    manifest["firms_n"] = n_firms
    manifest["dnbr_status"] = dnbr_status
    _write_json(pack_dir / "manifest.json", manifest)

    html = andp.map_html(
        pack_id=pack_id,
        rediam_fc=fc4326,
        firms_fc=firms_fc,
        hull_fc=hull_fc,
        area_ha=ha,
        center=center,
    )
    # retitle banner for EXT
    html = (
        html.replace("REDIAM AND", "EXT RAI")
        .replace(
            "Fuente: REDIAM — Junta de Andalucía",
            "Fuente: RAI — Junta de Extremadura / INFOEX",
        )
        .replace("REDIAM perímetro (O2)", "RAI perímetro (O2)")
    )
    (pack_dir / "map.html").write_text(html, encoding="utf-8")

    print(
        f"pack {pack_id}: verdict={scorecard['verdict']} ha={ha:.1f} "
        f"firms={n_firms} dnbr={dnbr_status} → {pack_dir}"
    )
    return pack_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    ap.add_argument("--tier", choices=["gold", "silver", "all"], default="all")
    ap.add_argument("--id", dest="only_id", default=None, help="Only one id_incen")
    ap.add_argument("--skip-firms", action="store_true")
    ap.add_argument("--skip-dnbr", action="store_true")
    args = ap.parse_args()
    if not args.selection.is_file():
        print(f"missing selection: {args.selection} (run inventory_ext_rai.py)", file=sys.stderr)
        return 2
    sel = json.loads(args.selection.read_text(encoding="utf-8"))
    events = sel.get("events") or {}
    ids: list[str] = []
    if args.only_id:
        ids = [args.only_id]
    elif args.tier == "gold":
        ids = list(sel.get("gold") or [])
    elif args.tier == "silver":
        ids = list(sel.get("silver") or [])
    else:
        ids = list(sel.get("gold") or []) + list(sel.get("silver") or [])
    if not ids:
        print("no events selected", file=sys.stderr)
        return 3
    for eid in ids:
        ev = events.get(eid)
        if not ev:
            print(f"skip unknown id {eid}", file=sys.stderr)
            continue
        build_one(ev, skip_firms=args.skip_firms, skip_dnbr=args.skip_dnbr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
