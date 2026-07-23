#!/usr/bin/env python3
"""Inventory Extremadura RAI shapefiles → event_catalog + selection_gold."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_RAW = ROOT / "data" / "open_if" / "extremadura_rai_2025" / "raw"
DEFAULT_OUT = ROOT / "data" / "open_if" / "extremadura_rai_2025" / "inventory"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _parse_fecha(s: str | None) -> str | None:
    if not s:
        return None
    t = str(s).strip()
    # 2025/08/14 00:00:00.000
    if len(t) >= 10 and t[4] == "/":
        return t[:10].replace("/", "-")
    if len(t) >= 10 and t[4] == "-":
        return t[:10]
    return t


def inventory_dir(raw: Path) -> list[dict[str, Any]]:
    try:
        import shapefile
    except ImportError as e:
        raise SystemExit("pyshp required: pip install pyshp") from e
    from pyproj import CRS, Transformer
    from shapely.geometry import shape
    from shapely.ops import transform

    rows: list[dict[str, Any]] = []
    for d in sorted(raw.iterdir()):
        if not d.is_dir():
            continue
        shps = list(d.rglob("*.shp"))
        if not shps:
            continue
        shp = shps[0]
        r = shapefile.Reader(str(shp))
        field_names = [f[0] for f in r.fields[1:]]
        prj = shp.with_suffix(".prj")
        crs_str = "EPSG:25829"
        if prj.exists():
            try:
                crs_str = CRS.from_wkt(prj.read_text(encoding="utf-8", errors="ignore")).to_string()
            except Exception:
                pass
        crs = CRS.from_user_input(crs_str)
        for sr in r.iterShapeRecords():
            props = {k: v for k, v in zip(field_names, sr.record)}
            g = shape(sr.shape.__geo_interface__)
            if not crs.is_geographic:
                tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                g4326 = transform(lambda x, y, z=None: tf.transform(x, y), g)
            else:
                g4326 = g
            tf_ea = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
            gea = transform(lambda x, y, z=None: tf_ea.transform(x, y), g4326)
            ha_geom = float(gea.area / 10000.0)
            id_raw = props.get("Id_incen")
            try:
                id_incen = str(int(float(id_raw))) if id_raw is not None else d.name
            except (TypeError, ValueError):
                id_incen = str(id_raw or d.name)
            fecha_det = _parse_fecha(props.get("fecha_det"))
            fecha_ext = _parse_fecha(props.get("fecha_ext"))
            name = d.name.replace(" ", "_")
            rows.append(
                {
                    "name": name,
                    "municipio": name.replace("_", " "),
                    "id_incen": id_incen,
                    "objectid": props.get("OBJECTID"),
                    "fecha_det": fecha_det,
                    "fecha_ext": fecha_ext,
                    "hectareas_attr": float(props["Hectareas"]) if props.get("Hectareas") is not None else None,
                    "area_geom_ha": round(ha_geom, 2),
                    "medicion": props.get("MEDICION"),
                    "crs_native": crs_str if crs_str.startswith("EPSG") else "EPSG:25829",
                    "shp_path": (
                        str(shp.relative_to(ROOT)).replace("\\", "/")
                        if shp.is_relative_to(ROOT)
                        else str(shp)
                    ),
                    "bounds_w": g4326.bounds[0],
                    "bounds_s": g4326.bounds[1],
                    "bounds_e": g4326.bounds[2],
                    "bounds_n": g4326.bounds[3],
                    "centroid_lon": g4326.centroid.x,
                    "centroid_lat": g4326.centroid.y,
                    "source": "RAI Junta de Extremadura",
                    "attribution": (
                        "Fuente: Registro de Áreas Incendiadas (RAI) — "
                        "Junta de Extremadura / INFOEX"
                    ),
                }
            )
    return rows


def select_gold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(rows, key=lambda r: float(r.get("area_geom_ha") or 0), reverse=True)
    gold = ranked[0] if ranked else None
    silver = ranked[1:3]
    return {
        "schema": "ext_rai_selection_v1",
        "built_at_utc": _utc(),
        "gold": [gold["id_incen"]] if gold else [],
        "silver": [r["id_incen"] for r in silver],
        "events": {
            r["id_incen"]: {
                "tier": (
                    "gold"
                    if gold and r["id_incen"] == gold["id_incen"]
                    else ("silver" if r["id_incen"] in {s["id_incen"] for s in silver} else "bronze")
                ),
                **{k: r[k] for k in r if k != "shp_path"},
                "shp_path": r["shp_path"],
            }
            for r in ranked
        },
        "rationale": {
            "gold": "Largest ha + multi-day det/ext window for FIRMS/dNBR",
            "silver": "Remaining RAI 2025 deliveries",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if not args.raw.is_dir():
        print(f"raw not found: {args.raw}", file=sys.stderr)
        return 2
    rows = inventory_dir(args.raw)
    if not rows:
        print("no shapefiles found", file=sys.stderr)
        return 3
    args.out.mkdir(parents=True, exist_ok=True)
    cat = args.out / "event_catalog.csv"
    fields = list(rows[0].keys())
    with cat.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    sel = select_gold(rows)
    sel_path = args.out / "selection_gold.json"
    sel_path.write_text(json.dumps(sel, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"catalog n={len(rows)} → {cat}")
    print(f"gold={sel['gold']} silver={sel['silver']} → {sel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
