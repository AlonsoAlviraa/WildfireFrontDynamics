#!/usr/bin/env python3
"""Run Rothermel-lite physics prior (optionally fit/apply calibration).

Usage:
  python scripts/run_rothermel_prior.py
  python scripts/run_rothermel_prior.py --fit-calibration --obs-ros 5.71 --vp 7
  python scripts/run_rothermel_prior.py --calibration-recipe outputs/fuel_stack/tobarra/ros_calibration_recipe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.calibration import CalibrationRefusedError  # noqa: E402
from wildfire_front.fuel.hybrid import hybrid_ros_prior  # noqa: E402
from wildfire_front.fuel.models import list_fuel_ids  # noqa: E402
from wildfire_front.fuel.rothermel_lite import physics_prior_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Rothermel-lite physics prior")
    ap.add_argument("--fuel", default="MED_MAQUIS_LOW")
    ap.add_argument("--wind-ms", type=float, default=4.4)
    ap.add_argument("--slope", type=float, default=5.0)
    ap.add_argument("--fmc", type=float, default=7.0)
    ap.add_argument("--wind-from", type=float, default=270.0)
    ap.add_argument("--obs-ros", type=float, default=5.71)
    ap.add_argument("--vp", type=float, default=7.0)
    ap.add_argument("--list-fuels", action="store_true")
    ap.add_argument("--abstain-demo", action="store_true")
    ap.add_argument("--fit-calibration", action="store_true")
    ap.add_argument("--calibration-recipe", type=Path, default=None)
    ap.add_argument("--dem-source", type=str, default="synthetic")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.list_fuels:
        print(json.dumps(list_fuel_ids(), indent=2))
        return 0

    if args.abstain_demo:
        report = physics_prior_report(
            fuel_id="UNKNOWN",
            wind_10m_ms=args.wind_ms,
            slope_deg=args.slope,
            dead_fmc_pct=args.fmc,
        )
        report2 = physics_prior_report(
            fuel_id=args.fuel,
            wind_10m_ms=None,
            slope_deg=args.slope,
            dead_fmc_pct=args.fmc,
        )
        out = {"unknown_fuel": report, "missing_wind": report2}
        print(json.dumps(out, indent=2))
        return 0

    try:
        phys = physics_prior_report(
            fuel_id=args.fuel,
            wind_10m_ms=args.wind_ms,
            slope_deg=args.slope,
            dead_fmc_pct=args.fmc,
            wind_from_deg=args.wind_from,
            observed_ros_m_min=args.obs_ros,
            vp_anchor_m_min=args.vp,
            fit_calibration=bool(args.fit_calibration),
            calibration_recipe=args.calibration_recipe,
            dem_source=args.dem_source,
            dem_binding={"dem_source": args.dem_source},
        )
    except CalibrationRefusedError as exc:
        print(
            json.dumps({"status": exc.status, "error": str(exc), "details": exc.details}, indent=2)
        )
        return 4

    hybrid = hybrid_ros_prior(
        args.obs_ros,
        fuel_id=args.fuel,
        wind_10m_ms=args.wind_ms,
        slope_deg=args.slope,
        dead_fmc_pct=args.fmc,
        wind_from_deg=args.wind_from,
        vp_anchor_m_min=args.vp,
        calibration_recipe=phys.get("calibration_recipe") or args.calibration_recipe,
        dem_source=args.dem_source,
    )
    bundle = {"physics": phys, "hybrid": hybrid}
    text = json.dumps(bundle, indent=2, ensure_ascii=False)
    print(text)
    out = args.out or (ROOT / "outputs" / "fuel_stack" / "tobarra" / "rothermel_prior.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if args.fit_calibration and phys.get("calibration_recipe"):
        recipe_out = out.parent / "ros_calibration_recipe.json"
        recipe_out.write_text(
            json.dumps(phys["calibration_recipe"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote recipe {recipe_out}", file=sys.stderr)
    print(f"\nWrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
