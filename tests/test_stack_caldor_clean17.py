from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts.stack_caldor_clean17 import CHANNEL_ORDER, stack_pair


def _write_tif(path: Path, value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.full((2, 3), value, dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:32610",
        transform=from_origin(0, 60, 30, 30),
        nodata=np.nan,
    ) as dataset:
        dataset.write(data, 1)


def test_stack_pair_encodes_wind_aspect_and_horizon(tmp_path: Path) -> None:
    names = [
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
    ]
    channels = {}
    for name in names:
        relative = f"covariates/{name}.tif"
        value = 90.0 if "direction" in name or name == "aspect_rad" else 1.0
        if name == "aspect_rad":
            value = float(np.pi / 2)
        if name == "canopy_height_m":
            value = np.nan
        path = tmp_path / relative
        if name == "canopy_height_m":
            path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=3,
                count=1,
                dtype="float32",
                crs="EPSG:32610",
                transform=from_origin(0, 60, 30, 30),
                nodata=np.nan,
            ) as dataset:
                dataset.write(np.full((2, 3), np.nan, dtype=np.float32), 1)
        else:
            _write_tif(path, value)
        channels[name] = {"path": relative}
    row = {
        "channels": channels,
        "delta_hours": 24.5,
        "t0_utc": "2021-08-18T03:20:00Z",
        "t1_utc": "2021-08-19T03:50:00Z",
    }
    stacked = stack_pair(tmp_path, row)
    assert stacked["features"].shape == (len(CHANNEL_ORDER), 2, 3)
    assert CHANNEL_ORDER[1] == "aspect_sin"
    aspect_sin = stacked["features"][CHANNEL_ORDER.index("aspect_sin")]
    wind_sin = stacked["features"][CHANNEL_ORDER.index("wind_sin")]
    horizon = stacked["features"][CHANNEL_ORDER.index("horizon_hours")]
    assert np.allclose(aspect_sin, 1.0, atol=1e-5)
    assert np.allclose(wind_sin, 1.0, atol=1e-5)
    assert np.allclose(horizon, 24.5)
    assert float(stacked["canopy_missing"].mean()) == 1.0
