"""Prepare real wildfire GeoTIFF overlays for the metric ingest pipeline.

The raw provider files remain untouched. This script filters a real extracted
folder, reprojects selected GeoTIFFs to a projected metric CRS, and writes a
flat sequence that can be passed to ``wildfire-front ingest-geotiff``.
"""

from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject


def _resampling(name: str) -> Resampling:
    try:
        return Resampling[name]
    except KeyError as exc:
        valid = ", ".join(item.name for item in Resampling)
        raise ValueError(f"unknown resampling '{name}'. Valid values: {valid}") from exc


def selected_geotiffs(source: Path, pattern: str) -> list[Path]:
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    return sorted(
        path
        for path in source.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".tif", ".tiff"}
        and fnmatch.fnmatch(path.name, pattern)
    )


def reproject_geotiff(
    source: Path,
    destination: Path,
    *,
    dst_crs: str,
    resolution_m: float,
    resampling: Resampling,
    overwrite: bool,
) -> None:
    if destination.exists() and not overwrite:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source) as dataset:
        if dataset.crs is None:
            raise ValueError(f"cannot reproject file without CRS: {source}")
        transform, width, height = calculate_default_transform(
            dataset.crs,
            dst_crs,
            dataset.width,
            dataset.height,
            *dataset.bounds,
            resolution=(resolution_m, resolution_m),
        )
        profile = dataset.profile.copy()
        profile.update(crs=dst_crs, transform=transform, width=width, height=height)
        with rasterio.open(destination, "w", **profile) as target:
            for band in range(1, dataset.count + 1):
                reproject(
                    source=rasterio.band(dataset, band),
                    destination=rasterio.band(target, band),
                    src_transform=dataset.transform,
                    src_crs=dataset.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=resampling,
                )


def prepare_sequence(
    source: Path,
    output: Path,
    *,
    pattern: str,
    dst_crs: str,
    resolution_m: float,
    resampling: Resampling,
    overwrite: bool = False,
    limit: int | None = None,
) -> list[Path]:
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    paths = selected_geotiffs(source, pattern)
    if limit is not None:
        paths = paths[:limit]
    if not paths:
        raise ValueError(f"no GeoTIFF files matching {pattern!r} in {source}")
    written: list[Path] = []
    for path in paths:
        destination = output / path.name
        reproject_geotiff(
            path,
            destination,
            dst_crs=dst_crs,
            resolution_m=resolution_m,
            resampling=resampling,
            overwrite=overwrite,
        )
        written.append(destination)
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare real IF GeoTIFFs for metric ingestion.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pattern", default="*_LWIR.tif")
    parser.add_argument("--dst-crs", default="EPSG:32630")
    parser.add_argument("--resolution-m", type=float, default=0.5)
    parser.add_argument("--resampling", default="nearest")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    written = prepare_sequence(
        args.source,
        args.output,
        pattern=args.pattern,
        dst_crs=args.dst_crs,
        resolution_m=args.resolution_m,
        resampling=_resampling(args.resampling),
        overwrite=args.overwrite,
        limit=args.limit,
    )
    print(f"wrote {len(written)} projected GeoTIFFs to {args.output}")


if __name__ == "__main__":
    main()
