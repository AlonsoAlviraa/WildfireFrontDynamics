#!/usr/bin/env python3
"""Fill real NDWS covariates (meteo / DEM / veg) onto LATAM+AU packs.

Sources (honest provenance):
  - meteo: Open-Meteo ERA5 archive already under pack/weather/ (mean + spread)
  - DEM: OpenTopoData SRTM90m sampled over pack bbox → elevation GeoTIFF
  - veg: S2 NBR (eo_aligned preferred) scaled to [0,1] vegetation proxy

Does NOT invent ROS, transfer IoU, or claim NDWS-native satellite stack.
Writes pack/covariates/ with PROVENANCE.json.

  python scripts/fill_latam_au_ndws_covariates.py --event-id AU_EMSR500_PERTH
  python scripts/fill_latam_au_ndws_covariates.py --all

Exit codes:
  0 — ok (or partial with documented gaps)
  1 — hard fail (no pack / no label grid)
  2 — usage
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    USER_AGENT,
    WEAK_PACK_SPECS,
    label_records_from_meta,
    pack_dir_for,
    parse_iso_utc,
    pick_pre_s2_path,
    source_pack_ready,
)
from wildfire_front.open_if.modis_ee import (  # noqa: E402
    LST_RASTER_NAME,
    NDVI_RASTER_NAME,
    detect_modis_ndvi_method,
    lst_sidecar_present,
    ndvi_to_veg_proxy,
)

CORE_CHANNELS = ("meteo", "dem", "veg")

COV_SCHEMA = "wfd_latam_au_ndws_covariates_v1"
OPENTOPO = "https://api.opentopodata.org/v1/srtm90m"


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mean_finite(vals: list[Any]) -> float | None:
    xs = [float(v) for v in vals if v is not None and np.isfinite(float(v))]
    if not xs:
        return None
    return float(sum(xs) / len(xs))


def _hourly_at_timestamp(hourly: dict[str, Any], when) -> dict[str, Any] | None:
    times = list(hourly.get("time") or [])
    if not times or when is None:
        return None
    parsed = []
    for t in times:
        dt = parse_iso_utc(str(t) + "Z" if "Z" not in str(t) and "+" not in str(t) else str(t))
        parsed.append(dt)
    best_i = None
    best_abs = None
    for i, dt in enumerate(parsed):
        if dt is None:
            continue
        delta = abs((dt - when).total_seconds())
        if best_abs is None or delta < best_abs:
            best_abs = delta
            best_i = i
    if best_i is None:
        return None

    def _at(key: str) -> float | None:
        vals = list(hourly.get(key) or [])
        if best_i >= len(vals) or vals[best_i] is None:
            return None
        try:
            return float(vals[best_i])
        except (TypeError, ValueError):
            return None

    wind_kmh = _at("wind_speed_10m")
    return {
        "time": times[best_i],
        "delta_seconds": best_abs,
        "temperature_c": _at("temperature_2m"),
        "humidity_pct": _at("relative_humidity_2m"),
        "wind_speed_kmh": wind_kmh,
        "wind_speed_ms": (wind_kmh / 3.6) if wind_kmh is not None else None,
        "wind_dir_deg": _at("wind_direction_10m"),
        "precip_mm": _at("precipitation"),
    }


def load_meteo_summary(pack: Path, *, at=None) -> dict[str, Any]:
    weather = pack / "weather" / "open_meteo_era5_archive.json"
    if not weather.is_file():
        return {"status": "gap", "error": "missing_open_meteo_era5_archive"}
    doc = json.loads(weather.read_text(encoding="utf-8"))
    hourly = doc.get("hourly") or {}
    snap = _hourly_at_timestamp(hourly, at) if at is not None else None
    if snap is not None:
        temp = snap.get("temperature_c")
        rh = snap.get("humidity_pct")
        wind_kmh = snap.get("wind_speed_kmh")
        wdir = snap.get("wind_dir_deg")
        precip = snap.get("precip_mm")
        wind_ms = snap.get("wind_speed_ms")
        sample = "label_timestamp_nearest_hour"
    else:
        temp = _mean_finite(list(hourly.get("temperature_2m") or []))
        rh = _mean_finite(list(hourly.get("relative_humidity_2m") or []))
        wind_kmh = _mean_finite(list(hourly.get("wind_speed_10m") or []))
        wdir = _mean_finite(list(hourly.get("wind_direction_10m") or []))
        precip = _mean_finite(list(hourly.get("precipitation") or []))
        wind_ms = (wind_kmh / 3.6) if wind_kmh is not None else None
        sample = "period_mean_fallback"
    elev = doc.get("elevation_m")
    return {
        "status": "ok",
        "source": "weather/open_meteo_era5_archive.json",
        "elevation_m_point": elev,
        "temperature_c_mean": temp,
        "humidity_pct_mean": rh,
        "wind_speed_ms_mean": wind_ms,
        "wind_speed_kmh_mean": wind_kmh,
        "wind_dir_deg_mean": wdir,
        "precip_mm_mean": precip,
        "n_hourly": len(hourly.get("time") or []),
        "not_cds_era5_land_native": True,
        "meteo_spatial": "constant_point",
        "spatial": "constant_point",
        "sample": sample,
        "sample_at": snap.get("time") if snap else None,
        "gridded": False,
    }


def label_reference(pack: Path) -> tuple[Path, Any, Any, int, int] | None:
    import rasterio

    labels = pack / "labels"
    if not labels.is_dir():
        return None
    tifs = sorted(labels.glob("*.tif"))
    if not tifs:
        return None
    path = tifs[0]
    with rasterio.open(path) as ds:
        return path, ds.transform, ds.crs, ds.height, ds.width


def pack_bbox_wgs84(pack: Path, transform, crs, h: int, w: int) -> list[float]:
    """Return [west, south, east, north] in WGS84."""
    from rasterio.warp import transform_bounds

    west = transform.c
    north = transform.f
    east = west + transform.a * w
    south = north + transform.e * h
    if transform.e > 0:
        south, north = north, south
    if crs and str(crs) not in ("EPSG:4326", "OGC:CRS84"):
        west, south, east, north = transform_bounds(crs, "EPSG:4326", west, south, east, north)
    return [float(west), float(south), float(east), float(north)]


def fetch_srtm_grid(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    n_y: int = 24,
    n_x: int = 24,
    timeout: int = 45,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sample SRTM90 via OpenTopoData; returns (n_y, n_x) elevation grid."""
    lats = np.linspace(north, south, n_y)  # north→south for image rows
    lons = np.linspace(west, east, n_x)
    locations: list[tuple[float, float]] = []
    for lat in lats:
        for lon in lons:
            locations.append((float(lat), float(lon)))

    elev = np.full((n_y * n_x,), np.nan, dtype=np.float32)
    batch = 90  # OpenTopoData free tier batch size
    n_ok = 0
    errors: list[str] = []
    for i0 in range(0, len(locations), batch):
        chunk = locations[i0 : i0 + batch]
        loc_str = "|".join(f"{lat:.5f},{lon:.5f}" for lat, lon in chunk)
        url = f"{OPENTOPO}?{urllib.parse.urlencode({'locations': loc_str})}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            results = payload.get("results") or []
            for j, row in enumerate(results):
                val = row.get("elevation")
                if val is not None:
                    elev[i0 + j] = float(val)
                    n_ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}:{exc}")
        time.sleep(0.35)  # be polite to free API

    grid = elev.reshape(n_y, n_x)
    # fill gaps with median
    if np.isfinite(grid).any():
        med = float(np.nanmedian(grid))
        grid = np.where(np.isfinite(grid), grid, med).astype(np.float32)
    meta = {
        "source": "opentopodata_srtm90m",
        "n_y": n_y,
        "n_x": n_x,
        "n_ok": n_ok,
        "n_requested": len(locations),
        "errors": errors[:5],
        "bbox_wgs84": [west, south, east, north],
    }
    return grid, meta


def write_elevation_tif(
    path: Path,
    elev_ll: np.ndarray,
    *,
    ref_transform,
    ref_crs,
    ref_h: int,
    ref_w: int,
    bbox: list[float],
) -> dict[str, Any]:
    """Resample latlon elev grid to reference label grid."""
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import Resampling, reproject

    path.parent.mkdir(parents=True, exist_ok=True)
    ny, nx = elev_ll.shape
    west, south, east, north = bbox
    src_transform = from_bounds(west, south, east, north, nx, ny)
    src_crs = "EPSG:4326"
    dst = np.zeros((ref_h, ref_w), dtype=np.float32)
    reproject(
        source=elev_ll,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=ref_transform,
        dst_crs=ref_crs,
        resampling=Resampling.bilinear,
    )
    profile = {
        "driver": "GTiff",
        "height": ref_h,
        "width": ref_w,
        "count": 1,
        "dtype": "float32",
        "crs": ref_crs,
        "transform": ref_transform,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(dst, 1)
    return {
        "rel": path.name,
        "shape": [ref_h, ref_w],
        "elev_min": float(np.nanmin(dst)),
        "elev_max": float(np.nanmax(dst)),
        "elev_mean": float(np.nanmean(dst)),
    }


def load_or_align_nbr(
    pack: Path, ref_shape, ref_transform, ref_crs
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Load pre-fire NBR when possible (not last/post scene as vegetation)."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    meta_path = pack / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    pick = pick_pre_s2_path(pack, meta, aligned=True)
    src_path = Path(pick["path"]) if pick and pick.get("path") else None
    extra = {
        "nbr_pick_rule": (pick or {}).get("pair_rule"),
        "nbr_rel": (pick or {}).get("rel"),
    }
    if src_path is None or not src_path.is_file():
        return None, extra
    with rasterio.open(src_path) as src:
        if src.shape == ref_shape and src.crs == ref_crs:
            arr = np.asarray(src.read(1), dtype=np.float32)
        else:
            arr = np.zeros(ref_shape, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=arr,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.bilinear,
            )
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0), extra


def load_or_align_modis_ndvi(
    pack: Path, ref_shape, ref_transform, ref_crs
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Load pack/covariates/modis_ndvi.tif onto the label grid. Does not invent."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    src_path = pack / "covariates" / NDVI_RASTER_NAME
    extra = {
        "modis_rel": f"covariates/{NDVI_RASTER_NAME}",
        "method": detect_modis_ndvi_method(pack),
    }
    if not src_path.is_file():
        extra["error"] = "no_modis_ndvi"
        return None, extra
    with rasterio.open(src_path) as src:
        if src.shape == ref_shape and src.crs == ref_crs:
            arr = np.asarray(src.read(1), dtype=np.float32)
        else:
            arr = np.zeros(ref_shape, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=arr,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.bilinear,
            )
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0), extra


def nbr_to_veg(nbr: np.ndarray) -> np.ndarray:
    """Map NBR [-1,1] to vegetation proxy [0,1] (high NBR → high veg)."""
    return np.clip((nbr + 1.0) * 0.5, 0.0, 1.0).astype(np.float32)


def write_constant_field(path: Path, value: float, *, ref_h: int, ref_w: int, transform, crs) -> None:
    import rasterio

    arr = np.full((ref_h, ref_w), float(value), dtype=np.float32)
    profile = {
        "driver": "GTiff",
        "height": ref_h,
        "width": ref_w,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(arr, 1)


def fill_pack(
    event_id: str,
    pack: Path,
    *,
    dem_ny: int = 24,
    dem_nx: int = 24,
    skip_dem_fetch: bool = False,
    allow_dem_fallback: bool = True,
    all_mode: bool = False,
) -> dict[str, Any]:
    ready, reason = source_pack_ready(pack)
    if not ready:
        return {"event_id": event_id, "ok": False, "error": reason}

    ref = label_reference(pack)
    if ref is None:
        return {"event_id": event_id, "ok": False, "error": "no_label_tif"}
    label_path, transform, crs, h, w = ref

    meta_doc: dict[str, Any] = {}
    meta_p = pack / "meta.json"
    if meta_p.is_file():
        try:
            meta_doc = json.loads(meta_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta_doc = {}
    label_recs = label_records_from_meta(pack, meta_doc) if meta_doc else []
    at = label_recs[-1]["dt"] if label_recs and label_recs[-1].get("dt") is not None else None

    cov = pack / "covariates"
    cov.mkdir(parents=True, exist_ok=True)
    meteo = load_meteo_summary(pack, at=at)
    meteo_by_label: list[dict[str, Any]] = []
    for rec in label_recs:
        snap = load_meteo_summary(pack, at=rec.get("dt"))
        meteo_by_label.append(
            {
                "label": rec.get("name"),
                "delivery_utc": rec.get("delivery_utc"),
                "sample_at": snap.get("sample_at"),
                "temperature_c": snap.get("temperature_c_mean"),
                "humidity_pct": snap.get("humidity_pct_mean"),
                "wind_speed_ms": snap.get("wind_speed_ms_mean"),
                "wind_dir_deg": snap.get("wind_dir_deg_mean"),
                "precip_mm": snap.get("precip_mm_mean"),
            }
        )
    forbid_fallback = bool(all_mode) and not bool(allow_dem_fallback)

    # DEM
    dem_meta: dict[str, Any]
    elev_path = cov / "elevation_m.tif"
    if skip_dem_fetch and elev_path.is_file():
        dem_meta = {"status": "reused", "rel": "covariates/elevation_m.tif"}
    elif skip_dem_fetch:
        if forbid_fallback:
            return {
                "event_id": event_id,
                "ok": False,
                "error": "dem_fallback_forbidden_in_all",
                "dem_status": "forbidden_fallback_constant",
                "hint": "pass --allow-dem-fallback to write a constant DEM under --all",
            }
        # Honest constant fallback when elev missing and network DEM skipped.
        elev0 = float(meteo.get("elevation_m_point") or 200.0)
        write_constant_field(elev_path, elev0, ref_h=h, ref_w=w, transform=transform, crs=crs)
        dem_meta = {
            "status": "fallback_constant",
            "rel": "covariates/elevation_m.tif",
            "elevation_m": elev0,
            "note": "skip_dem_fetch without existing elev — open_meteo_point_or_200m",
        }
    else:
        bbox = pack_bbox_wgs84(pack, transform, crs, h, w)
        try:
            grid, smeta = fetch_srtm_grid(bbox[0], bbox[1], bbox[2], bbox[3], n_y=dem_ny, n_x=dem_nx)
            if not np.isfinite(grid).any():
                if forbid_fallback:
                    return {
                        "event_id": event_id,
                        "ok": False,
                        "error": "dem_fetch_empty_fallback_forbidden",
                        "dem_status": "forbidden_fallback_constant",
                    }
                elev0 = float(meteo.get("elevation_m_point") or 200.0)
                grid = np.full((dem_ny, dem_nx), elev0, dtype=np.float32)
                smeta["fallback"] = "open_meteo_point_elevation"
            wmeta = write_elevation_tif(
                elev_path, grid, ref_transform=transform, ref_crs=crs, ref_h=h, ref_w=w, bbox=bbox
            )
            dem_status = "ok"
            if smeta.get("fallback"):
                dem_status = "fallback_constant" if forbid_fallback else "ok"
            dem_meta = {"status": dem_status, "rel": "covariates/elevation_m.tif", **smeta, **wmeta}
        except Exception as exc:  # noqa: BLE001
            if forbid_fallback:
                return {
                    "event_id": event_id,
                    "ok": False,
                    "error": f"dem_fetch_failed_fallback_forbidden:{type(exc).__name__}:{exc}",
                    "dem_status": "forbidden_fallback_constant",
                }
            elev0 = float(meteo.get("elevation_m_point") or 200.0)
            write_constant_field(elev_path, elev0, ref_h=h, ref_w=w, transform=transform, crs=crs)
            dem_meta = {
                "status": "fallback_constant",
                "rel": "covariates/elevation_m.tif",
                "elevation_m": elev0,
                "error": f"{type(exc).__name__}:{exc}",
            }

    # Meteo constant fields on label grid
    fields_written: list[str] = []
    if meteo.get("status") == "ok":
        mapping = {
            "temperature_c.tif": meteo.get("temperature_c_mean"),
            "humidity_pct.tif": meteo.get("humidity_pct_mean"),
            "wind_speed_ms.tif": meteo.get("wind_speed_ms_mean"),
            "wind_dir_deg.tif": meteo.get("wind_dir_deg_mean"),
            "precip_mm.tif": meteo.get("precip_mm_mean"),
        }
        for name, val in mapping.items():
            if val is None:
                continue
            write_constant_field(cov / name, float(val), ref_h=h, ref_w=w, transform=transform, crs=crs)
            fields_written.append(f"covariates/{name}")

    # Vegetation from PRE-fire NBR (not post-fire scar as fuel)
    nbr, nbr_pick = load_or_align_nbr(pack, (h, w), transform, crs)
    veg_meta: dict[str, Any]
    if nbr is not None:
        veg = nbr_to_veg(nbr)
        import rasterio

        veg_path = cov / "vegetation_proxy.tif"
        profile = {
            "driver": "GTiff",
            "height": h,
            "width": w,
            "count": 1,
            "dtype": "float32",
            "crs": crs,
            "transform": transform,
            "compress": "deflate",
        }
        with rasterio.open(veg_path, "w", **profile) as ds:
            ds.write(veg, 1)
        nbr_path = cov / "s2_nbr_aligned.tif"
        with rasterio.open(nbr_path, "w", **profile) as ds:
            ds.write(nbr, 1)
        veg_meta = {
            "status": "ok",
            "rel": "covariates/vegetation_proxy.tif",
            "nbr_rel": "covariates/s2_nbr_aligned.tif",
            "mapping": "veg = clip((nbr+1)/2, 0, 1) from pre-fire NBR",
            "veg_mean": float(veg.mean()),
            "nbr_pick_rule": nbr_pick.get("nbr_pick_rule"),
            "nbr_source_rel": nbr_pick.get("nbr_rel"),
            "source": "s2_nbr",
        }
    else:
        ndvi, ndvi_meta = load_or_align_modis_ndvi(pack, (h, w), transform, crs)
        if ndvi is not None:
            veg = ndvi_to_veg_proxy(ndvi)
            import rasterio

            veg_path = cov / "vegetation_proxy.tif"
            profile = {
                "driver": "GTiff",
                "height": h,
                "width": w,
                "count": 1,
                "dtype": "float32",
                "crs": crs,
                "transform": transform,
                "compress": "deflate",
            }
            with rasterio.open(veg_path, "w", **profile) as ds:
                ds.write(veg, 1)
            method = ndvi_meta.get("method") or "modis_monthly"
            if method not in {"modis_harmonic", "modis_monthly"}:
                method = "modis_monthly"
            veg_meta = {
                "status": method,
                "rel": "covariates/vegetation_proxy.tif",
                "modis_rel": "covariates/modis_ndvi.tif",
                "mapping": "veg = clip(ndvi, 0, 1) after MOD13Q1 0.0001 scale if DN",
                "veg_mean": float(veg.mean()),
                "source": method,
                "method": method,
            }
        else:
            veg_meta = {"status": "gap", "error": "no_s2_nbr", **nbr_pick}

    lst_ready = lst_sidecar_present(pack)
    if (cov / LST_RASTER_NAME).is_file() and (cov / "temperature_c.tif").is_file():
        # LST is a sidecar only — never copy into the Open-Meteo t2m slot.
        pass

    prov = {
        "schema": COV_SCHEMA,
        "as_of_utc": utc_now(),
        "event_id": event_id,
        "label_ref": str(label_path.relative_to(pack)).replace("\\", "/"),
        "shape": [h, w],
        "crs": str(crs),
        "meteo": meteo,
        "meteo_spatial": meteo.get("meteo_spatial") or "constant_point",
        "meteo_by_label": meteo_by_label,
        "dem": dem_meta,
        "vegetation": veg_meta,
        "meteo_fields": fields_written,
        "channels_ready": {
            "meteo": meteo.get("status") == "ok" and bool(fields_written),
            "dem": dem_meta.get("status") in {"ok", "fallback_constant", "reused"},
            "veg": veg_meta.get("status") in {"ok", "modis_harmonic", "modis_monthly"},
            "lst": bool(lst_ready),
        },
        "not_claims": [
            "not NDWS-native multi-band stack",
            "not CDS ERA5-Land native",
            "not transfer IoU",
            "meteo_spatial=constant_point (Open-Meteo archive is a point, not a grid)",
            (
                "veg is MODIS NDVI fallback (not S2 NBR) when S2 is missing"
                if veg_meta.get("status") in {"modis_harmonic", "modis_monthly"}
                else "veg is S2 NBR proxy not NDVI training covariate"
            ),
            "LST sidecar is not Open-Meteo t2m / not written to temperature_c.tif",
        ],
    }
    if (cov / NDVI_RASTER_NAME).is_file():
        prov["channels_ready"]["harmonic_ndvi"] = True
    # lst / harmonic_ndvi are optional sidecars — do not fail the sealed meteo/dem/veg path.
    all_ready = all(bool(prov["channels_ready"].get(k)) for k in CORE_CHANNELS)
    prov["ready_for_real_proxy_ndws"] = all_ready
    (cov / "PROVENANCE.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")

    # patch meta.json
    meta_p = pack / "meta.json"
    if meta_p.is_file():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            meta["ndws_covariates"] = {
                "schema": COV_SCHEMA,
                "as_of_utc": utc_now(),
                "ready_for_real_proxy_ndws": all_ready,
                "rel": "covariates/PROVENANCE.json",
            }
            meta_p.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "event_id": event_id,
        "ok": True,
        "ready_for_real_proxy_ndws": all_ready,
        "channels_ready": prov["channels_ready"],
        "dem_status": dem_meta.get("status"),
        "veg_status": veg_meta.get("status"),
        "meteo_status": meteo.get("status"),
        "meteo_spatial": meteo.get("meteo_spatial") or "constant_point",
        "provenance": "covariates/PROVENANCE.json",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fill real NDWS covariates on LATAM/AU packs")
    ap.add_argument("--event-id", action="append", dest="event_ids", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--include-weak", action="store_true", help="Also fill MapBiomas/NAFI if a label grid exists")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--skip-dem-fetch", action="store_true")
    ap.add_argument(
        "--allow-dem-fallback",
        action="store_true",
        help="Permit fallback_constant DEM under --all (otherwise fail the pack)",
    )
    ap.add_argument("--dem-ny", type=int, default=24)
    ap.add_argument("--dem-nx", type=int, default=24)
    ap.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au" / "inventories" / "ndws_covariates_report.json",
    )
    args = ap.parse_args(argv)

    catalog = dict(EMSR_PACK_SPECS)
    if args.include_weak:
        catalog.update(WEAK_PACK_SPECS)
    if args.all:
        ids = list(catalog.keys())
    elif args.event_ids:
        ids = list(args.event_ids)
    else:
        ids = ["AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"]

    rows: list[dict[str, Any]] = []
    any_fail = False
    for eid in ids:
        if eid not in catalog:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        pack = pack_dir_for(Path(args.data_root), catalog[eid])
        print(f"== {eid} ==", flush=True)
        skip_reason = None
        if args.all:
            ready, reason = source_pack_ready(pack)
            weather = pack / "weather" / "open_meteo_era5_archive.json"
            elev = pack / "covariates" / "elevation_m.tif"
            if not ready:
                skip_reason = reason
            elif not weather.is_file():
                skip_reason = "missing_open_meteo_era5_archive"
            elif args.skip_dem_fetch and not elev.is_file():
                skip_reason = "missing_dem_no_fetch"
        if skip_reason:
            row = {
                "event_id": eid,
                "ok": True,
                "skipped": True,
                "error": skip_reason,
                "ready_for_real_proxy_ndws": False,
            }
            rows.append(row)
            print(f"  SKIP {skip_reason} (no invented covariates)", flush=True)
            continue
        row = fill_pack(
            eid,
            pack,
            dem_ny=int(args.dem_ny),
            dem_nx=int(args.dem_nx),
            skip_dem_fetch=bool(args.skip_dem_fetch),
            allow_dem_fallback=bool(args.allow_dem_fallback) or not bool(args.all),
            all_mode=bool(args.all),
        )
        rows.append(row)
        if not row.get("ok"):
            any_fail = True
            print(f"  FAIL {row.get('error')}", flush=True)
        else:
            print(
                f"  ready={row.get('ready_for_real_proxy_ndws')} "
                f"dem={row.get('dem_status')} veg={row.get('veg_status')} "
                f"meteo={row.get('meteo_status')}",
                flush=True,
            )

    report = {
        "schema": COV_SCHEMA,
        "as_of_utc": utc_now(),
        "n": len(rows),
        "n_ok": sum(1 for r in rows if r.get("ok")),
        "n_ready": sum(1 for r in rows if r.get("ready_for_real_proxy_ndws")),
        "packs": rows,
        "not_claims": [
            "not transfer IoU",
            "not NDWS-native",
            "meteo is period-mean constant field",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.report).replace("\\", "/"), **{k: report[k] for k in ("n", "n_ok", "n_ready")}}, indent=2))
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
