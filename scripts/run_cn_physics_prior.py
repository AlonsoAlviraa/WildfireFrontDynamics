#!/usr/bin/env python3
"""Compare Chinese Wang Zhengfei prior vs observed ROS (e.g. Tobarra).

Usage:
  python scripts/run_cn_physics_prior.py
  python scripts/run_cn_physics_prior.py --obs-ros 5.71 --wind-from 270 --wind-force 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.cn_cellular_ca import run_ca  # noqa: E402
from wildfire_front.cn_wang_zhengfei import (  # noqa: E402
    hybrid_polar_to_geojson_ring,
    hybrid_ros_prior,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="CN Wang Zhengfei physics prior vs observed ROS")
    ap.add_argument("--obs-ros", type=float, default=5.71, help="Observed primary ROS m/min")
    ap.add_argument("--temp", type=float, default=32.0)
    ap.add_argument("--humidity", type=float, default=28.0)
    ap.add_argument("--wind-force", type=float, default=3.0)
    ap.add_argument("--wind-from", type=float, default=270.0)
    ap.add_argument("--slope", type=float, default=4.0)
    ap.add_argument("--fuel", type=str, default="mixed")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--ca", action="store_true", help="Also run minimal CA demo")
    ap.add_argument(
        "--geojson-origin",
        type=str,
        default=None,
        help="Optional UTM origin x,y for polar envelope GeoJSON (meters)",
    )
    args = ap.parse_args()

    report = hybrid_ros_prior(
        args.obs_ros,
        temperature_c=args.temp,
        humidity_pct=args.humidity,
        wind_force=args.wind_force,
        wind_from_deg=args.wind_from,
        slope_deg=args.slope,
        fuel=args.fuel,
    )
    # Compact polar in printed JSON (full ring still in file)
    report_print = dict(report)
    if "polar_calibrated" in report_print:
        report_print["polar_calibrated_sample"] = report_print["polar_calibrated"][:6]
        report_print["polar_calibrated_n"] = len(report["polar_calibrated"])
        del report_print["polar_calibrated"]
    if "envelope_radii_m" in report_print:
        report_print["envelope_radii_m_sample"] = {
            k: v[:4] for k, v in report_print["envelope_radii_m"].items()
        }
        del report_print["envelope_radii_m"]

    if args.ca:
        ca = run_ca(steps=30, seed=7)
        ca.pop("history_full", None)
        report["ca_demo"] = ca
        report_print["ca_demo"] = ca

    if args.geojson_origin:
        parts = [float(x.strip()) for x in args.geojson_origin.split(",")]
        gj = hybrid_polar_to_geojson_ring(report, (parts[0], parts[1]), horizon_min=15.0)
        report["geojson_15min"] = gj
        report_print["geojson_15min_n_coords"] = len(
            (gj.get("features") or [{}])[0].get("geometry", {}).get("coordinates", [[]])[0]
        )

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(json.dumps(report_print, indent=2, ensure_ascii=False))
    out = args.out or (ROOT / "outputs" / "cn_physics_prior_tobarra.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if args.geojson_origin and "geojson_15min" in report:
        gj_path = out.with_name(out.stem + "_polar15.geojson")
        gj_path.write_text(json.dumps(report["geojson_15min"], indent=2), encoding="utf-8")
        print(f"Wrote {gj_path}", file=sys.stderr)
    print(f"\nWrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
