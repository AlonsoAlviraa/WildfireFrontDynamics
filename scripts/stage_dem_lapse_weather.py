#!/usr/bin/env python3
"""Stage honest DEM-lapse weather rasters for spatial_v1 (not reanalysis).

Builds tmin/tmax/humidity/wind/precip geotiffs with spatial variance derived from
DEM elevation (adiabatic-style lapse) + per-fire scalar anchors. Stamps honesty
so these are NOT sold as AEMET gridded reanalysis.

Usage::

    $env:PYTHONPATH = "."
    python scripts/stage_dem_lapse_weather.py --fire CARDOSO
    python scripts/stage_dem_lapse_weather.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    CORE_SPATIAL_FIRES,
    get_fire_spec,
    list_core_source_ids,
    resolve_dem_path,
    weather_dir_for,
)

# Default scalars (same family as preprocess_clm_to_ndws_npz)
_WX = {
    "CARDOSO": {"temp": 35.0, "humidity": 18.0, "wind_speed": 5.0, "wind_dir": 90.0},
    "LA_ESTRELLA_ACOM1": {"temp": 37.0, "humidity": 16.0, "wind_speed": 5.0, "wind_dir": 90.0},
    "LA_ESTRELLA_ACOM2": {"temp": 37.0, "humidity": 16.0, "wind_speed": 5.0, "wind_dir": 90.0},
    "hellin_2024": {"temp": 36.0, "humidity": 20.0, "wind_speed": 5.0, "wind_dir": 90.0},
    "tobarra_20240802": {"temp": 36.0, "humidity": 18.0, "wind_speed": 4.4, "wind_dir": 270.0},
    "brazatortas_2025": {"temp": 28.0, "humidity": 35.0, "wind_speed": 5.0, "wind_dir": 90.0},
    "retuerta_2025": {"temp": 32.0, "humidity": 25.0, "wind_speed": 5.0, "wind_dir": 90.0},
}


def _write_tif(path: Path, arr: np.ndarray, profile: dict) -> None:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    prof = dict(profile)
    prof.update(count=1, dtype="float32", compress="deflate")
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(np.asarray(arr, dtype=np.float32), 1)


def stage_fire(source_id: str) -> dict:
    spec = get_fire_spec(source_id)
    dem_path = resolve_dem_path(source_id)
    if dem_path is None or not dem_path.is_file():
        return {"ok": False, "source_id": source_id, "error": "dem_missing"}

    import rasterio

    with rasterio.open(dem_path) as src:
        elev = src.read(1).astype(np.float32)
        profile = src.profile
        elev = np.where(np.isfinite(elev), elev, float(np.nanmean(elev)))

    sc = _WX.get(source_id, {"temp": 30.0, "humidity": 25.0, "wind_speed": 5.0, "wind_dir": 90.0})
    elev_m = elev
    elev_mean = float(np.mean(elev_m))
    # ~6.5 C / km lapse relative to mean elevation of window
    d_elev_km = (elev_m - elev_mean) / 1000.0
    temp = float(sc["temp"]) - 6.5 * d_elev_km
    tmin = temp - 5.0
    tmax = temp + 5.0
    # RH slightly higher on cooler higher ground
    humidity = np.clip(float(sc["humidity"]) + 3.0 * d_elev_km, 5.0, 95.0)
    # Wind proxy: slightly stronger on ridges (higher elev)
    wind_speed = np.clip(float(sc["wind_speed"]) + 1.5 * np.maximum(d_elev_km, 0), 0.5, 25.0)
    wind_dir = np.full_like(elev_m, float(sc["wind_dir"]), dtype=np.float32)
    precip = np.zeros_like(elev_m, dtype=np.float32)

    out = weather_dir_for(spec)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "tmin.tif": tmin,
        "tmax.tif": tmax,
        "humidity.tif": humidity,
        "wind_speed.tif": wind_speed,
        "wind_dir.tif": wind_dir,
        "precip.tif": precip,
        "temp.tif": temp,
    }
    written = []
    for name, arr in files.items():
        p = out / name
        _write_tif(p, arr, profile)
        written.append(name)

    meta = {
        "source_id": source_id,
        "method": "dem_lapse_proxy_v1",
        "honesty": (
            "NOT AEMET gridded reanalysis. Spatial variance from DEM elevation "
            "lapse + per-fire scalar anchors. Precip=0 constant (GAP for precip). "
            "wind_dir scalar broadcast. Suitable for engineering signal test only."
        ),
        "dem_path": str(dem_path.as_posix()),
        "weather_dir": str(out.as_posix()),
        "scalars": sc,
        "elev_mean_m": elev_mean,
        "files": written,
        "ok": True,
    }
    (out / "weather_stage_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fire", type=str, default=None)
    p.add_argument("--all", action="store_true")
    args = p.parse_args(argv)
    fires = list_core_source_ids() if args.all else [args.fire or "tobarra_20240802"]
    reports = {}
    for sid in fires:
        if sid not in CORE_SPATIAL_FIRES and args.fire:
            # alias resolve
            try:
                from wildfire_front.fuel.spatial_v1_sources import resolve_source_id

                sid = resolve_source_id(sid)
            except Exception:
                pass
        print(f"=== stage dem-lapse weather {sid} ===", flush=True)
        reports[sid] = stage_fire(sid)
        print(json.dumps(reports[sid], indent=2)[:500], flush=True)
    out = ROOT / "outputs" / "ml_eval" / "dem_lapse_weather_stage_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"Wrote {out}", flush=True)
    ok = all(r.get("ok") for r in reports.values())
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
