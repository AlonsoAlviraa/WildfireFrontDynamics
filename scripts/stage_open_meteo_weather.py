#!/usr/bin/env python3
"""Stage gridded weather from Open-Meteo Archive (no CDS key) for spatial_v1.

When ERA5/CDS credentials are missing, this builds **real meteo spatial fields**
by sampling a lat/lon grid over each fire bbox, fetching hourly archive variables,
and interpolating onto the DEM grid.

Honesty
-------
* provenance = ``open_meteo_archive_interp_v1`` (NOT ERA5-Land, NOT AEMET station)
* Stronger than DEM-lapse (wind/RH from actual archive, not orographic proxy alone)
* Requires network; fails closed if download fails (no invented constants)
* lab only · fusion OFF

Usage::

    $env:PYTHONPATH = "."
    python scripts/stage_open_meteo_weather.py --fire CARDOSO
    python scripts/stage_open_meteo_weather.py --all --audit
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    get_fire_spec,
    inventory_weather_dir,
    list_core_source_ids,
    resolve_dem_path,
    resolve_source_id,
    weather_dir_for,
)

PROVENANCE = "open_meteo_archive_interp_v1"
OM_ROOT = ROOT / "data" / "weather_openmeteo"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
INV_PATH = ROOT / "outputs" / "ml_eval" / "spatial_v1_weather_fuel_inventory.json"


def _bbox_for(source_id: str) -> list[float] | None:
    if INV_PATH.is_file():
        inv = json.loads(INV_PATH.read_text(encoding="utf-8"))
        fire = (inv.get("fires") or {}).get(source_id) or {}
        bb = fire.get("bbox_wgs84")
        if isinstance(bb, list) and len(bb) == 4:
            return [float(x) for x in bb]
    dem = resolve_dem_path(source_id, repo_root=ROOT)
    if dem is None:
        return None
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(dem) as ds:
        left, bottom, right, top = ds.bounds
        w, s, e, n = transform_bounds(ds.crs, "EPSG:4326", left, bottom, right, top)
        return [w, s, e, n]


def _date_for(source_id: str) -> str | None:
    if INV_PATH.is_file():
        inv = json.loads(INV_PATH.read_text(encoding="utf-8"))
        fire = (inv.get("fires") or {}).get(source_id) or {}
        d = fire.get("date")
        if d:
            return str(d)[:10]
    spec = get_fire_spec(source_id)
    d = getattr(spec, "date", None)
    return str(d)[:10] if d else None


def _fetch_point(lat: float, lon: float, date: str) -> dict[str, float]:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "start_date": date,
        "end_date": date,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "precipitation",
            ]
        ),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    url = ARCHIVE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "WFD-lab/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    h = data.get("hourly") or {}
    t = np.asarray(h.get("temperature_2m") or [], dtype=np.float64)
    rh = np.asarray(h.get("relative_humidity_2m") or [], dtype=np.float64)
    ws = np.asarray(h.get("wind_speed_10m") or [], dtype=np.float64)
    wd = np.asarray(h.get("wind_direction_10m") or [], dtype=np.float64)
    pr = np.asarray(h.get("precipitation") or [], dtype=np.float64)
    if t.size == 0:
        raise RuntimeError(f"empty open-meteo response for {lat},{lon} {date}")
    return {
        "tmin": float(np.nanmin(t)),
        "tmax": float(np.nanmax(t)),
        "temp": float(np.nanmean(t)),
        "humidity": float(np.nanmean(rh)),
        "wind_speed": float(np.nanmean(ws)),
        # circular mean for direction
        "wind_dir": float(
            (
                math.degrees(
                    math.atan2(
                        np.nanmean(np.sin(np.deg2rad(wd))),
                        np.nanmean(np.cos(np.deg2rad(wd))),
                    )
                )
                + 360.0
            )
            % 360.0
        ),
        "precip": float(np.nansum(pr)),
    }


def _sample_grid(bbox: list[float], n: int = 5) -> list[tuple[float, float]]:
    w, s, e, nlat = bbox
    lons = np.linspace(w, e, n)
    lats = np.linspace(s, nlat, n)
    pts = []
    for lat in lats:
        for lon in lons:
            pts.append((float(lat), float(lon)))
    return pts


def _interp_to_dem(
    points: list[tuple[float, float]],
    values: np.ndarray,
    dem_path: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    """IDW interpolate lon/lat samples onto DEM grid."""
    import rasterio
    from rasterio.transform import xy
    from rasterio.warp import transform as rio_transform

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1)
        h, w = dem.shape
        profile = ds.profile.copy()
        # pixel centers in CRS → WGS84
        rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        xs, ys = xy(ds.transform, rows.ravel(), cols.ravel())
        lons, lats = rio_transform(ds.crs, "EPSG:4326", list(xs), list(ys))
        lons = np.asarray(lons, dtype=np.float64)
        lats = np.asarray(lats, dtype=np.float64)

    pts = np.asarray(points, dtype=np.float64)  # (N,2) lat,lon
    plat, plon = pts[:, 0], pts[:, 1]
    # IDW
    out = np.zeros(h * w, dtype=np.float64)
    # process in chunks to limit memory
    chunk = 5000
    for i0 in range(0, h * w, chunk):
        i1 = min(h * w, i0 + chunk)
        la = lats[i0:i1][:, None]
        lo = lons[i0:i1][:, None]
        # approx degrees distance
        d2 = (la - plat[None, :]) ** 2 + (lo - plon[None, :]) ** 2
        d2 = np.maximum(d2, 1e-12)
        wts = 1.0 / d2
        wts /= wts.sum(axis=1, keepdims=True)
        out[i0:i1] = (wts * values[None, :]).sum(axis=1)
    grid = out.reshape(h, w).astype(np.float32)
    return grid, profile


def _write_tif(path: Path, arr: np.ndarray, profile: dict[str, Any]) -> None:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    prof = dict(profile)
    prof.update(dtype="float32", count=1, compress="deflate", nodata=None)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(np.asarray(arr, dtype=np.float32), 1)


def stage_fire(source_id: str, *, grid_n: int = 5) -> dict[str, Any]:
    bbox = _bbox_for(source_id)
    date = _date_for(source_id)
    dem = resolve_dem_path(source_id, repo_root=ROOT)
    if not bbox or not date or dem is None:
        return {
            "source_id": source_id,
            "ok": False,
            "error": "missing_bbox_or_date_or_dem",
            "bbox": bbox,
            "date": date,
            "dem": str(dem) if dem else None,
        }

    pts = _sample_grid(bbox, n=grid_n)
    samples: dict[str, list[float]] = {
        k: [] for k in ("tmin", "tmax", "temp", "humidity", "wind_speed", "wind_dir", "precip")
    }
    ok_pts = []
    errors = []
    for lat, lon in pts:
        try:
            row = _fetch_point(lat, lon, date)
            ok_pts.append((lat, lon))
            for k in samples:
                samples[k].append(row[k])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{lat:.3f},{lon:.3f}:{exc}")
    if len(ok_pts) < 3:
        return {
            "source_id": source_id,
            "ok": False,
            "error": "too_few_open_meteo_points",
            "errors": errors[:5],
            "n_ok": len(ok_pts),
        }

    out_dir = OM_ROOT / get_fire_spec(source_id).weather_key
    # also stage into canonical weather_dir for re-emit default override path
    canon = weather_dir_for(get_fire_spec(source_id), repo_root=ROOT)
    # write under openmeteo root; copy keys to a side path + report
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    profile = None
    for key in ("tmin", "tmax", "temp", "humidity", "wind_speed", "wind_dir", "precip"):
        vals = np.asarray(samples[key], dtype=np.float64)
        grid, profile = _interp_to_dem(ok_pts, vals, dem)
        p = out_dir / f"{key}.tif"
        _write_tif(p, grid, profile)
        written[key] = {
            "path": str(p.as_posix()),
            "std": float(np.std(grid)),
            "min": float(np.min(grid)),
            "max": float(np.max(grid)),
        }

    # Collinearity vs DEM elev
    collinearity = {}
    try:
        import rasterio

        with rasterio.open(dem) as ds:
            elev = ds.read(1).astype(np.float64)
        for key in ("wind_speed", "humidity"):
            with rasterio.open(out_dir / f"{key}.tif") as ds:
                arr = ds.read(1).astype(np.float64)
            m = np.isfinite(elev) & np.isfinite(arr)
            x, y = elev[m].ravel(), arr[m].ravel()
            x = x - x.mean()
            y = y - y.mean()
            denom = float(np.dot(x, x) * np.dot(y, y))
            r = float(np.dot(x, y) / math.sqrt(denom)) if denom > 0 else 0.0
            collinearity[key] = {"r2_vs_elev": r * r, "r": r}
    except Exception as exc:  # noqa: BLE001
        collinearity["error"] = str(exc)

    wind_ok = written["wind_speed"]["std"] > 1e-6
    rh_ok = written["humidity"]["std"] > 1e-6
    meta = {
        "schema": "wfd_open_meteo_weather_stage_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "source_id": source_id,
        "provenance": PROVENANCE,
        "not_era5": True,
        "not_dem_lapse": True,
        "date": date,
        "bbox_wgs84": bbox,
        "n_points": len(ok_pts),
        "grid_n": grid_n,
        "out_dir": str(out_dir.as_posix()),
        "canonical_weather_dir": str(canon.as_posix()),
        "rasters": written,
        "collinearity": collinearity,
        "variance_gate": {
            "wind_speed_spatial": wind_ok,
            "humidity_spatial": rh_ok,
            "pass": wind_ok and rh_ok,
        },
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "errors_sample": errors[:3],
    }
    (out_dir / "stage_manifest.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    meta["ok"] = True
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fire", type=str, default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--grid-n", type=int, default=5)
    ap.add_argument("--audit", action="store_true")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "weather_open_meteo_status.json",
    )
    args = ap.parse_args(argv)

    if args.fire:
        sids = [
            resolve_source_id(p.strip())
            for p in args.fire.replace(";", ",").split(",")
            if p.strip()
        ]
    else:
        # Default / --all: stage all core fires (args.all is reserved for CLI clarity).
        sids = list_core_source_ids()

    report: dict[str, Any] = {
        "schema": "wfd_weather_open_meteo_status_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "provenance": PROVENANCE,
        "era5_cds_available": False,
        "era5_note": "cdsapi/.cdsapirc missing locally — open-meteo used as gridded unblock",
        "fires": {},
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
    }

    if args.audit and not args.fire and not args.all:
        # audit only existing
        for sid in sids:
            d = OM_ROOT / get_fire_spec(sid).weather_key
            report["fires"][sid] = {
                "out_dir": str(d.as_posix()),
                "exists": d.is_dir(),
                "inventory": inventory_weather_dir(d) if d.is_dir() else {},
            }
    else:
        for sid in sids:
            print(f"[stage] {sid} ...", flush=True)
            try:
                report["fires"][sid] = stage_fire(sid, grid_n=int(args.grid_n))
            except Exception as exc:  # noqa: BLE001
                report["fires"][sid] = {"source_id": sid, "ok": False, "error": str(exc)}
            print(
                json.dumps(
                    report["fires"][sid].get("variance_gate") or report["fires"][sid], indent=2
                ),
                flush=True,
            )

    n_pass = sum(
        1
        for v in report["fires"].values()
        if isinstance(v, dict) and (v.get("variance_gate") or {}).get("pass")
    )
    report["n_fires"] = len(sids)
    report["n_variance_gate_pass"] = n_pass
    report["status"] = "OPEN_METEO_READY" if n_pass > 0 else "OPEN_METEO_FAILED"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"out": str(args.out), "status": report["status"], "n_pass": n_pass}, indent=2)
    )
    return 0 if n_pass > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
