"""Acquire and align leakage-safe clean17 covariates for Caldor FireBench."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import h5py
import hdf5plugin  # noqa: F401  # registers FireBench's HDF5 Zstandard filter
import numpy as np
import rasterio
from netCDF4 import Dataset, num2date
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.caldor_temporal import (  # noqa: E402
    choose_hrrr_leads,
    last_available_gridmet_day,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021"
DEFAULT_H5 = ROOT / "data/external/firebench/caldor_2021/v2026.1/Caldor.h5"
DEFAULT_OUTPUT = ROOT / "docs/CALDOR_CLEAN17_ACQUISITION.json"

TARGET_CRS = "EPSG:32610"
TARGET_BOUNDS = (702_510.0, 4_270_350.0, 768_480.0, 4_309_410.0)
TARGET_GSD = 30.0
TARGET_WIDTH = 2199
TARGET_HEIGHT = 1302
TARGET_TRANSFORM = from_origin(
    TARGET_BOUNDS[0], TARGET_BOUNDS[3], TARGET_GSD, TARGET_GSD
)

HRRR_BASE = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
HRRR_WANTED = {
    ("VIS", "surface"),
    ("PRES", "surface"),
    ("TMP", "2 m above ground"),
    ("DPT", "2 m above ground"),
    ("RH", "2 m above ground"),
    ("UGRD", "10 m above ground"),
    ("VGRD", "10 m above ground"),
    ("APCP", "surface"),
    ("TCDC", "entire atmosphere"),
}

CLEAN17_CHANNELS = (
    "slope_rad",
    "aspect_rad",
    "max_temperature_c",
    "min_temperature_c",
    "wind_speed_ms",
    "wind_direction_deg",
    "precipitation_mm_24h",
    "surface_pressure_hpa",
    "relative_humidity_pct",
    "total_cloud_cover_pct",
    "visibility_km",
    "dew_point_c",
    "canopy_height_m",
    "canopy_base_height_m",
    "canopy_bulk_density_kg_m3",
    "canopy_presence",
    "erc_g",
)

USGS_SOURCE_URLS = {
    "USGS_13_n39w120_20210701.tif": (
        "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/"
        "historical/n39w120/USGS_13_n39w120_20210701.tif"
    ),
    "USGS_13_n39w121_20200106.tif": (
        "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/"
        "historical/n39w121/USGS_13_n39w121_20200106.tif"
    ),
}
GRIDMET_URL = "https://www.northwestknowledge.net/metdata/data/erc_2021.nc"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_provenance(path: Path, source_url: str) -> dict[str, Any]:
    return {
        "path": path,
        "source_url": source_url,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "retrieved_at_utc": datetime.fromtimestamp(
            path.stat().st_ctime, tz=UTC
        ).isoformat().replace("+00:00", "Z"),
    }


def choose_hrrr_cycle(t0: datetime, availability_lag_hours: int = 1) -> datetime:
    """Choose the latest extended HRRR cycle conservatively available by t0."""
    available = t0.astimezone(UTC) - timedelta(hours=availability_lag_hours)
    cycle_hour = (available.hour // 6) * 6
    return available.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)


def _hrrr_urls(cycle: datetime, lead: int) -> tuple[str, str]:
    stamp = cycle.strftime("%Y%m%d")
    hour = cycle.strftime("%H")
    name = f"hrrr.t{hour}z.wrfsfcf{lead:02d}.grib2"
    base = f"{HRRR_BASE}/hrrr.{stamp}/conus/{name}"
    return base, f"{base}.idx"


def parse_hrrr_index(text: str) -> list[dict[str, Any]]:
    """Select one GRIB record for each clean17 weather variable."""
    lines = [line for line in text.splitlines() if line.strip()]
    offsets = [int(line.split(":", 2)[1]) for line in lines]
    selected: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        parts = line.split(":")
        if len(parts) < 6 or (parts[3], parts[4]) not in HRRR_WANTED:
            continue
        element, level, descriptor = parts[3], parts[4], parts[5]
        if element == "APCP" and not descriptor.startswith("0-"):
            continue
        selected.append(
            {
                "element": element,
                "level": level,
                "descriptor": descriptor,
                "start": offsets[index],
                "end": offsets[index + 1] - 1 if index + 1 < len(lines) else None,
            }
        )
    elements = [row["element"] for row in selected]
    expected = {element for element, _level in HRRR_WANTED}
    if set(elements) != expected or len(elements) != len(expected):
        raise ValueError(f"HRRR index selection incomplete: {elements}")
    if any(row["end"] is None for row in selected):
        raise ValueError("Selected HRRR record is last in index; byte end unknown")
    return selected


def _download_text(url: str, attempts: int = 6) -> str:
    for attempt in range(attempts):
        try:
            with urlopen(url, timeout=60) as response:
                return response.read().decode("utf-8")
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _download_range(url: str, start: int, end: int, attempts: int = 6) -> bytes:
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urlopen(request, timeout=120) as response:
                data = response.read()
            if len(data) != end - start + 1 or not data.startswith(b"GRIB"):
                raise OSError("invalid partial HRRR record")
            return data
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def acquire_hrrr_lead(cycle: datetime, lead: int, source_root: Path) -> dict[str, Any]:
    cycle_id = cycle.strftime("%Y%m%dT%H00Z")
    destination = source_root / cycle_id / f"f{lead:02d}.grib2"
    index_destination = destination.with_suffix(".source.idx")
    gdal_sidecar = Path(f"{destination}.idx")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data_url, index_url = _hrrr_urls(cycle, lead)
    # GDAL treats ``file.grib2.idx`` as an index for the local subset and then
    # exposes all bands from the original remote file. Keep the source index
    # under a non-sidecar name so the nine-record subset is read truthfully.
    if gdal_sidecar.is_file():
        gdal_sidecar.replace(index_destination)
    if destination.is_file() and destination.stat().st_size > 0:
        return {
            "path": destination,
            "source_url": data_url,
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "retrieved_at_utc": datetime.fromtimestamp(
                destination.stat().st_ctime, tz=UTC
            ).isoformat().replace("+00:00", "Z"),
            "reused": True,
        }
    index_text = _download_text(index_url)
    records = parse_hrrr_index(index_text)
    index_destination.write_text(index_text, encoding="utf-8")
    partial = destination.with_suffix(".grib2.part")
    with partial.open("wb") as stream:
        for record in records:
            stream.write(
                _download_range(
                    data_url,
                    int(record["start"]),
                    int(record["end"]),
                )
            )
    partial.replace(destination)
    return {
        "path": destination,
        "source_url": data_url,
        "sha256": sha256(destination),
        "bytes": destination.stat().st_size,
        "retrieved_at_utc": datetime.fromtimestamp(
            destination.stat().st_ctime, tz=UTC
        ).isoformat().replace("+00:00", "Z"),
        "records": records,
        "reused": False,
    }


def _target_array() -> np.ndarray:
    return np.full((TARGET_HEIGHT, TARGET_WIDTH), np.nan, dtype=np.float32)


def _reproject_array(
    source: np.ndarray,
    *,
    source_transform: Any,
    source_crs: Any,
    source_nodata: float | int | None,
    resampling: Resampling,
) -> np.ndarray:
    destination = _target_array()
    reproject(
        source=source,
        destination=destination,
        src_transform=source_transform,
        src_crs=source_crs,
        src_nodata=source_nodata,
        dst_transform=TARGET_TRANSFORM,
        dst_crs=TARGET_CRS,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return destination


def _write_tif(path: Path, array: np.ndarray, *, categorical: bool = False) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(array, dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=TARGET_HEIGHT,
        width=TARGET_WIDTH,
        count=1,
        dtype="float32",
        crs=TARGET_CRS,
        transform=TARGET_TRANSFORM,
        nodata=np.nan,
        compress="deflate",
        predictor=2,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dataset:
        dataset.write(data, 1)
    finite = data[np.isfinite(data)]
    return {
        "path": path,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "finite_fraction": float(np.isfinite(data).mean()),
        "min": float(finite.min()) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
        "categorical": categorical,
    }


def build_terrain(covariate_root: Path) -> dict[str, dict[str, Any]]:
    source_dir = covariate_root / "source/usgs_3dep"
    sources = sorted(source_dir.glob("*.tif"))
    if len(sources) != 2:
        raise FileNotFoundError("expected two USGS 3DEP source tiles")
    opened = [rasterio.open(path) for path in sources]
    try:
        mosaic, transform = merge(opened)
        dem = _reproject_array(
            mosaic[0],
            source_transform=transform,
            source_crs=opened[0].crs,
            source_nodata=opened[0].nodata,
            resampling=Resampling.bilinear,
        )
    finally:
        for dataset in opened:
            dataset.close()
    dy, dx = np.gradient(dem, TARGET_GSD, TARGET_GSD)
    slope = np.arctan(np.hypot(dx, dy)).astype(np.float32)
    aspect = np.mod(np.arctan2(-dy, dx), 2 * np.pi).astype(np.float32)
    output_dir = covariate_root / "static"
    return {
        "dem_m": _write_tif(output_dir / "dem_m.tif", dem),
        "slope_rad": _write_tif(output_dir / "slope_rad.tif", slope),
        "aspect_rad": _write_tif(output_dir / "aspect_rad.tif", aspect),
    }


def _h5_regular_grid(
    group: h5py.Group,
) -> tuple[Any, np.ndarray, float | int | None]:
    variable_name = next(
        name for name in group if name not in {"position_lat", "position_lon"}
    )
    variable = group[variable_name]
    lon = np.asarray(group["position_lon"][0, :], dtype=np.float64)
    lat = np.asarray(group["position_lat"][:, 0], dtype=np.float64)
    data = np.asarray(variable[:], dtype=np.float32)
    if lat[0] < lat[-1]:
        lat = lat[::-1]
        data = data[::-1]
    if lon[0] > lon[-1]:
        lon = lon[::-1]
        data = data[:, ::-1]
    dx = float(np.median(np.diff(lon)))
    dy = abs(float(np.median(np.diff(lat))))
    transform = from_origin(lon[0] - dx / 2, lat[0] + dy / 2, dx, dy)
    nodata = variable.attrs.get("_FillValue")
    return transform, data, np.asarray(nodata).item() if nodata is not None else None


def build_landfire(covariate_root: Path, h5_path: Path) -> dict[str, dict[str, Any]]:
    specs = {
        "canopy_height_m": ("spatial_2d/Caldor_CH", 0.1),
        "canopy_base_height_m": ("spatial_2d/Caldor_CBH", 0.1),
        "canopy_bulk_density_kg_m3": ("spatial_2d/Caldor_CBD", 0.01),
    }
    arrays: dict[str, np.ndarray] = {}
    with h5py.File(h5_path, "r") as handle:
        for channel, (group_name, scale) in specs.items():
            transform, source, nodata = _h5_regular_grid(handle[group_name])
            if nodata is not None:
                source[source == nodata] = np.nan
            source *= scale
            arrays[channel] = _reproject_array(
                source,
                source_transform=transform,
                source_crs="EPSG:4326",
                source_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
    arrays["canopy_presence"] = np.where(
        np.isfinite(arrays["canopy_height_m"]),
        (arrays["canopy_height_m"] > 0).astype(np.float32),
        np.nan,
    )
    output_dir = covariate_root / "static"
    return {
        channel: _write_tif(
            output_dir / f"{channel}.tif",
            array,
            categorical=channel == "canopy_presence",
        )
        for channel, array in arrays.items()
    }


def _read_hrrr_fields(path: Path) -> dict[str, np.ndarray]:
    fields: dict[str, np.ndarray] = {}
    with rasterio.open(path) as dataset:
        for band in range(1, dataset.count + 1):
            tags = dataset.tags(band)
            element = tags.get("GRIB_ELEMENT")
            if not element:
                description = dataset.descriptions[band - 1] or ""
                element = description.split(":", 1)[0]
            if element and element.startswith("APCP"):
                element = "APCP"
            if element in fields:
                raise ValueError(f"duplicate HRRR element {element} in {path}")
            fields[element] = _reproject_array(
                dataset.read(band).astype(np.float32),
                source_transform=dataset.transform,
                source_crs=dataset.crs,
                source_nodata=dataset.nodata,
                resampling=Resampling.bilinear,
            )
    expected = {element for element, _level in HRRR_WANTED}
    if set(fields) != expected:
        raise ValueError(f"unexpected HRRR bands in {path}: {sorted(fields)}")
    return fields


def build_hrrr_dynamic(
    cycle: datetime,
    source_root: Path,
    output_dir: Path,
    leads: list[int],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not leads:
        raise ValueError("HRRR lead list is empty")
    lead_fields: list[dict[str, np.ndarray]] = []
    source_rows: list[dict[str, Any]] = []
    for lead in leads:
        row = acquire_hrrr_lead(cycle, lead, source_root)
        path = Path(row.pop("path"))
        source_rows.append({**row, "path": path.as_posix(), "lead_hour": lead})
        lead_fields.append(_read_hrrr_fields(path))
    def stack(name: str) -> np.ndarray:
        return np.stack([fields[name] for fields in lead_fields])

    # GDAL's GRIB driver exposes HRRR TMP/DPT in degrees Celsius (GRIB_UNIT=[C])
    # even though the packed GRIB values are Kelvin.
    temperature = stack("TMP")
    u_wind = np.nanmean(stack("UGRD"), axis=0)
    v_wind = np.nanmean(stack("VGRD"), axis=0)
    wind_speed = np.hypot(u_wind, v_wind)
    wind_direction = np.mod(270.0 - np.degrees(np.arctan2(v_wind, u_wind)), 360.0)
    precip = lead_fields[-1]["APCP"].astype(np.float32)
    if len(lead_fields) > 1:
        precip = np.clip(precip - lead_fields[0]["APCP"], 0.0, None)
    arrays = {
        "max_temperature_c": np.nanmax(temperature, axis=0),
        "min_temperature_c": np.nanmin(temperature, axis=0),
        "wind_speed_ms": wind_speed,
        "wind_direction_deg": wind_direction,
        "precipitation_mm_24h": precip,
        "surface_pressure_hpa": np.nanmean(stack("PRES"), axis=0) / 100.0,
        "relative_humidity_pct": np.nanmean(stack("RH"), axis=0),
        "total_cloud_cover_pct": np.nanmean(stack("TCDC"), axis=0),
        "visibility_km": np.nanmean(stack("VIS"), axis=0) / 1000.0,
        "dew_point_c": np.nanmean(stack("DPT"), axis=0),
    }
    return (
        {
            channel: _write_tif(output_dir / f"{channel}.tif", array)
            for channel, array in arrays.items()
        },
        source_rows,
    )


def build_gridmet_erc(
    netcdf_path: Path,
    date: datetime,
    output_path: Path,
) -> dict[str, Any]:
    with Dataset(netcdf_path) as dataset:
        day = dataset.variables["day"]
        dates: Any = num2date(day[:], day.units, calendar=day.calendar)
        target = last_available_gridmet_day(date)
        index = next(
            i
            for i, value in enumerate(dates)
            if (value.year, value.month, value.day)
            == (target.year, target.month, target.day)
        )
        variable = dataset.variables["energy_release_component-g"]
        source = np.ma.asarray(variable[index]).filled(np.nan).astype(np.float32)
        lon = np.asarray(dataset.variables["lon"][:])
        lat = np.asarray(dataset.variables["lat"][:])
        dx = float(np.median(np.diff(lon)))
        dy = abs(float(np.median(np.diff(lat))))
        if lat[0] < lat[-1]:
            lat = lat[::-1]
            source = source[::-1]
        transform = from_origin(lon[0] - dx / 2, lat[0] + dy / 2, dx, dy)
        aligned = _reproject_array(
            source,
            source_transform=transform,
            source_crs="EPSG:4326",
            source_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        result = _write_tif(output_path, aligned)
        result["gridmet_day"] = target.isoformat()
        result["day_definition"] = (
            "last complete gridMET day ending 07:00 UTC the following morning; "
            "selected only if that end is <= t0"
        )
        result["gridmet_day_end_utc"] = (
            datetime(target.year, target.month, target.day, tzinfo=UTC)
            + timedelta(days=1, hours=7)
        ).isoformat().replace("+00:00", "Z")
        result["source_vintage"] = getattr(dataset, "date", None)
        return result


def _serialize_file_row(row: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        key: (
            value.relative_to(root).as_posix()
            if isinstance(value, Path) and value.is_relative_to(root)
            else str(value)
            if isinstance(value, Path)
            else value
        )
        for key, value in row.items()
    }


def acquire(
    pack_root: Path,
    h5_path: Path,
    *,
    max_pairs: int | None = None,
    download_only: bool = False,
) -> dict[str, Any]:
    covariate_root = pack_root / "covariates"
    meta = json.loads((pack_root / "meta.json").read_text(encoding="utf-8"))
    pairs = json.loads((pack_root / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    selected = [pair for pair in pairs if pair["next_day_compatible"]]
    if max_pairs is not None:
        selected = selected[:max_pairs]
    t0_values = [
        datetime.fromisoformat(pair["previous_utc"].replace("Z", "+00:00"))
        for pair in selected
    ]
    t1_values = [
        datetime.fromisoformat(pair["current_utc"].replace("Z", "+00:00"))
        for pair in selected
    ]
    cycles = [choose_hrrr_cycle(t0) for t0 in t0_values]
    lead_lists = [
        choose_hrrr_leads(cycle, t0, t1)
        for cycle, t0, t1 in zip(cycles, t0_values, t1_values, strict=True)
    ]
    source_root = covariate_root / "source/hrrr"
    if download_only:
        downloaded = []
        wanted = {
            (cycle, lead)
            for cycle, leads in zip(cycles, lead_lists, strict=True)
            for lead in leads
        }
        for index, (cycle, lead) in enumerate(sorted(wanted), start=1):
            print(
                f"[caldor-hrrr] {index}/{len(wanted)} "
                f"{cycle.strftime('%Y%m%dT%H')}Z f{lead:02d}",
                flush=True,
            )
            downloaded.append(acquire_hrrr_lead(cycle, lead, source_root))
        return {
            "schema": "wfd_caldor_clean17_acquisition_v1",
            "status": "hrrr_download_only_complete",
            "n_cycles": len({cycle for cycle, _lead in wanted}),
            "n_leads": len(downloaded),
        }

    static = {
        **build_terrain(covariate_root),
        **build_landfire(covariate_root, h5_path),
    }
    gridmet_path = covariate_root / "source/gridmet/erc_2021.nc"
    dynamic: list[dict[str, Any]] = []
    for pair, t0, cycle, leads in zip(
        selected, t0_values, cycles, lead_lists, strict=True
    ):
        timestamp_id = t0.strftime("%Y%m%dT%H%M%SZ")
        output_dir = covariate_root / "dynamic" / timestamp_id
        weather, sources = build_hrrr_dynamic(
            cycle, source_root, output_dir, leads
        )
        erc = build_gridmet_erc(gridmet_path, t0, output_dir / "erc_g.tif")
        channels = {
            **{name: static[name] for name in CLEAN17_CHANNELS if name in static},
            **weather,
            "erc_g": erc,
        }
        if set(channels) != set(CLEAN17_CHANNELS):
            raise ValueError(f"clean17 channel mismatch: {sorted(channels)}")
        dynamic.append(
            {
                "t0_utc": pair["previous_utc"],
                "t1_utc": pair["current_utc"],
                "delta_hours": pair["delta_hours"],
                "hrrr_cycle_utc": cycle.isoformat().replace("+00:00", "Z"),
                "hrrr_availability_lag_hours": 1,
                "hrrr_leads_hours": list(leads),
                "hrrr_sources": [
                    _serialize_file_row(
                        {**source, "path": Path(source["path"])}, pack_root
                    )
                    for source in sources
                ],
                "channels": {
                    name: _serialize_file_row(row, pack_root)
                    for name, row in channels.items()
                },
            }
        )
    usgs_sources = [
        file_provenance(path, USGS_SOURCE_URLS[path.name])
        for path in sorted((covariate_root / "source/usgs_3dep").glob("*.tif"))
    ]
    h5_source = file_provenance(
        h5_path,
        "https://zenodo.org/records/19041000",
    )
    h5_source["landfire_datasets"] = {
        "canopy_height_m": "LF2020_CH_200_CONUS/LC20_CH_200.tif",
        "canopy_base_height_m": "LF2020_CBH_200_CONUS/LC20_CBH_200.tif",
        "canopy_bulk_density_kg_m3": "LF2020_CBD_200_CONUS/LC20_CBD_200.tif",
        "canopy_presence": "derived from LF2020 canopy height > 0",
    }
    gridmet_source = file_provenance(gridmet_path, GRIDMET_URL)
    report = {
        "schema": "wfd_caldor_clean17_acquisition_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "complete" if len(dynamic) == len(selected) else "incomplete",
        "event_id": meta["event_id"],
        "target_grid": {
            "crs": TARGET_CRS,
            "bounds_m": list(TARGET_BOUNDS),
            "gsd_m": TARGET_GSD,
            "width": TARGET_WIDTH,
            "height": TARGET_HEIGHT,
        },
        "schema_contract": "clean17_physical_v1_not_legacy17_checkpoint_compatible",
        "channel_order": list(CLEAN17_CHANNELS),
        "n_real_channels": len(CLEAN17_CHANNELS),
        "n_pairs": len(dynamic),
        "static": {
            name: _serialize_file_row(row, pack_root) for name, row in static.items()
        },
        "dynamic": dynamic,
        "sources": {
            "terrain": [
                _serialize_file_row(row, pack_root) for row in usgs_sources
            ],
            "weather": {
                "provider": "NOAA HRRR AWS Open Data",
                "access": "byte-range records; exact URLs and hashes per dynamic row",
            },
            "vegetation": _serialize_file_row(h5_source, pack_root),
            "fire_danger": _serialize_file_row(gridmet_source, pack_root),
        },
        "leakage_audit": {
            "hrrr_cycle_initialized_before_t0_minus_one_hour": all(
                cycle <= t0 - timedelta(hours=1)
                for cycle, t0 in zip(cycles, t0_values, strict=True)
            ),
            "landfire_release": "LF2020 pre-Caldor",
            "post_fire_outcomes_used": False,
            "t1_labels_used_as_inputs": False,
            "neutral_placeholder_channels_used": False,
        },
        "compatibility": {
            "clean17_ready": len(dynamic) == len(selected),
            "legacy17_checkpoint_compatible": False,
            "reason": (
                "legacy17 checkpoints learned constant placeholder slots; real pressure, cloud, "
                "visibility, dew point and four continuous canopy channels define a new schema"
            ),
            "training_required_before_model_iou": True,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--h5", type=Path, default=DEFAULT_H5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    report = acquire(
        args.pack_root,
        args.h5,
        max_pairs=args.max_pairs,
        download_only=args.download_only,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "n_pairs": report.get("n_pairs"),
                "n_real_channels": report.get("n_real_channels"),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["status"] in {"complete", "hrrr_download_only_complete"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
