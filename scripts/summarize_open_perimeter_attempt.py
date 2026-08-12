#!/usr/bin/env python3
"""R-A1 — Best-effort EFFIS/CEMS open perimeter summary + Hausdorff-lite.

Loads an **existing** open_if pack (no live CEMS download required). Writes:

* ``outputs/open_perimeter_attempts/<pack_id>/perimeter_summary.json``
* optional MD note

Honesty
-------
* CEMS / REDIAM open perimeters are **not** national cadastre O2 unlock.
* Hausdorff-lite is **intra-pack** (timeline steps or two vector products), or
  vs optional ``--ops-geojson`` when co-incident geometry is provided.
* Never invents official O2 GO; never invents Vp.

Usage
-----
::

    python scripts/summarize_open_perimeter_attempt.py --pack outputs/open_if/emsr578
    python scripts/summarize_open_perimeter_attempt.py --pack outputs/open_if/emsr578 \\
        --ops-geojson outputs/tobarra_pablo_perimeters/tobarra_ops_perimeters.geojson
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _walk_coords(geom: dict[str, Any] | None, out: list[tuple[float, float]]) -> None:
    if not geom:
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point" and c:
        out.append((float(c[0]), float(c[1])))
    elif t in ("LineString", "MultiPoint") and c:
        for p in c:
            out.append((float(p[0]), float(p[1])))
    elif t in ("Polygon", "MultiLineString") and c:
        for ring in c:
            for p in ring:
                out.append((float(p[0]), float(p[1])))
    elif t == "MultiPolygon" and c:
        for poly in c:
            for ring in poly:
                for p in ring:
                    out.append((float(p[0]), float(p[1])))
    elif t == "Feature":
        _walk_coords(geom.get("geometry"), out)
    elif t == "FeatureCollection":
        for f in geom.get("features") or []:
            _walk_coords(f, out)
    elif t == "GeometryCollection":
        for g in geom.get("geometries") or []:
            _walk_coords(g, out)


def _bbox(coords: list[tuple[float, float]]) -> list[float] | None:
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return [min(xs), min(ys), max(xs), max(ys)]


def _centroid(coords: list[tuple[float, float]]) -> list[float] | None:
    if not coords:
        return None
    return [sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)]


def _approx_haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance metres (WGS84 sphere)."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371000.0 * math.asin(min(1.0, math.sqrt(h)))


def _sample_ring(coords: list[tuple[float, float]], n: int = 48) -> list[tuple[float, float]]:
    if len(coords) <= n:
        return coords
    step = max(1, len(coords) // n)
    return coords[::step][:n]


def hausdorff_lite_m(
    a_coords: list[tuple[float, float]],
    b_coords: list[tuple[float, float]],
    n: int = 48,
) -> float | None:
    """Symmetric max of directed nearest-neighbour distances (sampled)."""
    if not a_coords or not b_coords:
        return None
    sa, sb = _sample_ring(a_coords, n), _sample_ring(b_coords, n)

    def directed(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> float:
        worst = 0.0
        for p in src:
            best = min(_approx_haversine_m(p, q) for q in dst)
            if best > worst:
                worst = best
        return worst

    return max(directed(sa, sb), directed(sb, sa))


def _load_geojson_coords(path: Path) -> list[tuple[float, float]]:
    data = _load(path)
    if not isinstance(data, dict):
        return []
    out: list[tuple[float, float]] = []
    _walk_coords(data, out)
    return out


def summarize_pack(pack: Path, ops_geojson: Path | None = None) -> dict[str, Any]:
    pack = pack.resolve()
    man = _load(pack / "manifest.json") or {}
    score = (
        _load(pack / "scorecard_pista_b.json")
        or _load(pack / "scorecard_and_industrial.json")
        or _load(pack / "scorecard_ext_industrial.json")
        or {}
    )

    vectors_dir = pack / "vectors"
    vector_files: list[Path] = []
    if vectors_dir.is_dir():
        vector_files = sorted(vectors_dir.glob("*.geojson"))
    timeline = pack / "timeline_perimeters.geojson"
    if timeline.is_file() and timeline not in vector_files:
        vector_files.append(timeline)

    products: list[dict[str, Any]] = []
    all_coords: list[tuple[float, float]] = []
    for vf in vector_files:
        coords = _load_geojson_coords(vf)
        all_coords.extend(coords)
        products.append(
            {
                "file": vf.name,
                "rel": str(vf.relative_to(pack)).replace("\\", "/"),
                "n_coords": len(coords),
                "bbox": _bbox(coords),
                "centroid": _centroid(coords),
            }
        )

    # Prefer manifest product rows when present
    man_products = man.get("products") if isinstance(man, dict) else None
    man_rows: list[dict[str, Any]] = []
    if isinstance(man_products, list):
        for p in man_products:
            if not isinstance(p, dict):
                continue
            man_rows.append(
                {
                    "kind": p.get("kind"),
                    "area_ha": p.get("area_ha"),
                    "centroid_lon": p.get("centroid_lon"),
                    "centroid_lat": p.get("centroid_lat"),
                    "geojson_path": p.get("geojson_path"),
                }
            )

    # Intra-pack Hausdorff-lite: first two vector products with coords
    h_intra: float | None = None
    h_pair: list[str] | None = None
    with_coords = [p for p in products if (p.get("n_coords") or 0) > 3]
    if len(with_coords) >= 2:
        a = _load_geojson_coords(pack / with_coords[0]["rel"])
        b = _load_geojson_coords(pack / with_coords[1]["rel"])
        h_intra = hausdorff_lite_m(a, b)
        h_pair = [with_coords[0]["file"], with_coords[1]["file"]]

    # Optional ops compare (honest: may be different geography)
    ops_block: dict[str, Any] = {
        "provided": False,
        "coincident_geometry": False,
        "hausdorff_lite_m": None,
        "note": "No ops geojson provided; skip ops↔open compare.",
    }
    if ops_geojson is not None and ops_geojson.is_file():
        ops_coords = _load_geojson_coords(ops_geojson)
        open_coords = all_coords
        h_ops = hausdorff_lite_m(ops_coords, open_coords) if ops_coords and open_coords else None
        # Coincident heuristic: centroids within ~50 km
        c_open = _centroid(open_coords)
        c_ops = _centroid(ops_coords)
        coincident = False
        dist_km = None
        if c_open and c_ops:
            dist_km = _approx_haversine_m((c_open[0], c_open[1]), (c_ops[0], c_ops[1])) / 1000.0
            coincident = dist_km < 50.0
        ops_block = {
            "provided": True,
            "ops_path": str(ops_geojson).replace("\\", "/"),
            "n_ops_coords": len(ops_coords),
            "centroid_ops": c_ops,
            "centroid_open": c_open,
            "centroid_distance_km": dist_km,
            "coincident_geometry": coincident,
            "hausdorff_lite_m": h_ops if coincident else None,
            "note": (
                "Ops↔open Hausdorff reported only when centroids < 50 km (coincident heuristic). "
                "Different-fire compares are recorded as distance only — not O2."
                if not coincident
                else "Coincident heuristic PASS; Hausdorff-lite is proxy, not national O2."
            ),
        }

    o2_national = (
        score.get("O2_national_official") or man.get("O2_national_official") or "NO_GO_CEMS_PROXY"
    )
    o2_cems = score.get("O2_cems_delineation") or man.get("O2_cems_delineation")

    summary: dict[str, Any] = {
        "schema": "open_perimeter_attempt_v1",
        "graph_id": "R-A1",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "pack_id": pack.name,
        "pack_path": str(pack.relative_to(ROOT)).replace("\\", "/")
        if pack.is_relative_to(ROOT)
        else str(pack),
        "activation": man.get("activation") or score.get("activation") or pack.name,
        "max_area_ha": man.get("max_area_ha") or score.get("max_area_ha"),
        "n_timeline_steps": score.get("n_timeline_steps") or man.get("n_timeline_steps"),
        "n_vector_files": len(vector_files),
        "bbox_union": _bbox(all_coords),
        "centroid_union": _centroid(all_coords),
        "products_from_manifest": man_rows,
        "vector_files": products,
        "hausdorff_lite_intra_pack_m": h_intra,
        "hausdorff_lite_pair": h_pair,
        "ops_compare": ops_block,
        "O2_cems_delineation": o2_cems,
        "O2_national_official": o2_national,
        "o2_national_unlocked": False,
        "rails": {
            "not_national_cadastre": True,
            "not_tactical_dispatch": True,
            "not_ops_ros": True,
            "no_invented_vp": True,
        },
        "note": (
            "Best-effort summary of **existing** open pack geometry (CEMS/REDIAM/etc.). "
            "Does **not** unlock O2 national. Hausdorff-lite is sampled nearest-neighbour "
            "symmetric distance on WGS84 — diagnostic only."
        ),
        "status": "OK_OPEN_PACK" if vector_files or man_rows else "GAP_NO_GEOMETRY",
    }
    return summary


def render_md(summary: dict[str, Any]) -> str:
    ops = summary.get("ops_compare") or {}
    lines = [
        f"# Open perimeter attempt — {summary.get('pack_id')} (R-A1)",
        "",
        f"_UTC: {summary.get('built_at_utc')}_",
        "",
        f"- **activation:** `{summary.get('activation')}`",
        f"- **status:** `{summary.get('status')}`",
        f"- **max_area_ha:** {summary.get('max_area_ha')}",
        f"- **n_vector_files:** {summary.get('n_vector_files')}",
        f"- **O2_cems_delineation:** {summary.get('O2_cems_delineation')}",
        f"- **O2_national_official:** {summary.get('O2_national_official')} "
        f"(unlocked={summary.get('o2_national_unlocked')})",
        f"- **Hausdorff-lite intra-pack (m):** {summary.get('hausdorff_lite_intra_pack_m')} "
        f"pair={summary.get('hausdorff_lite_pair')}",
        f"- **ops compare:** coincident={ops.get('coincident_geometry')} "
        f"H≈{ops.get('hausdorff_lite_m')} m · {ops.get('note')}",
        "",
        "> CEMS/open perimeter is **proxy**, not Spanish national cadastre. No Vp invented.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R-A1 open perimeter summary / Hausdorff-lite")
    ap.add_argument(
        "--pack",
        type=Path,
        default=ROOT / "outputs" / "open_if" / "emsr578",
        help="Existing open_if pack directory",
    )
    ap.add_argument(
        "--ops-geojson",
        type=Path,
        default=None,
        help="Optional ops perimeter GeoJSON for coincident compare",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: outputs/open_perimeter_attempts/<pack_id>/",
    )
    args = ap.parse_args(argv)

    pack = args.pack
    if not pack.is_dir():
        print(json.dumps({"ok": False, "error": f"pack not found: {pack}"}), file=sys.stderr)
        return 2

    summary = summarize_pack(pack, ops_geojson=args.ops_geojson)
    out_dir = args.out_dir or (ROOT / "outputs" / "open_perimeter_attempts" / pack.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "perimeter_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "perimeter_summary.md").write_text(render_md(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "graph_id": "R-A1",
                "pack_id": summary["pack_id"],
                "status": summary["status"],
                "o2_national_unlocked": False,
                "hausdorff_lite_intra_pack_m": summary.get("hausdorff_lite_intra_pack_m"),
                "out": str(out_dir.relative_to(ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
