"""Prepare real wildfire GeoTIFF overlays for the metric ingest pipeline.

The raw provider files remain untouched. This script filters a real extracted
folder, reprojects selected GeoTIFFs to a projected metric CRS, and writes a
flat sequence that can be passed to ``wildfire-front ingest-geotiff``.

A reprojection manifest (CSV) is optionally written alongside the output. Each
row records the source path, its SHA-256, the destination path, the source and
destination CRS, the nominal resolution, the inferred timestamp and the sensor
label, so every produced file is fully traceable to its raw origin.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
from dataclasses import asdict, dataclass
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from wildfire_front.identity import sha256_of_file
from wildfire_front.ingestion.geotiff import infer_timestamp


@dataclass(frozen=True)
class ReprojectManifestRow:
    """One row in the reprojection manifest."""

    source_path: str
    source_sha256: str
    destination_path: str
    source_crs: str
    destination_crs: str
    resolution_m: float
    resampling: str
    timestamp_utc: str
    sensor: str
    width: int
    height: int


def _resampling(name: str) -> Resampling:
    try:
        return Resampling[name]
    except KeyError as exc:
        valid = ", ".join(item.name for item in Resampling)
        raise ValueError(f"unknown resampling '{name}'. Valid values: {valid}") from exc


def _classify_sensor(path: Path) -> str:
    name = path.name.upper()
    if "_LWIR" in name:
        return "LWIR"
    if "_HD-EO" in name or "_HD_EO" in name:
        return "HD-EO"
    return "UNKNOWN"


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
) -> tuple[str, int, int]:
    """Reproject a GeoTIFF. Returns (source_crs, width, height) of the output."""
    if destination.exists() and not overwrite:
        with rasterio.open(destination) as existing:
            return str(existing.crs), existing.width, existing.height
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
        return str(dataset.crs), width, height


def write_reproject_manifest(rows: list[ReprojectManifestRow], output: Path) -> None:
    """Write the reprojection manifest to a CSV file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(ReprojectManifestRow.__dataclass_fields__.keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


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
    manifest_path: Path | None = None,
) -> list[Path]:
    """Reproject selected GeoTIFFs and optionally write a reprojection manifest.

    When ``manifest_path`` is provided, a CSV manifest is written recording the
    source path, SHA-256, destination path, CRS pair, resolution, timestamp and
    sensor for every produced file, enabling full provenance traceability.
    """
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    paths = selected_geotiffs(source, pattern)
    if limit is not None:
        paths = paths[:limit]
    if not paths:
        raise ValueError(f"no GeoTIFF files matching {pattern!r} in {source}")
    written: list[Path] = []
    manifest_rows: list[ReprojectManifestRow] = []
    for path in paths:
        destination = output / path.name
        source_crs, width, height = reproject_geotiff(
            path,
            destination,
            dst_crs=dst_crs,
            resolution_m=resolution_m,
            resampling=resampling,
            overwrite=overwrite,
        )
        written.append(destination)
        if manifest_path is not None:
            manifest_rows.append(
                ReprojectManifestRow(
                    source_path=str(path),
                    source_sha256=sha256_of_file(path),
                    destination_path=str(destination),
                    source_crs=source_crs,
                    destination_crs=dst_crs,
                    resolution_m=resolution_m,
                    resampling=resampling.name,
                    timestamp_utc=infer_timestamp(path),
                    sensor=_classify_sensor(path),
                    width=width,
                    height=height,
                )
            )
    if manifest_path is not None and manifest_rows:
        write_reproject_manifest(manifest_rows, manifest_path)
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
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional CSV manifest path recording source provenance for each output file.",
    )
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
        manifest_path=args.manifest,
    )
    print(f"wrote {len(written)} projected GeoTIFFs to {args.output}")
    if args.manifest:
        print(f"wrote reprojection manifest to {args.manifest}")


if __name__ == "__main__":
    main()