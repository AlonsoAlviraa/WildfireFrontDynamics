#!/usr/bin/env python3
"""Build landcover → fuel map for Tobarra (ESA WorldCover or local GeoTIFF).

Usage:
  python scripts/build_fuel_map.py --allow-download
  python scripts/build_fuel_map.py --landcover path/to/clc.tif --scheme clc
  python scripts/build_fuel_map.py --allow-synthetic
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
from wildfire_front.fuel.stack import build_stack_from_dem, write_stack  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Build fuel map + optional stack update")
    ap.add_argument("--landcover", type=Path, default=None, help="Local LC GeoTIFF")
    ap.add_argument("--scheme", default="worldcover", help="worldcover|clc|prometheus")
    ap.add_argument("--allow-download", action="store_true")
    ap.add_argument("--allow-synthetic", action="store_true")
    ap.add_argument("--cache-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--with-stack", action="store_true", help="Also rebuild fuel_terrain stack")
    ap.add_argument("--dem", type=Path, default=None)
    ap.add_argument("--allow-dem-download", action="store_true")
    args = ap.parse_args()

    cache = args.cache_dir or (ROOT / "data" / "fuel_map" / "tobarra")
    out = args.out or (ROOT / "outputs" / "fuel_stack" / "tobarra")

    # Align to DEM grid when available
    dem = None
    ref_shape = None
    ref_transform = None
    dem_cache = ROOT / "data" / "dem" / "tobarra"
    try:
        dem = resolve_dem(
            bbox_wgs84=TOBARRA_BBOX_WGS84,
            local_path=args.dem,
            cache_dir=dem_cache if dem_cache.is_dir() else None,
            allow_download=bool(args.allow_dem_download),
            allow_synthetic=bool(args.allow_synthetic) or (
                args.dem is None and not args.allow_dem_download
            ),
        )
        ref_shape = dem.elevation_m.shape
        ref_transform = dem.transform
    except Exception as exc:
        print(f"NOTE: DEM resolve skipped ({exc}); fuel map uses own grid", file=sys.stderr)

    try:
        fmap = resolve_fuel_map(
            bbox_wgs84=TOBARRA_BBOX_WGS84,
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
        # convenience fallback like DEM
        if not args.allow_synthetic and args.landcover is None and not args.allow_download:
            print(
                "NOTE: no landcover/cache/download; using synthetic fuel mosaic",
                file=sys.stderr,
            )
            fmap = resolve_fuel_map(
                bbox_wgs84=TOBARRA_BBOX_WGS84,
                allow_synthetic=True,
                reference_shape=ref_shape,
                reference_transform=ref_transform,
            )
        else:
            print(f"Fuel map unavailable: {exc}", file=sys.stderr)
            return 3

    paths = write_fuel_map_geotiffs(fmap, out)
    summary = {
        "source": fmap.source,
        "scheme": fmap.scheme,
        "synthetic": fmap.synthetic,
        "fuel_id_dominant": fmap.fuel_id_dominant,
        "fuel_mix": fmap.fuel_mix,
        "shape": list(fmap.landcover_code.shape),
        "paths": paths,
    }

    if args.with_stack and dem is not None:
        stack = build_stack_from_dem(dem, fuel_map=fmap)
        sp = write_stack(stack, out, save_geotiff=True)
        paths.update(sp)
        summary["stack_fuel_dominant"] = stack.fuel_id_dominant
        summary["stack_fuel_mix"] = stack.fuel_mix
        summary["stack_paths"] = sp

    report = out / "fuel_map_build_report.json"
    report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWrote {report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
