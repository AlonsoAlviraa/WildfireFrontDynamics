#!/usr/bin/env python3
"""Evaluate Pablo/GEACAM Tobarra operational KMZ perimeters (2026-07-30 drop).

Loads the two multi-hour perímetro activo KMZ files, reports Sup_ha growth,
pairwise Hausdorff between ops polygons, and (if available) Hausdorff vs the
Tobarra reconstructed main_front pack.

Honesty:
  - Ops perimeter ≠ national cadastre (O2 national remains BLOCKED).
  - Area growth ≠ Vp m/min.
  - Clock model is documented per-instant (see report.clock_model).
  - Metric transforms require pyproj (no silent CRS fallback).

Usage:
  python scripts/eval_tobarra_pablo_perimeters.py
  python scripts/eval_tobarra_pablo_perimeters.py --export-geojson
  python scripts/eval_tobarra_pablo_perimeters.py --export-geojson-to-drop
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.console import configure_console_output  # noqa: E402
from wildfire_front.evaluation import front_distance_metrics  # noqa: E402
from wildfire_front.ops_perimeter import (  # noqa: E402
    METRIC_CRS,
    MetricCrsError,
    OpsPerimeter,
    area_growth_summary,
    area_ha_from_ring_wgs84,
    parse_ops_perimeter,
    pyproj_available,
    repo_relative_path,
    ring_wgs84_to_utm30n,
    write_geojson,
)

DEFAULT_DROP = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
DEFAULT_KMZ = [
    "2024020124_TOBARRA_20240802_1830.kmz",
    "2024020124_TOBARRA_20240802_2143.kmz",
]
DEFAULT_MAIN_FRONT = (
    ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "main_front.geojson"
)
DEFAULT_OUT_DIR = ROOT / "outputs" / "tobarra_pablo_perimeters"
DEFAULT_OUT = DEFAULT_OUT_DIR / "eval_report.json"

# Inventory expectations keyed by basename (not list position)
INVENTORY_SUP_HA_BY_BASENAME: dict[str, float] = {
    "2024020124_TOBARRA_20240802_1830.kmz": 21.489832,
    "2024020124_TOBARRA_20240802_1830.kml": 21.489832,
    "2024020124_TOBARRA_20240802_2143.kmz": 37.075054,
    "2024020124_TOBARRA_20240802_2143.kml": 37.075054,
}

# August 2024 Spain mainland is CEST = UTC+2
CEST_OFFSET = timedelta(hours=2)

# If |Δt| under a model is within this window of main_front span, flag possible overlap
OVERLAP_WINDOW_MIN = 45.0


def _load_inventory_sup_ha(drop_dir: Path) -> dict[str, float]:
    """Merge static map with inventory.json when present (keyed by basename)."""
    out = dict(INVENTORY_SUP_HA_BY_BASENAME)
    inv_path = drop_dir / "inventory.json"
    if not inv_path.is_file():
        return out
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    for row in inv.get("kmz_perimeters") or []:
        f = row.get("file")
        ha = row.get("sup_ha")
        if f and ha is not None:
            out[str(f)] = float(ha)
            # also allow .kml sibling key
            if str(f).lower().endswith(".kmz"):
                out[str(f)[:-4] + ".kml"] = float(ha)
    return out


def _load_main_front_rings_utm(path: Path) -> list[dict]:
    """Load main_front rings already in UTM (EPSG:32630) with metadata."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for feat in data.get("features") or []:
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        coords = geom.get("coordinates")
        gtype = geom.get("type")
        ring = None
        if gtype == "Polygon" and coords:
            ring = tuple((float(x), float(y)) for x, y in coords[0])
        elif gtype == "LineString" and coords:
            ring = tuple((float(x), float(y)) for x, y in coords)
        if ring is None or len(ring) < 3:
            continue
        out.append(
            {
                "ring_utm": ring,
                "observed_at": props.get("observed_at"),
                "area_ha": props.get("area_ha"),
                "observation_id": props.get("observation_id"),
            }
        )
    return out


def _ring_area_m2(ring: tuple[tuple[float, float], ...]) -> float:
    pts = np.asarray(ring, dtype=float)
    if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    if len(pts) < 3:
        return 0.0
    x, y = pts[:, 0], pts[:, 1]
    return abs(0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _select_largest_frame(frames: list[dict]) -> dict:
    """Pick one frame by geometric ring area; keep ring + properties together."""
    return max(frames, key=lambda f: _ring_area_m2(f["ring_utm"]))


def _parse_iso_naive(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = ts.strip().replace("Z", "").replace("z", "")
    # drop fractional if present for simple compare after normalizing
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _clock_model_doc() -> dict:
    return {
        "ops_time": (
            "Filename YYYYMMDD_HHMM = Spanish local wall-clock as INFOCAM export "
            "(August 2024 → CEST = UTC+2 when converting)."
        ),
        "main_front_time": (
            "observed_at from geotiff infer_timestamp, stored with Z suffix. "
            "For this Tobarra pack the numeric wall-clock matches LWIR filenames "
            "and the operational narrative (detection ~16:42), so Z is treated as "
            "a labeling artifact of the pack, not proven IANA UTC."
        ),
        "primary_comparison": "wallclock_naive",
        "primary_comparison_note": (
            "Compare ops local naive vs main_front observed_at with Z stripped "
            "(same wall-clock family). Preferred for this CLM pack."
        ),
        "secondary_comparison": "ops_cest_to_utc_vs_main_front_as_utc",
        "secondary_comparison_note": (
            "Alternative: ops local − 2h (CEST→UTC) vs main_front as true UTC. "
            "If Z were real UTC, 18:30 local ≈ 16:30 UTC could land inside the "
            "LWIR span; we report that delta but do not promote it to official O2."
        ),
    }


def _time_deltas_for_ops(
    ops_local_iso: str | None,
    mf_first_iso: str | None,
    mf_last_iso: str | None,
) -> dict:
    ops = _parse_iso_naive(ops_local_iso)
    mf_first = _parse_iso_naive(mf_first_iso)
    mf_last = _parse_iso_naive(mf_last_iso)
    out: dict = {
        "ops_time_local": ops_local_iso,
        "main_front_first": mf_first_iso,
        "main_front_last": mf_last_iso,
    }
    if ops is None or mf_last is None:
        out["status"] = "unparsed_time"
        return out

    # Primary: wall-clock naive
    d_last = (ops - mf_last).total_seconds() / 60.0
    d_first = (ops - mf_first).total_seconds() / 60.0 if mf_first else None
    out["wallclock_naive"] = {
        "delta_min_vs_main_front_last": round(d_last, 2),
        "delta_min_vs_main_front_first": round(d_first, 2) if d_first is not None else None,
        "within_main_front_span": bool(
            mf_first is not None and mf_first <= ops <= mf_last
        ),
        "near_main_front_window": abs(d_last) <= OVERLAP_WINDOW_MIN
        or (
            mf_first is not None
            and abs((ops - mf_first).total_seconds() / 60.0) <= OVERLAP_WINDOW_MIN
        )
        or (mf_first is not None and mf_first <= ops <= mf_last),
    }

    # Secondary: ops as CEST → UTC, main_front Z as true UTC
    ops_utc = ops - CEST_OFFSET
    mf_last_utc = mf_last  # interpret as UTC
    mf_first_utc = mf_first
    d_last_u = (ops_utc - mf_last_utc).total_seconds() / 60.0
    out["ops_cest_to_utc_vs_main_front_as_utc"] = {
        "ops_as_utc": ops_utc.strftime("%Y-%m-%dT%H:%M:%S"),
        "delta_min_vs_main_front_last": round(d_last_u, 2),
        "within_main_front_span": bool(
            mf_first_utc is not None and mf_first_utc <= ops_utc <= mf_last_utc
        ),
        "near_main_front_window": abs(d_last_u) <= OVERLAP_WINDOW_MIN
        or (
            mf_first_utc is not None
            and abs((ops_utc - mf_first_utc).total_seconds() / 60.0) <= OVERLAP_WINDOW_MIN
        )
        or (mf_first_utc is not None and mf_first_utc <= ops_utc <= mf_last_utc),
    }

    # Per-instant primary flag
    wc = out["wallclock_naive"]
    sec = out["ops_cest_to_utc_vs_main_front_as_utc"]
    if wc["within_main_front_span"] or wc["near_main_front_window"]:
        out["status"] = "POSSIBLE_OVERLAP_WALLCLOCK"
    elif sec["within_main_front_span"] or sec["near_main_front_window"]:
        out["status"] = "POSSIBLE_OVERLAP_ONLY_IF_MF_Z_IS_UTC"
    else:
        out["status"] = "TEMPORAL_MISMATCH"
    return out


def _perim_record(p: OpsPerimeter) -> dict:
    geom_ha = None
    geom_err = None
    try:
        geom_ha = round(area_ha_from_ring_wgs84(p.coords_wgs84), 6)
    except MetricCrsError as exc:
        geom_err = str(exc)
    return {
        "source_path": p.source_path,
        "name": p.name,
        "time_local_inferred": p.time_local_inferred,
        "time_source": p.time_source,
        "sup_ha": p.sup_ha,
        "sup_ha_source": p.sup_ha_source,
        "n_vertices": p.n_vertices,
        "area_ha_geom_utm30n": geom_ha,
        "area_ha_geom_error": geom_err,
        "sup_ha_vs_geom_delta_ha": (
            round(float(p.sup_ha) - geom_ha, 6)
            if p.sup_ha is not None and geom_ha is not None
            else None
        ),
        "centroid_wgs84": _centroid_wgs84(p.coords_wgs84),
        "notes": p.notes,
        "metric_crs": METRIC_CRS if geom_ha is not None else None,
    }


def _centroid_wgs84(ring: tuple[tuple[float, float], ...]) -> list[float]:
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not pts:
        return [0.0, 0.0]
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return [round(lon, 6), round(lat, 6)]


def _pair_hausdorff_ops(
    a: OpsPerimeter, b: OpsPerimeter, sample_spacing_m: float
) -> dict:
    try:
        ra = ring_wgs84_to_utm30n(a.coords_wgs84)
        rb = ring_wgs84_to_utm30n(b.coords_wgs84)
    except MetricCrsError as exc:
        return {
            "from": a.time_local_inferred,
            "to": b.time_local_inferred,
            "status": "DEGRADED",
            "reason": str(exc),
            "metrics_m": None,
        }
    m = front_distance_metrics(ra, rb, sample_spacing=sample_spacing_m)
    return {
        "from": a.time_local_inferred,
        "to": b.time_local_inferred,
        "from_sup_ha": a.sup_ha,
        "to_sup_ha": b.sup_ha,
        "status": "OK",
        "metric_crs": METRIC_CRS,
        "metrics_m": m,
        "note": "Ops-to-ops Hausdorff in UTM30N meters (active perimeter evolution).",
    }


def _compare_to_main_front(
    perims: list[OpsPerimeter],
    main_front_path: Path,
    sample_spacing_m: float,
) -> dict:
    if not main_front_path.is_file():
        return {
            "status": "SKIPPED",
            "reason": f"main_front not found: {repo_relative_path(main_front_path)}",
            "o2_official": False,
        }
    if not pyproj_available():
        return {
            "status": "DEGRADED",
            "reason": (
                "pyproj unavailable; refusing metric Hausdorff vs main_front "
                "(no equirectangular fallback)"
            ),
            "o2_official": False,
            "metrics_m": None,
        }

    frames = _load_main_front_rings_utm(main_front_path)
    if not frames:
        return {
            "status": "SKIPPED",
            "reason": "no rings in main_front",
            "o2_official": False,
        }

    largest_frame = _select_largest_frame(frames)
    last_frame = frames[-1]
    front_times = [f.get("observed_at") for f in frames if f.get("observed_at")]
    mf_first = front_times[0] if front_times else None
    mf_last = front_times[-1] if front_times else None

    comparisons = []
    instant_statuses: list[str] = []
    try:
        for p in perims:
            ring_utm = ring_wgs84_to_utm30n(p.coords_wgs84)
            m_largest = front_distance_metrics(
                ring_utm, largest_frame["ring_utm"], sample_spacing=sample_spacing_m
            )
            m_last = front_distance_metrics(
                ring_utm, last_frame["ring_utm"], sample_spacing=sample_spacing_m
            )
            # Sanity: UTM distances for Tobarra should be << 50 km if CRS aligned
            for label, m in (("largest", m_largest), ("last", m_last)):
                if m["front_hausdorff"] > 1e5:
                    return {
                        "status": "DEGRADED",
                        "reason": (
                            f"Hausdorff {m['front_hausdorff']:.0f} m vs {label} main_front "
                            f"exceeds 100 km — likely CRS mix; refusing to publish metrics"
                        ),
                        "o2_official": False,
                        "metrics_m": None,
                    }
            tinfo = _time_deltas_for_ops(p.time_local_inferred, mf_first, mf_last)
            instant_statuses.append(tinfo.get("status") or "unknown")
            comparisons.append(
                {
                    "ops_time_local": p.time_local_inferred,
                    "ops_sup_ha": p.sup_ha,
                    "time_alignment": tinfo,
                    "vs_largest_main_front": {
                        "main_front_observed_at": largest_frame.get("observed_at"),
                        "main_front_area_ha": largest_frame.get("area_ha"),
                        "observation_id": largest_frame.get("observation_id"),
                        "selection": "max_geometric_ring_area_utm",
                        "metrics_m": m_largest,
                    },
                    "vs_last_main_front": {
                        "main_front_observed_at": last_frame.get("observed_at"),
                        "main_front_area_ha": last_frame.get("area_ha"),
                        "observation_id": last_frame.get("observation_id"),
                        "metrics_m": m_last,
                    },
                }
            )
    except MetricCrsError as exc:
        return {
            "status": "DEGRADED",
            "reason": str(exc),
            "o2_official": False,
            "metrics_m": None,
        }

    # Aggregate status: only claim uniform mismatch if all instants mismatch
    if all(s == "TEMPORAL_MISMATCH" for s in instant_statuses):
        status = "OK_PROXY_TEMPORAL_MISMATCH"
    elif any(s.startswith("POSSIBLE_OVERLAP") for s in instant_statuses):
        status = "OK_PROXY_MIXED_TEMPORAL"
    else:
        status = "OK_PROXY_TEMPORAL_MISMATCH"

    return {
        "status": status,
        "o2_official": False,
        "metric_crs": METRIC_CRS,
        "main_front_path": repo_relative_path(main_front_path),
        "n_main_front_rings": len(frames),
        "main_front_time_range": {"first": mf_first, "last": mf_last},
        "clock_model": _clock_model_doc(),
        "instant_time_statuses": instant_statuses,
        "comparisons": comparisons,
        "disclaimer": (
            "Distances measure geometric agreement between ops active perimeter and "
            "LWIR main_front at different products/FOV scopes — NOT same-time official "
            "O2 validation. See clock_model and per-instant time_alignment. "
            "LWIR main_front is FOV-limited; ops polygon is full active perimeter. "
            "Primary clock model treats main_front Z as wall-clock family of LWIR "
            "filenames (not proven UTC)."
        ),
        "verdict": "PARTIAL_O2_OPS_PROXY",
    }


def _sup_ha_checks(perims: list[OpsPerimeter], expected_by_name: dict[str, float]) -> list[dict]:
    checks = []
    for p in perims:
        base = Path(p.source_path).name
        exp = expected_by_name.get(base)
        if exp is None:
            # try stem match
            stem = Path(base).stem
            for k, v in expected_by_name.items():
                if Path(k).stem == stem:
                    exp = v
                    break
        if exp is None:
            checks.append(
                {
                    "file": base,
                    "sup_ha_parsed": p.sup_ha,
                    "sup_ha_expected_inventory": None,
                    "match": None,
                    "note": "no inventory expectation for basename",
                }
            )
            continue
        ok = p.sup_ha is not None and abs(float(p.sup_ha) - exp) < 1e-4
        checks.append(
            {
                "file": base,
                "sup_ha_parsed": p.sup_ha,
                "sup_ha_expected_inventory": exp,
                "match": ok,
            }
        )
    return checks


def build_report(
    drop_dir: Path,
    kmz_names: list[str],
    main_front: Path | None,
    sample_spacing_m: float,
    *,
    export_geojson: bool,
    geojson_dir: Path | None = None,
) -> dict:
    paths = []
    for name in kmz_names:
        p = drop_dir / name
        if not p.is_file():
            alt = p.with_suffix(".kml")
            if alt.is_file():
                p = alt
            else:
                raise FileNotFoundError(f"missing perimeter file: {p}")
        paths.append(p)

    perims = [parse_ops_perimeter(p, root=ROOT) for p in paths]
    perims.sort(key=lambda x: x.time_local_inferred or x.source_path)

    geojson_paths: list[str] = []
    if export_geojson:
        out_dir = geojson_dir or DEFAULT_OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        for p in perims:
            stem = Path(p.source_path).stem
            out_gj = out_dir / f"{stem}.geojson"
            write_geojson([p], out_gj, name=stem)
            geojson_paths.append(repo_relative_path(out_gj))
        coll = out_dir / "tobarra_ops_perimeters.geojson"
        write_geojson(perims, coll, name="tobarra_ops_perimeters_pablo_20260730")
        geojson_paths.append(repo_relative_path(coll))

    pair_metrics = None
    if len(perims) >= 2:
        pair_metrics = _pair_hausdorff_ops(perims[0], perims[-1], sample_spacing_m)

    mf_block: dict = {"status": "SKIPPED", "reason": "no main_front path", "o2_official": False}
    if main_front is not None:
        mf_block = _compare_to_main_front(perims, main_front, sample_spacing_m)

    expected = _load_inventory_sup_ha(drop_dir)
    sup_checks = _sup_ha_checks(perims, expected)

    report = {
        "schema": "wfd_tobarra_pablo_perimeter_eval_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "fire_id": "tobarra_20240802",
        "incident_code": "2024020124",
        "source_drop": repo_relative_path(drop_dir),
        "source_contact": "pablo.arroyobretano@geacam.com / GEACAM-CMA",
        "received_date": "2026-07-30",
        "product_class": "operational_active_perimeter",
        "clock_model": _clock_model_doc(),
        "metric_backend": {
            "pyproj_available": pyproj_available(),
            "metric_crs": METRIC_CRS,
            "fallback": None,
            "note": "No equirectangular fallback; MetricCrsError → DEGRADED metrics",
        },
        "o2_status": {
            "tobarra_ops_proxy": "PARTIAL_GO",
            "national_cadastre_official": "BLOCKED",
            "note": (
                "Pablo KMZ multi-hour perímetro activo unblocks Tobarra O2 as "
                "ops proxy only. National/catastral O2 remains BLOCKED."
            ),
        },
        "disclaimers": [
            "Ops perimeter ≠ national cadastre / EGIF final.",
            "Area growth (ha/h) ≠ Vp m/min or linear front ROS.",
            "Do not invent Vp; do not set anchors to confirmed without parte text.",
            "Cardoso O1 remains pending_external (no extra Cardoso material).",
            "field_ops fusion OFF; no fake ROS from ML.",
            "Metric Hausdorff requires pyproj EPSG:32630; no silent CRS fallback.",
        ],
        "perimeters": [_perim_record(p) for p in perims],
        "sup_ha_inventory_checks": sup_checks,
        "area_growth": area_growth_summary(perims),
        "ops_pair_hausdorff": pair_metrics,
        "vs_reconstructed_main_front": mf_block,
        "geojson_exports": geojson_paths,
        "verdict": "PARTIAL_O2_TOBARRA_OPS_PROXY",
    }
    return report


def main() -> int:
    configure_console_output()
    ap = argparse.ArgumentParser(description="Tobarra Pablo ops perimeter eval")
    ap.add_argument("--drop-dir", type=Path, default=DEFAULT_DROP)
    ap.add_argument(
        "--kmz",
        nargs="+",
        default=DEFAULT_KMZ,
        help="KMZ/KML basenames under drop-dir",
    )
    ap.add_argument(
        "--main-front",
        type=Path,
        default=DEFAULT_MAIN_FRONT,
        help="Optional reconstructed main_front.geojson (UTM)",
    )
    ap.add_argument("--no-main-front", action="store_true")
    ap.add_argument("--sample-spacing-m", type=float, default=5.0)
    ap.add_argument(
        "--export-geojson",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write GeoJSON under outputs/tobarra_pablo_perimeters/ (default: on)",
    )
    ap.add_argument(
        "--export-geojson-to-drop",
        action="store_true",
        help="Also/instead write GeoJSON into the intake drop dir (opt-in)",
    )
    ap.add_argument(
        "--geojson-dir",
        type=Path,
        default=None,
        help="Override GeoJSON output directory (default: outputs/tobarra_pablo_perimeters)",
    )
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    main_front = None if args.no_main_front else args.main_front
    export_gj = bool(args.export_geojson) or bool(args.export_geojson_to_drop)
    if args.export_geojson_to_drop:
        geojson_dir = args.drop_dir
    else:
        geojson_dir = args.geojson_dir or DEFAULT_OUT_DIR

    report = build_report(
        args.drop_dir,
        list(args.kmz),
        main_front,
        args.sample_spacing_m,
        export_geojson=export_gj,
        geojson_dir=geojson_dir if export_gj else None,
    )

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    pair = report.get("ops_pair_hausdorff") or {}
    summary = {
        "verdict": report["verdict"],
        "o2_status": report["o2_status"],
        "metric_backend": report["metric_backend"],
        "perimeters": [
            {
                "t": p["time_local_inferred"],
                "sup_ha": p["sup_ha"],
                "geom_ha": p["area_ha_geom_utm30n"],
            }
            for p in report["perimeters"]
        ],
        "area_growth": report["area_growth"],
        "ops_pair_hausdorff_m": pair.get("metrics_m"),
        "ops_pair_status": pair.get("status"),
        "vs_main_front_status": report["vs_reconstructed_main_front"].get("status"),
        "instant_time_statuses": report["vs_reconstructed_main_front"].get(
            "instant_time_statuses"
        ),
        "output": repo_relative_path(out),
        "geojson_exports": report.get("geojson_exports"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
