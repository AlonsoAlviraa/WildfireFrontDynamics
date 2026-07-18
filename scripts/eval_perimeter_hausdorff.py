#!/usr/bin/env python3
"""O2 — Hausdorff / front distance vs reference perimeter.

Supports:
  - Official GeoJSON Polygon/MultiPolygon (--reference)
  - Temporal self-consistency: consecutive main_front rings (no official data)
  - KMZ LatLonQuad footprint as geo-alignment proxy (not fire perimeter)

Usage:
  python scripts/eval_perimeter_hausdorff.py \\
    --observed outputs/observatorio/tobarra_20240802/main_front.geojson \\
    --mode temporal

  python scripts/eval_perimeter_hausdorff.py \\
    --observed outputs/observatorio/tobarra_20240802/main_front.geojson \\
    --reference path/to/official.geojson --sample-spacing-m 5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.evaluation import front_distance_metrics  # noqa: E402


def _wgs84_to_utm30n(lon: float, lat: float) -> tuple[float, float]:
    """Approximate WGS84 → UTM zone 30N (EPSG:32630) for Spain CLM."""
    # Use pyproj if available
    try:
        from pyproj import Transformer

        tr = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)
        x, y = tr.transform(lon, lat)
        return float(x), float(y)
    except Exception:
        # fallback crude equirectangular around 38.6N 1.7W
        lat0 = math.radians(38.6)
        x = (lon + 1.7) * 111320.0 * math.cos(lat0)
        y = (lat - 38.6) * 110540.0
        return x, y


def load_rings_from_geojson(path: Path) -> list[tuple[tuple[float, float], ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rings = []
    for feat in data.get("features") or []:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and coords:
            ring = tuple((float(x), float(y)) for x, y in coords[0])
            rings.append(ring)
        elif gtype == "MultiPolygon" and coords:
            for poly in coords:
                ring = tuple((float(x), float(y)) for x, y in poly[0])
                rings.append(ring)
        elif gtype == "LineString" and coords:
            ring = tuple((float(x), float(y)) for x, y in coords)
            rings.append(ring)
    return rings


def load_kmz_quad_utm(kmz_path: Path) -> tuple[tuple[float, float], ...] | None:
    with zipfile.ZipFile(kmz_path) as zf:
        kml_name = next((n for n in zf.namelist() if n.endswith(".kml")), None)
        if not kml_name:
            return None
        root = ET.fromstring(zf.read(kml_name))
    # handle namespaces
    coords_text = None
    for el in root.iter():
        if el.tag.endswith("coordinates") and el.text and "," in (el.text or ""):
            # prefer LatLonQuad block (4 corners)
            coords_text = el.text.strip()
            break
    if not coords_text:
        return None
    pts = []
    for token in coords_text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            pts.append(_wgs84_to_utm30n(lon, lat))
    if len(pts) < 3:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return tuple(pts)


def largest_ring(rings: list[tuple[tuple[float, float], ...]]) -> tuple[tuple[float, float], ...]:
    def area(ring):
        pts = np.asarray(ring, dtype=float)
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        x, y = pts[:, 0], pts[:, 1]
        return abs(0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

    return max(rings, key=area)


def main() -> int:
    ap = argparse.ArgumentParser(description="O2 Hausdorff perimeter eval")
    ap.add_argument("--observed", type=Path, required=True, help="main_front.geojson or fronts.geojson")
    ap.add_argument("--reference", type=Path, default=None, help="Official perimeter GeoJSON")
    ap.add_argument(
        "--mode",
        choices=["official", "temporal", "kmz_footprint"],
        default="temporal",
    )
    ap.add_argument("--kmz", type=Path, default=None, help="KMZ for footprint proxy")
    ap.add_argument("--sample-spacing-m", type=float, default=5.0)
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = ap.parse_args()

    rings = load_rings_from_geojson(args.observed)
    if len(rings) < 1:
        print("No rings in observed GeoJSON")
        return 1

    report: dict = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "observed": str(args.observed),
        "mode": args.mode,
        "sample_spacing_m": args.sample_spacing_m,
        "n_observed_rings": len(rings),
        "o2_official": False,
    }

    if args.mode == "official":
        if not args.reference or not args.reference.is_file():
            report["status"] = "BLOCKED"
            report["reason"] = "official perimeter GeoJSON not provided"
            report["verdict"] = "BLOCKED_NO_OFFICIAL_PERIMETER"
        else:
            ref_rings = load_rings_from_geojson(args.reference)
            obs = largest_ring(rings)
            ref = largest_ring(ref_rings)
            metrics = front_distance_metrics(obs, ref, sample_spacing=args.sample_spacing_m)
            report["status"] = "OK"
            report["o2_official"] = True
            report["metrics_m"] = metrics
            metrics["front_distance_mean"]  # mean as proxy; add p50 via symmetric
            report["verdict"] = (
                "GO" if metrics["front_distance_p95"] < 100 and metrics["front_distance_mean"] < 50 else "REVIEW"
            )
            report["note"] = "Distances in CRS units of GeoJSON (expect meters if projected)."

    elif args.mode == "temporal":
        if len(rings) < 2:
            report["status"] = "BLOCKED"
            report["reason"] = "need >=2 rings for temporal Hausdorff"
            report["verdict"] = "BLOCKED"
        else:
            pair_metrics = []
            for i in range(1, len(rings)):
                m = front_distance_metrics(
                    rings[i - 1], rings[i], sample_spacing=args.sample_spacing_m
                )
                pair_metrics.append(m)
            means = [m["front_distance_mean"] for m in pair_metrics]
            haus = [m["front_hausdorff"] for m in pair_metrics]
            report["status"] = "OK_PROXY"
            report["o2_official"] = False
            report["pair_metrics_m"] = pair_metrics
            report["summary"] = {
                "mean_front_distance_mean": float(np.mean(means)),
                "mean_hausdorff": float(np.mean(haus)),
                "max_hausdorff": float(np.max(haus)),
            }
            report["verdict"] = "PROXY_TEMPORAL_STABILITY"
            report["note"] = (
                "Not official perimeter validation. Measures frame-to-frame main_front "
                "geometry change (meters if CRS projected)."
            )

    elif args.mode == "kmz_footprint":
        if not args.kmz or not args.kmz.is_file():
            report["status"] = "BLOCKED"
            report["reason"] = "kmz path required"
            report["verdict"] = "BLOCKED"
        else:
            quad = load_kmz_quad_utm(args.kmz)
            if quad is None:
                report["status"] = "FAIL"
                report["reason"] = "could not parse LatLonQuad"
                report["verdict"] = "FAIL"
            else:
                obs = largest_ring(rings)
                # reproject note: main_front already UTM; kmz converted to UTM30N
                m = front_distance_metrics(obs, quad, sample_spacing=args.sample_spacing_m)
                report["status"] = "OK_PROXY"
                report["o2_official"] = False
                report["metrics_m"] = m
                report["verdict"] = "PROXY_IMAGE_FOOTPRINT_NOT_FIRE_PERIMETER"
                report["note"] = (
                    "KMZ LatLonQuad is image footprint, NOT official fire perimeter. "
                    "Useful only for geo-alignment sanity."
                )

    out = args.output
    if out is None:
        out = args.observed.parent / "hausdorff_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k not in ("pair_metrics_m",)}, indent=2, default=str))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
