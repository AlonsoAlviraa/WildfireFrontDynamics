#!/usr/bin/env python3
"""Build fuel–terrain stack for a fire (Fase 1 mega-plan + real DEM).

Usage:
  python scripts/build_fuel_terrain_stack.py --fire tobarra --allow-synthetic
  python scripts/build_fuel_terrain_stack.py --fire tobarra --dem path/to.tif --with-physics
  python scripts/build_fuel_terrain_stack.py --fire tobarra --allow-download --with-physics --fit-calibration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.calibration import (  # noqa: E402
    CalibrationRefusedError,
)
from wildfire_front.fuel.dem import (  # noqa: E402
    TOBARRA_BBOX_WGS84,
    DemUnavailableError,
    resolve_dem,
)

# TOBARRA_BBOX also used for envelope origin
from wildfire_front.fuel.hybrid import hybrid_ros_prior  # noqa: E402
from wildfire_front.fuel.rothermel_lite import (  # noqa: E402
    physics_prior_report,
)
from wildfire_front.fuel.sector_fuels import sector_fuel_summary_from_product  # noqa: E402
from wildfire_front.fuel.stack import (  # noqa: E402
    build_stack_from_dem,
    default_fuel_for_stack,
    representative_terrain,
    stack_summary,
    write_stack,
)
from wildfire_front.fuel.weather import (  # noqa: E402
    DEFAULT_TOBARRA_AEMET_STATION,
    WeatherScenario,
    build_aemet_weather_for_fire_day,
    load_aemet_api_key,
    load_dotenv,
    load_weather_scenario,
    merge_weather_drivers,
    resolve_weather_for_stack,
    save_weather_scenario,
)


def _load_vp_anchor() -> tuple[float | None, str | None]:
    p = ROOT / "data" / "infocam_anchors.json"
    if not p.is_file():
        return None, None
    data = json.loads(p.read_text(encoding="utf-8"))
    a = (data.get("anchors") or {}).get("tobarra_20240802") or {}
    if a.get("status") == "confirmed" and a.get("vp_m_min") is not None:
        return float(a["vp_m_min"]), "confirmed"
    return None, a.get("status")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build fuel–terrain stack")
    ap.add_argument("--fire", default="tobarra", help="Fire key (tobarra only for now)")
    ap.add_argument("--n", type=int, default=40, help="Grid size for synthetic stack")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dem", type=Path, default=None, help="Local DEM GeoTIFF")
    ap.add_argument(
        "--allow-download",
        action="store_true",
        help="Opt-in GLO-30 download (default OFF)",
    )
    ap.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow synthetic DEM if no local/cache/download",
    )
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--with-physics", action="store_true")
    ap.add_argument("--fit-calibration", action="store_true")
    ap.add_argument("--calibration-recipe", type=Path, default=None)
    ap.add_argument(
        "--force-recipe",
        action="store_true",
        help="Apply recipe even if dem_source/fuel_id mismatch",
    )
    ap.add_argument("--obs-ros", type=float, default=5.71, help="Observed primary ROS m/min")
    ap.add_argument("--wind-ms", type=float, default=4.4)
    ap.add_argument("--fmc", type=float, default=7.0, help="Dead fine fuel moisture %")
    ap.add_argument("--wind-from", type=float, default=270.0)
    ap.add_argument(
        "--weather",
        type=Path,
        default=None,
        help="WeatherScenario JSON (sets weather_scenario_assumed from source)",
    )
    ap.add_argument(
        "--fetch-aemet",
        action="store_true",
        help="Fetch live AEMET daily climatology (needs AEMET_API_KEY / .env)",
    )
    ap.add_argument(
        "--aemet-date",
        default="2024-08-02",
        help="Date YYYY-MM-DD for --fetch-aemet (default Tobarra day)",
    )
    ap.add_argument(
        "--aemet-station",
        default=DEFAULT_TOBARRA_AEMET_STATION,
        help="AEMET station id (default Albacete Base Aérea 8175)",
    )
    ap.add_argument(
        "--weather-tobarra-map",
        action="store_true",
        help="Use Pablo map-note scenario (pre_analisis_1711) — always assumed",
    )
    ap.add_argument(
        "--no-spatial-fuels",
        action="store_true",
        help="Disable sector-majority fuels; use stack dominant fuel only",
    )
    ap.add_argument("--save-geotiff", action="store_true")
    ap.add_argument(
        "--with-envelope",
        action="store_true",
        help="Also write hybrid envelope v3 (15/30/60) under out dir",
    )
    ap.add_argument(
        "--with-ensemble",
        action="store_true",
        help="With --with-envelope: attach hybrid+physics_only ensemble bands",
    )
    ap.add_argument(
        "--landcover",
        type=Path,
        default=None,
        help="Local land-cover GeoTIFF (CLC / WorldCover codes)",
    )
    ap.add_argument(
        "--fuel-scheme",
        default="worldcover",
        help="Landcover scheme: worldcover|clc|prometheus",
    )
    ap.add_argument(
        "--allow-fuel-download",
        action="store_true",
        help="Opt-in ESA WorldCover download for fuel map",
    )
    ap.add_argument(
        "--allow-fuel-synthetic",
        action="store_true",
        help="Allow synthetic fuel mosaic",
    )
    ap.add_argument(
        "--fuel-cache-dir",
        type=Path,
        default=None,
        help="Fuel map cache dir (default data/fuel_map/tobarra)",
    )
    args = ap.parse_args()

    fire = args.fire.lower().replace(" ", "_")
    if "tobarra" not in fire:
        print(
            "Only tobarra stack is implemented (no multi-IF DEM yet).",
            file=sys.stderr,
        )
        return 2

    allow_syn = bool(args.allow_synthetic)
    cache = args.cache_dir or (ROOT / "data" / "dem" / "tobarra")
    # Prefer real sources: local → cache → optional download → optional synthetic.
    # If none available and synthetic not allowed, exit 3 (do not silently invent DEM).
    try:
        dem = resolve_dem(
            bbox_wgs84=TOBARRA_BBOX_WGS84,
            local_path=args.dem,
            cache_dir=cache,
            allow_download=bool(args.allow_download),
            allow_synthetic=allow_syn,
            synthetic_n=args.n,
        )
    except DemUnavailableError as exc:
        # Legacy convenience: bare CLI with no flags falls back to synthetic once,
        # with an explicit stderr note (never silent).
        if args.dem is None and not args.allow_download and not allow_syn:
            print(
                "NOTE: no local DEM/cache and --allow-download not set; "
                "falling back to synthetic DEM. Pass --dem, --allow-download, "
                "or --allow-synthetic explicitly for production runs.",
                file=sys.stderr,
            )
            dem = resolve_dem(
                bbox_wgs84=TOBARRA_BBOX_WGS84,
                cache_dir=cache,
                allow_download=False,
                allow_synthetic=True,
                synthetic_n=args.n,
            )
        else:
            print(f"DEM unavailable: {exc}", file=sys.stderr)
            return 3

    # Fuel map: local → cache → opt-in WorldCover → synthetic
    from wildfire_front.fuel.fuel_map import (
        FuelMapUnavailableError,
        resolve_fuel_map,
        write_fuel_map_geotiffs,
    )

    fuel_cache = args.fuel_cache_dir or (ROOT / "data" / "fuel_map" / "tobarra")
    allow_fuel_syn = bool(args.allow_fuel_synthetic)
    try:
        fmap = resolve_fuel_map(
            bbox_wgs84=TOBARRA_BBOX_WGS84,
            local_path=args.landcover,
            cache_dir=fuel_cache,
            allow_download=bool(args.allow_fuel_download),
            allow_synthetic=allow_fuel_syn,
            scheme=args.fuel_scheme,
            cell_size_m=float(dem.cell_size_m),
            reference_shape=dem.elevation_m.shape,
            reference_transform=dem.transform,
        )
    except FuelMapUnavailableError as exc:
        if args.landcover is None and not args.allow_fuel_download and not allow_fuel_syn:
            print(
                "NOTE: no landcover/cache; using synthetic fuel mosaic. "
                "Pass --landcover, --allow-fuel-download, or --allow-fuel-synthetic.",
                file=sys.stderr,
            )
            fmap = resolve_fuel_map(
                bbox_wgs84=TOBARRA_BBOX_WGS84,
                allow_synthetic=True,
                cell_size_m=float(dem.cell_size_m),
                reference_shape=dem.elevation_m.shape,
                reference_transform=dem.transform,
            )
        else:
            print(f"Fuel map unavailable: {exc}", file=sys.stderr)
            return 3

    stack = build_stack_from_dem(dem, fire_id="tobarra_20240802", fuel_map=fmap)
    out = args.out or (ROOT / "outputs" / "fuel_stack" / "tobarra")
    paths = write_stack(stack, out, save_geotiff=bool(args.save_geotiff))
    try:
        paths.update(write_fuel_map_geotiffs(fmap, out))
    except Exception as exc:
        print(f"NOTE: fuel map geotiff write skipped: {exc}", file=sys.stderr)
    summary = stack_summary(stack)
    summary["dem_source"] = dem.source
    summary["fuel_map_source"] = fmap.source
    summary["fuel_scheme"] = fmap.scheme
    summary["fuel_id_dominant"] = fmap.fuel_id_dominant
    summary["fuel_mix"] = fmap.fuel_mix
    summary["dem_synthetic"] = bool(dem.synthetic)
    summary["fuel_map_synthetic"] = bool(fmap.synthetic)
    # Any synthetic layer → synthetic stack (honesty; not only when both are synthetic)
    summary["synthetic"] = bool(dem.synthetic or fmap.synthetic)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # dem manifest in outputs
    dem_manifest = {
        **dem.to_meta(),
        "fire_id": "tobarra_20240802",
    }
    dem_man_path = out / "dem_manifest.json"
    dem_man_path.write_text(json.dumps(dem_manifest, indent=2), encoding="utf-8")
    paths["dem_manifest"] = str(dem_man_path)

    payload: dict = {
        "stack_summary": summary,
        "paths": paths,
        "dem_meta": dem.to_meta(),
        "honest_label": (
            "synthetic_pipeline_wiring_not_survey_grade"
            if dem.synthetic
            else "real_dem_fuel_mosaic_still_proxy"
        ),
    }

    if args.with_physics:
        fuel = default_fuel_for_stack(stack)
        terr = representative_terrain(stack)
        vp, vp_status = _load_vp_anchor()
        dem_binding = {
            "dem_source": dem.source,
            "dem_cache_sha256": dem.sha256,
            "stack_terrain_fingerprint": {
                "slope_deg_mean": terr.slope_deg,
                "slope_deg_p90": stack.terrain_summary.get("slope_deg_p90"),
                "elevation_m_range": stack.terrain_summary.get("elevation_m_range"),
            },
        }

        # Weather priority: --weather file > --fetch-aemet > map-note > CLI defaults
        load_dotenv(ROOT / ".env")
        weather: WeatherScenario | None = None
        if args.weather is not None:
            weather = load_weather_scenario(args.weather)
        elif args.fetch_aemet:
            key = load_aemet_api_key()
            if not key:
                print(
                    "AEMET: need AEMET_API_KEY in env or .env for --fetch-aemet",
                    file=sys.stderr,
                )
                return 2
            try:
                weather = build_aemet_weather_for_fire_day(
                    api_key=key,
                    date=str(args.aemet_date),
                    station=str(args.aemet_station),
                    fire_id="tobarra_20240802",
                )
            except Exception as exc:
                print(f"AEMET fetch failed: {exc}", file=sys.stderr)
                return 1
            aemet_cache = (
                ROOT
                / "data"
                / "fuel_stack"
                / "tobarra"
                / f"weather_aemet_{str(args.aemet_date).replace('-', '')}.json"
            )
            save_weather_scenario(weather, aemet_cache)
            paths["weather_aemet_cache"] = str(aemet_cache)
            print(f"AEMET weather cached → {aemet_cache}", file=sys.stderr)
        else:
            weather = resolve_weather_for_stack(
                weather_path=None,
                wind_10m_ms=args.wind_ms,
                wind_from_deg=args.wind_from,
                dead_fmc_pct=args.fmc,
                use_tobarra_map_default=bool(args.weather_tobarra_map),
                fire_id="tobarra_20240802",
            )
        if weather is None:
            # CLI defaults always yield a scenario via resolve; defensive fallback
            weather = WeatherScenario(
                wind_10m_ms=args.wind_ms,
                wind_from_deg=args.wind_from,
                dead_fmc_pct=args.fmc,
                source="scenario_assumed",
                notes=["cli_defaults_fallback"],
                fire_id="tobarra_20240802",
            )
        # Honesty merge: incomplete observed/aemet never inherits CLI wind as "observed"
        wx_merge = merge_weather_drivers(
            weather,
            wind_10m_ms=args.wind_ms,
            wind_from_deg=args.wind_from,
            dead_fmc_pct=args.fmc,
        )
        wind_ms = wx_merge.wind_10m_ms  # may be None → physics ABSTAIN
        wind_from = float(wx_merge.wind_from_deg) if wx_merge.wind_from_deg is not None else 0.0
        fmc = float(wx_merge.dead_fmc_pct) if wx_merge.dead_fmc_pct is not None else float(args.fmc)
        weather_assumed = bool(wx_merge.weather_scenario_assumed)
        head_b = (wind_from + 180.0) % 360.0

        use_spatial = not bool(args.no_spatial_fuels)
        sector_summary = None
        if use_spatial:
            try:
                sector_summary = sector_fuel_summary_from_product(fmap, head_bearing_deg=head_b)
            except Exception as exc:
                print(
                    f"NOTE: sector fuel summary failed ({exc}); dominant fuel only", file=sys.stderr
                )
                use_spatial = False

        slope_grid = stack.layers.get("slope_deg") if use_spatial else None
        try:
            phys = physics_prior_report(
                fuel_id=fuel.id,
                wind_10m_ms=wind_ms,
                slope_deg=terr.slope_deg,
                dead_fmc_pct=fmc,
                wind_from_deg=wind_from,
                head_bearing_deg=head_b,
                observed_ros_m_min=args.obs_ros,
                vp_anchor_m_min=vp,
                vp_status=vp_status if vp is not None else None,
                fit_calibration=bool(args.fit_calibration),
                calibration_recipe=args.calibration_recipe,
                dem_source=dem.source,
                dem_binding=dem_binding,
                force_recipe=bool(args.force_recipe),
                fuel_map=fmap if use_spatial else None,
                sector_fuels=sector_summary if use_spatial else None,
                slope_deg_grid=slope_grid,
                weather_scenario=weather,
            )
        except CalibrationRefusedError as exc:
            print(f"Calibration refused: {exc.status} {exc}", file=sys.stderr)
            return 4

        recipe_path = None
        if args.fit_calibration and phys.get("calibration_recipe"):
            recipe_path = out / "ros_calibration_recipe.json"
            recipe_path.write_text(
                json.dumps(phys["calibration_recipe"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            paths["calibration_recipe"] = str(recipe_path)

        hybrid = hybrid_ros_prior(
            args.obs_ros,
            fuel_id=fuel.id,
            wind_10m_ms=wind_ms,
            slope_deg=terr.slope_deg,
            dead_fmc_pct=fmc,
            wind_from_deg=wind_from,
            head_bearing_deg=head_b,
            vp_anchor_m_min=vp,
            vp_status=vp_status if vp is not None else None,
            calibration_recipe=phys.get("calibration_recipe") or args.calibration_recipe,
            dem_source=dem.source,
            fuel_map=fmap if use_spatial else None,
            sector_fuels=sector_summary if use_spatial else None,
            slope_deg_grid=slope_grid,
            weather_scenario=weather,
        )
        payload["physics_prior"] = phys
        payload["hybrid_prior"] = hybrid
        payload["weather_scenario"] = weather.to_dict()
        payload["weather_scenario_assumed"] = weather_assumed
        payload["weather_drivers_merge"] = wx_merge.to_audit_dict()
        if sector_summary is not None:
            payload["sector_fuels"] = sector_summary.to_dict()
            sec_path = out / "sector_fuels_tobarra.json"
            sec_path.write_text(
                json.dumps(sector_summary.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            paths["sector_fuels"] = str(sec_path)
        # Persist sector DEM slopes when spatial path used
        drivers = (phys.get("drivers") or {}) if isinstance(phys, dict) else {}
        if drivers.get("sector_terrain") or drivers.get("sector_slopes_deg"):
            st_path = out / "sector_slopes_tobarra.json"
            st_doc = {
                "sector_slopes_deg": drivers.get("sector_slopes_deg"),
                "sector_terrain": drivers.get("sector_terrain"),
            }
            st_path.write_text(json.dumps(st_doc, indent=2, ensure_ascii=False), encoding="utf-8")
            paths["sector_slopes"] = str(st_path)
            payload["sector_slopes"] = st_doc
        wx_path = out / "weather_scenario.json"
        wx_path.write_text(
            json.dumps(weather.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["weather_scenario"] = str(wx_path)
        phys_path = out / "physics_prior_tobarra.json"
        phys_path.write_text(
            json.dumps(
                {
                    "physics": phys,
                    "hybrid": hybrid,
                    "weather_scenario": weather.to_dict(),
                    "weather_drivers_merge": wx_merge.to_audit_dict(),
                    "sector_fuels": (
                        sector_summary.to_dict() if sector_summary is not None else None
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["physics"] = str(phys_path)
        print(
            json.dumps(
                {
                    "physics_status": phys.get("status"),
                    "product_claim": phys.get("product_claim"),
                    "head_m_min": phys.get("ros_head_m_min"),
                    "method": phys.get("method"),
                    "sector_fuel_ids": (phys.get("drivers") or {}).get("sector_fuel_ids"),
                    "calibration_raw_ratios": phys.get("calibration"),
                    "calibrated": phys.get("calibration_applied"),
                    "hybrid_sectors": hybrid.get("sectors"),
                    "alpha_obs": hybrid.get("alpha_obs"),
                    "dem_source": dem.source,
                    "weather_scenario_assumed": weather_assumed,
                    "weather_source": weather.source,
                    "weather_drivers_merge": wx_merge.to_audit_dict(),
                    "wind_10m_ms": wind_ms,
                    "rh_pct": weather.rh_pct,
                    "temp_c": weather.temp_c,
                },
                indent=2,
            )
        )

        if args.with_envelope:
            from wildfire_front.fuel.envelope import (
                bbox_center_utm,
                compute_hybrid_envelope,
                write_hybrid_envelope_geojson,
                write_hybrid_envelope_json,
            )

            origin_xy = bbox_center_utm(stack.bbox_wgs84 or list(TOBARRA_BBOX_WGS84))
            env = compute_hybrid_envelope(
                hybrid,
                observed_ros_m_min=args.obs_ros,
                fuel_id=fuel.id,
                wind_10m_ms=wind_ms,
                wind_from_deg=wind_from,
                slope_deg=terr.slope_deg,
                dead_fmc_pct=fmc,
                calibration_recipe=phys.get("calibration_recipe") or args.calibration_recipe,
                dem_source=dem.source,
                head_bearing_deg=head_b,
                origin_xy=origin_xy,
                origin_source="stack_bbox_center",
                fire_id="tobarra_20240802",
                with_ensemble=bool(args.with_ensemble),
                weather_scenario_assumed=weather_assumed,
            )
            env["weather_scenario"] = weather.to_dict()
            env["weather_drivers_merge"] = wx_merge.to_audit_dict()
            env_path = out / "envelope_v3_hybrid.json"
            write_hybrid_envelope_json(env, env_path)
            gj_path = out / "envelope_v3_hybrid.geojson"
            write_hybrid_envelope_geojson(
                env,
                gj_path,
                center_xy=origin_xy,
                fire_id="tobarra_20240802",
                include_polar=True,
                include_ensemble_rings=bool(args.with_ensemble),
                include_physics_only_rings=bool(args.with_ensemble),
            )
            paths["envelope"] = str(env_path)
            paths["envelope_geojson"] = str(gj_path)
            payload["hybrid_envelope"] = {
                "status": env.get("status"),
                "product": env.get("product"),
                "sector_ros_m_min": env.get("sector_ros_m_min"),
                "head_radius_15_m": (env.get("envelopes") or [{}])[0].get("head_radius_m"),
                "ensemble_meta": env.get("ensemble_meta"),
                "weather_scenario_assumed": weather_assumed,
                "weather_source": weather.source,
            }
            print(json.dumps(payload["hybrid_envelope"], indent=2))

    report_path = out / "build_report.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {report_path}", file=sys.stderr)
    for k, v in paths.items():
        print(f"  {k}: {v}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
