#!/usr/bin/env python3
"""Build hybrid short-horizon envelope v3 (15/30/60 min).

Usage:
  python scripts/build_hybrid_envelope.py --preset tobarra_scenario --with-ensemble
  python scripts/build_hybrid_envelope.py --obs-ros 5.71 --wind-ms 4.4 --wind-from 270 --fmc 7 --slope 3.3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.dem import TOBARRA_BBOX_WGS84  # noqa: E402
from wildfire_front.fuel.envelope import (  # noqa: E402
    bbox_center_utm,
    compute_hybrid_envelope,
    envelope_decision_reasons,
    write_hybrid_envelope_geojson,
    write_hybrid_envelope_json,
)
from wildfire_front.fuel.weather import (  # noqa: E402
    WeatherScenario,
    load_weather_scenario,
    merge_weather_drivers,
    resolve_weather_for_stack,
    tobarra_20240802_default_scenario,
)


def resolve_envelope_cli_weather(
    *,
    weather_path: Path | None = None,
    weather_tobarra_map: bool = False,
    preset: str | None = None,
    wind_ms: float | None = None,
    wind_from: float | None = None,
    fmc: float | None = None,
    fire_id: str = "tobarra_20240802",
):
    """Load weather + honesty-merge (same rails as stack / hybrid library).

    Incomplete ``source=observed|aemet`` never inherits preset/library 4.4 m/s
    while keeping ``weather_scenario_assumed=False``. Preset defaults only apply
    as merge fallbacks when no weather file/map scenario is present.

    Returns ``(ws_obj | None, MergedWeatherDrivers)``.
    """
    from wildfire_front.fuel.weather import MergedWeatherDrivers

    ws_obj: WeatherScenario | None = None
    cli_wind = wind_ms
    cli_from = wind_from
    cli_fmc = fmc

    if weather_path is not None:
        ws_obj = load_weather_scenario(weather_path)
    elif weather_tobarra_map:
        ws_obj = tobarra_20240802_default_scenario()

    if preset == "tobarra_scenario":
        # Pure preset (no weather file): invent assumed engineering scenario.
        # If a weather file/map scenario is already loaded, do **not** fill
        # missing wind with 4.4 here — merge_weather_drivers owns that honesty.
        if ws_obj is None:
            cli_wind = 4.4 if cli_wind is None else cli_wind
            cli_from = 270.0 if cli_from is None else cli_from
            cli_fmc = 7.0 if cli_fmc is None else cli_fmc
            resolved = resolve_weather_for_stack(
                wind_10m_ms=cli_wind,
                wind_from_deg=cli_from,
                dead_fmc_pct=cli_fmc,
                fire_id=fire_id,
            )
            ws_obj = resolved

    # fill_library_when_missing only when we have a scenario or pure preset
    # (so bare --obs-ros without wind stays obs-only, wind=None)
    fill_lib = ws_obj is not None or preset == "tobarra_scenario"
    wx_merge: MergedWeatherDrivers = merge_weather_drivers(
        ws_obj,
        wind_10m_ms=cli_wind,
        wind_from_deg=cli_from,
        dead_fmc_pct=cli_fmc,
        fill_library_when_missing=fill_lib,
    )
    return ws_obj, wx_merge


def main() -> int:
    ap = argparse.ArgumentParser(description="Hybrid envelope v3 15/30/60")
    ap.add_argument("--obs-ros", type=float, default=None)
    ap.add_argument("--wind-ms", type=float, default=None)
    ap.add_argument("--wind-from", type=float, default=None)
    ap.add_argument("--fmc", type=float, default=None)
    ap.add_argument("--slope", type=float, default=None)
    ap.add_argument("--fuel", default="MED_MAQUIS_LOW")
    ap.add_argument("--fire-id", default="tobarra_20240802")
    ap.add_argument(
        "--preset",
        choices=["tobarra_scenario"],
        default=None,
        help="Named scenario defaults for missing ROS/weather (assumed when no --weather)",
    )
    ap.add_argument(
        "--weather",
        type=Path,
        default=None,
        help="WeatherScenario JSON; assumed flag from merge_weather_drivers",
    )
    ap.add_argument(
        "--fetch-aemet",
        action="store_true",
        help="Fetch AEMET daily climatology (AEMET_API_KEY / .env)",
    )
    ap.add_argument("--aemet-date", default="2024-08-02")
    ap.add_argument("--aemet-station", default=None)
    ap.add_argument(
        "--weather-tobarra-map",
        action="store_true",
        help="Use Pablo map-note weather (pre_analisis_1711); always assumed",
    )
    ap.add_argument("--with-ensemble", action="store_true")
    ap.add_argument("--origin-xy", type=str, default=None, help="easting,northing EPSG:32630")
    ap.add_argument("--head-bearing", type=float, default=None)
    ap.add_argument("--calibration-recipe", type=Path, default=None)
    ap.add_argument("--dem-source", type=str, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--no-geojson", action="store_true")
    args = ap.parse_args()

    obs = args.obs_ros
    slope = args.slope
    dem_source = args.dem_source
    recipe = args.calibration_recipe
    fuel_id = args.fuel

    if args.preset == "tobarra_scenario":
        obs = 5.71 if obs is None else obs
        # slope / fuel from real stack if available
        stack_meta = ROOT / "outputs" / "fuel_stack" / "tobarra" / "fuel_terrain_stack.json"
        if stack_meta.is_file():
            meta = json.loads(stack_meta.read_text(encoding="utf-8"))
            if slope is None:
                slope = float((meta.get("terrain_summary") or {}).get("slope_deg_mean") or 3.3)
            dem_source = dem_source or meta.get("dem_source")
            if meta.get("fuel_id_dominant"):
                fuel_id = str(meta["fuel_id_dominant"])
        elif slope is None:
            slope = 3.3
        default_recipe = (
            ROOT / "outputs" / "fuel_stack" / "tobarra" / "ros_calibration_recipe.json"
        )
        if recipe is None and default_recipe.is_file():
            recipe = default_recipe
            try:
                rd = json.loads(default_recipe.read_text(encoding="utf-8"))
                if rd.get("fuel_id"):
                    fuel_id = str(rd["fuel_id"])
            except (OSError, json.JSONDecodeError):
                pass

    weather_path = args.weather
    if weather_path is None and args.fetch_aemet:
        from wildfire_front.fuel.weather import (
            DEFAULT_TOBARRA_AEMET_STATION,
            build_aemet_weather_for_fire_day,
            load_aemet_api_key,
            load_dotenv,
            save_weather_scenario,
        )

        load_dotenv(ROOT / ".env")
        key = load_aemet_api_key()
        if not key:
            print("Need AEMET_API_KEY for --fetch-aemet", file=sys.stderr)
            return 2
        station = args.aemet_station or DEFAULT_TOBARRA_AEMET_STATION
        try:
            ws_fetch = build_aemet_weather_for_fire_day(
                api_key=key,
                date=str(args.aemet_date),
                station=str(station),
                fire_id=args.fire_id,
            )
        except Exception as exc:
            print(f"AEMET fetch failed: {exc}", file=sys.stderr)
            return 1
        cache = (
            ROOT
            / "data"
            / "fuel_stack"
            / "tobarra"
            / f"weather_aemet_{str(args.aemet_date).replace('-', '')}.json"
        )
        save_weather_scenario(ws_fetch, cache)
        weather_path = cache
        print(f"AEMET weather → {cache}", file=sys.stderr)

    ws_obj, wx_merge = resolve_envelope_cli_weather(
        weather_path=weather_path,
        weather_tobarra_map=bool(args.weather_tobarra_map),
        preset=args.preset,
        wind_ms=args.wind_ms,
        wind_from=args.wind_from,
        fmc=args.fmc,
        fire_id=args.fire_id,
    )
    wind = wx_merge.wind_10m_ms
    wind_from = wx_merge.wind_from_deg
    fmc = wx_merge.dead_fmc_pct
    assumed = bool(wx_merge.weather_scenario_assumed)
    weather_doc = ws_obj.to_dict() if ws_obj is not None else None

    if obs is None and wind is None:
        print(
            "Need --obs-ros and/or weather, --weather, or --preset tobarra_scenario",
            file=sys.stderr,
        )
        return 2

    origin_xy = None
    origin_source = "none"
    if args.origin_xy:
        parts = [float(x.strip()) for x in args.origin_xy.split(",")]
        origin_xy = (parts[0], parts[1])
        origin_source = "cli"
    else:
        origin_xy = bbox_center_utm(TOBARRA_BBOX_WGS84)
        origin_source = "bbox_center_utm"

    head_bearing = args.head_bearing
    if head_bearing is None and wind_from is not None:
        head_bearing = (float(wind_from) + 180.0) % 360.0

    env = compute_hybrid_envelope(
        None,
        observed_ros_m_min=obs,
        fuel_id=fuel_id,
        wind_10m_ms=wind,
        wind_from_deg=wind_from if wind_from is not None else 0.0,
        slope_deg=float(slope) if slope is not None else 5.0,
        dead_fmc_pct=fmc if fmc is not None else 7.0,
        calibration_recipe=recipe,
        dem_source=dem_source,
        head_bearing_deg=head_bearing,
        origin_xy=origin_xy,
        origin_source=origin_source,
        fire_id=args.fire_id,
        with_ensemble=bool(args.with_ensemble),
        weather_scenario_assumed=assumed,
    )
    if weather_doc is not None:
        env["weather_scenario"] = weather_doc
    env["weather_drivers_merge"] = wx_merge.to_audit_dict()
    env["weather_scenario_assumed"] = assumed

    out_dir = args.out_dir or (ROOT / "outputs" / "fuel_stack" / "tobarra")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "envelope_v3_hybrid.json"
    write_hybrid_envelope_json(env, json_path)

    gj_path = None
    if not args.no_geojson and origin_xy is not None:
        gj_path = out_dir / "envelope_v3_hybrid.geojson"
        write_hybrid_envelope_geojson(
            env,
            gj_path,
            center_xy=origin_xy,
            fire_id=args.fire_id,
            include_polar=True,
            include_ensemble_rings=bool(args.with_ensemble),
            include_physics_only_rings=bool(args.with_ensemble),
        )

    summary = {
        "status": env.get("status"),
        "product": env.get("product"),
        "sector_ros_m_min": env.get("sector_ros_m_min"),
        "envelopes_n": len(env.get("envelopes") or []),
        "head_radius_15_m": (env.get("envelopes") or [{}])[0].get("head_radius_m"),
        "ensemble_meta": env.get("ensemble_meta"),
        "decision_reasons": envelope_decision_reasons(env),
        "weather_scenario_assumed": assumed,
        "weather_drivers_merge": wx_merge.to_audit_dict(),
        "paths": {
            "json": str(json_path),
            "geojson": str(gj_path) if gj_path else None,
        },
        "not_tactical_dispatch": True,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWrote {json_path}", file=sys.stderr)
    if gj_path:
        print(f"Wrote {gj_path}", file=sys.stderr)
    return 0 if env.get("status") != "abstained" else 3


if __name__ == "__main__":
    raise SystemExit(main())
