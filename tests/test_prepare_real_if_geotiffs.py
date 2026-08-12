from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from scripts.prepare_real_if_geotiffs import prepare_sequence


def write_lonlat_tiff(path: Path) -> None:
    data = np.zeros((4, 10, 10), dtype=np.uint8)
    data[0, 2:6, 2:6] = 255
    data[3, 2:6, 2:6] = 255
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=4,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=from_origin(-1.71, 38.64, 0.00001, 0.00001),
    ) as dataset:
        dataset.write(data)


class PrepareRealIfGeoTiffsTests:
    def test_reprojects_selected_lwir_files_to_metric_crs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            write_lonlat_tiff(source / "2024-08-02_16-08-21-553_LWIR.tif")
            write_lonlat_tiff(source / "2024-08-02_16-08-21-553_HD-EO.tif")

            written = prepare_sequence(
                source,
                output,
                pattern="*_LWIR.tif",
                dst_crs="EPSG:32630",
                resolution_m=1.0,
                resampling=Resampling.nearest,
            )

            assert len(written) == 1
            with rasterio.open(written[0]) as dataset:
                assert str(dataset.crs) == "EPSG:32630"
                assert dataset.crs.is_projected
                assert dataset.count == 4
                assert pytest.approx(abs(dataset.transform.a), abs=10**-6) == 1.0
