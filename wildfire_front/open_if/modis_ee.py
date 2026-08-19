"""MODIS LST / harmonic NDVI recipes ported from FlameForecast notebooks.

Pure functions first. Earth Engine fetch lives behind optional helpers and
is not imported at module load. Does not write official MET artifacts, does
not invent ROS, and does not replace Open-Meteo t2m or S2 NBR by default.

Source algorithms:
  - LST: MODIS/061/MOD11A1, LST_C = DN * 0.02 - 273.15, annual sine
  - NDVI: monthly composites + 3-harmonic Fourier (constant, t, cos, sin)
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np

LST_COLLECTION = "MODIS/061/MOD11A1"
LST_BAND = "LST_Day_1km"
LST_QC_BAND = "QC_Day"
LST_SCALE_M = 1000.0
LST_DN_SCALE = 0.02
LST_DN_OFFSET_K = 273.15

# FlameForecast C6 collection is superseded; keep the name for provenance.
NDVI_COLLECTION_FLAMEFORECAST = "MODIS/MOD09GA_006_NDVI"
NDVI_COLLECTION = "MODIS/061/MOD13Q1"
NDVI_BAND = "NDVI"
NDVI_SCALE_M = 250.0
NDVI_DN_SCALE = 0.0001
N_HARMONICS = 3
EE_PROJECT_ENV = "WFD_EE_PROJECT"
EE_UNAVAILABLE = "ee_unavailable"
FORBIDDEN_EE_PROJECTS = frozenset({"ee-alangtz51"})
LST_POINT_REL = "weather/modis_lst_point.json"
LST_RASTER_REL = "covariates/lst_day_c.tif"
NDVI_RASTER_REL = "covariates/modis_ndvi.tif"
LST_RASTER_NAME = "lst_day_c.tif"
NDVI_RASTER_NAME = "modis_ndvi.tif"
EE_DOWNLOAD_HOSTS = frozenset(
    {
        "earthengine.googleapis.com",
        "earthengine.google.com",
        "code.earthengine.google.com",
    }
)

# Notebook p0 tau: 365 d in unix milliseconds.
ANNUAL_TAU_MS = 365 * 24 * 3600 * 1000
MIN_SINE_SAMPLES = 30
LST_POINT_SCHEMA = "wfd_modis_lst_point_v1"

# MOD11A1 QC_Day bits 0-1 (mandatory QA).
QC_MANDATORY_GOOD = 0  # 00 produced, good quality
QC_MANDATORY_OTHER = 1  # 01 produced, other quality
QC_MANDATORY_CLOUD = 2  # 10 not produced (cloud)
QC_MANDATORY_OTHER_FAIL = 3  # 11 not produced (other)


def lst_dn_to_celsius(dn: float | np.ndarray) -> float | np.ndarray:
    """Convert MOD11A1 LST_Day_1km digital number to °C."""
    arr = np.asarray(dn, dtype=np.float64)
    out = arr * LST_DN_SCALE - LST_DN_OFFSET_K
    if np.ndim(dn) == 0:
        return float(out)
    return out.astype(np.float32)


def qc_day_mandatory(qc: int | float) -> int | None:
    """Return bits 0-1 of QC_Day, or None if qc is missing."""
    if qc is None:
        return None
    try:
        value = int(qc)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return int(value & 0b11)


def qc_day_ok(qc: int | float | None, *, allow_other_quality: bool = False) -> bool:
    """True when MOD11A1 produced an LST pixel.

    Default accepts only mandatory QA ``00`` (good). ``allow_other_quality``
    also keeps ``01``. Cloud / not-produced bits never pass.
    """
    bits = qc_day_mandatory(qc) if qc is not None else None
    if bits is None:
        return False
    if bits == QC_MANDATORY_GOOD:
        return True
    return bool(allow_other_quality and bits == QC_MANDATORY_OTHER)


def annual_sine(times_ms: np.ndarray, lst0: float, delta_lst: float, phi: float) -> np.ndarray:
    """Notebook sine with tau pinned to one year (ms)."""
    t = np.asarray(times_ms, dtype=np.float64)
    return lst0 + (delta_lst / 2.0) * np.sin(2.0 * np.pi * t / ANNUAL_TAU_MS + phi)


def fit_annual_sine(
    times_ms: np.ndarray,
    lst_c: np.ndarray,
    *,
    min_samples: int = MIN_SINE_SAMPLES,
) -> dict[str, Any] | None:
    """Fit lst0 + (Δ/2) sin(2π t/τ + φ) with τ fixed at 365 d.

    Linearised as lst0 + A sin(ωt) + B cos(ωt). Returns None if too few
    finite samples (does not invent a climatology).
    """
    t = np.asarray(times_ms, dtype=np.float64).reshape(-1)
    y = np.asarray(lst_c, dtype=np.float64).reshape(-1)
    if t.size != y.size:
        return None
    ok = np.isfinite(t) & np.isfinite(y)
    t = t[ok]
    y = y[ok]
    if t.size < int(min_samples):
        return None
    omega = 2.0 * np.pi / float(ANNUAL_TAU_MS)
    sin_t = np.sin(omega * t)
    cos_t = np.cos(omega * t)
    design = np.column_stack([np.ones(t.size), sin_t, cos_t])
    try:
        coef, *_rest = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    lst0, amp_sin, amp_cos = (float(coef[0]), float(coef[1]), float(coef[2]))
    # (Δ/2) sin(ωt + φ) = (Δ/2)(sin ωt cos φ + cos ωt sin φ)
    half_delta = math.hypot(amp_sin, amp_cos)
    phi = math.atan2(amp_cos, amp_sin)
    fitted = lst0 + amp_sin * sin_t + amp_cos * cos_t
    resid = y - fitted
    return {
        "lst0": lst0,
        "delta_lst": 2.0 * half_delta,
        "tau_ms": float(ANNUAL_TAU_MS),
        "phi": phi,
        "n": int(t.size),
        "rmse_c": float(np.sqrt(np.mean(resid * resid))),
        "tau_pinned_annual": True,
    }


def sine_anomaly_c(
    time_ms: float,
    lst_c: float,
    fit: dict[str, Any],
) -> float | None:
    """Observed LST minus fitted annual sine (°C)."""
    if fit is None or not np.isfinite(time_ms) or not np.isfinite(lst_c):
        return None
    pred = annual_sine(
        np.asarray([time_ms], dtype=np.float64),
        float(fit["lst0"]),
        float(fit["delta_lst"]),
        float(fit["phi"]),
    )
    return float(lst_c - pred[0])


def years_since_1970(unix_ms: float) -> float:
    return float(unix_ms) / (365.25 * 24.0 * 3600.0 * 1000.0)


def harmonic_column_names(n_harmonics: int = N_HARMONICS) -> list[str]:
    n = int(n_harmonics)
    names = ["constant", "t"]
    names.extend(f"cos_{i}" for i in range(1, n + 1))
    names.extend(f"sin_{i}" for i in range(1, n + 1))
    return names


def harmonic_design(
    years: np.ndarray,
    *,
    n_harmonics: int = N_HARMONICS,
) -> np.ndarray:
    """Design matrix [constant, t, cos_1..n, sin_1..n] with t = 2π years."""
    y = np.asarray(years, dtype=np.float64).reshape(-1)
    n = int(n_harmonics)
    t = y * (2.0 * np.pi)
    cols = [np.ones(y.size), t]
    for k in range(1, n + 1):
        cols.append(np.cos(t * k))
    for k in range(1, n + 1):
        cols.append(np.sin(t * k))
    return np.column_stack(cols)


def apply_harmonic_coefs(design: np.ndarray, coefs: np.ndarray) -> np.ndarray:
    mat = np.asarray(design, dtype=np.float64)
    vec = np.asarray(coefs, dtype=np.float64).reshape(-1)
    if mat.ndim != 2 or mat.shape[1] != vec.size:
        raise ValueError(f"coef length {vec.size} != design cols {mat.shape[1]}")
    return mat @ vec


def fit_harmonic_ndvi(
    years: np.ndarray,
    ndvi: np.ndarray,
    *,
    n_harmonics: int = N_HARMONICS,
    min_samples: int | None = None,
) -> dict[str, Any] | None:
    """Ordinary least squares of the FlameForecast 3-harmonic model."""
    y = np.asarray(years, dtype=np.float64).reshape(-1)
    v = np.asarray(ndvi, dtype=np.float64).reshape(-1)
    if y.size != v.size:
        return None
    ok = np.isfinite(y) & np.isfinite(v)
    y = y[ok]
    v = v[ok]
    need = int(min_samples) if min_samples is not None else (2 + 2 * int(n_harmonics) + 4)
    if y.size < need:
        return None
    design = harmonic_design(y, n_harmonics=n_harmonics)
    try:
        coef, *_rest = np.linalg.lstsq(design, v, rcond=None)
    except np.linalg.LinAlgError:
        return None
    fitted = design @ coef
    resid = v - fitted
    names = harmonic_column_names(n_harmonics)
    return {
        "n_harmonics": int(n_harmonics),
        "names": names,
        "coefs": {name: float(c) for name, c in zip(names, coef, strict=True)},
        "n": int(y.size),
        "rmse": float(np.sqrt(np.mean(resid * resid))),
    }


def empty_lst_point_doc(*, reason: str) -> dict[str, Any]:
    return {
        "schema": LST_POINT_SCHEMA,
        "ok": False,
        "reason": reason,
        "collection": LST_COLLECTION,
        "scale_m": LST_SCALE_M,
        "lst_c_formula": "dn * 0.02 - 273.15",
        "sine_fit": None,
        "not_open_meteo_t2m": True,
        "not_ros": True,
        "not_official_perimeter": True,
    }


class EarthEngineUnavailable(RuntimeError):
    """Raised when earthengine-api or WFD_EE_PROJECT is missing."""

    def __init__(self, reason: str = EE_UNAVAILABLE) -> None:
        super().__init__(reason)
        self.reason = reason


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _iso_date(value: Any) -> str | None:
    dt = _as_utc(value)
    if dt is None:
        return None
    return dt.date().isoformat()


def last_complete_month_bounds(at_date: Any) -> tuple[datetime, datetime] | None:
    """Return [start, end) of the last complete calendar month before at_date."""
    dt = _as_utc(at_date)
    if dt is None:
        return None
    first_this = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (first_this - timedelta(days=1)).replace(day=1)
    return start, first_this


def scale_modis_ndvi(ndvi: float | np.ndarray) -> float | np.ndarray:
    """Apply MOD13Q1 0.0001 scale when values look like digital numbers."""
    arr = np.asarray(ndvi, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if finite.size and float(np.nanmax(np.abs(finite))) > 2.0:
        arr = arr * NDVI_DN_SCALE
    if np.ndim(ndvi) == 0:
        return float(arr)
    return arr.astype(np.float32)


def ndvi_to_veg_proxy(ndvi: np.ndarray) -> np.ndarray:
    """Map MODIS NDVI to the [0, 1] vegetation slot (not S2 NBR)."""
    scaled = np.asarray(scale_modis_ndvi(ndvi), dtype=np.float32)
    return np.clip(scaled, 0.0, 1.0).astype(np.float32)


def parse_getregion_table(table: Any) -> list[dict[str, Any]]:
    """Parse Earth Engine ``getRegion`` ``[header, *rows]`` into dicts."""
    if not isinstance(table, list) or len(table) < 2:
        return []
    header_raw = table[0]
    if not isinstance(header_raw, (list, tuple)):
        return []
    header = [str(h) for h in header_raw]
    if not header:
        return []
    rows: list[dict[str, Any]] = []
    for raw in table[1:]:
        if not isinstance(raw, (list, tuple)) or len(raw) != len(header):
            continue
        rows.append({header[i]: raw[i] for i in range(len(header))})
    return rows


def lst_point_from_getregion(
    table: Any,
    *,
    allow_other_quality: bool = False,
    label_time_ms: float | None = None,
    lon: float | None = None,
    lat: float | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Convert a getRegion table to ``wfd_modis_lst_point_v1`` (no EE)."""
    parsed = parse_getregion_table(table)
    series: list[dict[str, Any]] = []
    times: list[float] = []
    vals: list[float] = []
    for row in parsed:
        dn_raw = row.get(LST_BAND)
        if dn_raw is None:
            dn_raw = row.get("LST_Day_1km")
        t_raw = row.get("time")
        qc_raw = row.get(LST_QC_BAND)
        if qc_raw is None:
            qc_raw = row.get("QC_Day")
        if dn_raw is None or t_raw is None:
            continue
        try:
            dn_f = float(dn_raw)
            t_f = float(t_raw)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(dn_f) or not np.isfinite(t_f):
            continue
        ok = qc_day_ok(qc_raw, allow_other_quality=allow_other_quality)
        lst_c = float(lst_dn_to_celsius(dn_f))
        series.append(
            {
                "time_ms": t_f,
                "dn": dn_f,
                "lst_c": lst_c,
                "qc": qc_raw,
                "qc_ok": ok,
            }
        )
        if ok:
            times.append(t_f)
            vals.append(lst_c)
    fit = None
    if times:
        fit = fit_annual_sine(np.asarray(times, dtype=np.float64), np.asarray(vals, dtype=np.float64))
    anomaly = None
    if fit is not None and label_time_ms is not None:
        label_obs = None
        best_abs = None
        for rec in series:
            if not rec.get("qc_ok"):
                continue
            delta = abs(float(rec["time_ms"]) - float(label_time_ms))
            if best_abs is None or delta < best_abs:
                best_abs = delta
                label_obs = rec
        if label_obs is not None:
            anomaly = sine_anomaly_c(float(label_obs["time_ms"]), float(label_obs["lst_c"]), fit)
    return {
        "schema": LST_POINT_SCHEMA,
        "ok": bool(vals),
        "collection": LST_COLLECTION,
        "scale_m": LST_SCALE_M,
        "lst_c_formula": "dn * 0.02 - 273.15",
        "qc_rule": "QC_Day bits 0-1 == 00 (good); 01 only if allow_other_quality",
        "lon": lon,
        "lat": lat,
        "start": start,
        "end": end,
        "n_rows": len(series),
        "n_qc_ok": len(vals),
        "series": series,
        "sine_fit": fit,
        "anomaly_c": anomaly,
        "label_time_ms": label_time_ms,
        "not_open_meteo_t2m": True,
        "not_ros": True,
        "not_official_perimeter": True,
    }


def detect_modis_ndvi_method(pack: Path) -> str:
    """Return ``modis_harmonic`` or ``modis_monthly`` from sidecar tags/provenance."""
    pack = Path(pack)
    prov_p = pack / "covariates" / "PROVENANCE.json"
    if prov_p.is_file():
        try:
            doc = json.loads(prov_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = {}
        for key in ("modis_ee", "modis_ndvi", "vegetation"):
            block = doc.get(key) or {}
            if not isinstance(block, dict):
                continue
            for field in ("veg_status", "method", "status"):
                raw = str(block.get(field) or "").strip().lower()
                if raw in {"modis_harmonic", "harmonic_fitted", "harmonic"}:
                    return "modis_harmonic"
                if raw in {"modis_monthly", "monthly_median", "monthly"}:
                    return "modis_monthly"
    path = pack / "covariates" / NDVI_RASTER_NAME
    if path.is_file():
        try:
            import rasterio

            with rasterio.open(path) as ds:
                tags = ds.tags() or {}
            raw = str(tags.get("modis_method") or tags.get("method") or "").strip().lower()
            if raw in {"modis_harmonic", "harmonic_fitted", "harmonic"}:
                return "modis_harmonic"
            if raw in {"modis_monthly", "monthly_median", "monthly"}:
                return "modis_monthly"
        except Exception:
            pass
    return "modis_monthly"


def lst_sidecar_present(pack: Path) -> bool:
    pack = Path(pack)
    return (pack / "covariates" / LST_RASTER_NAME).is_file() or (
        pack / "weather" / "modis_lst_point.json"
    ).is_file()


def ndvi_sidecar_present(pack: Path) -> bool:
    return (Path(pack) / "covariates" / NDVI_RASTER_NAME).is_file()


def lst_point_recipe(
    lon: float,
    lat: float,
    start: str,
    end: str,
) -> dict[str, Any]:
    return {
        "op": "fetch_lst_point",
        "collection": LST_COLLECTION,
        "bands": [LST_BAND, LST_QC_BAND],
        "scale_m": LST_SCALE_M,
        "lon": float(lon),
        "lat": float(lat),
        "start": start,
        "end": end,
        "formula": "dn * 0.02 - 273.15",
        "qc_rule": "QC_Day bits 0-1 == 00",
        "sine": "lst0 + (delta_lst/2)*sin(2*pi*t/tau + phi); tau pinned 365d",
        "writes": LST_POINT_REL,
    }


def lst_raster_recipe(bbox: list[float], date_iso: str) -> dict[str, Any]:
    return {
        "op": "fetch_lst_raster",
        "collection": LST_COLLECTION,
        "band": LST_BAND,
        "qc_band": LST_QC_BAND,
        "bbox_wgs84": list(bbox),
        "date": date_iso,
        "resample": "bilinear_to_label_grid",
        "formula": "dn * 0.02 - 273.15",
        "writes": LST_RASTER_REL,
        "not_temperature_c": True,
    }


def harmonic_ndvi_recipe(
    bbox: list[float],
    start: str,
    end: str,
    at_date: str,
) -> dict[str, Any]:
    return {
        "op": "fetch_harmonic_ndvi",
        "collection": NDVI_COLLECTION,
        "flameforecast_collection_cited": NDVI_COLLECTION_FLAMEFORECAST,
        "band": NDVI_BAND,
        "scale_m": NDVI_SCALE_M,
        "dn_scale": NDVI_DN_SCALE,
        "bbox_wgs84": list(bbox),
        "start": start,
        "end": end,
        "at_date": at_date,
        "n_harmonics": N_HARMONICS,
        "columns": harmonic_column_names(N_HARMONICS),
        "fallback": "last_complete_pre_fire_month_median",
        "writes": NDVI_RASTER_REL,
        "not_s2_nbr": True,
        "not_perimeter": True,
    }


def pack_fetch_recipe(
    event_id: str,
    *,
    lon: float,
    lat: float,
    bbox: list[float],
    start: str,
    end: str,
    at_date: str,
) -> dict[str, Any]:
    return {
        "schema": "wfd_modis_ee_fetch_recipe_v1",
        "event_id": event_id,
        "dry_run": True,
        "ee_init": "ee.Initialize(project=os.environ.get('WFD_EE_PROJECT'))",
        "ee_project_env": EE_PROJECT_ENV,
        "never_hardcode_project": "ee-alangtz51",
        "lst_point": lst_point_recipe(lon, lat, start, end),
        "lst_raster": lst_raster_recipe(bbox, at_date),
        "ndvi": harmonic_ndvi_recipe(bbox, start, end, at_date),
        "writes": [LST_POINT_REL, LST_RASTER_REL, NDVI_RASTER_REL],
        "not_claims": [
            "not Open-Meteo t2m",
            "not temperature_c overwrite",
            "not S2 NBR replacement by default",
            "not ROS",
            "not official perimeter",
            "not GO_Q",
        ],
    }


def earthengine_status(*, project: str | None = None) -> dict[str, Any]:
    installed = False
    try:
        import ee  # noqa: F401
    except ImportError:
        installed = False
    else:
        installed = True
    raw = project if project is not None else os.environ.get(EE_PROJECT_ENV)
    proj = str(raw or "").strip() or None
    if proj in FORBIDDEN_EE_PROJECTS:
        proj = None
    ok = bool(installed and proj)
    return {
        "ee_installed": installed,
        "project": proj if ok else None,
        "available": ok,
        "reason": None if ok else EE_UNAVAILABLE,
    }


def initialize_earthengine(*, project: str | None = None, ee_module: Any = None) -> Any:
    """Lazy-import ee and Initialize with WFD_EE_PROJECT. Never hardcodes FlameForecast."""
    raw = project if project is not None else os.environ.get(EE_PROJECT_ENV)
    proj = str(raw or "").strip()
    if not proj or proj in FORBIDDEN_EE_PROJECTS:
        raise EarthEngineUnavailable(EE_UNAVAILABLE)
    if ee_module is None:
        try:
            import ee as ee_module
        except ImportError as exc:
            raise EarthEngineUnavailable(EE_UNAVAILABLE) from exc
    ee_module.Initialize(project=proj)
    return ee_module


def _resolve_ee(ee_module: Any, project: str | None) -> Any:
    if ee_module is not None:
        return ee_module
    return initialize_earthengine(project=project)


def _ee_download_host_ok(host: str) -> bool:
    """Exact / suffix host check. Not startswith (rejects 127.0.0.1.evil)."""
    cleaned = str(host or "").strip().lower().rstrip(".")
    if not cleaned:
        return False
    if cleaned in EE_DOWNLOAD_HOSTS:
        return True
    return any(cleaned.endswith("." + allowed) for allowed in EE_DOWNLOAD_HOSTS)


def download_ee_bytes(url: str, *, timeout: int = 120) -> bytes:
    parsed = urlparse(str(url))
    if parsed.scheme != "https":
        raise ValueError("ee_download_scheme_rejected")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not _ee_download_host_ok(host):
        raise ValueError(f"ee_download_host_rejected:{host}")
    req = Request(url, headers={"User-Agent": "WildfireFrontDynamics-modis-ee/1.0"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def array_from_sample_rectangle(info: Any) -> np.ndarray:
    if not isinstance(info, dict):
        raise ValueError("ee_sample_empty")
    bands: dict[str, Any] = {}
    for key, val in info.items():
        if isinstance(val, list) and val and isinstance(val[0], list):
            bands[str(key)] = val
    if not bands:
        raise ValueError("ee_sample_empty")
    preferred = [LST_BAND, "lst_c", NDVI_BAND, "NDVI", "fitted", "constant"]
    key = next((k for k in preferred if k in bands), next(iter(bands)))
    arr = np.asarray(bands[key], dtype=np.float32)
    if arr.ndim != 2 or arr.size < 1:
        raise ValueError("ee_sample_empty")
    return arr


_WARP_NODATA = np.float32(-9999.0)


def _mask_ee_nodata(arr: np.ndarray, nodata: Any = None) -> np.ndarray:
    """Treat EE -inf / NaN / tagged nodata as holes so bilinear cannot poison neighbors."""
    out = np.asarray(arr, dtype=np.float32).copy()
    invalid = ~np.isfinite(out)
    if nodata is not None:
        try:
            fill = float(nodata)
        except (TypeError, ValueError):
            fill = None
        else:
            if np.isfinite(fill):
                invalid |= out == np.float32(fill)
    out[invalid] = _WARP_NODATA
    return out


def _reproject_array(
    src: np.ndarray,
    *,
    src_transform: Any,
    src_crs: Any,
    ref_grid: dict[str, Any],
    src_nodata: Any = None,
) -> np.ndarray:
    from rasterio.warp import Resampling, reproject

    h = int(ref_grid["height"])
    w = int(ref_grid["width"])
    if h < 1 or w < 1:
        raise ValueError("ref_grid_empty")
    source = _mask_ee_nodata(src, src_nodata)
    dst = np.full((h, w), _WARP_NODATA, dtype=np.float32)
    reproject(
        source=source,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=float(_WARP_NODATA),
        dst_transform=ref_grid["transform"],
        dst_crs=ref_grid["crs"],
        dst_nodata=float(_WARP_NODATA),
        resampling=Resampling.bilinear,
    )
    dst = np.asarray(dst, dtype=np.float32)
    dst[(dst == _WARP_NODATA) | (~np.isfinite(dst))] = np.nan
    return dst


def _resample_ll_to_ref(arr_ll: np.ndarray, bbox: list[float], ref_grid: dict[str, Any]) -> np.ndarray:
    from rasterio.transform import from_bounds

    src = np.asarray(arr_ll, dtype=np.float32)
    if src.ndim != 2 or src.size < 1:
        raise ValueError("ee_array_empty")
    ny, nx = src.shape
    west, south, east, north = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    if not (east > west and north > south):
        raise ValueError("bbox_invalid")
    return _reproject_array(
        src,
        src_transform=from_bounds(west, south, east, north, nx, ny),
        src_crs="EPSG:4326",
        ref_grid=ref_grid,
    )


def _reproject_geotiff_bytes(raw: bytes, ref_grid: dict[str, Any]) -> np.ndarray:
    from rasterio.io import MemoryFile

    if int(ref_grid.get("height") or 0) < 1 or int(ref_grid.get("width") or 0) < 1:
        raise ValueError("ref_grid_empty")
    if not raw:
        raise ValueError("ee_geotiff_empty")
    with MemoryFile(raw) as mem:
        with mem.open() as src:
            return _reproject_array(
                src.read(1),
                src_transform=src.transform,
                src_crs=src.crs,
                ref_grid=ref_grid,
                src_nodata=src.nodata,
            )


def _ee_bbox_rect(ee: Any, bbox: list[float]) -> Any:
    coords = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    try:
        return ee.Geometry.Rectangle(coords, proj="EPSG:4326", geodesic=False)
    except TypeError:
        return ee.Geometry.Rectangle(coords)


def _ee_image_to_array(
    img: Any,
    bbox: list[float],
    ref_grid: dict[str, Any],
    *,
    ee: Any,
    download: Callable[[str], bytes] | None,
    scale_m: float,
) -> np.ndarray:
    geom = _ee_bbox_rect(ee, bbox)
    url = None
    clipped = img.clip(geom) if hasattr(img, "clip") else img
    if hasattr(clipped, "toFloat"):
        clipped = clipped.toFloat()
    if hasattr(img, "getDownloadURL"):
        try:
            url = clipped.getDownloadURL(
                {
                    "scale": float(scale_m),
                    "crs": "EPSG:4326",
                    "region": geom,
                    "format": "GEO_TIFF",
                }
            )
        except Exception:
            url = None
        else:
            try:
                getter = download if download is not None else download_ee_bytes
                raw = getter(str(url))
                return _reproject_geotiff_bytes(raw, ref_grid)
            except Exception:
                url = None
    if not hasattr(clipped, "sampleRectangle"):
        raise EarthEngineUnavailable(EE_UNAVAILABLE)
    info = clipped.sampleRectangle(region=geom, defaultValue=-9999).getInfo()
    native = array_from_sample_rectangle(info)
    return _resample_ll_to_ref(native, bbox, ref_grid)


def _one_day_window(value: Any) -> tuple[str, str]:
    dt = _as_utc(value)
    if dt is None:
        raise ValueError("date_invalid")
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.date().isoformat(), end.date().isoformat()


def fetch_lst_point(
    lon: float,
    lat: float,
    start: Any,
    end: Any,
    *,
    ee_module: Any = None,
    project: str | None = None,
    allow_other_quality: bool = False,
    label_time_ms: float | None = None,
) -> dict[str, Any]:
    """Sample MOD11A1 LST/QC at a point via getRegion. Imports ee inside."""
    start_s = _iso_date(start)
    end_s = _iso_date(end)
    if start_s is None or end_s is None:
        raise ValueError("date_invalid")
    ee = _resolve_ee(ee_module, project)
    point = ee.Geometry.Point([float(lon), float(lat)])
    col = (
        ee.ImageCollection(LST_COLLECTION)
        .filterDate(start_s, end_s)
        .filterBounds(point)
        .select([LST_BAND, LST_QC_BAND])
    )
    table = col.getRegion(point, LST_SCALE_M).getInfo()
    return lst_point_from_getregion(
        table,
        allow_other_quality=allow_other_quality,
        label_time_ms=label_time_ms,
        lon=float(lon),
        lat=float(lat),
        start=start_s,
        end=end_s,
    )


MIN_LST_COVERAGE = 0.05


def _finite_in_range_frac(arr: np.ndarray, lo: float, hi: float) -> float:
    a = np.asarray(arr, dtype=np.float64)
    if a.size < 1:
        return 0.0
    return float(np.mean(np.isfinite(a) & (a >= lo) & (a <= hi)))


def fetch_lst_raster(
    bbox: list[float],
    date: Any,
    ref_grid: dict[str, Any],
    *,
    ee_module: Any = None,
    project: str | None = None,
    download: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """MOD11A1 LST_Day in °C, bilinear-resampled to the label grid."""
    if ref_grid is None:
        raise ValueError("ref_grid_required")
    if int(ref_grid.get("height") or 0) < 1 or int(ref_grid.get("width") or 0) < 1:
        raise ValueError("ref_grid_empty")
    if len(bbox) != 4 or not (float(bbox[2]) > float(bbox[0]) and float(bbox[3]) > float(bbox[1])):
        raise ValueError("bbox_invalid")
    start_s, end_s = _one_day_window(date)
    ee = _resolve_ee(ee_module, project)
    at_dt = _as_utc(date)
    if at_dt is None:
        raise ValueError("date_invalid")
    windows = [
        (start_s, end_s, False, "day_qc00"),
        (start_s, end_s, True, "day_qc01"),
        (
            (at_dt - timedelta(days=7)).date().isoformat(),
            (at_dt + timedelta(days=8)).date().isoformat(),
            False,
            "pm7d_qc00",
        ),
        (
            (at_dt - timedelta(days=7)).date().isoformat(),
            (at_dt + timedelta(days=8)).date().isoformat(),
            True,
            "pm7d_qc01",
        ),
    ]

    def _prep(allow_other: bool) -> Callable[[Any], Any]:
        def _map(img: Any) -> Any:
            qa = img.select(LST_QC_BAND)
            good = qa.bitwiseAnd(3).eq(0)
            if allow_other:
                good = good.Or(qa.bitwiseAnd(3).eq(1))
            return (
                img.select(LST_BAND)
                .updateMask(good)
                .multiply(LST_DN_SCALE)
                .subtract(LST_DN_OFFSET_K)
                .rename("lst_c")
            )

        return _map

    arr: np.ndarray | None = None
    used = windows[0][3]
    last_exc: Exception | None = None
    best: tuple[float, np.ndarray, str, str, str] | None = None
    for w0, w1, allow_other, label in windows:
        try:
            col = (
                ee.ImageCollection(LST_COLLECTION)
                .filterDate(w0, w1)
                .filterBounds(_ee_bbox_rect(ee, bbox))
                .select([LST_BAND, LST_QC_BAND])
            )
            img = col.map(_prep(allow_other)).median()
            candidate = _ee_image_to_array(
                img, list(bbox), ref_grid, ee=ee, download=download, scale_m=LST_SCALE_M
            )
            candidate = np.asarray(candidate, dtype=np.float32)
            candidate[~np.isfinite(candidate)] = np.nan
            frac = _finite_in_range_frac(candidate, -80.0, 80.0)
            if best is None or frac > best[0]:
                best = (frac, candidate, label, w0, w1)
            if frac >= MIN_LST_COVERAGE:
                break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    if best is None or best[0] <= 0.0:
        if last_exc is not None:
            raise last_exc
        raise ValueError("lst_raster_empty")
    _frac, arr, used, start_s, end_s = best
    return {
        "ok": True,
        "array": arr,
        "collection": LST_COLLECTION,
        "date": start_s,
        "end": end_s,
        "qc_window": used,
        "bbox_wgs84": list(bbox),
        "formula": "dn * 0.02 - 273.15",
        "resample": "bilinear",
        "not_temperature_c": True,
        "not_open_meteo_t2m": True,
        "not_ros": True,
    }


def _add_harmonic_bands(ee: Any) -> Callable[[Any], Any]:
    def _map(image: Any) -> Any:
        date_ee = ee.Date(image.get("system:time_start"))
        years = date_ee.difference(ee.Date("1970-01-01"), "year")
        # Constant images must be Float: uncast scalars get a 1-value type
        # range and EE rejects the collection as inhomogeneous (HTTP 400).
        t = ee.Image.constant(years.multiply(2.0 * math.pi)).toFloat().rename("t")
        base = image.toFloat() if hasattr(image, "toFloat") else image
        out = base.addBands(ee.Image.constant(1).toFloat().rename("constant")).addBands(t)
        for k in range(1, N_HARMONICS + 1):
            out = out.addBands(t.multiply(k).cos().toFloat().rename(f"cos_{k}"))
        for k in range(1, N_HARMONICS + 1):
            out = out.addBands(t.multiply(k).sin().toFloat().rename(f"sin_{k}"))
        return out

    return _map


def fetch_harmonic_ndvi(
    bbox: list[float],
    start: Any,
    end: Any,
    at_date: Any,
    *,
    ee_module: Any = None,
    project: str | None = None,
    download: Callable[[str], bytes] | None = None,
    ref_grid: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pre-fire MOD13Q1 NDVI: 3-harmonic fitted band, else last complete month."""
    if ref_grid is None:
        raise ValueError("ref_grid_required")
    if int(ref_grid.get("height") or 0) < 1 or int(ref_grid.get("width") or 0) < 1:
        raise ValueError("ref_grid_empty")
    if len(bbox) != 4 or not (float(bbox[2]) > float(bbox[0]) and float(bbox[3]) > float(bbox[1])):
        raise ValueError("bbox_invalid")
    start_s = _iso_date(start)
    end_s = _iso_date(end)
    at_s = _iso_date(at_date)
    if start_s is None or end_s is None or at_s is None:
        raise ValueError("date_invalid")
    ee = _resolve_ee(ee_module, project)
    geom = _ee_bbox_rect(ee, bbox)
    method = "monthly_median"
    img = None
    try:
        col = (
            ee.ImageCollection(NDVI_COLLECTION)
            .filterDate(start_s, end_s)
            .filterBounds(geom)
            .select(NDVI_BAND)
            .map(
                lambda im: im.multiply(NDVI_DN_SCALE)
                .toFloat()
                .copyProperties(im, ["system:time_start"])
            )
        )
        with_vars = col.map(_add_harmonic_bands(ee))
        names = harmonic_column_names(N_HARMONICS)
        independents = names
        fitted_src = with_vars.select(independents + [NDVI_BAND]).reduce(
            ee.Reducer.linearRegression(numX=len(independents), numY=1)
        )
        coeffs = fitted_src.select("coefficients").arrayProject([0]).arrayFlatten([independents])
        at_ms = _as_utc(at_date)
        assert at_ms is not None
        design = harmonic_design(np.array([years_since_1970(at_ms.timestamp() * 1000.0)]))[0]
        fitted = ee.Image.constant(float(design[0])).toFloat().rename("fitted")
        for i, name in enumerate(names[1:], start=1):
            fitted = fitted.add(coeffs.select(name).toFloat().multiply(float(design[i])))
        img = fitted.rename(NDVI_BAND).toFloat()
        method = "harmonic_fitted"
        arr = _ee_image_to_array(
            img, list(bbox), ref_grid, ee=ee, download=download, scale_m=NDVI_SCALE_M
        )
        arr = np.asarray(arr, dtype=np.float32)
        # Unstable 3-harmonic pixels explode (seen live on Tenerife).
        if _finite_in_range_frac(arr, -0.2, 1.2) < 0.5:
            raise ValueError("harmonic_ndvi_out_of_range")
    except Exception:
        img = None
        arr = None
        method = "monthly_median"
    if img is None or arr is None:
        bounds = last_complete_month_bounds(at_date)
        if bounds is None:
            raise ValueError("date_invalid")
        m0, m1 = bounds
        img = (
            ee.ImageCollection(NDVI_COLLECTION)
            .filterDate(m0.date().isoformat(), m1.date().isoformat())
            .filterBounds(geom)
            .select(NDVI_BAND)
            .map(lambda im: im.multiply(NDVI_DN_SCALE))
            .median()
            .rename(NDVI_BAND)
        )
        method = "monthly_median"
        arr = _ee_image_to_array(
            img, list(bbox), ref_grid, ee=ee, download=download, scale_m=NDVI_SCALE_M
        )
    veg_status = "modis_harmonic" if method == "harmonic_fitted" else "modis_monthly"
    return {
        "ok": True,
        "array": arr,
        "method": method,
        "veg_status": veg_status,
        "collection": NDVI_COLLECTION,
        "flameforecast_collection_cited": NDVI_COLLECTION_FLAMEFORECAST,
        "start": start_s,
        "end": end_s,
        "at_date": at_s,
        "bbox_wgs84": list(bbox),
        "not_s2_nbr": True,
        "not_perimeter": True,
        "not_ros": True,
    }
