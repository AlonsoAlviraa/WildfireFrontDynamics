#!/usr/bin/env python3
"""Build landcover → fuel map for Tobarra or any core spatial_v1 fire.

Usage:
  python scripts/build_fuel_map.py --allow-download
  python scripts/build_fuel_map.py --fire hellin_2024 --allow-download
  python scripts/build_fuel_map.py --fire CARDOSO --landcover path/to/clc.tif --scheme clc
  python scripts/build_fuel_map.py --allow-synthetic

Cache layout: ``data/fuel_map/<fuel_key>/worldcover_window.tif``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.dem import TOBARRA_BBOX_WGS84, resolve_dem  # noqa: E402
from wildfire_front.fuel.fuel_map import (  # noqa: E402
    FuelMapUnavailableError,
    resolve_fuel_map,
    write_fuel_map_geotiffs,
)
from wildfire_front.fuel.spatial_v1_sources import (  # noqa: E402
    CORE_SPATIAL_FIRES,
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_OK,
    fuel_dir_for,
    get_fire_spec,
    list_core_source_ids,
    load_bbox_wgs84,
    resolve_dem_path,
    resolve_fuel_path,
)
from wildfire_front.fuel.stack import build_stack_from_dem, write_stack  # noqa: E402


def _resolve_source_id(raw: str | None) -> str:
    if raw is None or raw.strip() == "" or raw.strip().lower() == "tobarra":
        return "tobarra_20240802"
    p = raw.strip()
    if p in CORE_SPATIAL_FIRES:
        return p
    for sid, spec in CORE_SPATIAL_FIRES.items():
        if p in {spec.dem_key, spec.fuel_key, spec.weather_key}:
            return sid
    raise SystemExit(f"unknown --fire {raw!r}; known={list_core_source_ids()} or 'tobarra'")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build fuel map + optional stack update")
    ap.add_argument(
        "--fire",
        type=str,
        default="tobarra",
        help="source_id or dem_key (default tobarra → tobarra_20240802)",
    )
    ap.add_argument("--landcover", type=Path, default=None, help="Local LC GeoTIFF")
    ap.add_argument("--scheme", default="worldcover", help="worldcover|clc|prometheus")
    ap.add_argument("--allow-download", action="store_true")
    ap.add_argument("--allow-synthetic", action="store_true")
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--with-stack", action="store_true", help="Also rebuild fuel_terrain stack")
    ap.add_argument("--dem", type=Path, default=None)
    ap.add_argument("--allow-dem-download", action="store_true")
    ap.add_argument(
        "--resolve-only",
        action="store_true",
        help="Print resolved fuel path if present; exit 0/2 (no download)",
    )
    args = ap.parse_args(argv)

    try:
        source_id = _resolve_source_id(args.fire)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR

    spec = get_fire_spec(source_id)
    cache = args.cache_dir or fuel_dir_for(spec, repo_root=ROOT)
    out = args.out or (ROOT / "outputs" / "fuel_stack" / spec.fuel_key)

    if args.resolve_only:
        existing = resolve_fuel_path(source_id, repo_root=ROOT, explicit=args.landcover)
        payload = {
            "source_id": source_id,
            "fuel_key": spec.fuel_key,
            "cache_dir": str(cache.as_posix()),
            "fuel_path": str(existing.as_posix()) if existing else None,
            "present": existing is not None,
        }
        print(json.dumps(payload, indent=2))
        return EXIT_OK if existing is not None else EXIT_BLOCKED

    bbox = load_bbox_wgs84(source_id, repo_root=ROOT)
    if bbox is None:
        if source_id == "tobarra_20240802":
            bbox = list(TOBARRA_BBOX_WGS84)
        else:
            print(
                f"No dem_manifest bbox for {source_id}; need data/dem/{spec.dem_key}/"
                "dem_manifest.json or pass --landcover on a pre-windowed grid",
                file=sys.stderr,
            )
            if not args.landcover and not args.allow_synthetic:
                return EXIT_BLOCKED
            bbox = list(TOBARRA_BBOX_WGS84)  # last resort for synthetic only
            print("NOTE: using Tobarra bbox fallback for synthetic/local path", file=sys.stderr)

    # Align to DEM grid when available
    dem = None
    ref_shape = None
    ref_transform = None
    dem_path = resolve_dem_path(source_id, repo_root=ROOT, explicit=args.dem)
    dem_cache = ROOT / "data" / "dem" / spec.dem_key
    try:
        dem = resolve_dem(
            bbox_wgs84=tuple(bbox),
            local_path=dem_path,
            cache_dir=dem_cache if dem_cache.is_dir() else None,
            allow_download=bool(args.allow_dem_download),
            allow_synthetic=bool(args.allow_synthetic)
            or (dem_path is None and not args.allow_dem_download and args.landcover is None),
        )
        ref_shape = dem.elevation_m.shape
        ref_transform = dem.transform
    except Exception as exc:  # noqa: BLE001
        print(f"NOTE: DEM resolve skipped ({exc}); fuel map uses own grid", file=sys.stderr)

    try:
        fmap = resolve_fuel_map(
            bbox_wgs84=bbox,
            local_path=args.landcover,
            cache_dir=cache,
            allow_download=bool(args.allow_download),
            allow_synthetic=bool(args.allow_synthetic),
            scheme=args.scheme,
            reference_shape=ref_shape,
            reference_transform=ref_transform,
            cell_size_m=float(dem.cell_size_m) if dem is not None else 25.0,
        )
    except FuelMapUnavailableError as exc:
        # convenience fallback like DEM (Tobarra default path only when no fire override intent)
        if (
            not args.allow_synthetic
            and args.landcover is None
            and not args.allow_download
            and source_id == "tobarra_20240802"
        ):
            print(
                "NOTE: no landcover/cache/download; using synthetic fuel mosaic",
                file=sys.stderr,
            )
            fmap = resolve_fuel_map(
                bbox_wgs84=bbox,
                allow_synthetic=True,
                reference_shape=ref_shape,
                reference_transform=ref_transform,
            )
        else:
            print(f"Fuel map unavailable: {exc}", file=sys.stderr)
            return EXIT_BLOCKED

    # Always write cache under data/fuel_map/<key> when using default cache
    cache.mkdir(parents=True, exist_ok=True)
    # Prefer writing worldcover_window.tif into cache when product came from download/local
    paths = write_fuel_map_geotiffs(fmap, out)
    # Also materialize cache window for re-emit discovery
    try:
        import rasterio

        cache_tif = cache / "worldcover_window.tif"
        if not cache_tif.is_file() or args.allow_download or args.landcover:
            # write landcover into canonical cache name for resolve_fuel_path
            with rasterio.open(
                cache_tif,
                "w",
                driver="GTiff",
                height=fmap.landcover_code.shape[0],
                width=fmap.landcover_code.shape[1],
                count=1,
                dtype="float64",
                crs=fmap.crs,
                transform=fmap.transform,
                compress="deflate",
            ) as dst:
                dst.write(fmap.landcover_code.astype("float64"), 1)
            paths["cache_worldcover"] = str(cache_tif.as_posix())
    except Exception as exc:  # noqa: BLE001
        print(f"NOTE: cache worldcover write skipped ({exc})", file=sys.stderr)

    summary = {
        "source_id": source_id,
        "fuel_key": spec.fuel_key,
        "source": fmap.source,
        "scheme": fmap.scheme,
        "synthetic": fmap.synthetic,
        "fuel_id_dominant": fmap.fuel_id_dominant,
        "fuel_mix": fmap.fuel_mix,
        "shape": list(fmap.landcover_code.shape),
        "bbox_wgs84": bbox,
        "cache_dir": str(cache.as_posix()),
        "paths": paths,
        "resolved_for_reemit": (
            str(p.as_posix())
            if (p := resolve_fuel_path(source_id, repo_root=ROOT)) is not None
            else None
        ),
    }

    if args.with_stack and dem is not None:
        stack = build_stack_from_dem(dem, fuel_map=fmap, fire_id=source_id)
        sp = write_stack(stack, out, save_geotiff=True)
        paths.update(sp)
        summary["stack_fuel_dominant"] = stack.fuel_id_dominant
        summary["stack_fuel_mix"] = stack.fuel_mix
        summary["stack_paths"] = sp

    report = out / "fuel_map_build_report.json"
    out.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWrote {report}", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
