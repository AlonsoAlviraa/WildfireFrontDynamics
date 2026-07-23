#!/usr/bin/env python3
"""Inventory REDIAM Andalucía WFS cache → event catalog + gold/silver selection.

Reads GeoJSON from data/open_if/rediam_andalucia/wfs_cache/YYYY/
Writes:
  inventory/event_catalog.csv
  inventory/selection_gold.json
  inventory/inventory_stats.json

Scoring (0–100, no invented Vp):
  ha ≥100/500/1000 → +10/+20/+30
  year ≥2023 → +15
  FIRMS probe (optional live) ≥20 hotspots → +25
  attrs municipio/provincia → +5
  (S2 cloud check left as future bonus; default 0)

Examples:
  python scripts/inventory_rediam_and.py
  python scripts/inventory_rediam_and.py --cache data/open_if/rediam_andalucia/wfs_cache --no-firms
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from shapely.geometry import mapping, shape
    from shapely.ops import transform
except ImportError:  # pragma: no cover
    print("shapely required: pip install shapely", file=sys.stderr)
    raise

try:
    from pyproj import Transformer
except ImportError:  # pragma: no cover
    Transformer = None  # type: ignore

ATTRIBUTION = "Fuente: REDIAM — Junta de Andalucía. Uso libre con mención de autores y propietarios."
DEFAULT_CACHE = ROOT / "data" / "open_if" / "rediam_andalucia" / "wfs_cache"
DEFAULT_OUT = ROOT / "data" / "open_if" / "rediam_andalucia" / "inventory"
NATIVE_CRS = "EPSG:3042"
# Andalucía rough bounds in WGS84 for CRS sanity
AND_BBOX_WGS84 = (-7.6, 35.9, -1.5, 38.8)


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def parse_crs_from_geojson(fc: dict[str, Any] | None) -> str | None:
    if not fc:
        return None
    props = fc.get("properties") or {}
    for key in ("crs_native", "crs", "CRS"):
        v = props.get(key)
        if isinstance(v, str) and "EPSG" in v.upper():
            import re

            m = re.search(r"EPSG[:\s]*:?(\d+)", v, re.I)
            if m:
                return f"EPSG:{m.group(1)}"
    crs = fc.get("crs")
    if isinstance(crs, dict):
        name = (crs.get("properties") or {}).get("name") or ""
        import re

        m = re.search(r"EPSG[:\s]*:?(\d+)", str(name), re.I)
        if m:
            return f"EPSG:{m.group(1)}"
    return None


def _transformer_to_wgs84(src_crs: str = NATIVE_CRS):
    if Transformer is None:
        return None
    return Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)


def _transformer_equal_area(src_crs: str = NATIVE_CRS):
    if Transformer is None:
        return None
    return Transformer.from_crs(src_crs, "EPSG:6933", always_xy=True)


def area_ha_native(geom: Any) -> float:
    """Area in ha from native EPSG:3042 meters (UTM-like)."""
    if geom is None or geom.is_empty:
        return 0.0
    # 3042 is meter-based projected CRS → area directly in m²
    try:
        return float(geom.area) / 10_000.0
    except Exception:
        return 0.0


def area_ha_equal_area(geom_native: Any, src_crs: str = NATIVE_CRS) -> float:
    tf = _transformer_equal_area(src_crs)
    if tf is None:
        return area_ha_native(geom_native)

    def _proj(x, y, z=None):
        return tf.transform(x, y)

    try:
        g = transform(_proj, geom_native)
        return float(g.area) / 10_000.0
    except Exception:
        return area_ha_native(geom_native)


def to_wgs84_geom(geom_native: Any, src_crs: str = NATIVE_CRS) -> Any | None:
    tf = _transformer_to_wgs84(src_crs)
    if tf is None or geom_native is None or geom_native.is_empty:
        return None

    def _proj(x, y, z=None):
        return tf.transform(x, y)

    try:
        return transform(_proj, geom_native)
    except Exception:
        return None


def parse_fecha_inc(raw: Any) -> str | None:
    """Parse FECHA_INC YYYYMMDD → YYYY-MM-DD."""
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def sup_total_ha(props: dict[str, Any]) -> float | None:
    keys = ("SUP_ARBOLA", "SUP_MATORR", "SUP_PASTIZ", "SUP_TOTAL", "SUP_HA", "SUP")
    vals = []
    for k in keys:
        v = props.get(k)
        if v is None or v == "":
            continue
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    # Prefer explicit total if present
    for k in ("SUP_TOTAL", "SUP_HA", "SUP"):
        if props.get(k) not in (None, ""):
            try:
                return float(props[k])
            except (TypeError, ValueError):
                pass
    if not vals:
        return None
    # If only tipology fields, sum the three main ones if all present-ish
    tip = []
    for k in ("SUP_ARBOLA", "SUP_MATORR", "SUP_PASTIZ"):
        if props.get(k) not in (None, ""):
            try:
                tip.append(float(props[k]))
            except (TypeError, ValueError):
                pass
    if tip:
        return sum(tip)
    return sum(vals) if vals else None


def load_year_features(cache: Path, year: int) -> list[dict[str, Any]]:
    path = cache / str(year) / f"perim_incendios_{year}.geojson"
    if not path.is_file():
        # allow flat layout
        alt = cache / f"perim_incendios_{year}.geojson"
        if alt.is_file():
            path = alt
        else:
            return []
    fc = json.loads(path.read_text(encoding="utf-8"))
    # Nullable — do not silently force EPSG:3042 at load time
    src_crs = parse_crs_from_geojson(fc)
    feats = []
    for i, f in enumerate(fc.get("features") or []):
        f = dict(f)
        f["_source_year"] = year
        try:
            f["_source_path"] = str(path.relative_to(ROOT))
        except ValueError:
            f["_source_path"] = str(path)
        f["_feature_index"] = i
        f["_source_crs"] = src_crs  # may be None
        feats.append(f)
    return feats


def feature_row(f: dict[str, Any]) -> dict[str, Any]:
    props = dict(f.get("properties") or {})
    year = int(f.get("_source_year") or 0)
    src_crs: str | None = f.get("_source_crs")
    if src_crs is not None:
        src_crs = str(src_crs)
    geom = None
    qa = "ok"
    try:
        g = f.get("geometry")
        if g:
            geom = shape(g)
            if geom.is_empty:
                qa = "empty"
            elif not geom.is_valid:
                geom = geom.buffer(0)
                qa = "repaired" if geom.is_valid else "invalid"
        else:
            qa = "no_geometry"
    except Exception as exc:
        qa = f"geom_error:{type(exc).__name__}"
        geom = None

    # Projected coords without declared CRS: sanity-box → assumed 3042 (flagged);
    # outside box → missing_crs_projected and skip transforms (branch is live).
    if geom is not None and not geom.is_empty:
        minx, miny, maxx, maxy = geom.bounds
        projected = abs(minx) > 180 or abs(miny) > 90 or abs(maxx) > 180 or abs(maxy) > 90
        if projected and src_crs is None:
            if 50_000 < minx < 900_000 and 3_500_000 < miny < 4_600_000:
                src_crs = NATIVE_CRS
                qa = (
                    "assumed_epsg3042_sanity"
                    if qa == "ok"
                    else f"{qa};assumed_epsg3042_sanity"
                )
            else:
                qa = (
                    "missing_crs_projected"
                    if qa == "ok"
                    else f"{qa};missing_crs_projected"
                )
                geom = None

    geom_ha = (
        area_ha_equal_area(geom, src_crs or NATIVE_CRS)
        if geom is not None and src_crs is not None
        else (area_ha_native(geom) if geom is not None else 0.0)
    )
    attr_ha = sup_total_ha(props)
    qa_area = ""
    if attr_ha is not None and attr_ha > 0 and geom_ha > 0:
        ratio = attr_ha / geom_ha if geom_ha else 0.0
        if ratio < 0.25 or ratio > 4.0:
            # Prefer geometry when attribute units look wrong
            ha = geom_ha
            qa_area = "qa_area_mismatch"
            qa = f"{qa};{qa_area}" if qa == "ok" else f"{qa};{qa_area}"
        else:
            ha = attr_ha
    elif attr_ha is not None and attr_ha > 0:
        ha = attr_ha
    else:
        ha = geom_ha

    wgs = (
        to_wgs84_geom(geom, src_crs)
        if geom is not None and src_crs is not None
        else None
    )
    bbox_wgs = None
    centroid = None
    and_ok = False
    if wgs is not None and not wgs.is_empty:
        minx, miny, maxx, maxy = wgs.bounds
        bbox_wgs = [minx, miny, maxx, maxy]
        c = wgs.centroid
        centroid = [float(c.x), float(c.y)]
        and_ok = (
            AND_BBOX_WGS84[0] - 0.5 <= c.x <= AND_BBOX_WGS84[2] + 0.5
            and AND_BBOX_WGS84[1] - 0.5 <= c.y <= AND_BBOX_WGS84[3] + 0.5
        )

    fecha = parse_fecha_inc(props.get("FECHA_INC") or props.get("fecha_inc"))
    codigo = str(props.get("CODIGO") or props.get("codigo") or f"IDX{year}_{f.get('_feature_index')}")

    score = 0
    reasons: list[str] = []
    if ha >= 1000:
        score += 30
        reasons.append("ha>=1000(+30)")
    elif ha >= 500:
        score += 20
        reasons.append("ha>=500(+20)")
    elif ha >= 100:
        score += 10
        reasons.append("ha>=100(+10)")
    if year >= 2023:
        score += 15
        reasons.append("year>=2023(+15)")
    mun = props.get("Municipio") or props.get("municipio")
    prov = props.get("Provincia") or props.get("provincia")
    if mun and prov:
        score += 5
        reasons.append("attrs_loc(+5)")
    if fecha:
        score += 0  # hard filter handled elsewhere
    if and_ok:
        reasons.append("bbox_and_ok")

    return {
        "codigo": codigo,
        "year": year,
        "fecha_inc": fecha or "",
        "municipio": mun or "",
        "provincia": prov or "",
        "ha_attr": round(attr_ha, 2) if attr_ha is not None else "",
        "ha_geom": round(geom_ha, 2),
        "ha_best": round(ha, 2),
        "bbox_wgs84": json.dumps(bbox_wgs) if bbox_wgs else "",
        "centroid_lon": centroid[0] if centroid else "",
        "centroid_lat": centroid[1] if centroid else "",
        "and_bbox_ok": and_ok,
        "qa_geometry": qa,
        "score_base": score,
        "score_reasons": ";".join(reasons),
        "source_path": f.get("_source_path") or "",
        "feature_index": f.get("_feature_index"),
        "sup_arbola": props.get("SUP_ARBOLA", ""),
        "sup_matorr": props.get("SUP_MATORR", ""),
        "sup_pastiz": props.get("SUP_PASTIZ", ""),
        "firms_n": "",
        "score_total": score,
        "tier": "bronze",
    }


def score_firms_bonus(n_hotspots: int) -> tuple[int, str]:
    if n_hotspots >= 20:
        return 25, f"firms>={n_hotspots}(+25)"
    if n_hotspots >= 5:
        return 10, f"firms>={n_hotspots}(+10)"
    if n_hotspots >= 1:
        return 5, f"firms>={n_hotspots}(+5)"
    return 0, "firms=0"


def try_firms_probe(row: dict[str, Any], *, pad_days: int = 2) -> int:
    """Optional live FIRMS Spain-year probe. Returns hotspot count or -1 on skip/fail."""
    try:
        from scripts.fetch_firms_hotspots import fetch_spain_year  # type: ignore
    except Exception:
        # import sibling module by path
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "fetch_firms_hotspots", ROOT / "scripts" / "fetch_firms_hotspots.py"
        )
        if spec is None or spec.loader is None:
            return -1
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            return -1
        fetch_spain_year = mod.fetch_spain_year

    fecha = row.get("fecha_inc") or ""
    if not fecha or len(fecha) < 10:
        return -1
    try:
        lon = float(row["centroid_lon"])
        lat = float(row["centroid_lat"])
    except (KeyError, TypeError, ValueError):
        return -1
    year = int(fecha[:4])
    pad = 0.25
    bbox = (lon - pad, lat - pad, lon + pad, lat + pad)
    try:
        from datetime import date, timedelta

        d0 = date.fromisoformat(fecha)
        dates = {(d0 + timedelta(days=k)).isoformat() for k in range(-pad_days, pad_days + 1)}
        rows = fetch_spain_year(year, sensor="viirs-snpp")
        n = 0
        for r in rows:
            try:
                if (r.get("acq_date") or "") not in dates:
                    continue
                rlat = float(r["latitude"])
                rlon = float(r["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            if bbox[0] <= rlon <= bbox[2] and bbox[1] <= rlat <= bbox[3]:
                n += 1
        return n
    except Exception:
        return -1


def select_tiers(rows: list[dict[str, Any]], *, gold_n: int = 1, silver_n: int = 2) -> dict[str, Any]:
    ranked = sorted(
        rows,
        key=lambda r: (
            float(r.get("score_total") or 0),
            float(r.get("ha_best") or 0),
            str(r.get("fecha_inc") or ""),
        ),
        reverse=True,
    )
    # Hard filters only — never promote invalid / non-Andalucía rows to gold
    def _qa_ok(r: dict[str, Any]) -> bool:
        q = str(r.get("qa_geometry") or "")
        parts = set(q.split(";"))
        # assumed_epsg3042_sanity is explicit (not silent) and still usable for gold
        if "missing_crs_projected" in parts or "empty" in parts or "no_geometry" in parts:
            return False
        if "invalid" in parts:
            return False
        if any(p.startswith("geom_error") for p in parts):
            return False
        base = q.split(";")[0] if q else ""
        return base in {"ok", "repaired", "assumed_epsg3042_sanity"} or (
            "assumed_epsg3042_sanity" in parts and "empty" not in parts
        )

    eligible = [
        r
        for r in ranked
        if r.get("fecha_inc")
        and _qa_ok(r)
        and float(r.get("ha_best") or 0) > 10
        and r.get("and_bbox_ok")
    ]
    # No soft fallback: empty eligible → empty gold/silver
    gold = eligible[:gold_n]
    silver = eligible[gold_n : gold_n + silver_n]
    for r in rows:
        cod = r["codigo"]
        if any(g["codigo"] == cod for g in gold):
            r["tier"] = "gold"
        elif any(s["codigo"] == cod for s in silver):
            r["tier"] = "silver"
        else:
            r["tier"] = "bronze"

    def slim(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "codigo": r["codigo"],
            "year": r["year"],
            "fecha_inc": r["fecha_inc"],
            "municipio": r["municipio"],
            "provincia": r["provincia"],
            "ha_best": r["ha_best"],
            "score_total": r["score_total"],
            "score_reasons": r["score_reasons"],
            "centroid_lon": r["centroid_lon"],
            "centroid_lat": r["centroid_lat"],
            "bbox_wgs84": r["bbox_wgs84"],
            "source_path": r["source_path"],
            "feature_index": r["feature_index"],
            "firms_n": r.get("firms_n"),
            "hypothesis": (
                f"Selected for industrial open E2E: {r['ha_best']} ha, "
                f"{r['municipio']}/{r['provincia']}, fecha {r['fecha_inc']}. "
                "Official REDIAM perimeter (O2). No Vp/ROS invented."
            ),
        }

    return {
        "schema": "rediam_and_selection_v1",
        "built_at_utc": _utc(),
        "attribution": ATTRIBUTION,
        "track": "Pista_B_plus_open_o2_and",
        "gold": [slim(r) for r in gold],
        "silver": [slim(r) for r in silver],
        "n_catalog": len(rows),
        "n_eligible": len(eligible),
        "selection_error": (
            None
            if eligible
            else "no_eligible_events_after_hard_filters_fecha_geom_ha_and_bbox"
        ),
        "notes": [
            "Gold = full E2E pack + acta",
            "Silver = pack + scorecard (dNBR optional)",
            "Bronze = catalog only",
            "FIRMS hull is never official burned area",
            "No tactical Vp without ASEMA anchor",
            "Gold/silver require hard filters; no junk fallback",
        ],
    }


def build_inventory(
    cache: Path,
    out_dir: Path,
    *,
    years: list[int],
    probe_firms: bool,
    firms_top_n: int,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    for y in years:
        feats = load_year_features(cache, y)
        for f in feats:
            all_rows.append(feature_row(f))

    # Optional FIRMS probe on top-N by base score × ha
    if probe_firms and all_rows:
        top = sorted(
            all_rows,
            key=lambda r: (float(r.get("score_base") or 0), float(r.get("ha_best") or 0)),
            reverse=True,
        )[:firms_top_n]
        top_ids = {r["codigo"] for r in top}
        for r in all_rows:
            if r["codigo"] not in top_ids:
                continue
            n = try_firms_probe(r)
            if n < 0:
                r["firms_n"] = "SKIP"
                continue
            r["firms_n"] = n
            bonus, reason = score_firms_bonus(n)
            r["score_total"] = int(r.get("score_base") or 0) + bonus
            if bonus:
                r["score_reasons"] = (r.get("score_reasons") or "") + f";{reason}"
    else:
        for r in all_rows:
            r["score_total"] = int(r.get("score_base") or 0)

    selection = select_tiers(all_rows)

    # CSV
    csv_path = out_dir / "event_catalog.csv"
    fields = [
        "codigo",
        "year",
        "fecha_inc",
        "municipio",
        "provincia",
        "ha_attr",
        "ha_geom",
        "ha_best",
        "centroid_lon",
        "centroid_lat",
        "and_bbox_ok",
        "qa_geometry",
        "score_base",
        "firms_n",
        "score_total",
        "tier",
        "score_reasons",
        "source_path",
        "feature_index",
        "sup_arbola",
        "sup_matorr",
        "sup_pastiz",
        "bbox_wgs84",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(all_rows, key=lambda x: (-float(x.get("score_total") or 0), -float(x.get("ha_best") or 0))):
            w.writerow(r)

    sel_path = out_dir / "selection_gold.json"
    sel_path.write_text(json.dumps(selection, indent=2, ensure_ascii=False), encoding="utf-8")

    by_year: dict[str, int] = {}
    by_prov: dict[str, int] = {}
    ha_sum = 0.0
    for r in all_rows:
        by_year[str(r["year"])] = by_year.get(str(r["year"]), 0) + 1
        p = r.get("provincia") or "?"
        by_prov[p] = by_prov.get(p, 0) + 1
        try:
            ha_sum += float(r.get("ha_best") or 0)
        except (TypeError, ValueError):
            pass

    stats = {
        "schema": "rediam_and_inventory_stats_v1",
        "built_at_utc": _utc(),
        "attribution": ATTRIBUTION,
        "n_events": len(all_rows),
        "ha_sum_best": round(ha_sum, 1),
        "by_year": by_year,
        "by_provincia": dict(sorted(by_prov.items(), key=lambda kv: -kv[1])),
        "n_gold": len(selection.get("gold") or []),
        "n_silver": len(selection.get("silver") or []),
        "qa_counts": {},
        "cache": str(cache),
        "catalog_csv": str(csv_path.relative_to(ROOT)) if csv_path.is_relative_to(ROOT) else str(csv_path),
        "selection_json": str(sel_path.relative_to(ROOT)) if sel_path.is_relative_to(ROOT) else str(sel_path),
    }
    qa_counts: dict[str, int] = {}
    for r in all_rows:
        qa_counts[r.get("qa_geometry") or "?"] = qa_counts.get(r.get("qa_geometry") or "?", 0) + 1
    stats["qa_counts"] = qa_counts
    (out_dir / "inventory_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(json.dumps({
        "n_events": stats["n_events"],
        "n_gold": stats["n_gold"],
        "n_silver": stats["n_silver"],
        "gold": [g["codigo"] for g in selection.get("gold") or []],
        "silver": [s["codigo"] for s in selection.get("silver") or []],
        "catalog": stats["catalog_csv"],
        "selection_error": selection.get("selection_error"),
    }, indent=2))
    return {"stats": stats, "selection": selection, "rows": all_rows}


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventory REDIAM AND WFS cache")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--years", default="2022,2023,2024,2025")
    ap.add_argument("--no-firms", action="store_true", help="Skip live FIRMS probe")
    ap.add_argument("--firms-top", type=int, default=20, help="Probe FIRMS for top N by ha/score")
    args = ap.parse_args()

    cache = args.cache if args.cache.is_absolute() else ROOT / args.cache
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    if not cache.is_dir():
        print(f"Cache missing: {cache}", file=sys.stderr)
        print("Run: python scripts/fetch_rediam_perimeters.py", file=sys.stderr)
        return 2

    result = build_inventory(
        cache,
        out_dir,
        years=years,
        probe_firms=not args.no_firms,
        firms_top_n=args.firms_top,
    )
    n_events = int(result["stats"].get("n_events") or 0)
    n_gold = int(result["stats"].get("n_gold") or 0)
    if n_events == 0:
        print(
            "ERROR: zero events in cache for requested years. "
            "Re-run: python scripts/fetch_rediam_perimeters.py --years …",
            file=sys.stderr,
        )
        return 2
    if n_gold == 0:
        print(
            "ERROR: no gold IF after hard filters (fecha + valid geom + ha>10 + AND bbox). "
            "Check inventory/event_catalog.csv qa_geometry and and_bbox_ok.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
