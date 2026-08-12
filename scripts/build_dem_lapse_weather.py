#!/usr/bin/env python3
"""Build honest DEM-lapse spatial weather geotiffs for spatial_v1 re-emit.

When gridded reanalysis (ERA5 / AEMET grid) is unavailable, derive **physical
orographic structure** from GLO-30 DEM + fire-day scalar anchors:

* Temperature: standard atmosphere lapse 6.5 K/km relative to DEM mean
* Humidity: slight increase with elevation (orographic moisture proxy)
* Wind speed: base × (1 + k·normalized_slope) — topographic speed-up
* Wind dir: base + mild aspect-aligned diversion (degrees; stamped proxy)
* Precip: base + mild windward orographic enhancement

Honesty (never sold as reanalysis)::

    weather_provenance = "dem_lapse_v1"
    weather_is_spatial = True  (grids have real variance from DEM)
    not_reanalysis = True
    scalar_anchors = per-fire DEFAULT_WEATHER_SCALARS

Usage::

    $env:PYTHONPATH = "."
    python scripts/build_dem_lapse_weather.py
    python scripts/build_dem_lapse_weather.py --fire CARDOSO,hellin_2024
    python scripts/build_dem_lapse_weather.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    CORE_SPATIAL_FIRES,
    default_weather_scalars,
    geotiff_spatial_stats,
    inventory_weather_dir,
    list_core_source_ids,
    resolve_dem_path,
    resolve_source_id,
    weather_dir_for,
)

# Standard atmosphere environmental lapse (°C per meter)
LAPSE_C_PER_M = 0.0065
# Humidity: relative increase per km elevation above mean (capped)
RH_PER_KM = 4.0  # percentage points per km
# Wind speed-up coefficient vs normalized slope
WIND_SLOPE_K = 0.35
# Precip orographic add (mm) at max windward slope factor
PRECIP_ORO_MAX = 0.5
PROVENANCE = "dem_lapse_v1"


def _write_geotiff(path: Path, arr: np.ndarray, profile: dict[str, Any]) -> None:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(arr, dtype=np.float32)
    prof = dict(profile)
    prof.update(
        {
            "dtype": "float32",
            "count": 1,
            "compress": "deflate",
            "nodata": None,
        }
    )
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(data, 1)
        dst.update_tags(
            weather_provenance=PROVENANCE,
            not_reanalysis="true",
            note="DEM-lapse / orographic proxy — not AEMET/ERA5 gridded fields",
        )


def _slope_aspect(elev: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return slope (rise/run, unitless) and aspect (radians from north, CW)."""
    # simple central differences in pixel space; scale not critical for proxies
    dy, dx = np.gradient(elev.astype(np.float64))
    slope = np.sqrt(dx * dx + dy * dy).astype(np.float32)
    # aspect: 0 = north-ish; atan2(dx, -dy) common GIS convention approx
    aspect = np.arctan2(dx, -dy).astype(np.float32)
    return slope, aspect


def build_dem_lapse_fields(
    elev: np.ndarray,
    scalars: dict[str, float],
) -> dict[str, np.ndarray]:
    """Map DEM elevation + scalar anchors → weather field grids."""
    z = np.asarray(elev, dtype=np.float32)
    finite = z[np.isfinite(z)]
    if finite.size == 0:
        raise ValueError("DEM has no finite elevation cells")
    z_ref = float(np.mean(finite))
    dz = z - z_ref  # meters relative to window mean

    temp_ref = float(scalars.get("temp", 30.0))
    rh_ref = float(scalars.get("humidity", 30.0))
    ws_ref = float(scalars.get("wind_speed", 5.0))
    wd_ref = float(scalars.get("wind_dir", 90.0))
    pr_ref = float(scalars.get("precip", 0.0))

    # tmin / tmax: diurnal split around temp_ref with same lapse
    tmin = (temp_ref - 4.0) - LAPSE_C_PER_M * dz
    tmax = (temp_ref + 6.0) - LAPSE_C_PER_M * dz

    # humidity: cooler higher elevations slightly more RH (proxy, capped)
    humidity = rh_ref + RH_PER_KM * (dz / 1000.0)
    humidity = np.clip(humidity, 5.0, 95.0).astype(np.float32)

    slope, aspect = _slope_aspect(z)
    s_finite = slope[np.isfinite(slope)]
    s_p95 = float(np.percentile(s_finite, 95)) if s_finite.size else 1.0
    s_p95 = max(s_p95, 1e-6)
    s_norm = np.clip(slope / s_p95, 0.0, 1.5).astype(np.float32)

    wind_speed = (ws_ref * (1.0 + WIND_SLOPE_K * s_norm)).astype(np.float32)

    # Mild aspect diversion of wind direction (proxy — stamped dem_lapse)
    # Convert aspect rad → deg offset ±15° max
    aspect_deg = np.degrees(aspect).astype(np.float32)
    wind_dir = (wd_ref + 15.0 * np.sin(np.radians(aspect_deg - wd_ref))).astype(np.float32)
    wind_dir = np.mod(wind_dir, 360.0).astype(np.float32)

    # Windward precip proxy: elevation relative + slope facing mean wind
    wd_rad = np.radians(wd_ref)
    # unit wind vector (meteo: dir = from which wind blows)
    wx = -np.sin(wd_rad)
    wy = -np.cos(wd_rad)
    # local gradient unit (upslope)
    dy, dx = np.gradient(z.astype(np.float64))
    gnorm = np.sqrt(dx * dx + dy * dy) + 1e-6
    ux, uy = dx / gnorm, dy / gnorm
    windward = np.clip(-(ux * wx + uy * wy), 0.0, 1.0).astype(np.float32)
    precip = (pr_ref + PRECIP_ORO_MAX * windward * s_norm).astype(np.float32)
    precip = np.clip(precip, 0.0, 50.0).astype(np.float32)

    return {
        "tmin": tmin.astype(np.float32),
        "tmax": tmax.astype(np.float32),
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "precip": precip,
    }


def emit_fire(
    source_id: str,
    *,
    repo_root: Path = ROOT,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    dem = resolve_dem_path(source_id, repo_root=repo_root)
    if dem is None or not dem.is_file():
        return {
            "source_id": source_id,
            "ok": False,
            "error": "dem_missing",
        }

    import rasterio

    with rasterio.open(dem) as src:
        elev = src.read(1).astype(np.float32)
        profile = src.profile.copy()

    scalars = default_weather_scalars(source_id)
    fields = build_dem_lapse_fields(elev, scalars)
    out_dir = weather_dir_for(CORE_SPATIAL_FIRES[source_id], repo_root=repo_root)

    rec: dict[str, Any] = {
        "source_id": source_id,
        "ok": True,
        "dem_path": str(dem.as_posix()),
        "weather_dir": str(out_dir.as_posix()),
        "provenance": PROVENANCE,
        "not_reanalysis": True,
        "scalar_anchors": scalars,
        "lapse_c_per_m": LAPSE_C_PER_M,
        "dry_run": dry_run,
        "fields": {},
        "honesty": {
            "weather_provenance": PROVENANCE,
            "not_reanalysis": True,
            "not_aemet_gridded": True,
            "not_era5": True,
            "spatial_variance_from_dem": True,
            "scalar_anchors_fire_day": True,
        },
    }

    if dry_run:
        for k, arr in fields.items():
            rec["fields"][k] = {
                "std": float(np.nanstd(arr)),
                "min": float(np.nanmin(arr)),
                "max": float(np.nanmax(arr)),
                "would_write": str((out_dir / f"{k}.tif").as_posix()),
            }
        return rec

    if out_dir.is_dir() and not force:
        list(out_dir.glob("*.tif"))
        # Only skip if full core present and already dem_lapse tagged
        core_ok = all((out_dir / f"{k}.tif").is_file() for k in fields)
        prov_path = out_dir / "weather_provenance.json"
        if core_ok and prov_path.is_file():
            try:
                prev = json.loads(prov_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                prev = {}
            if prev.get("provenance") == PROVENANCE:
                rec["skipped"] = True
                rec["reason"] = "already_dem_lapse_v1"
                rec["inventory"] = inventory_weather_dir(out_dir)
                return rec

    out_dir.mkdir(parents=True, exist_ok=True)
    for k, arr in fields.items():
        dest = out_dir / f"{k}.tif"
        _write_geotiff(dest, arr, profile)
        stats = geotiff_spatial_stats(dest)
        rec["fields"][k] = {
            "path": str(dest.as_posix()),
            "stats": stats,
        }
        if not stats.get("is_spatial"):
            rec["ok"] = False
            rec["error"] = f"field_{k}_not_spatial"

    prov = {
        "schema": "wfd_dem_lapse_weather_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "source_id": source_id,
        "provenance": PROVENANCE,
        "not_reanalysis": True,
        "dem_path": str(dem.as_posix()),
        "scalar_anchors": scalars,
        "params": {
            "lapse_c_per_m": LAPSE_C_PER_M,
            "rh_per_km": RH_PER_KM,
            "wind_slope_k": WIND_SLOPE_K,
            "precip_oro_max": PRECIP_ORO_MAX,
        },
        "fields": {k: v.get("path") for k, v in rec["fields"].items()},
        "honesty": rec["honesty"],
    }
    (out_dir / "weather_provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    rec["inventory"] = inventory_weather_dir(out_dir)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fire",
        type=str,
        default=None,
        help="Comma-separated source_id or dem_key (default: all core)",
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing dem_lapse")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "dem_lapse_weather_manifest.json",
    )
    args = ap.parse_args(argv)

    if args.fire:
        sids = []
        for part in args.fire.replace(";", ",").split(","):
            p = part.strip()
            if not p:
                continue
            sids.append(resolve_source_id(p))
    else:
        sids = list_core_source_ids()

    reports: dict[str, Any] = {}
    n_ok = 0
    for sid in sids:
        r = emit_fire(sid, force=bool(args.force), dry_run=bool(args.dry_run))
        reports[sid] = r
        status = "OK" if r.get("ok") else "FAIL"
        if r.get("skipped"):
            status = "SKIP"
        inv = r.get("inventory") or {}
        print(
            f"{sid}: {status} spatial={inv.get('weather_spatial_available')} "
            f"full_core={inv.get('weather_full_core')} "
            f"prov={r.get('provenance')}",
            flush=True,
        )
        if r.get("ok") or r.get("skipped"):
            n_ok += 1

    man = {
        "schema": "wfd_dem_lapse_weather_batch_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "provenance": PROVENANCE,
        "not_reanalysis": True,
        "n_fires": len(sids),
        "n_ok": n_ok,
        "fires": reports,
        "honesty": {
            "weather_provenance": PROVENANCE,
            "not_reanalysis": True,
            "gridded_reanalysis_preferred_when_available": True,
            "spatial_variance_from_dem": True,
        },
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"manifest → {args.manifest_out}", flush=True)
    return 0 if n_ok == len(sids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
