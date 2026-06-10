"""Generate a tiny projected GeoTIFF sequence for the auditable CLI demo."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin


def write_tiff(path: Path, array: np.ndarray) -> None:
    data = array if array.ndim == 3 else array[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[2],
        height=data.shape[1],
        count=data.shape[0],
        dtype=data.dtype,
        crs="EPSG:32630",
        transform=from_origin(500000.0, 4100000.0, 5.0, 5.0),
    ) as dataset:
        dataset.write(data)


def main() -> None:
    root = Path("outputs/geotiff-fixture")
    if root.exists():
        shutil.rmtree(root)
    images = root / "images"
    masks = root / "masks"
    images.mkdir(parents=True)
    masks.mkdir()
    for timestamp, radius in (("20260610_120000", 4), ("20260610_120100", 5), ("20260610_120200", 6)):
        rows, cols = np.ogrid[:32, :32]
        candidate = (rows - 16) ** 2 + ((cols - 16) / 1.4) ** 2 <= radius**2
        image = np.zeros((2, 32, 32), dtype=np.uint16)
        image[0, candidate] = 450
        image[1, candidate] = 1200
        mask = candidate.astype(np.uint8)
        filename = f"controlled_burn_{timestamp}.tif"
        write_tiff(images / filename, image)
        write_tiff(masks / filename, mask)
    print(root)


if __name__ == "__main__":
    main()

