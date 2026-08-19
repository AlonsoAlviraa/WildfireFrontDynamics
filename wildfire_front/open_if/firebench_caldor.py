"""Materialize the FireBench Caldor KML progression as an auditable label pack.

The source KMLs contain many polygon components per timestamp.  This bridge
keeps those raw observations and also emits an explicitly derived cumulative
union for models whose target is a monotonic burned-area mask.  It does not
turn the benchmark polygons into imagery, operational ROS, or product truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping
from shapely.ops import transform, unary_union

from .external_ros import parse_caldor_kml_timestamp

SCHEMA = "wfd_firebench_caldor_label_pack_v1"
PAIR_SCHEMA = "wfd_firebench_caldor_pairs_v1"
DEFAULT_EPSG = 32610
DEFAULT_GSD_M = 30.0
MAX_RASTER_DIM = 4096


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def _coordinates(text: str | None) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for token in (text or "").split():
        fields = token.split(",")
        if len(fields) < 2:
            continue
        try:
            coords.append((float(fields[0]), float(fields[1])))
        except ValueError:
            continue
    if len(coords) >= 3 and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _polygonal(geom: Any) -> Any:
    """Repair a geometry and retain only polygonal pieces."""
    if geom.is_empty:
        return geom
    if not geom.is_valid:
        geom = geom.buffer(0)
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        pieces = [part for part in geom.geoms if isinstance(part, (Polygon, MultiPolygon))]
        return unary_union(pieces) if pieces else Polygon()
    return Polygon()


def parse_caldor_kml(path: Path) -> dict[str, Any]:
    """Parse and union every Polygon in one Caldor KML (WGS84)."""
    path = Path(path)
    root = ET.parse(path).getroot()
    polygons: list[Any] = []
    n_invalid_repaired = 0
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "Polygon":
            continue
        outer: list[tuple[float, float]] = []
        holes: list[list[tuple[float, float]]] = []
        for child in element.iter():
            local = child.tag.rsplit("}", 1)[-1]
            if local not in {"outerBoundaryIs", "innerBoundaryIs"}:
                continue
            coord_text = next(
                (
                    node.text
                    for node in child.iter()
                    if node.tag.rsplit("}", 1)[-1] == "coordinates"
                ),
                None,
            )
            ring = _coordinates(coord_text)
            if len(ring) < 4:
                continue
            if local == "outerBoundaryIs":
                outer = ring
            else:
                holes.append(ring)
        if len(outer) < 4:
            continue
        polygon = Polygon(outer, holes)
        if not polygon.is_valid:
            n_invalid_repaired += 1
        polygon = _polygonal(polygon)
        if not polygon.is_empty:
            polygons.append(polygon)
    if not polygons:
        raise ValueError(f"no polygon geometry in {path}")
    geom = _polygonal(unary_union(polygons))
    return {
        "path": path,
        "geometry_wgs84": geom,
        "n_polygon_elements": len(polygons),
        "n_invalid_repaired": n_invalid_repaired,
        "bounds_wgs84": [float(value) for value in geom.bounds],
    }


def _project(geom: Any, epsg: int) -> Any:
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    return transform(transformer.transform, geom)


def _grid(
    geoms_projected: list[Any], *, gsd_m: float, pad_m: float, max_dim: int
) -> dict[str, Any]:
    bounds = unary_union(geoms_projected).bounds
    minx = math.floor((bounds[0] - pad_m) / gsd_m) * gsd_m
    miny = math.floor((bounds[1] - pad_m) / gsd_m) * gsd_m
    maxx = math.ceil((bounds[2] + pad_m) / gsd_m) * gsd_m
    maxy = math.ceil((bounds[3] + pad_m) / gsd_m) * gsd_m
    used_gsd = float(gsd_m)
    width = max(8, int(round((maxx - minx) / used_gsd)))
    height = max(8, int(round((maxy - miny) / used_gsd)))
    if width > max_dim or height > max_dim:
        used_gsd *= max(width / max_dim, height / max_dim)
        used_gsd = math.ceil(used_gsd * 10.0) / 10.0
        width = max(8, int(math.ceil((maxx - minx) / used_gsd)))
        height = max(8, int(math.ceil((maxy - miny) / used_gsd)))
    return {
        "bounds_m": [float(minx), float(miny), float(maxx), float(maxy)],
        "gsd_m": used_gsd,
        "width": width,
        "height": height,
    }


def _rasterize(geom: Any, dest: Path, *, epsg: int, grid: dict[str, Any], role: str) -> dict[str, Any]:
    import numpy as np
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    minx, _miny, _maxx, maxy = grid["bounds_m"]
    transform_aff = from_origin(minx, maxy, grid["gsd_m"], grid["gsd_m"])
    mask = rasterize(
        [(geom, 1)],
        out_shape=(grid["height"], grid["width"]),
        transform=transform_aff,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        dest,
        "w",
        driver="GTiff",
        height=grid["height"],
        width=grid["width"],
        count=1,
        dtype="uint8",
        crs=f"EPSG:{epsg}",
        transform=transform_aff,
        compress="deflate",
        nodata=0,
    ) as dataset:
        dataset.write(np.asarray(mask, dtype="uint8"), 1)
        dataset.update_tags(
            source="FireBench Caldor 2021 KML perimeter",
            role=role,
            not_imagery="true",
            not_product_ros="true",
        )
    return {
        "file": dest.name,
        "positive_pixels": int(mask.sum()),
        "bytes": int(dest.stat().st_size),
        "sha256": _sha256(dest),
    }


def _write_geojson(geom: Any, dest: Path, properties: dict[str, Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": properties, "geometry": mapping(geom)}],
    }
    dest.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def _rights(pack_root: Path) -> dict[str, Any]:
    license_dir = pack_root / "DATA_LICENSES"
    names = sorted(path.name for path in license_dir.glob("*") if path.is_file())
    synoptic_notice = any("synoptic" in name.lower() for name in names)
    return {
        "dataset_license_present": (pack_root / "LICENSE").is_file(),
        "data_terms_present": (pack_root / "data_term_of_use.md").is_file(),
        "data_license_files": names,
        "synoptic_notice_present": synoptic_notice,
        "training_allowed": False,
        "redistribution_allowed": False,
        "evaluation_allowed_in_place": True,
        "reason": (
            "Synoptic station data are present in Caldor.h5 but no Synoptic notice is staged; "
            "this bridge therefore remains evaluation-only and is not redistributable."
            if not synoptic_notice
            else "Conservative evaluation-only gate pending a human review of all upstream terms."
        ),
    }


def materialize_caldor_label_pack(
    source_root: Path,
    out_dir: Path,
    *,
    epsg: int = DEFAULT_EPSG,
    gsd_m: float = DEFAULT_GSD_M,
    pad_m: float = 300.0,
    max_dim: int = MAX_RASTER_DIM,
) -> dict[str, Any]:
    """Build aligned raw/cumulative masks and an interval-aware pair manifest."""
    source_root = Path(source_root)
    out_dir = Path(out_dir)
    kml_dir = source_root / "kml"
    # Idempotence: remove only files owned by this builder, never arbitrary
    # content that may coexist under a caller-provided output directory.
    for folder, pattern in (
        ("raw_masks", "caldor_*_raw.tif"),
        ("cumulative_masks", "caldor_*_cumulative.tif"),
        ("raw_labels", "caldor_*_raw.geojson"),
    ):
        for stale in (out_dir / folder).glob(pattern):
            stale.unlink()
    dated: list[dict[str, Any]] = []
    mtbs: dict[str, Any] | None = None
    for path in sorted(kml_dir.glob("*.kml")):
        parsed = parse_caldor_kml(path)
        timestamp = parse_caldor_kml_timestamp(path.name)
        if timestamp is None:
            if "perimeter_mtbs" in path.name.lower():
                mtbs = parsed
            continue
        parsed["timestamp"] = timestamp
        parsed["geometry_projected"] = _project(parsed["geometry_wgs84"], epsg)
        dated.append(parsed)
    dated.sort(key=lambda row: row["timestamp"].astimezone(UTC))
    if len(dated) < 2:
        raise ValueError(f"need at least two dated Caldor KMLs under {kml_dir}")

    grid_geoms = [row["geometry_projected"] for row in dated]
    if mtbs is not None:
        mtbs["geometry_projected"] = _project(mtbs["geometry_wgs84"], epsg)
        grid_geoms.append(mtbs["geometry_projected"])
    grid = _grid(grid_geoms, gsd_m=gsd_m, pad_m=pad_m, max_dim=max_dim)

    observations: list[dict[str, Any]] = []
    cumulative = Polygon()
    for index, row in enumerate(dated):
        # Filenames carry a literal Z only after conversion to UTC.
        stamp = row["timestamp"].astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        raw_wgs84 = row["geometry_wgs84"]
        raw_projected = row["geometry_projected"]
        cumulative = _polygonal(unary_union([cumulative, raw_wgs84]))
        cumulative_projected = _project(cumulative, epsg)
        raw_name = f"caldor_{stamp}_raw.tif"
        cumulative_name = f"caldor_{stamp}_cumulative.tif"
        raw_raster = _rasterize(
            raw_projected,
            out_dir / "raw_masks" / raw_name,
            epsg=epsg,
            grid=grid,
            role="raw_observed_nirops_perimeter",
        )
        cumulative_raster = _rasterize(
            cumulative_projected,
            out_dir / "cumulative_masks" / cumulative_name,
            epsg=epsg,
            grid=grid,
            role="derived_cumulative_union_of_nirops_perimeters",
        )
        properties = {
            "event_id": "US_FIREBENCH_CALDOR_2021",
            "timestamp_utc": _utc_iso(row["timestamp"]),
            "source_kml": row["path"].name,
            "not_product_ros": True,
        }
        _write_geojson(raw_wgs84, out_dir / "raw_labels" / f"caldor_{stamp}_raw.geojson", properties)
        observations.append(
            {
                "index": index,
                "timestamp_local": row["timestamp"].isoformat(),
                "timestamp_utc": _utc_iso(row["timestamp"]),
                "source_kml": row["path"].name,
                "n_polygon_elements": row["n_polygon_elements"],
                "n_invalid_repaired": row["n_invalid_repaired"],
                "raw_area_ha": float(raw_projected.area / 10_000.0),
                "cumulative_area_ha": float(cumulative_projected.area / 10_000.0),
                "raw_mask": f"raw_masks/{raw_name}",
                "cumulative_mask": f"cumulative_masks/{cumulative_name}",
                "raw_label": f"raw_labels/caldor_{stamp}_raw.geojson",
                "raw_raster": raw_raster,
                "cumulative_raster": cumulative_raster,
            }
        )

    pairs: list[dict[str, Any]] = []
    for previous, current in zip(dated, dated[1:], strict=False):
        delta_hours = (
            current["timestamp"].astimezone(UTC) - previous["timestamp"].astimezone(UTC)
        ).total_seconds() / 3600.0
        previous_geom = previous["geometry_projected"]
        current_geom = current["geometry_projected"]
        retained = (
            float(previous_geom.intersection(current_geom).area / previous_geom.area)
            if previous_geom.area > 0
            else 0.0
        )
        pairs.append(
            {
                "previous_index": len(pairs),
                "current_index": len(pairs) + 1,
                "previous_utc": _utc_iso(previous["timestamp"]),
                "current_utc": _utc_iso(current["timestamp"]),
                "delta_hours": float(delta_hours),
                "next_day_compatible": 12.0 <= delta_hours <= 36.0,
                "raw_previous_area_retained_fraction": retained,
                "raw_has_material_revision": retained < 0.95,
                "recommended_target": "cumulative_mask",
            }
        )

    mtbs_record: dict[str, Any] | None = None
    if mtbs is not None:
        mtbs_path = out_dir / "references" / "caldor_mtbs_final_reference.tif"
        raster = _rasterize(
            mtbs["geometry_projected"],
            mtbs_path,
            epsg=epsg,
            grid=grid,
            role="mtbs_final_reference_not_temporal_target",
        )
        _write_geojson(
            mtbs["geometry_wgs84"],
            out_dir / "references" / "caldor_mtbs_final_reference.geojson",
            {"event_id": "US_FIREBENCH_CALDOR_2021", "role": "final_reference"},
        )
        mtbs_record = {
            "mask": "references/caldor_mtbs_final_reference.tif",
            "label": "references/caldor_mtbs_final_reference.geojson",
            "area_ha": float(mtbs["geometry_projected"].area / 10_000.0),
            "raster": raster,
            "excluded_from_temporal_pairs": True,
        }

    rights = _rights(source_root)
    meta = {
        "schema": SCHEMA,
        "event_id": "US_FIREBENCH_CALDOR_2021",
        "source": "FireBench: 2021 Caldor Benchmarks for Fire Models v2026.1",
        "source_root": str(source_root).replace("\\", "/"),
        "crs": f"EPSG:{epsg}",
        "grid": grid,
        "n_observations": len(observations),
        "n_pairs": len(pairs),
        "n_pairs_12_to_36h": sum(pair["next_day_compatible"] for pair in pairs),
        "n_pairs_with_material_raw_revision": sum(
            pair["raw_has_material_revision"] for pair in pairs
        ),
        "class": "ml_weak",
        "role": "observational_progression_evaluation_labels",
        "raw_masks_are_observations": True,
        "cumulative_masks_are_derived": True,
        "not_imagery": True,
        "not_product_ros": True,
        "not_tactical_dispatch": True,
        "rights": rights,
        "observations": observations,
        "mtbs_final_reference": mtbs_record,
        "built_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pairs.json").write_text(
        json.dumps({"schema": PAIR_SCHEMA, "pairs": pairs}, indent=2), encoding="utf-8"
    )
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
