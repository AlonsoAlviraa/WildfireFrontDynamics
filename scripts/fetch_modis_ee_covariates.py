#!/usr/bin/env python3
"""Fetch optional MODIS LST / harmonic-NDVI sidecars via Earth Engine.

Does not invent rasters when EE is missing. Does not overwrite temperature_c.tif
or replace S2 NBR by default. Does not write official MET artifacts.

  python scripts/fetch_modis_ee_covariates.py --event-id ES_EMSR685_TENERIFE --dry-run
  python scripts/fetch_modis_ee_covariates.py --event-id ES_EMSR685_TENERIFE

Requires WFD_EE_PROJECT and earthengine-api for a live fetch. Init is always
``ee.Initialize(project=os.environ.get("WFD_EE_PROJECT"))`` — never FlameForecast
``ee-alangtz51``.

Exit:
  0 — dry-run recipe, or live write
  1 — missing pack / label grid (live only)
  2 — usage / ee_unavailable / path not allowlisted
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    GROWTH_LABEL_KINDS,
    is_allowed_pack_path,
    label_records_from_meta,
    pack_dir_for,
)
from wildfire_front.open_if.modis_ee import (  # noqa: E402
    EE_PROJECT_ENV,
    EE_UNAVAILABLE,
    LST_POINT_REL,
    LST_RASTER_NAME,
    LST_RASTER_REL,
    NDVI_RASTER_NAME,
    NDVI_RASTER_REL,
    EarthEngineUnavailable,
    detect_modis_ndvi_method,
    earthengine_status,
    fetch_harmonic_ndvi,
    fetch_lst_point,
    fetch_lst_raster,
    initialize_earthengine,
    last_complete_month_bounds,
    lst_sidecar_present,
    pack_fetch_recipe,
)

EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
EXIT_OK = 0
EXIT_MISSING_PACK = 1
EXIT_USAGE_OR_EE = 2


def sanitize_event_id(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text or ".." in text or "/" in text or "\\" in text:
        return None
    if not EVENT_ID_RE.fullmatch(text):
        return None
    return text


def _dest_inside_pack(dest: Path, pack: Path) -> bool:
    try:
        dest.resolve().relative_to(pack.resolve())
        return True
    except (OSError, ValueError):
        return False


def pack_allowed(pack: Path) -> bool:
    try:
        under_repo = pack.resolve().is_relative_to(ROOT.resolve())
    except (OSError, ValueError):
        under_repo = False
    if under_repo and not is_allowed_pack_path(pack, repo_root=ROOT):
        return False
    return True


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


def pack_bbox_wgs84(transform, crs, h: int, w: int) -> list[float]:
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


def first_growth_dt(pack: Path) -> Any:
    meta_p = pack / "meta.json"
    if not meta_p.is_file():
        return None
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    recs = label_records_from_meta(pack, meta)
    growth = [r["dt"] for r in recs if r.get("dt") is not None and r.get("kind") in GROWTH_LABEL_KINDS]
    dated = [r["dt"] for r in recs if r.get("dt") is not None]
    pool = growth or dated
    if not pool:
        return None
    return min(pool)


def window_for_spec(spec: dict[str, Any], pack: Path) -> dict[str, Any]:
    lon, lat = spec.get("approx_lonlat") or (0.0, 0.0)
    year = int(spec.get("year") or 2023)
    at = first_growth_dt(pack)
    if at is None:
        from datetime import datetime, timezone

        at = datetime(year, 8, 1, tzinfo=timezone.utc)
    start_lst = at - timedelta(days=365)
    end_lst = at + timedelta(days=1)
    start_ndvi = at - timedelta(days=365 * 3)
    bbox = [float(lon) - 0.15, float(lat) - 0.15, float(lon) + 0.15, float(lat) + 0.15]
    ref = None
    if pack.is_dir():
        ref = label_reference(pack)
        if ref is not None:
            _path, transform, crs, h, w = ref
            bbox = pack_bbox_wgs84(transform, crs, h, w)
            lon = (bbox[0] + bbox[2]) / 2.0
            lat = (bbox[1] + bbox[3]) / 2.0
    month = last_complete_month_bounds(at)
    return {
        "lon": float(lon),
        "lat": float(lat),
        "bbox": bbox,
        "at": at,
        "start_lst": start_lst,
        "end_lst": end_lst,
        "start_ndvi": start_ndvi,
        "end_ndvi": at,
        "month_bounds": month,
        "ref": ref,
    }


def write_float_tif(
    path: Path,
    arr: Any,
    *,
    transform,
    crs,
    tags: dict[str, str] | None = None,
) -> None:
    import numpy as np
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(arr, dtype=np.float32)
    profile = {
        "driver": "GTiff",
        "height": int(data.shape[0]),
        "width": int(data.shape[1]),
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(data, 1)
        if tags:
            ds.update_tags(**tags)


def merge_provenance(pack: Path, rec: dict[str, Any]) -> None:
    cov = pack / "covariates"
    cov.mkdir(parents=True, exist_ok=True)
    path = cov / "PROVENANCE.json"
    doc: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                doc = loaded
        except (OSError, json.JSONDecodeError):
            doc = {}
    channels = dict(doc.get("channels_ready") or {})
    if lst_sidecar_present(pack):
        channels["lst"] = True
    if (cov / NDVI_RASTER_NAME).is_file():
        channels["harmonic_ndvi"] = True
    doc["channels_ready"] = channels
    doc["modis_ee"] = rec
    if "not_claims" not in doc:
        doc["not_claims"] = []
    extra = [
        "LST sidecar is not Open-Meteo t2m / not temperature_c",
        "MODIS NDVI is not S2 NBR unless fill fallback is used",
        "not ROS",
        "not official LATAM MET",
    ]
    claims = list(doc["not_claims"])
    for item in extra:
        if item not in claims:
            claims.append(item)
    doc["not_claims"] = claims
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Fetch optional MODIS LST/NDVI via Earth Engine")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--dry-run", action="store_true", help="Print recipe only; no network, no writes")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    event_id = sanitize_event_id(str(args.event_id))
    if event_id is None:
        print("error: invalid event-id (path separators / unknown chars rejected)", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    if event_id not in ALL_PACK_SPECS:
        print(f"error: unknown event_id {event_id}", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    spec = ALL_PACK_SPECS[event_id]
    pack = pack_dir_for(Path(args.data_root), spec)
    if not pack_allowed(pack):
        print(f"error: pack_path_not_allowlisted:{pack}", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    win = window_for_spec(spec, pack)
    at_s = win["at"].date().isoformat() if hasattr(win["at"], "date") else str(win["at"])[:10]
    recipe = pack_fetch_recipe(
        event_id,
        lon=float(win["lon"]),
        lat=float(win["lat"]),
        bbox=list(win["bbox"]),
        start=win["start_lst"].date().isoformat(),
        end=win["end_lst"].date().isoformat(),
        at_date=at_s,
    )
    if args.dry_run:
        print(json.dumps(recipe, indent=2))
        return EXIT_OK

    status = earthengine_status()
    if not status.get("available"):
        print(f"error: {EE_UNAVAILABLE} (need {EE_PROJECT_ENV} and earthengine-api)", file=sys.stderr)
        return EXIT_USAGE_OR_EE

    if not pack.is_dir() or not (pack / "meta.json").is_file():
        print(f"error: missing pack {pack}", file=sys.stderr)
        return EXIT_MISSING_PACK
    if win["ref"] is None:
        print("error: no_label_tif", file=sys.stderr)
        return EXIT_MISSING_PACK

    label_path, transform, crs, h, w = win["ref"]
    if h < 1 or w < 1:
        print("error: ref_grid_empty", file=sys.stderr)
        return EXIT_MISSING_PACK
    ref_grid = {"transform": transform, "crs": crs, "height": h, "width": w}

    weather = pack / "weather"
    cov = pack / "covariates"
    point_dest = pack / "weather" / "modis_lst_point.json"
    lst_dest = pack / "covariates" / LST_RASTER_NAME
    ndvi_dest = pack / "covariates" / NDVI_RASTER_NAME
    for dest in (point_dest, lst_dest, ndvi_dest):
        if not _dest_inside_pack(dest, pack):
            print("error: dest_escapes_pack", file=sys.stderr)
            return EXIT_USAGE_OR_EE

    wrote: list[str] = []
    errors: list[str] = []
    lst_doc: dict[str, Any] | None = None
    ndvi_method = None
    try:
        ee = initialize_earthengine()
    except EarthEngineUnavailable:
        print(f"error: {EE_UNAVAILABLE}", file=sys.stderr)
        return EXIT_USAGE_OR_EE

    try:
        label_ms = win["at"].timestamp() * 1000.0
        lst_doc = fetch_lst_point(
            float(win["lon"]),
            float(win["lat"]),
            win["start_lst"],
            win["end_lst"],
            ee_module=ee,
            label_time_ms=label_ms,
        )
        weather.mkdir(parents=True, exist_ok=True)
        point_dest.write_text(json.dumps(lst_doc, indent=2) + "\n", encoding="utf-8")
        wrote.append(LST_POINT_REL)
    except EarthEngineUnavailable:
        print(f"error: {EE_UNAVAILABLE}", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    except Exception as exc:  # noqa: BLE001
        errors.append(f"lst_point:{type(exc).__name__}:{exc}")

    try:
        rast = fetch_lst_raster(list(win["bbox"]), win["at"], ref_grid, ee_module=ee)
        cov.mkdir(parents=True, exist_ok=True)
        write_float_tif(
            lst_dest,
            rast["array"],
            transform=transform,
            crs=crs,
            tags={
                "collection": str(rast.get("collection") or ""),
                "formula": "dn * 0.02 - 273.15",
                "qc_window": str(rast.get("qc_window") or ""),
                "not_temperature_c": "true",
            },
        )
        wrote.append(LST_RASTER_REL)
    except EarthEngineUnavailable:
        print(f"error: {EE_UNAVAILABLE}", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    except Exception as exc:  # noqa: BLE001
        errors.append(f"lst_raster:{type(exc).__name__}:{exc}")

    try:
        ndvi = fetch_harmonic_ndvi(
            list(win["bbox"]),
            win["start_ndvi"],
            win["end_ndvi"],
            win["at"],
            ee_module=ee,
            ref_grid=ref_grid,
        )
        cov.mkdir(parents=True, exist_ok=True)
        ndvi_method = ndvi.get("veg_status") or ndvi.get("method")
        write_float_tif(
            ndvi_dest,
            ndvi["array"],
            transform=transform,
            crs=crs,
            tags={
                "collection": str(ndvi.get("collection") or ""),
                "modis_method": str(ndvi_method or "modis_monthly"),
                "flameforecast_collection_cited": str(ndvi.get("flameforecast_collection_cited") or ""),
                "not_s2_nbr": "true",
            },
        )
        wrote.append(NDVI_RASTER_REL)
    except EarthEngineUnavailable:
        print(f"error: {EE_UNAVAILABLE}", file=sys.stderr)
        return EXIT_USAGE_OR_EE
    except Exception as exc:  # noqa: BLE001
        errors.append(f"ndvi:{type(exc).__name__}:{exc}")

    rec = {
        "event_id": event_id,
        "ok": bool(wrote) and not errors,
        "wrote": wrote,
        "errors": errors,
        "ee_project_env": EE_PROJECT_ENV,
        "lst_point_ok": lst_doc.get("ok") if isinstance(lst_doc, dict) else False,
        "ndvi_method": ndvi_method or (
            detect_modis_ndvi_method(pack) if ndvi_dest.is_file() else None
        ),
        "label_ref": str(label_path.relative_to(pack)).replace("\\", "/"),
        "not_temperature_c_overwrite": True,
        "not_open_meteo_t2m": True,
        "not_ros": True,
    }
    merge_provenance(pack, rec)
    print(json.dumps({"event_id": event_id, "wrote": wrote, "errors": errors}, indent=2))
    return EXIT_OK if wrote and not errors else EXIT_MISSING_PACK


if __name__ == "__main__":
    raise SystemExit(main())
