"""Bounded, resumable EO tensor materialization for approved WFIGS pairs.

The grid is positioned from the t0 perimeter only.  The t1 perimeter is used as
the prediction target and for truncation QA, never to choose the crop.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.validation import make_valid

from wildfire_front.fuel.dem import glo30_public_href, glo30_tile_ids_for_bbox

from .base import _atomic_write_json, sha256_bytes, utc_now
from .pair_enrichment import _inside_hrrr_conus
from .temporal_pairs import _iter_geojson_features
from .wfigs_rights import wfigs_rights_summary

MATERIALIZATION_SCHEMA = "wfd_wfigs_eo_materialization_v1"
DEFAULT_BANDS = ("blue", "green", "red", "nir")
SCL_CLEAR_CLASSES = frozenset({2, 4, 5, 6, 7})
HRRR_FIELDS = {
    ("PRES", "surface"),
    ("TMP", "2 m above ground"),
    ("RH", "2 m above ground"),
    ("UGRD", "10 m above ground"),
    ("VGRD", "10 m above ground"),
    ("APCP", "surface"),
}


@dataclass(frozen=True)
class TargetBlindGrid:
    """A fixed-resolution square crop whose position depends only on t0."""

    crs: CRS
    transform: Affine
    size: int
    resolution_m: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        west = self.transform.c
        north = self.transform.f
        east = west + self.size * self.resolution_m
        south = north - self.size * self.resolution_m
        return west, south, east, north


def _safe_geometry(value: dict[str, Any]) -> BaseGeometry:
    geometry = shape(value)
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    if geometry.is_empty:
        raise ValueError("empty geometry")
    return geometry


def _local_utm(longitude: float, latitude: float) -> CRS:
    zone = max(1, min(60, int((longitude + 180.0) // 6.0) + 1))
    epsg = (32600 if latitude >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def target_blind_grid(
    t0_geometry: BaseGeometry,
    *,
    size: int = 256,
    resolution_m: float = 60.0,
) -> tuple[TargetBlindGrid, BaseGeometry]:
    """Create a north-up grid centred on t0 and return projected t0."""

    if size < 32:
        raise ValueError("size must be at least 32 pixels")
    if resolution_m <= 0:
        raise ValueError("resolution_m must be positive")
    centroid = t0_geometry.centroid
    crs = _local_utm(float(centroid.x), float(centroid.y))
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    projected = shapely_transform(transformer.transform, t0_geometry)
    cx, cy = projected.centroid.x, projected.centroid.y
    span = float(size) * float(resolution_m)
    transform = Affine(resolution_m, 0.0, cx - span / 2.0, 0.0, -resolution_m, cy + span / 2.0)
    return TargetBlindGrid(crs, transform, size, float(resolution_m)), projected


def _project_geometry(geometry: BaseGeometry, crs: CRS) -> BaseGeometry:
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return shapely_transform(transformer.transform, geometry)


def _mask(geometry: BaseGeometry, grid: TargetBlindGrid) -> np.ndarray:
    return rasterize(
        [(mapping(geometry), 1)],
        out_shape=(grid.size, grid.size),
        transform=grid.transform,
        fill=0,
        dtype="uint8",
        all_touched=False,
    )


def _atomic_savez(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_asset(
    href: str,
    grid: TargetBlindGrid,
    *,
    resampling: Resampling,
) -> np.ma.MaskedArray:
    environment = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }
    with rasterio.Env(**environment), rasterio.open(href) as source, WarpedVRT(
        source,
        crs=grid.crs,
        transform=grid.transform,
        width=grid.size,
        height=grid.size,
        resampling=resampling,
    ) as warped:
        return warped.read(1, masked=True)


def read_sentinel_scene(
    candidate: dict[str, Any], grid: TargetBlindGrid
) -> dict[str, np.ndarray]:
    """Read only the requested spatial windows from public Sentinel COGs."""

    assets = candidate.get("assets") or {}
    missing = [band for band in (*DEFAULT_BANDS, "scl") if band not in assets]
    if missing:
        raise ValueError(f"candidate missing assets: {', '.join(missing)}")
    output: dict[str, np.ndarray] = {}
    valid = np.ones((grid.size, grid.size), dtype=bool)
    for band in DEFAULT_BANDS:
        source = _read_asset(str(assets[band]["href"]), grid, resampling=Resampling.bilinear)
        band_valid = ~np.ma.getmaskarray(source)
        valid &= band_valid
        output[band] = np.asarray(source.filled(0), dtype=np.float32) / 10_000.0
    scl_source = _read_asset(str(assets["scl"]["href"]), grid, resampling=Resampling.nearest)
    scl = np.asarray(scl_source.filled(0), dtype=np.uint8)
    scl_valid = np.isin(scl, tuple(SCL_CLEAR_CLASSES)) & ~np.ma.getmaskarray(scl_source)
    valid &= scl_valid
    denominator = output["nir"] + output["red"]
    ndvi = np.divide(
        output["nir"] - output["red"],
        denominator,
        out=np.zeros_like(denominator),
        where=np.abs(denominator) > 1e-6,
    )
    for band in DEFAULT_BANDS:
        output[band] = np.where(valid, output[band], 0.0).astype(np.float32)
    output["ndvi"] = np.where(valid, ndvi, 0.0).astype(np.float32)
    output["valid_data"] = valid.astype(np.uint8)
    output["scl"] = scl
    return output


SceneReader = Callable[[dict[str, Any], TargetBlindGrid], dict[str, np.ndarray]]
DemReader = Callable[[TargetBlindGrid], dict[str, np.ndarray]]
WeatherReader = Callable[[dict[str, Any], TargetBlindGrid, Path], dict[str, np.ndarray]]


def read_copernicus_dem(grid: TargetBlindGrid) -> dict[str, np.ndarray]:
    """Mosaic only the GLO-30 COG windows intersecting the target grid."""

    transformer = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
    footprint_wgs84 = shapely_transform(transformer.transform, box(*grid.bounds))
    bbox = tuple(float(value) for value in footprint_wgs84.bounds)
    elevation = np.full((grid.size, grid.size), np.nan, dtype=np.float32)
    for tile_id in glo30_tile_ids_for_bbox(bbox):
        source = _read_asset(
            glo30_public_href(tile_id), grid, resampling=Resampling.bilinear
        )
        values = np.asarray(source.filled(np.nan), dtype=np.float32)
        fill = np.isnan(elevation) & np.isfinite(values)
        elevation[fill] = values[fill]
    valid = np.isfinite(elevation)
    if not valid.any():
        raise ValueError("Copernicus GLO-30 window is all nodata")
    return {
        "dem": np.where(valid, elevation, 0.0).astype(np.float32),
        "dem_valid": valid.astype(np.uint8),
    }


def _download_text(url: str, attempts: int = 4) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "WFD-WFIGS/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except OSError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(8, 2**attempt))
    raise OSError(f"failed to download {url}: {last_error}")


def _download_range(url: str, start: int, end: int, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "WFD-WFIGS/1.0",
                    "Range": f"bytes={start}-{end}",
                },
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            if len(payload) != end - start + 1 or not payload.startswith(b"GRIB"):
                raise OSError("invalid HRRR byte-range response")
            return payload
        except OSError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(8, 2**attempt))
    raise OSError(f"failed HRRR range {start}-{end}: {last_error}")


def _select_hrrr_records(index_text: str) -> list[dict[str, Any]]:
    lines = [line for line in index_text.splitlines() if line.strip()]
    offsets = [int(line.split(":", 2)[1]) for line in lines]
    selected: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        parts = line.split(":")
        if len(parts) < 6 or (parts[3], parts[4]) not in HRRR_FIELDS:
            continue
        if parts[3] == "APCP" and not parts[5].startswith("0-"):
            continue
        end = offsets[index + 1] - 1 if index + 1 < len(offsets) else None
        if end is None:
            raise ValueError("selected HRRR record has no byte end")
        selected.append(
            {
                "element": parts[3],
                "start": offsets[index],
                "end": end,
            }
        )
    expected = {field for field, _level in HRRR_FIELDS}
    if {row["element"] for row in selected} != expected or len(selected) != len(expected):
        raise ValueError("HRRR index does not contain the required unique fields")
    return selected


def _hrrr_lead_url(last_index_url: str, lead: int) -> tuple[str, str]:
    index_url, replacements = re.subn(
        r"wrfsfcf\d{2}\.grib2\.idx$",
        f"wrfsfcf{lead:02d}.grib2.idx",
        last_index_url,
    )
    if replacements != 1:
        raise ValueError("unrecognized HRRR index URL")
    return index_url.removesuffix(".idx"), index_url


def _acquire_hrrr_subset(index_url: str, output: Path) -> Path:
    if output.is_file() and output.stat().st_size > 0:
        return output
    data_url = index_url.removesuffix(".idx")
    records = _select_hrrr_records(_download_text(index_url))
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, suffix=".grib2", delete=False) as handle:
        temporary = Path(handle.name)
        for record in records:
            handle.write(_download_range(data_url, int(record["start"]), int(record["end"])))
    try:
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def _read_hrrr_subset(path: Path, grid: TargetBlindGrid) -> dict[str, np.ndarray]:
    fields: dict[str, np.ndarray] = {}
    with rasterio.open(path) as source, WarpedVRT(
        source,
        crs=grid.crs,
        transform=grid.transform,
        width=grid.size,
        height=grid.size,
        resampling=Resampling.bilinear,
    ) as warped:
        for band in range(1, warped.count + 1):
            element = str(source.tags(band).get("GRIB_ELEMENT") or "")
            if element.startswith("APCP"):
                element = "APCP"
            fields[element] = np.asarray(
                warped.read(band, masked=True).filled(np.nan), dtype=np.float32
            )
    expected = {field for field, _level in HRRR_FIELDS}
    if set(fields) != expected:
        raise ValueError(f"unexpected HRRR subset fields: {sorted(fields)}")
    return fields


def read_hrrr_weather(
    weather: dict[str, Any], grid: TargetBlindGrid, cache_root: Path
) -> dict[str, np.ndarray]:
    """Read three forecast times from a run demonstrably available by t0."""

    if weather.get("status") != "resolved" or weather.get("available_by_t0_verified") is not True:
        raise ValueError("HRRR run is not verified available by t0")
    transformer = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
    bbox = list(shapely_transform(transformer.transform, box(*grid.bounds)).bounds)
    if not _inside_hrrr_conus(bbox):
        raise ValueError("target grid is outside the HRRR CONUS domain")
    first = int(weather["first_lead"])
    last = int(weather["last_lead"])
    leads = sorted({first, (first + last) // 2, last})
    last_index_url = str(weather["last_index_url"])
    match = re.search(r"hrrr\.(\d{8}).*hrrr\.t(\d{2})z", last_index_url)
    if match is None:
        raise ValueError("cannot derive HRRR cycle from URL")
    cycle_id = f"{match.group(1)}T{match.group(2)}00Z"
    snapshots: list[dict[str, np.ndarray]] = []
    for lead in leads:
        _data_url, index_url = _hrrr_lead_url(last_index_url, lead)
        path = _acquire_hrrr_subset(
            index_url, Path(cache_root) / cycle_id / f"f{lead:02d}.grib2"
        )
        snapshots.append(_read_hrrr_subset(path, grid))

    def average(name: str) -> np.ndarray:
        return np.nanmean(np.stack([snapshot[name] for snapshot in snapshots]), axis=0)

    u_wind = average("UGRD")
    v_wind = average("VGRD")
    temperature = average("TMP")
    if float(np.nanmedian(temperature)) < 150.0:
        temperature = temperature + 273.15
    pressure = average("PRES")
    humidity = average("RH")
    precipitation = snapshots[-1]["APCP"]
    speed = np.hypot(u_wind, v_wind)
    direction = np.arctan2(u_wind, v_wind)
    air_density = pressure / np.maximum(287.05 * temperature, 1e-6)
    valid = np.logical_and.reduce(
        [
            np.isfinite(speed),
            np.isfinite(direction),
            np.isfinite(temperature),
            np.isfinite(precipitation),
            np.isfinite(humidity),
            np.isfinite(air_density),
        ]
    )
    if not valid.any():
        raise ValueError("HRRR target window is all nodata")

    def clean(values: np.ndarray) -> np.ndarray:
        return np.where(valid, values, 0.0).astype(np.float32)

    return {
        "wind_speed": clean(speed),
        "wind_direction_rad": clean(direction),
        "temperature_k": clean(temperature),
        "precipitation_mm": clean(precipitation),
        "humidity_pct": clean(humidity),
        "air_density": clean(air_density),
        "weather_valid": valid.astype(np.uint8),
        "hrrr_sampled_leads": np.asarray(leads, dtype=np.int16),
    }


class WFIGSEOMaterializer:
    """Materialize leakage-safe WFIGS geometry + Sentinel windows with QA."""

    def __init__(
        self,
        *,
        pairs_path: Path,
        enrichment_path: Path,
        observations_path: Path,
        output_root: Path,
        limit: int = 10,
        splits: tuple[str, ...] = ("train", "validation", "test"),
        pair_ids: tuple[str, ...] = (),
        size: int = 256,
        resolution_m: float = 60.0,
        min_valid_fraction: float = 0.70,
        overwrite: bool = False,
        scene_reader: SceneReader = read_sentinel_scene,
        dem_reader: DemReader = read_copernicus_dem,
        weather_reader: WeatherReader = read_hrrr_weather,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not 0.0 <= min_valid_fraction <= 1.0:
            raise ValueError("min_valid_fraction must be in [0, 1]")
        self.pairs_path = Path(pairs_path)
        self.enrichment_path = Path(enrichment_path)
        self.observations_path = Path(observations_path)
        self.output_root = Path(output_root)
        self.limit = limit
        self.splits = tuple(splits)
        self.pair_ids = frozenset(pair_ids)
        self.size = size
        self.resolution_m = resolution_m
        self.min_valid_fraction = min_valid_fraction
        self.overwrite = overwrite
        self.scene_reader = scene_reader
        self.dem_reader = dem_reader
        self.weather_reader = weather_reader

    @staticmethod
    def _candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
        sentinel = ((row.get("eo") or {}).get("sentinel2") or {})
        eligible: list[dict[str, Any]] = []
        for candidate in sentinel.get("candidates") or []:
            if candidate.get("stac_created_at_or_before_t0") is not True:
                continue
            assets = candidate.get("assets") or {}
            if all(name in assets for name in (*DEFAULT_BANDS, "scl")):
                eligible.append(candidate)
        return eligible

    def _selected_pairs(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        pairs_doc = json.loads(self.pairs_path.read_text(encoding="utf-8"))
        enrich_doc = json.loads(self.enrichment_path.read_text(encoding="utf-8"))
        enrichment = {str(row["pair_id"]): row for row in enrich_doc.get("pairs") or []}
        selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for pair in pairs_doc.get("pairs") or []:
            if pair.get("approved") is not True or pair.get("split") not in self.splits:
                continue
            if self.pair_ids and str(pair.get("pair_id")) not in self.pair_ids:
                continue
            enriched = enrichment.get(str(pair.get("pair_id")))
            if enriched is None:
                continue
            selected.append((pair, enriched))
            if len(selected) >= self.limit:
                break
        return selected

    def _geometries(
        self, selected: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> dict[str, BaseGeometry]:
        wanted = {
            str(pair[key])
            for pair, _ in selected
            for key in ("t0_observation_id", "t1_observation_id")
        }
        geometries: dict[str, BaseGeometry] = {}
        for feature in _iter_geojson_features(self.observations_path):
            properties = feature.get("properties") or {}
            observation_id = str(properties.get("observation_id") or "")
            if observation_id not in wanted:
                continue
            try:
                geometries[observation_id] = _safe_geometry(feature["geometry"])
            except (KeyError, TypeError, ValueError):
                continue
            if len(geometries) == len(wanted):
                break
        return geometries

    def _materialize_one(
        self,
        pair: dict[str, Any],
        enriched: dict[str, Any],
        geometries: dict[str, BaseGeometry],
    ) -> dict[str, Any]:
        pair_id = str(pair["pair_id"])
        row: dict[str, Any] = {
            "pair_id": pair_id,
            "event_id": str(pair["event_id"]),
            "split": str(pair["split"]),
            "status": "rejected",
        }
        candidates = self._candidates(enriched)
        if not candidates:
            row["reason"] = "no_sentinel_candidate_created_by_t0"
            return row
        first = geometries.get(str(pair["t0_observation_id"]))
        second = geometries.get(str(pair["t1_observation_id"]))
        if first is None or second is None:
            row["reason"] = "geometry_missing"
            return row
        grid, projected_first = target_blind_grid(
            first, size=self.size, resolution_m=self.resolution_m
        )
        projected_second = _project_geometry(second, grid.crs)
        tile = box(*grid.bounds)
        if not tile.covers(projected_first):
            row["reason"] = "t0_geometry_outside_fixed_grid"
            return row
        if not tile.covers(projected_second):
            row["reason"] = "t1_geometry_truncated"
            return row
        weather_meta = enriched.get("weather") or {}
        if weather_meta.get("status") != "resolved":
            row["reason"] = str(weather_meta.get("status") or "hrrr_weather_unavailable")
            return row

        relative = Path(str(pair["split"])) / f"{pair_id}.npz"
        output_path = self.output_root / relative
        sidecar_path = output_path.with_suffix(".json")
        if not self.overwrite and output_path.exists() and sidecar_path.exists():
            existing = json.loads(sidecar_path.read_text(encoding="utf-8"))
            existing["resumed"] = True
            return existing

        scene: dict[str, np.ndarray] | None = None
        candidate: dict[str, Any] | None = None
        valid_fraction = 0.0
        attempts: list[dict[str, Any]] = []
        for proposed in candidates:
            try:
                proposed_scene = self.scene_reader(proposed, grid)
            except Exception as exc:  # try the next pre-t0 scene on network/GDAL failure
                attempts.append(
                    {
                        "scene_id": str(proposed.get("id") or ""),
                        "status": "read_failed",
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            proposed_valid = float(
                np.asarray(proposed_scene["valid_data"], dtype=np.uint8).mean()
            )
            attempts.append(
                {
                    "scene_id": str(proposed.get("id") or ""),
                    "status": "accepted" if proposed_valid >= self.min_valid_fraction else "rejected",
                    "valid_fraction": round(proposed_valid, 8),
                }
            )
            if proposed_valid >= self.min_valid_fraction:
                scene = proposed_scene
                candidate = proposed
                valid_fraction = proposed_valid
                break
        if scene is None or candidate is None:
            row["reason"] = (
                "insufficient_clear_valid_pixels"
                if any(attempt["status"] == "rejected" for attempt in attempts)
                else "eo_window_read_failed"
            )
            row["scene_attempts"] = attempts
            return row
        try:
            dem = self.dem_reader(grid)
        except Exception as exc:  # remote DEM errors remain explicit and resumable
            row["reason"] = "dem_window_read_failed"
            row["error_type"] = type(exc).__name__
            return row
        try:
            weather = self.weather_reader(
                weather_meta, grid, self.output_root / ".cache/hrrr"
            )
        except Exception as exc:
            row["reason"] = "hrrr_window_read_failed"
            row["error_type"] = type(exc).__name__
            return row
        previous_fire = _mask(projected_first, grid)
        target_fire = _mask(projected_second, grid)
        arrays = {
            "previous_fire": previous_fire,
            "target_fire": target_fire,
            **{name: np.asarray(values) for name, values in scene.items()},
            **{name: np.asarray(values) for name, values in dem.items()},
            **{name: np.asarray(values) for name, values in weather.items()},
            "horizon_hours": np.asarray(float(pair["metrics"]["delta_hours"]), dtype=np.float32),
            "transform": np.asarray(tuple(grid.transform)[:6], dtype=np.float64),
            "crs_epsg": np.asarray(int(grid.crs.to_epsg() or 0), dtype=np.int32),
            "resolution_m": np.asarray(grid.resolution_m, dtype=np.float32),
        }
        _atomic_savez(output_path, **arrays)
        digest = sha256_bytes(output_path.read_bytes())
        row.update(
            {
                "status": "materialized",
                "sensor": "sentinel-2-l2a",
                "scene_id": str(candidate["id"]),
                "scene_datetime": candidate.get("datetime"),
                "scene_created": candidate.get("created"),
                "stac_created_at_or_before_t0": True,
                "relative_path": relative.as_posix(),
                "sha256": digest,
                "shape": [self.size, self.size],
                "resolution_m": grid.resolution_m,
                "crs": grid.crs.to_string(),
                "valid_fraction": round(valid_fraction, 8),
                "scene_attempts": attempts,
                "previous_fire_pixels": int(previous_fire.sum()),
                "target_fire_pixels": int(target_fire.sum()),
                "growth_pixels": int(np.logical_and(target_fire > 0, previous_fire == 0).sum()),
                "target_blind_grid": True,
                "dem_source": "Copernicus GLO-30 AWS Open Data",
                "dem_valid_fraction": round(float(np.asarray(dem["dem_valid"]).mean()), 8),
                "weather_source": "NOAA HRRR AWS Open Data",
                "weather_available_by_t0_verified": True,
                "weather_valid_fraction": round(
                    float(np.asarray(weather["weather_valid"]).mean()), 8
                ),
                "training_ready": True,
                "missing_for_training": [],
                "resumed": False,
            }
        )
        _atomic_write_json(sidecar_path, row)
        return row

    def build(self) -> dict[str, Any]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        selected = self._selected_pairs()
        geometries = self._geometries(selected)
        rows = [self._materialize_one(pair, enriched, geometries) for pair, enriched in selected]
        reasons = Counter(str(row.get("reason")) for row in rows if row["status"] != "materialized")
        inventory = {
            "schema": MATERIALIZATION_SCHEMA,
            "generated_at": utc_now(),
            "configuration": {
                "limit": self.limit,
                "splits": list(self.splits),
                "pair_ids": sorted(self.pair_ids),
                "size": self.size,
                "resolution_m": self.resolution_m,
                "min_valid_fraction": self.min_valid_fraction,
                "grid_positioned_from_t0_only": True,
                "candidate_must_exist_in_stac_by_t0": True,
            },
            "counts": {
                "pairs_selected": len(selected),
                "pairs_materialized": sum(row["status"] == "materialized" for row in rows),
                "pairs_rejected": sum(row["status"] != "materialized" for row in rows),
                "rejection_reasons": dict(sorted(reasons.items())),
                "training_ready": sum(row.get("training_ready") is True for row in rows),
            },
            "rows": rows,
            "rights": {
                **wfigs_rights_summary(),
                "materialization_scope": "internal_noncommercial_research_only",
            },
            "claims": {
                "eo_pixels_materialized": any(row["status"] == "materialized" for row in rows),
                "weather_pixels_materialized": any(
                    row["status"] == "materialized" for row in rows
                ),
                "dem_pixels_materialized": any(
                    row["status"] == "materialized" for row in rows
                ),
                "model_training_ready": any(row.get("training_ready") is True for row in rows),
                "external_validation_executed": False,
                "raw_or_derived_tensor_publication_allowed": False,
            },
        }
        _atomic_write_json(self.output_root / "INVENTORY.json", inventory)
        return inventory


__all__ = [
    "MATERIALIZATION_SCHEMA",
    "TargetBlindGrid",
    "WFIGSEOMaterializer",
    "read_copernicus_dem",
    "read_hrrr_weather",
    "read_sentinel_scene",
    "target_blind_grid",
]
