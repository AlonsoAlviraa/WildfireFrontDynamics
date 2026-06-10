"""Auditable GeoTIFF and binary-mask ingestion.

Reading patterns are adapted from ActiveFire's rasterio generator. Hashing,
timestamp inference, and QA manifest patterns are adapted from DetectorDeIncendios.
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.features import shapes

from ..identity import build_observation_id, sha256_of_file
from ..models import FrontObservation, MultiLine

TIFF_EXTENSIONS = {".tif", ".tiff"}


@dataclass(frozen=True)
class GeoTiffIngestRecord:
    source_path: str
    mask_path: str
    source_sha256: str
    observed_at: str
    status: str
    reason: str
    crs: str
    coordinate_system: str
    resolution_m: float | None
    method: str
    component_count: int


@dataclass(frozen=True)
class GeoTiffIngestResult:
    observations: tuple[FrontObservation, ...]
    records: tuple[GeoTiffIngestRecord, ...]


def infer_timestamp(path: Path) -> str:
    """Infer UTC timestamp from common filenames without inventing one."""

    stem = path.stem
    match = re.search(r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})", stem)
    if match:
        values = match.groups()
        return f"{values[0]}-{values[1]}-{values[2]}T{values[3]}:{values[4]}:{values[5]}Z"
    match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})[T_-](\d{2})[-_:](\d{2})[-_:](\d{2})", stem)
    if match:
        values = match.groups()
        return f"{values[0]}-{values[1]}-{values[2]}T{values[3]}:{values[4]}:{values[5]}Z"
    match = re.search(r"(?:^|_)(\d{10})(?:_|$)", stem)
    if match:
        return datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return ""


def _coordinate_system(crs: rasterio.crs.CRS | None) -> str:
    if crs is None:
        return "unknown"
    return "projected_metric" if crs.is_projected else "geographic"


def _resolution_m(dataset: rasterio.io.DatasetReader) -> float | None:
    if not dataset.crs or not dataset.crs.is_projected:
        return None
    return float((abs(dataset.transform.a) + abs(dataset.transform.e)) / 2.0)


def _has_georeferencing(dataset: rasterio.io.DatasetReader) -> bool:
    return dataset.crs is not None and dataset.transform != Affine.identity()


def read_raster_band(path: Path, band: int) -> tuple[np.ndarray, dict[str, object]]:
    """Read one native-dtype band and metadata without radiometric conversion."""

    with rasterio.open(path) as dataset:
        if band < 1 or band > dataset.count:
            raise ValueError(f"band {band} outside valid range 1..{dataset.count}")
        array = dataset.read(band)
        metadata = {
            "width": dataset.width,
            "height": dataset.height,
            "count": dataset.count,
            "dtype": dataset.dtypes[band - 1],
            "crs": dataset.crs,
            "transform": dataset.transform,
            "resolution_m": _resolution_m(dataset),
            "coordinate_system": _coordinate_system(dataset.crs),
            "has_georeferencing": _has_georeferencing(dataset),
        }
    return array, metadata


def segment_band_threshold(image: np.ndarray, threshold: float) -> np.ndarray:
    """Deterministic hot-region candidate baseline; not a validated active front."""

    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    return np.asarray(image > threshold, dtype=np.uint8)


def read_binary_mask(path: Path) -> tuple[np.ndarray, dict[str, object]]:
    mask, metadata = read_raster_band(path, 1)
    return np.asarray(mask > 0, dtype=np.uint8), metadata


def extract_mask_components(mask: np.ndarray, transform: Affine) -> MultiLine:
    """Extract exterior rings in raster coordinates transformed to source CRS."""

    components: list[tuple[tuple[float, float], ...]] = []
    for geometry, value in shapes(mask.astype(np.uint8), mask=mask.astype(bool), transform=transform):
        if int(value) != 1:
            continue
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            exterior = tuple((float(x), float(y)) for x, y in polygon[0])
            if len(exterior) >= 4:
                components.append(exterior)
    return tuple(components)


def _find_mask(image: Path, masks_dir: Path) -> Path | None:
    exact = masks_dir / image.name
    if exact.exists():
        return exact
    matches = [path for path in masks_dir.glob(f"{image.stem}.*") if path.suffix.lower() in TIFF_EXTENSIONS]
    return sorted(matches)[0] if matches else None


def _record(
    source: Path,
    mask: Path | None,
    digest: str,
    observed_at: str,
    status: str,
    reason: str,
    metadata: dict[str, object] | None,
    method: str,
    component_count: int = 0,
) -> GeoTiffIngestRecord:
    crs = str(metadata.get("crs") or "") if metadata else ""
    coordinate_system = str(metadata.get("coordinate_system") or "unknown") if metadata else "unknown"
    resolution = metadata.get("resolution_m") if metadata else None
    return GeoTiffIngestRecord(
        source_path=str(source),
        mask_path=str(mask) if mask else "",
        source_sha256=digest,
        observed_at=observed_at,
        status=status,
        reason=reason,
        crs=crs,
        coordinate_system=coordinate_system,
        resolution_m=float(resolution) if resolution is not None else None,
        method=method,
        component_count=component_count,
    )


def write_ingest_manifest(records: tuple[GeoTiffIngestRecord, ...], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(GeoTiffIngestRecord.__dataclass_fields__.keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def ingest_geotiff_sequence(
    images_dir: Path,
    *,
    masks_dir: Path | None,
    event_id: str,
    sensor_id: str,
    estimated_error_m: float,
    band: int = 1,
    threshold: float | None = None,
) -> GeoTiffIngestResult:
    """Validate GeoTIFF inputs and convert accepted masks to observations."""

    if estimated_error_m < 0:
        raise ValueError("estimated_error_m cannot be negative")
    if not images_dir.is_dir():
        raise ValueError(f"images directory does not exist: {images_dir}")
    if masks_dir is not None and not masks_dir.is_dir():
        raise ValueError(f"masks directory does not exist: {masks_dir}")
    if masks_dir is None and threshold is None:
        raise ValueError("threshold is required when masks_dir is not provided")

    image_paths = sorted(path for path in images_dir.iterdir() if path.suffix.lower() in TIFF_EXTENSIONS)
    if not image_paths:
        raise ValueError(f"no GeoTIFF images found in {images_dir}")

    records: list[GeoTiffIngestRecord] = []
    candidates: list[tuple[str, FrontObservation]] = []
    for image_path in image_paths:
        digest = sha256_of_file(image_path)
        observed_at = infer_timestamp(image_path)
        mask_path = _find_mask(image_path, masks_dir) if masks_dir else None
        method = "provided_binary_mask" if masks_dir else f"band_{band}_threshold_{threshold}"
        try:
            image, image_meta = read_raster_band(image_path, band)
        except Exception as exc:  # noqa: BLE001
            records.append(_record(image_path, mask_path, digest, observed_at, "rejected", f"image_read_error:{exc}", None, method))
            continue
        if not image_meta["has_georeferencing"]:
            records.append(_record(image_path, mask_path, digest, observed_at, "rejected", "missing_crs_or_transform", image_meta, method))
            continue
        if not observed_at:
            records.append(_record(image_path, mask_path, digest, observed_at, "review", "missing_timestamp", image_meta, method))
            continue

        if masks_dir:
            if mask_path is None:
                records.append(_record(image_path, None, digest, observed_at, "rejected", "mask_not_found", image_meta, method))
                continue
            try:
                binary_mask, mask_meta = read_binary_mask(mask_path)
            except Exception as exc:  # noqa: BLE001
                records.append(_record(image_path, mask_path, digest, observed_at, "rejected", f"mask_read_error:{exc}", image_meta, method))
                continue
            if (image_meta["width"], image_meta["height"]) != (mask_meta["width"], mask_meta["height"]):
                records.append(_record(image_path, mask_path, digest, observed_at, "rejected", "mask_dimensions_mismatch", image_meta, method))
                continue
            if image_meta["transform"] != mask_meta["transform"] or image_meta["crs"] != mask_meta["crs"]:
                records.append(_record(image_path, mask_path, digest, observed_at, "rejected", "mask_georeferencing_mismatch", image_meta, method))
                continue
        else:
            binary_mask = segment_band_threshold(image, float(threshold))

        if not np.any(binary_mask):
            records.append(_record(image_path, mask_path, digest, observed_at, "rejected", "empty_mask", image_meta, method))
            continue
        components = extract_mask_components(binary_mask, image_meta["transform"])  # type: ignore[arg-type]
        if not components:
            records.append(_record(image_path, mask_path, digest, observed_at, "rejected", "no_exterior_components", image_meta, method))
            continue

        limitations = (
            "mask_boundary_is_not_validated_active_flame_front",
            "real_geometry_speed_estimator_not_implemented",
        )
        observation = FrontObservation(
            observation_id=build_observation_id(event_id, sensor_id, observed_at, digest),
            event_id=event_id,
            sensor_id=sensor_id,
            time_s=0.0,
            observed_at=observed_at,
            components=components,
            estimated_error_m=estimated_error_m,
            crs=str(image_meta["crs"]),
            coordinate_system=str(image_meta["coordinate_system"]),
            resolution_m=image_meta["resolution_m"],  # type: ignore[arg-type]
            source_uri=str(image_path),
            source_sha256=digest,
            method=method,
            limitations=limitations,
        )
        candidates.append((observed_at, observation))
        records.append(_record(image_path, mask_path, digest, observed_at, "accepted", "", image_meta, method, len(components)))

    observations: list[FrontObservation] = []
    if candidates:
        candidates.sort(key=lambda item: item[0])
        start = datetime.fromisoformat(candidates[0][0].replace("Z", "+00:00"))
        for observed_at, item in candidates:
            current = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            observations.append(
                FrontObservation(
                    **{**asdict(item), "time_s": (current - start).total_seconds()}
                )
            )
    return GeoTiffIngestResult(tuple(observations), tuple(records))
