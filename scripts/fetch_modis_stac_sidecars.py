#!/usr/bin/env python3
"""Write the same MODIS LST/NDVI pack sidecars via Planetary Computer STAC.

Used when the GCP project is not registered for Earth Engine. Does not invent
pixels. Does not overwrite official MET JSON or temperature_c.tif.

  python scripts/fetch_modis_stac_sidecars.py --event-id ES_EMSR685_TENERIFE
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fetch_modis_ee_covariates import (  # noqa: E402
    EXIT_MISSING_PACK,
    EXIT_OK,
    EXIT_USAGE_OR_EE,
    _dest_inside_pack,
    first_growth_dt,
    merge_provenance,
    pack_allowed,
    sanitize_event_id,
    window_for_spec,
    write_float_tif,
)
from wildfire_front.open_if.latam_au import ALL_PACK_SPECS, USER_AGENT, pack_dir_for  # noqa: E402
from wildfire_front.open_if.modis_ee import (  # noqa: E402
    LST_DN_OFFSET_K,
    LST_DN_SCALE,
    LST_POINT_REL,
    LST_RASTER_NAME,
    NDVI_RASTER_NAME,
    qc_day_ok,
    fit_annual_sine,
    fit_harmonic_ndvi,
    sine_anomaly_c,
    years_since_1970,
)

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
COLL_LST = "modis-11A1-061"
COLL_NDVI = "modis-13Q1-061"
NDVI_SCALE = 0.0001


def _get(url: str, *, timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, payload: dict[str, Any], *, timeout: int = 60) -> dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def sign_href(href: str) -> str:
    doc = _get(f"{SIGN}?{urllib.parse.urlencode({'href': href})}")
    return str(doc.get("href") or href)


def stac_items(collection: str, bbox: list[float], start: str, end: str, *, limit: int = 200) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": min(100, limit),
    }
    while payload and len(items) < limit:
        doc = _post(STAC, payload)
        feats = list(doc.get("features") or [])
        items.extend(feats)
        nxt = None
        for link in doc.get("links") or []:
            if link.get("rel") == "next":
                nxt = link
                break
        if nxt is None or not feats:
            break
        payload = nxt.get("body") or {}
        if not payload:
            break
    return items[:limit]


def item_date(item: dict[str, Any]) -> str | None:
    props = item.get("properties") or {}
    for key in ("start_datetime", "datetime", "end_datetime"):
        raw = props.get(key)
        if raw:
            return str(raw)[:10]
    return None


def item_ms(item: dict[str, Any]) -> float | None:
    day = item_date(item)
    if not day:
        return None
    dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.timestamp() * 1000.0


def sample_point(href: str, lon: float, lat: float) -> float | None:
    import rasterio
    from rasterio.warp import transform as warp_xy

    signed = sign_href(href)
    with rasterio.open(signed) as ds:
        xs, ys = warp_xy("EPSG:4326", ds.crs, [lon], [lat])
        val = next(ds.sample([(xs[0], ys[0])]))[0]
    if val is None:
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(num) or num <= 0:
        return None
    return num


def warp_asset_to_grid(href: str, ref: dict[str, Any], *, scale: float, offset: float) -> np.ndarray:
    import rasterio
    from rasterio.warp import Resampling, reproject

    signed = sign_href(href)
    dest = np.zeros((int(ref["height"]), int(ref["width"])), dtype=np.float32)
    with rasterio.open(signed) as src:
        src_arr = src.read(1).astype(np.float32)
        src_arr = np.where(src_arr > 0, src_arr * float(scale) + float(offset), np.nan)
        reproject(
            source=src_arr,
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref["transform"],
            dst_crs=ref["crs"],
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )
    return dest


def pick_closest(items: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    best = None
    best_abs = None
    tgt = datetime.strptime(target[:10], "%Y-%m-%d")
    for item in items:
        day = item_date(item)
        if not day:
            continue
        delta = abs((datetime.strptime(day, "%Y-%m-%d") - tgt).days)
        if best_abs is None or delta < best_abs:
            best_abs = delta
            best = item
    return best


def fetch_one(event_id: str, data_root: Path) -> dict[str, Any]:
    spec = ALL_PACK_SPECS[event_id]
    pack = pack_dir_for(data_root, spec)
    if not pack_allowed(pack) or not pack.is_dir() or not (pack / "meta.json").is_file():
        raise FileNotFoundError(f"missing_or_blocked_pack:{pack}")
    win = window_for_spec(spec, pack)
    if win["ref"] is None:
        raise FileNotFoundError("no_label_tif")
    _label, transform, crs, h, w = win["ref"]
    ref_grid = {"transform": transform, "crs": crs, "height": h, "width": w}
    at_s = win["at"].date().isoformat()
    start_lst = win["start_lst"].date().isoformat()
    end_lst = win["end_lst"].date().isoformat()
    start_ndvi = win["start_ndvi"].date().isoformat()
    lon, lat = float(win["lon"]), float(win["lat"])
    bbox = list(win["bbox"])
    # Point search uses a tiny bbox so we stay on one MODIS tile.
    point_bbox = [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05]

    errors: list[str] = []
    wrote: list[str] = []

    lst_items = stac_items(COLL_LST, point_bbox, start_lst, end_lst, limit=140)
    lst_items.sort(key=lambda it: item_date(it) or "")
    # Subsample (~every 3rd scene) so a year stays tractable.
    sampled = lst_items[:: max(1, len(lst_items) // 80)] if lst_items else []
    rows: list[dict[str, Any]] = []
    for item in sampled:
        href = ((item.get("assets") or {}).get("LST_Day_1km") or {}).get("href")
        qc_href = ((item.get("assets") or {}).get("QC_Day") or {}).get("href")
        if not href:
            continue
        try:
            dn = sample_point(href, lon, lat)
            qc = sample_point(qc_href, lon, lat) if qc_href else 0.0
        except Exception as exc:  # noqa: BLE001
            errors.append(f"lst_sample:{item_date(item)}:{type(exc).__name__}")
            continue
        if dn is None:
            continue
        qc_int = int(qc) if qc is not None else None
        if qc_int is not None and not qc_day_ok(qc_int, allow_other_quality=True):
            continue
        lst_c = float(dn) * LST_DN_SCALE - LST_DN_OFFSET_K
        rows.append(
            {
                "date": item_date(item),
                "time_ms": item_ms(item),
                "dn": float(dn),
                "lst_c": lst_c,
                "qc": qc_int,
                "id": item.get("id"),
            }
        )
    times = np.array([r["time_ms"] for r in rows if r.get("time_ms") is not None], dtype=np.float64)
    vals = np.array([r["lst_c"] for r in rows if r.get("time_ms") is not None], dtype=np.float64)
    fit = fit_annual_sine(times, vals) if times.size else None
    label_ms = win["at"].timestamp() * 1000.0
    nearest = min(rows, key=lambda r: abs((r.get("time_ms") or 0) - label_ms), default=None)
    anomaly = None
    if nearest and fit:
        anomaly = sine_anomaly_c(float(nearest["time_ms"]), float(nearest["lst_c"]), fit)
    lst_doc = {
        "schema": "wfd_modis_lst_point_v1",
        "ok": bool(rows),
        "source": "planetary_computer_stac",
        "collection": COLL_LST,
        "ee_unregistered": "project-89d8567f-49f2-48bc-a00",
        "lon": lon,
        "lat": lat,
        "n_scenes_listed": len(lst_items),
        "n_samples": len(rows),
        "sine_fit": fit,
        "anomaly_c": anomaly,
        "label_date": at_s,
        "nearest_sample": nearest,
        "samples": rows,
        "not_open_meteo_t2m": True,
        "not_ros": True,
        "not_official_perimeter": True,
    }
    weather = pack / "weather"
    weather.mkdir(parents=True, exist_ok=True)
    (pack / LST_POINT_REL).write_text(json.dumps(lst_doc, indent=2) + "\n", encoding="utf-8")
    wrote.append(LST_POINT_REL)

    close = pick_closest(lst_items, at_s)
    if close and ((close.get("assets") or {}).get("LST_Day_1km") or {}).get("href"):
        try:
            arr = warp_asset_to_grid(
                close["assets"]["LST_Day_1km"]["href"],
                ref_grid,
                scale=LST_DN_SCALE,
                offset=-LST_DN_OFFSET_K,
            )
            write_float_tif(
                pack / "covariates" / LST_RASTER_NAME,
                np.nan_to_num(arr, nan=0.0),
                transform=transform,
                crs=crs,
                tags={
                    "source": "planetary_computer_stac",
                    "collection": COLL_LST,
                    "scene": str(close.get("id") or ""),
                    "units": "celsius",
                },
            )
            wrote.append(f"covariates/{LST_RASTER_NAME}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"lst_raster:{type(exc).__name__}:{exc}")
    else:
        errors.append("lst_raster:no_scene")

    ndvi_items = stac_items(COLL_NDVI, point_bbox, start_ndvi, at_s, limit=40)
    ndvi_items.sort(key=lambda it: item_date(it) or "")
    ndvi_rows: list[dict[str, Any]] = []
    for item in ndvi_items:
        href = ((item.get("assets") or {}).get("250m_16_days_NDVI") or {}).get("href")
        if not href:
            continue
        try:
            raw = sample_point(href, lon, lat)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ndvi_sample:{item_date(item)}:{type(exc).__name__}")
            continue
        if raw is None:
            continue
        ndvi_rows.append(
            {
                "date": item_date(item),
                "time_ms": item_ms(item),
                "ndvi": float(raw) * NDVI_SCALE,
            }
        )
    years = np.array(
        [years_since_1970(float(r["time_ms"])) for r in ndvi_rows if r.get("time_ms")],
        dtype=np.float64,
    )
    ndvis = np.array([r["ndvi"] for r in ndvi_rows if r.get("time_ms")], dtype=np.float64)
    harm = fit_harmonic_ndvi(years, ndvis) if years.size else None
    pre = [it for it in ndvi_items if (item_date(it) or "9999") < at_s]
    ndvi_src = pre[-1] if pre else pick_closest(ndvi_items, at_s)
    ndvi_method = "modis_harmonic" if harm else "modis_monthly"
    if ndvi_src and ((ndvi_src.get("assets") or {}).get("250m_16_days_NDVI") or {}).get("href"):
        try:
            arr = warp_asset_to_grid(
                ndvi_src["assets"]["250m_16_days_NDVI"]["href"],
                ref_grid,
                scale=NDVI_SCALE,
                offset=0.0,
            )
            arr = np.clip(np.nan_to_num(arr, nan=0.0), -1.0, 1.0)
            write_float_tif(
                pack / "covariates" / NDVI_RASTER_NAME,
                arr,
                transform=transform,
                crs=crs,
                tags={
                    "source": "planetary_computer_stac",
                    "collection": COLL_NDVI,
                    "modis_method": ndvi_method,
                    "scene": str(ndvi_src.get("id") or ""),
                },
            )
            wrote.append(f"covariates/{NDVI_RASTER_NAME}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ndvi_raster:{type(exc).__name__}:{exc}")
    else:
        errors.append("ndvi_raster:no_scene")

    rec = {
        "source": "planetary_computer_stac",
        "ok": bool(wrote),
        "event_id": event_id,
        "wrote": wrote,
        "errors": errors[:12],
        "lst_n_samples": len(rows),
        "ndvi_n_samples": len(ndvi_rows),
        "sine_fit_ok": fit is not None,
        "harmonic_ok": harm is not None,
        "veg_status": ndvi_method,
        "method": ndvi_method,
        "not_earth_engine": True,
        "ee_block": "project_not_registered",
    }
    if harm:
        rec["harmonic"] = {"n": harm["n"], "rmse": harm["rmse"]}
    merge_provenance(pack, rec)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--event-id", action="append", dest="event_ids", required=True)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    args = ap.parse_args(argv)
    rows = []
    any_fail = False
    for raw in args.event_ids:
        eid = sanitize_event_id(str(raw))
        if eid is None or eid not in ALL_PACK_SPECS:
            print(f"error: invalid_or_unknown {raw}", file=sys.stderr)
            return EXIT_USAGE_OR_EE
        print(f"== {eid} ==", flush=True)
        try:
            rec = fetch_one(eid, Path(args.data_root))
            rows.append(rec)
            print(json.dumps({k: rec[k] for k in ("event_id", "wrote", "errors", "lst_n_samples", "ndvi_n_samples")}, indent=2))
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            any_fail = True
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}:{exc}", file=sys.stderr)
            any_fail = True
    return EXIT_MISSING_PACK if any_fail else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
