"""Frame-manifest builder and quality gates for real wildfire data.

This module converts a raw extracted real-if folder (GeoTIFF + KML/KMZ + JPG + PNG)
into a structured, auditable frame manifest with one row per (timestamp, sensor).

Design principles:
- Real observations are never treated as ground truth.
- Every row carries provenance (source_sha256) and QA gates.
- CRS metric checks are explicit: speeds/areas require projected CRS.
- Temporal gaps and duplicates are flagged, never silently interpolated.
"""

from __future__ import annotations

import csv
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from .identity import sha256_of_file
from .ingestion.geotiff import _coordinate_system, infer_timestamp

# -- Constants ---------------------------------------------------------------

MIN_ALPHA_FRACTION = 0.05
GAP_THRESHOLD_S = 300.0  # 5 minutes
EARTH_RADIUS_M = 6_378_137.0

SENSOR_PATTERNS: list[tuple[str, str]] = [
    ("LWIR", r"_LWIR(?:_|\.|$)"),
    ("HD-EO", r"_HD-EO(?:_|\.|$)"),
]

# Supported file extensions
TIFF_EXTENSIONS = {".tif", ".tiff"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
KML_EXTENSIONS = {".kml"}
KMZ_EXTENSIONS = {".kmz"}
ALL_EXTENSIONS = TIFF_EXTENSIONS | IMAGE_EXTENSIONS | KML_EXTENSIONS | KMZ_EXTENSIONS

# -- Dataclasses -------------------------------------------------------------


@dataclass(frozen=True)
class FrameManifestRow:
    """One row in the frame manifest: a single (timestamp, sensor) observation."""

    event_id: str
    timestamp_utc: str
    sensor: str
    geotiff_path: str
    jpg_path: str
    raw_jpg_path: str
    kml_path: str
    kmz_path: str
    window_path: str
    width: int
    height: int
    band_count: int
    dtype: str
    crs: str
    coordinate_system: str
    bbox_west: float
    bbox_south: float
    bbox_east: float
    bbox_north: float
    latlon_quad: str
    resolution_estimate_m: float | None
    alpha_valid_fraction: float | None
    source_sha256: str
    qa_status: str
    qa_reasons: str


@dataclass(frozen=True)
class TemporalGap:
    """A temporal gap between two consecutive timestamps exceeding a threshold."""

    from_timestamp: str
    to_timestamp: str
    gap_seconds: float


@dataclass(frozen=True)
class FrameManifestResult:
    """Full output of manifest building: rows, gaps, duplicates, summary."""

    rows: tuple[FrameManifestRow, ...]
    gaps: tuple[TemporalGap, ...]
    duplicate_timestamps: tuple[tuple[str, str], ...]
    summary: dict[str, str | int | float]


# -- Sensor classification ---------------------------------------------------


def classify_sensor(path: Path) -> str:
    """Return 'LWIR', 'HD-EO', or 'UNKNOWN' based on filename."""
    name = path.name.upper()
    for label, pattern in SENSOR_PATTERNS:
        if re.search(pattern, name):
            return label
    return "UNKNOWN"


# -- GeoTIFF metadata reading ------------------------------------------------


def read_geotiff_info(path: Path) -> dict[str, object]:
    """Read geospatial metadata from a GeoTIFF without loading the full raster."""
    with rasterio.open(path) as dataset:
        bounds = dataset.bounds
        transform = dataset.transform
        crs = dataset.crs
        coordinate_system = _coordinate_system(crs)
        band_count = dataset.count
        dtype = str(dataset.dtypes[0]) if dataset.dtypes else ""

        alpha_valid_fraction: float | None = None
        if band_count >= 4:
            alpha = dataset.read(4, out_shape=(min(dataset.height, 256), min(dataset.width, 256)))
            alpha_valid_fraction = float(np.mean(alpha > 0))

        resolution_estimate_m = _estimate_resolution_m(crs, transform, bounds)

        return {
            "width": dataset.width,
            "height": dataset.height,
            "band_count": band_count,
            "dtype": dtype,
            "crs": str(crs) if crs else "",
            "coordinate_system": coordinate_system,
            "bbox": (
                float(bounds.left),
                float(bounds.bottom),
                float(bounds.right),
                float(bounds.top),
            ),
            "transform": transform,
            "resolution_estimate_m": resolution_estimate_m,
            "alpha_valid_fraction": alpha_valid_fraction,
        }


def _estimate_resolution_m(
    crs: rasterio.crs.CRS | None,
    transform: Affine,
    bounds: rasterio.coords.BoundingBox,
) -> float | None:
    """Estimate pixel resolution in meters for both projected and geographic CRS."""
    if crs is None:
        return None
    pixel_x = abs(transform.a)
    pixel_y = abs(transform.e)
    if crs.is_projected:
        return float((pixel_x + pixel_y) / 2.0)
    center_lat = math.radians((bounds.bottom + bounds.top) / 2.0)
    meters_per_deg_lat = math.pi * EARTH_RADIUS_M / 180.0
    meters_per_deg_lon = meters_per_deg_lat * abs(math.cos(center_lat))
    return float((pixel_x * meters_per_deg_lon + pixel_y * meters_per_deg_lat) / 2.0)


# -- KML parsing -------------------------------------------------------------


def parse_kml_metadata(path: Path) -> dict[str, str]:
    """Extract LatLonQuad, camera position and timestamp from a KML file."""
    info: dict[str, str] = {
        "latlon_quad": "",
        "camera_lon": "",
        "camera_lat": "",
        "camera_alt": "",
        "timestamp": "",
    }
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return info
    root = tree.getroot()

    for elem in root.iter():
        tag = _strip_namespace(elem.tag)

        if tag == "LatLonQuad":
            for child in elem:
                if _strip_namespace(child.tag) == "coordinates" and child.text:
                    info["latlon_quad"] = child.text.strip()

        if tag == "Camera":
            for child in elem:
                child_tag = _strip_namespace(child.tag)
                if child_tag in ("longitude", "latitude", "altitude") and child.text:
                    key = "camera_" + child_tag[:3]
                    info[key] = child.text.strip()
                if child_tag == "TimeStamp":
                    for ts_child in child:
                        if _strip_namespace(ts_child.tag) == "when" and ts_child.text:
                            info["timestamp"] = ts_child.text.strip()
    return info


def _strip_namespace(tag: str) -> str:
    """Remove XML namespace prefix from a tag name."""
    return tag.split("}")[-1] if "}" in tag else tag


# -- Quality gates -----------------------------------------------------------


def assess_frame_quality(
    *,
    timestamp_utc: str,
    crs: str,
    coordinate_system: str,
    alpha_valid_fraction: float | None,
    bbox: tuple[float, float, float, float] | None,
    resolution_estimate_m: float | None,
) -> tuple[str, list[str]]:
    """Assess a frame's quality and return (qa_status, qa_reasons).

    qa_status is 'ok', 'review', or 'rejected'.
    Hard blockers (missing CRS/timestamp) cause rejection.
    Soft issues (non-metric CRS, low alpha) cause review.
    """
    reasons: list[str] = []

    if not timestamp_utc:
        reasons.append("missing_timestamp")
    if not crs:
        reasons.append("missing_crs")
    elif coordinate_system != "projected_metric":
        reasons.append("crs_not_projected_metric")

    if alpha_valid_fraction is not None and alpha_valid_fraction < MIN_ALPHA_FRACTION:
        reasons.append("alpha_almost_empty")

    if resolution_estimate_m is not None and resolution_estimate_m <= 0:
        reasons.append("invalid_resolution")

    if bbox is not None:
        west, south, east, north = bbox
        if west >= east or south >= north:
            reasons.append("invalid_bbox")
        # Longitude/latitude range checks only apply to geographic CRS.
        # Projected metric CRS use metre-based coordinates outside [-180, 180].
        if coordinate_system == "geographic":
            if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
                reasons.append("bbox_longitude_out_of_range")
            if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
                reasons.append("bbox_latitude_out_of_range")

    if not reasons:
        return "ok", []

    hard_blockers = {"missing_crs"}
    if any(r in hard_blockers for r in reasons):
        return "rejected", reasons
    return "review", reasons


# -- Manifest building -------------------------------------------------------


def _group_files_by_key(source: Path) -> dict[tuple[str, str], dict[str, Path]]:
    """Scan recursively and group files by (timestamp, sensor).

    Returns a dict mapping (timestamp, sensor) to a dict of file_type -> Path
    where file_type is one of 'geotiff', 'jpg', 'raw_jpg', 'kml', 'kmz', 'window'.
    """
    grouped: dict[tuple[str, str], dict[str, Path]] = {}

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in ALL_EXTENSIONS:
            continue

        timestamp = infer_timestamp(path)
        sensor = classify_sensor(path)
        name_lower = path.name.lower()

        if ext in TIFF_EXTENSIONS:
            file_type = "geotiff"
        elif ext in KML_EXTENSIONS:
            file_type = "kml"
        elif ext in KMZ_EXTENSIONS:
            file_type = "kmz"
        elif "_raw" in name_lower:
            file_type = "raw_jpg"
        elif ext in (".jpg", ".jpeg") and sensor != "UNKNOWN":
            file_type = "jpg"
        elif ext == ".png":
            file_type = "window"
            sensor = "WINDOW"
        else:
            file_type = "jpg"

        key = (timestamp, sensor)
        if key not in grouped:
            grouped[key] = {}
        grouped[key][file_type] = path

    return grouped


def build_frame_manifest(source: Path, event_id: str) -> FrameManifestResult:
    """Build a complete frame manifest from an extracted real-if folder.

    Scans recursively for GeoTIFF, KML, KMZ, JPG and PNG files, groups them
    by (timestamp, sensor), reads metadata, applies quality gates, and
    computes temporal gaps and duplicate timestamps.
    """
    if not source.is_dir():
        raise ValueError("source directory does not exist: " + str(source))

    grouped = _group_files_by_key(source)
    if not grouped:
        raise ValueError("source directory contains no recognised files: " + str(source))
    rows: list[FrameManifestRow] = []

    for (timestamp, sensor), files in sorted(grouped.items()):
        window_path = files.get("window", "")
        if not window_path:
            for (ts, _), other_files in grouped.items():
                if ts == timestamp and "window" in other_files:
                    window_path = other_files["window"]
                    break

        geotiff_path = files.get("geotiff")
        geotiff_info: dict[str, object] = {}
        if geotiff_path:
            try:
                geotiff_info = read_geotiff_info(geotiff_path)
            except Exception:
                geotiff_info = {}

        kml_path = files.get("kml")
        kml_info: dict[str, str] = {}
        if kml_path:
            kml_info = parse_kml_metadata(kml_path)

        bbox = geotiff_info.get("bbox") if geotiff_info else None
        crs = str(geotiff_info.get("crs", "")) if geotiff_info else ""
        coordinate_system = (
            str(geotiff_info.get("coordinate_system", "unknown")) if geotiff_info else "unknown"
        )
        alpha_frac = geotiff_info.get("alpha_valid_fraction") if geotiff_info else None
        resolution = geotiff_info.get("resolution_estimate_m") if geotiff_info else None

        qa_status, qa_reasons = assess_frame_quality(
            timestamp_utc=timestamp,
            crs=crs,
            coordinate_system=coordinate_system,
            alpha_valid_fraction=alpha_frac if isinstance(alpha_frac, float) else None,
            bbox=bbox if isinstance(bbox, tuple) else None,
            resolution_estimate_m=resolution if isinstance(resolution, float) else None,
        )

        sha = ""
        if geotiff_path:
            sha = sha256_of_file(geotiff_path)

        west = south = east = north = 0.0
        if isinstance(bbox, tuple) and len(bbox) == 4:
            west, south, east, north = (float(v) for v in bbox)

        _width = geotiff_info.get("width")
        _height = geotiff_info.get("height")
        _bands = geotiff_info.get("band_count")

        rows.append(
            FrameManifestRow(
                event_id=event_id,
                timestamp_utc=timestamp,
                sensor=sensor,
                geotiff_path=str(geotiff_path) if geotiff_path else "",
                jpg_path=str(files.get("jpg", "")),
                raw_jpg_path=str(files.get("raw_jpg", "")),
                kml_path=str(kml_path) if kml_path else "",
                kmz_path=str(files.get("kmz", "")),
                window_path=str(window_path) if window_path else "",
                width=int(_width) if isinstance(_width, int) else 0,
                height=int(_height) if isinstance(_height, int) else 0,
                band_count=int(_bands) if isinstance(_bands, int) else 0,
                dtype=str(geotiff_info.get("dtype", "")),
                crs=crs,
                coordinate_system=coordinate_system,
                bbox_west=west,
                bbox_south=south,
                bbox_east=east,
                bbox_north=north,
                latlon_quad=kml_info.get("latlon_quad", ""),
                resolution_estimate_m=resolution if isinstance(resolution, float) else None,
                alpha_valid_fraction=alpha_frac if isinstance(alpha_frac, float) else None,
                source_sha256=sha,
                qa_status=qa_status,
                qa_reasons=";".join(qa_reasons),
            )
        )

    gaps = compute_temporal_gaps(rows, GAP_THRESHOLD_S)
    duplicates = find_duplicate_timestamps(rows)
    summary = _build_summary(rows, gaps, duplicates)
    return FrameManifestResult(
        rows=tuple(rows),
        gaps=tuple(gaps),
        duplicate_timestamps=tuple(duplicates),
        summary=summary,
    )


# -- Temporal analysis -------------------------------------------------------


def compute_temporal_gaps(
    rows: list[FrameManifestRow] | tuple[FrameManifestRow, ...],
    threshold_s: float = GAP_THRESHOLD_S,
) -> list[TemporalGap]:
    """Detect temporal gaps exceeding threshold between consecutive timestamps."""
    gaps: list[TemporalGap] = []
    by_sensor: dict[str, list[str]] = {}
    for row in rows:
        if row.timestamp_utc and row.sensor != "UNKNOWN":
            by_sensor.setdefault(row.sensor, []).append(row.timestamp_utc)

    for _sensor, timestamps in by_sensor.items():
        unique_sorted = sorted(set(timestamps))
        for i in range(1, len(unique_sorted)):
            try:
                prev_str = unique_sorted[i - 1].replace("Z", "+00:00")
                curr_str = unique_sorted[i].replace("Z", "+00:00")
                prev_dt = datetime.fromisoformat(prev_str)
                curr_dt = datetime.fromisoformat(curr_str)
            except ValueError:
                continue
            delta = (curr_dt - prev_dt).total_seconds()
            if delta > threshold_s:
                gaps.append(
                    TemporalGap(
                        from_timestamp=unique_sorted[i - 1],
                        to_timestamp=unique_sorted[i],
                        gap_seconds=delta,
                    )
                )
    return sorted(gaps, key=lambda g: g.from_timestamp)


def find_duplicate_timestamps(
    rows: list[FrameManifestRow] | tuple[FrameManifestRow, ...],
) -> list[tuple[str, str]]:
    """Find (timestamp, sensor) pairs that appear more than once."""
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row.timestamp_utc, row.sensor)
        counts[key] = counts.get(key, 0) + 1
    return [(ts, sensor) for (ts, sensor), count in counts.items() if count > 1]


def _build_summary(
    rows: list[FrameManifestRow] | tuple[FrameManifestRow, ...],
    gaps: list[TemporalGap] | tuple[TemporalGap, ...],
    duplicates: list[tuple[str, str]] | tuple[tuple[str, str], ...],
) -> dict[str, str | int | float]:
    """Build a summary dict for the manifest."""
    total = len(rows)
    ok_count = sum(1 for r in rows if r.qa_status == "ok")
    review_count = sum(1 for r in rows if r.qa_status == "review")
    rejected_count = sum(1 for r in rows if r.qa_status == "rejected")

    sensors = sorted({r.sensor for r in rows if r.sensor != "UNKNOWN"})
    timestamps = sorted({r.timestamp_utc for r in rows if r.timestamp_utc})

    duration_s = 0.0
    if len(timestamps) >= 2:
        try:
            start_str = timestamps[0].replace("Z", "+00:00")
            end_str = timestamps[-1].replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            duration_s = (end_dt - start_dt).total_seconds()
        except ValueError:
            pass

    return {
        "total_rows": total,
        "qa_ok": ok_count,
        "qa_review": review_count,
        "qa_rejected": rejected_count,
        "sensors": ";".join(sensors),
        "unique_timestamps": len(timestamps),
        "gaps_above_threshold": len(gaps),
        "duplicate_timestamp_sensor_pairs": len(duplicates),
        "duration_s": duration_s,
    }


# -- Output writers ----------------------------------------------------------


def write_frame_manifest(rows: tuple[FrameManifestRow, ...], output: Path) -> None:
    """Write frame manifest rows to a CSV file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(FrameManifestRow.__dataclass_fields__.keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_manifest_summary(result: FrameManifestResult, output: Path) -> None:
    """Write a human-readable summary of the manifest to a text file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Frame manifest summary",
        "# Generated: " + datetime.now(UTC).isoformat(),
        "",
        "Total rows:          " + str(result.summary["total_rows"]),
        "QA ok:               " + str(result.summary["qa_ok"]),
        "QA review:           " + str(result.summary["qa_review"]),
        "QA rejected:         " + str(result.summary["qa_rejected"]),
        "Sensors:             " + str(result.summary["sensors"]),
        "Unique timestamps:   " + str(result.summary["unique_timestamps"]),
        "Duration (s):        " + str(result.summary["duration_s"]),
        "Gaps > "
        + str(int(GAP_THRESHOLD_S))
        + "s:       "
        + str(result.summary["gaps_above_threshold"]),
        "Duplicate ts/sensor: " + str(result.summary["duplicate_timestamp_sensor_pairs"]),
        "",
    ]
    if result.gaps:
        lines.append("Temporal gaps:")
        for gap in result.gaps:
            line = (
                "  "
                + gap.from_timestamp
                + " -> "
                + gap.to_timestamp
                + "  ("
                + str(round(gap.gap_seconds, 1))
                + " s)"
            )
            lines.append(line)
        lines.append("")

    if result.duplicate_timestamps:
        lines.append("Duplicate (timestamp, sensor) pairs:")
        for ts, sensor in result.duplicate_timestamps:
            lines.append("  " + ts + "  " + sensor)
        lines.append("")

    reason_counts: dict[str, int] = {}
    for row in result.rows:
        if row.qa_reasons:
            for reason in row.qa_reasons.split(";"):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
    if reason_counts:
        lines.append("QA reason breakdown:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append("  " + reason + ": " + str(count))

    output.write_text("\n".join(lines), encoding="utf-8")
