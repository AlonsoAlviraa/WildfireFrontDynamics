#!/usr/bin/env python3
"""Stage ERA5-Land hourly weather for spatial_v1 fires (V3 scaffold).

Honesty
-------
* Does **not** invent constants when download fails — exits blocked.
* DEM-lapse remains fallback via ``scripts/stage_dem_lapse_weather.py``.
* lab only · not field fusion · not AEMET station broadcast.

Usage
-----
    # inventory only (no CDS call)
    python scripts/stage_era5_land_weather.py --inventory-only

    # attempt download for one fire (requires cdsapi + ~/.cdsapirc)
    python scripts/stage_era5_land_weather.py --fire CARDOSO --download

    # variance + collinearity audit on existing staged tifs
    python scripts/stage_era5_land_weather.py --audit
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

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

ERA5_ROOT = ROOT / "data" / "weather_era5"
CORE_KEYS = ("tmin", "tmax", "humidity", "wind_speed", "wind_dir", "precip")


def era5_dir_for(source_id: str) -> Path:
    spec = get_fire_spec(source_id)
    return ERA5_ROOT / spec.weather_key


def _read_tif_stats(path: Path) -> dict:
    try:
        import rasterio

        with rasterio.open(path) as ds:
            arr = ds.read(1).astype(np.float64)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return {"exists": True, "std": 0.0, "min": None, "max": None, "error": "empty"}
        return {
            "exists": True,
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"exists": path.is_file(), "std": None, "min": None, "max": None, "error": str(exc)}


def audit_fire(source_id: str) -> dict:
    d = era5_dir_for(source_id)
    dem = resolve_dem_path(source_id, repo_root=ROOT)
    inv = (
        inventory_weather_dir(d)
        if d.is_dir()
        else {
            "weather_spatial_available": False,
            "constant_keys": list(CORE_KEYS),
            "gaps": ["era5_dir_missing"],
        }
    )
    rasters = {}
    for name in CORE_KEYS:
        p = d / f"{name}.tif"
        rasters[name] = _read_tif_stats(p) if p.is_file() else {"exists": False}

    collinearity = {}
    if dem is not None and dem.is_file():
        try:
            import rasterio
            from rasterio.warp import Resampling, reproject

            with rasterio.open(dem) as ds_dem:
                elev = ds_dem.read(1).astype(np.float64)
                dem_tf, dem_crs = ds_dem.transform, ds_dem.crs
                h, w = elev.shape
            for key in ("wind_speed", "humidity"):
                p = d / f"{key}.tif"
                if not p.is_file():
                    collinearity[key] = {"r2_vs_elev": None, "reason": "missing"}
                    continue
                with rasterio.open(p) as ds:
                    dest = np.zeros((h, w), dtype=np.float64)
                    reproject(
                        source=ds.read(1),
                        destination=dest,
                        src_transform=ds.transform,
                        src_crs=ds.crs,
                        dst_transform=dem_tf,
                        dst_crs=dem_crs,
                        resampling=Resampling.bilinear,
                    )
                m = np.isfinite(elev) & np.isfinite(dest)
                if m.sum() < 20:
                    collinearity[key] = {"r2_vs_elev": None, "reason": "too_few_pixels"}
                    continue
                x, y = elev[m].ravel(), dest[m].ravel()
                # R^2 linear
                x = x - x.mean()
                y = y - y.mean()
                denom = float(np.dot(x, x) * np.dot(y, y))
                r = float(np.dot(x, y) / math.sqrt(denom)) if denom > 0 else 0.0
                collinearity[key] = {"r2_vs_elev": r * r, "r": r}
        except Exception as exc:  # noqa: BLE001
            collinearity["error"] = str(exc)

    wind_ok = bool(rasters.get("wind_speed", {}).get("std") or 0) > 1e-6
    rh_ok = bool(rasters.get("humidity", {}).get("std") or 0) > 1e-6
    return {
        "source_id": source_id,
        "era5_dir": str(d.as_posix()),
        "inventory": inv,
        "rasters": rasters,
        "collinearity": collinearity,
        "variance_gate": {
            "wind_speed_spatial": wind_ok,
            "humidity_spatial": rh_ok,
            "pass": wind_ok and rh_ok,
        },
        "dem_lapse_fallback": str(
            weather_dir_for(get_fire_spec(source_id), repo_root=ROOT).as_posix()
        ),
    }


def _bbox_from_dem(source_id: str, pad_deg: float = 0.25) -> list[float] | None:
    """Return [W, S, E, N] WGS84 padded bbox from DEM (or dem_manifest)."""
    from wildfire_front.fuel.spatial_v1_sources import load_bbox_wgs84

    bb = load_bbox_wgs84(source_id, repo_root=ROOT)
    if bb and len(bb) == 4:
        w, s, e, n = bb
        return [w - pad_deg, s - pad_deg, e + pad_deg, n + pad_deg]
    dem = resolve_dem_path(source_id, repo_root=ROOT)
    if dem is None:
        return None
    try:
        import rasterio
        from rasterio.warp import transform_bounds

        with rasterio.open(dem) as ds:
            w, s, e, n = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
        return [w - pad_deg, s - pad_deg, e + pad_deg, n + pad_deg]
    except Exception:  # noqa: BLE001
        return None


def _rh_from_t_td(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """Magnus approximation RH% from T and dewpoint °C."""

    # es(T) ≈ 6.112 * exp(17.67*T/(T+243.5))
    def es(t: np.ndarray) -> np.ndarray:
        return 6.112 * np.exp((17.67 * t) / (t + 243.5))

    rh = 100.0 * es(td_c) / np.maximum(es(t_c), 1e-6)
    return np.clip(rh, 0.0, 100.0).astype(np.float32)


def _write_tif_like_dem(path: Path, arr: np.ndarray, dem_path: Path) -> None:
    import rasterio
    from scipy.ndimage import zoom

    with rasterio.open(dem_path) as dem:
        profile = dem.profile.copy()
        profile.update(dtype="float32", count=1, compress="deflate", nodata=None)
        arr = np.asarray(arr, dtype=np.float32)
        if arr.shape != (dem.height, dem.width):
            zy = dem.height / max(arr.shape[0], 1)
            zx = dem.width / max(arr.shape[1], 1)
            arr = zoom(arr, (zy, zx), order=1).astype(np.float32)
            # exact crop/pad
            arr = arr[: dem.height, : dem.width]
            if arr.shape[0] < dem.height or arr.shape[1] < dem.width:
                pad = np.full((dem.height, dem.width), float(np.nanmedian(arr)), dtype=np.float32)
                pad[: arr.shape[0], : arr.shape[1]] = arr
                arr = pad
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr, 1)


def _netcdf_daily_fields(nc_path: Path) -> dict[str, np.ndarray]:
    """Load ERA5-Land NetCDF → daily grids (native ERA5 grid)."""
    import xarray as xr

    ds = xr.open_dataset(nc_path)

    # variable name variants across CDS versions
    def _pick(*names: str):
        for n in names:
            if n in ds:
                return ds[n]
        # case-insensitive
        lower = {k.lower(): k for k in ds.data_vars}
        for n in names:
            if n.lower() in lower:
                return ds[lower[n.lower()]]
        raise KeyError(f"none of {names} in {list(ds.data_vars)}")

    t2m = _pick("t2m", "2m_temperature")
    d2m = _pick("d2m", "2m_dewpoint_temperature")
    u10 = _pick("u10", "10m_u_component_of_wind")
    v10 = _pick("v10", "10m_v_component_of_wind")
    try:
        tp = _pick("tp", "total_precipitation")
    except KeyError:
        tp = None

    # CDS NetCDF may use time or valid_time
    tdim = None
    for cand in ("time", "valid_time"):
        if cand in t2m.dims:
            tdim = cand
            break
    if tdim is None:
        raise KeyError(f"no time dim in {t2m.dims}")

    # Kelvin → °C
    t_c = (t2m - 273.15).astype("float64")
    td_c = (d2m - 273.15).astype("float64")
    # reduce over time
    tmin = t_c.min(dim=tdim).values.astype(np.float32)
    tmax = t_c.max(dim=tdim).values.astype(np.float32)
    temp = t_c.mean(dim=tdim).values.astype(np.float32)
    humidity = _rh_from_t_td(t_c.mean(dim=tdim).values, td_c.mean(dim=tdim).values)
    u = u10.mean(dim=tdim).values.astype(np.float64)
    v = v10.mean(dim=tdim).values.astype(np.float64)
    wind_speed = np.sqrt(u * u + v * v).astype(np.float32)
    wind_dir = (np.degrees(np.arctan2(u, v)) + 360.0) % 360.0
    wind_dir = wind_dir.astype(np.float32)
    if tp is not None:
        # ERA5-Land tp is m; convert to mm
        precip = (tp.sum(dim=tdim).values * 1000.0).astype(np.float32)
    else:
        precip = np.zeros_like(temp, dtype=np.float32)

    # lat/lon coords for reproject
    lats = None
    lons = None
    for lat_n in ("latitude", "lat"):
        if lat_n in ds.coords:
            lats = ds.coords[lat_n].values
            break
    for lon_n in ("longitude", "lon"):
        if lon_n in ds.coords:
            lons = ds.coords[lon_n].values
            break
    ds.close()
    return {
        "tmin": tmin,
        "tmax": tmax,
        "temp": temp,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "precip": precip,
        "lats": lats,
        "lons": lons,
    }


def _regrid_to_dem(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    dem_path: Path,
) -> np.ndarray:
    """Regrid ERA5 lat/lon field onto DEM grid (IDW; handles sparse 1×N grids)."""
    import rasterio
    from rasterio.transform import xy
    from rasterio.warp import transform as rio_transform

    lat = np.asarray(lats, dtype=np.float64).ravel()
    lon = np.asarray(lons, dtype=np.float64).ravel()
    data = np.asarray(field, dtype=np.float64)
    data = np.squeeze(data)
    # Build sample points (lat, lon, value)
    if data.ndim == 0:
        samples_lat = lat if lat.size else np.array([0.0])
        samples_lon = lon if lon.size else np.array([0.0])
        samples_val = np.full(max(samples_lat.size, samples_lon.size), float(data))
        if samples_lat.size == 1 and samples_lon.size > 1:
            samples_lat = np.full(samples_lon.size, float(samples_lat[0]))
        if samples_lon.size == 1 and samples_lat.size > 1:
            samples_lon = np.full(samples_lat.size, float(samples_lon[0]))
    elif data.ndim == 1:
        # 1D along lon or lat
        if data.size == lon.size:
            samples_lon = lon
            samples_lat = np.full(lon.size, float(lat[0]) if lat.size else 0.0)
            samples_val = data
        elif data.size == lat.size:
            samples_lat = lat
            samples_lon = np.full(lat.size, float(lon[0]) if lon.size else 0.0)
            samples_val = data
        else:
            samples_lat = np.repeat(lat, lon.size) if lat.size else np.zeros(data.size)
            samples_lon = np.tile(lon, lat.size) if lon.size else np.zeros(data.size)
            samples_val = data
    else:
        # 2D (nlat, nlon)
        if lat.size != data.shape[0] and lat.size == data.shape[1]:
            data = data.T
        if lat[0] > lat[-1]:
            lat = lat[::-1]
            data = data[::-1, :]
        if lon[0] > lon[-1]:
            lon = lon[::-1]
            data = data[:, ::-1]
        lon_g, lat_g = np.meshgrid(lon, lat)
        samples_lat = lat_g.ravel()
        samples_lon = lon_g.ravel()
        samples_val = data.ravel()

    # drop non-finite samples
    m = np.isfinite(samples_val) & np.isfinite(samples_lat) & np.isfinite(samples_lon)
    samples_lat, samples_lon, samples_val = samples_lat[m], samples_lon[m], samples_val[m]
    if samples_val.size == 0:
        raise RuntimeError("no finite ERA5 samples to regrid")

    with rasterio.open(dem_path) as ds:
        h, w = ds.height, ds.width
        rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        xs, ys = xy(ds.transform, rows.ravel(), cols.ravel())
        lons_p, lats_p = rio_transform(ds.crs, "EPSG:4326", list(xs), list(ys))
        la = np.asarray(lats_p, dtype=np.float64)
        lo = np.asarray(lons_p, dtype=np.float64)
        # IDW in degree space
        out = np.zeros(h * w, dtype=np.float64)
        chunk = 8000
        plat, plon, pval = samples_lat, samples_lon, samples_val
        for i0 in range(0, h * w, chunk):
            i1 = min(h * w, i0 + chunk)
            d2 = (la[i0:i1, None] - plat[None, :]) ** 2 + (lo[i0:i1, None] - plon[None, :]) ** 2
            d2 = np.maximum(d2, 1e-14)
            wts = 1.0 / d2
            wts /= wts.sum(axis=1, keepdims=True)
            out[i0:i1] = (wts * pval[None, :]).sum(axis=1)
        return out.reshape(h, w).astype(np.float32)


def try_download(source_id: str, *, execute: bool = False) -> dict:
    """CDS ERA5-Land download. Fails closed if cdsapi/licence/credentials missing.

    When ``execute=True``, retrieves NetCDF for the fire day and writes GeoTIFFs
    on the DEM grid under ``data/weather_era5/<weather_key>/``.
    """
    try:
        import cdsapi  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "blocked": True,
            "reason": "cdsapi_not_installed",
            "hint": "pip install cdsapi; configure ~/.cdsapirc; accept ERA5-Land licence on CDS",
            "source_id": source_id,
        }

    spec = get_fire_spec(source_id)
    out = era5_dir_for(source_id)
    out.mkdir(parents=True, exist_ok=True)
    date = str(getattr(spec, "date", None) or "")[:10]
    bbox = _bbox_from_dem(source_id)
    dem = resolve_dem_path(source_id, repo_root=ROOT)
    template = {
        "dataset": "reanalysis-era5-land",
        "source_id": source_id,
        "weather_key": spec.weather_key,
        "date": date,
        "bbox_wgs84": bbox,
        "variables": [
            "2m_temperature",
            "2m_dewpoint_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "total_precipitation",
        ],
        "out_dir": str(out.as_posix()),
    }
    tpl_path = out / "era5_request_template.json"
    tpl_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    try:
        client = cdsapi.Client(progress=True)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "blocked": True,
            "reason": "cds_client_init_failed",
            "error": str(exc),
            "template": str(tpl_path.as_posix()),
            "source_id": source_id,
        }

    if not execute:
        return {
            "ok": False,
            "blocked": True,
            "reason": "download_not_auto_executed",
            "honesty": "Pass execute=True / --download --execute to pull CDS data.",
            "template": str(tpl_path.as_posix()),
            "source_id": source_id,
            "cdsapi": True,
        }

    if not date or bbox is None or dem is None:
        return {
            "ok": False,
            "blocked": True,
            "reason": "missing_date_bbox_or_dem",
            "date": date,
            "bbox": bbox,
            "dem": str(dem) if dem else None,
            "source_id": source_id,
        }

    year, month, day = date.split("-")
    w, s, e, n = bbox
    # CDS area = [North, West, South, East]
    area = [float(n), float(w), float(s), float(e)]
    nc_path = out / f"era5_land_{date}.nc"
    request = {
        "variable": template["variables"],
        "year": year,
        "month": month,
        "day": day,
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    try:
        client.retrieve("reanalysis-era5-land", request, str(nc_path))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        reason = "cds_retrieve_failed"
        if "licence" in msg.lower() or "403" in msg:
            reason = "licence_not_accepted"
        return {
            "ok": False,
            "blocked": True,
            "reason": reason,
            "error": msg[:800],
            "licence_url": (
                "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land"
                "?tab=download#manage-licences"
            ),
            "request": request,
            "template": str(tpl_path.as_posix()),
            "source_id": source_id,
        }

    try:
        fields = _netcdf_daily_fields(nc_path)
        lats, lons = fields.pop("lats"), fields.pop("lons")
        if lats is None or lons is None:
            raise RuntimeError("NetCDF missing lat/lon coordinates")
        written = {}
        for key in ("tmin", "tmax", "temp", "humidity", "wind_speed", "wind_dir", "precip"):
            grid = _regrid_to_dem(fields[key], lats, lons, dem)
            dest = out / f"{key}.tif"
            _write_tif_like_dem(dest, grid, dem)
            written[key] = str(dest.as_posix())
        # also stage into canonical data/weather/<key>/ for spatial re-emit discovery
        import shutil

        from wildfire_front.fuel.spatial_v1_sources import weather_dir_for

        canon = weather_dir_for(spec, repo_root=ROOT)
        canon.mkdir(parents=True, exist_ok=True)
        for key, path in written.items():
            shutil.copy2(path, canon / f"{key}.tif")
        prov = {
            "schema": "wfd_weather_provenance_v1",
            "created_utc": datetime.now(UTC).isoformat(),
            "source_id": source_id,
            "provenance": "era5_land_cds_v1",
            "not_era5": False,
            "not_dem_lapse": True,
            "date": date,
            "bbox_wgs84": bbox,
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
        }
        (out / "PROVENANCE.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        (canon / "PROVENANCE.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        audit = audit_fire(source_id)
        return {
            "ok": True,
            "blocked": False,
            "source_id": source_id,
            "nc_path": str(nc_path.as_posix()),
            "written": written,
            "canonical_weather_dir": str(canon.as_posix()),
            "audit": audit,
            "variance_gate": audit.get("variance_gate"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "blocked": True,
            "reason": "postprocess_failed",
            "error": str(exc)[:800],
            "nc_path": str(nc_path.as_posix()) if nc_path.is_file() else None,
            "source_id": source_id,
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fire", type=str, default=None, help="source_id or alias")
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "weather_era5_status.json",
    )
    args = ap.parse_args(argv)

    sids = [resolve_source_id(args.fire)] if args.fire else list_core_source_ids()

    report: dict = {
        "schema": "wfd_weather_era5_status_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "work_class": "weather_gridded_v1",
        "source": "ERA5-Land",
        "ml_product_go": False,
        "field_ops_allow_ml_live_in_fusion": False,
        "dem_lapse_is_not_reanalysis": True,
        "fires": {},
    }

    if args.download:
        for sid in sids:
            report["fires"][sid] = try_download(sid, execute=True)
    elif args.audit or args.inventory_only:
        for sid in sids:
            report["fires"][sid] = audit_fire(sid)
    else:
        # default: inventory + audit + download template (no execute)
        for sid in sids:
            row = audit_fire(sid)
            row["download_probe"] = try_download(sid, execute=False)
            report["fires"][sid] = row

    n_pass = sum(
        1
        for v in report["fires"].values()
        if isinstance(v, dict)
        and (
            (v.get("variance_gate") or {}).get("pass")
            or ((v.get("audit") or {}).get("variance_gate") or {}).get("pass")
        )
    )
    n_ok = sum(1 for v in report["fires"].values() if isinstance(v, dict) and v.get("ok"))
    report["n_fires"] = len(sids)
    report["n_variance_gate_pass"] = n_pass
    report["n_download_ok"] = n_ok
    if n_pass > 0 and n_pass == len(sids):
        report["status"] = "ERA5_READY"
    elif n_ok > 0:
        report["status"] = "ERA5_PARTIAL"
    else:
        # surface licence block if any
        lic = any(
            isinstance(v, dict) and v.get("reason") == "licence_not_accepted"
            for v in report["fires"].values()
        )
        report["status"] = "BLOCKED_LICENCE" if lic else "ERA5_PENDING_DOWNLOAD"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps({"out": str(args.out), "status": report["status"], "n_pass": n_pass}, indent=2)
    )
    return 0 if report["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
