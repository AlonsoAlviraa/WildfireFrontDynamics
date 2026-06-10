"""Generate a small semireal candidate dataset for validation workflow tests.

The images are synthetic GeoTIFFs, but the observed masks and independent
annotations are intentionally separated. This gives the project a reproducible
stand-in for a real controlled-burn sequence while FLAME 3 or field data are
being audited.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin


ROOT = Path("data/candidates/semireal_controlled_001")
CRS = "EPSG:32630"
TRANSFORM = from_origin(500000.0, 4100000.0, 2.0, 2.0)


def ellipse_mask(
    rows: np.ndarray,
    cols: np.ndarray,
    *,
    center_row: float,
    center_col: float,
    radius_row: float,
    radius_col: float,
) -> np.ndarray:
    return (
        ((rows - center_row) / radius_row) ** 2
        + ((cols - center_col) / radius_col) ** 2
    ) <= 1.0


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
        crs=CRS,
        transform=TRANSFORM,
    ) as dataset:
        dataset.write(data)


def main() -> None:
    images = ROOT / "images"
    masks = ROOT / "masks"
    annotations = ROOT / "annotations"
    for directory in (images, masks, annotations):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    rows, cols = np.ogrid[:96, :128]
    timestamps = ("20260610_120000", "20260610_120045", "20260610_120130", "20260610_120230")
    for index, timestamp in enumerate(timestamps):
        center_row = 55.0 - index * 1.2
        center_col = 42.0 + index * 5.5
        radius_row = 7.0 + index * 2.0
        radius_col = 10.0 + index * 3.2
        reference = ellipse_mask(
            rows,
            cols,
            center_row=center_row,
            center_col=center_col,
            radius_row=radius_row,
            radius_col=radius_col,
        )
        observed = ellipse_mask(
            rows,
            cols,
            center_row=center_row + 0.6,
            center_col=center_col - 0.8,
            radius_row=radius_row * 0.96,
            radius_col=radius_col * 1.03,
        )
        image = np.full((2, 96, 128), 90, dtype=np.uint16)
        image[0, reference] = 650 + index * 25
        image[1, reference] = 1200 + index * 35
        image[0, observed & ~reference] = 430
        filename = f"semireal_controlled_001_{timestamp}.tif"
        write_tiff(images / filename, image)
        write_tiff(masks / filename, observed.astype(np.uint8))
        write_tiff(annotations / filename, reference.astype(np.uint8))

    print(ROOT)


if __name__ == "__main__":
    main()
