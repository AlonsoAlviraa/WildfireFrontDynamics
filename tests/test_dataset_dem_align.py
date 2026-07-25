"""B4: DEM gradient scale by resolution_m + refuse unaligned multi-frame crop."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

try:
    import rasterio
    from rasterio.transform import from_origin
except ModuleNotFoundError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    from_origin = None  # type: ignore[assignment]

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover
    torch = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(torch is None, reason="PyTorch not installed"),
    pytest.mark.skipif(rasterio is None, reason="rasterio not installed"),
]


def _write_mask(path: Path, h: int, w: int, *, transform=None, crs: str = "EPSG:32630") -> None:
    transform = transform or from_origin(500000.0, 4200000.0, 10.0, 10.0)
    data = np.zeros((h, w), dtype=np.uint8)
    data[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = 1
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def _write_image(path: Path, h: int, w: int, *, transform=None, crs: str = "EPSG:32630") -> None:
    transform = transform or from_origin(500000.0, 4200000.0, 10.0, 10.0)
    data = np.random.default_rng(0).random((h, w)).astype(np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def _write_dem(path: Path, h: int, w: int, res_m: float = 10.0) -> None:
    """Plane DEM z = x * res so physical slope is known when gradient is scaled."""
    transform = from_origin(0.0, h * res_m, res_m, res_m)
    # elevation rises 1 m per pixel east → dz/dx = 1/res_m in world if scaled
    xs = np.arange(w, dtype=float)
    dem = np.tile(xs * res_m, (h, 1))  # z increases  res_m metres per pixel
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float64",
        crs="EPSG:32630",
        transform=transform,
    ) as dst:
        dst.write(dem, 1)


def _aligned_pair_dirs(tmp_path: Path, n: int = 4, h: int = 40, w: int = 40) -> tuple[Path, Path]:
    images = tmp_path / "images"
    masks = tmp_path / "masks"
    images.mkdir()
    masks.mkdir()
    transform = from_origin(500000.0, 4200000.0, 10.0, 10.0)
    for i in range(n):
        # timestamps in name for infer_timestamp
        name = f"frame_2024060{i + 1}_120000.tif"
        _write_image(images / name, h, w, transform=transform)
        _write_mask(masks / name, h, w, transform=transform)
    return images, masks


def test_dem_gradient_scaled_by_resolution(tmp_path: Path):
    from wildfire_front.ml.dataset import WildfireDataset

    images, masks = _aligned_pair_dirs(tmp_path, n=4, h=32, w=32)
    dem_path = tmp_path / "dem.tif"
    _write_dem(dem_path, 32, 32, res_m=10.0)

    ds = WildfireDataset(
        images_dir=images,
        masks_dir=masks,
        sequence_length=2,
        patch_size=16,
        dem_path=dem_path,
        max_patches=2,
    )
    assert ds.dem_slope_physical_metres is True
    assert ds.dem_slope_is_synthetic is False
    assert ds.dem_resolution_m is not None
    # Plane with dz/dx = 1 (world) → slope angle arctan(1) ≈ π/4
    mean_slope = float(np.mean(ds.dem_slope))
    assert abs(mean_slope - math.atan(1.0)) < 0.15


def test_dem_missing_resolution_marks_non_physical(tmp_path: Path):
    from wildfire_front.ml.dataset import WildfireDataset

    images, masks = _aligned_pair_dirs(tmp_path, n=4, h=32, w=32)
    ds = WildfireDataset(
        images_dir=images,
        masks_dir=masks,
        sequence_length=2,
        patch_size=16,
        max_patches=2,
    )
    # Synthesized DEM path
    assert ds.dem_slope_is_synthetic is True
    assert ds.dem_slope_physical_metres is False


def test_unaligned_shapes_refuse_by_default(tmp_path: Path):
    from wildfire_front.ml.dataset import WildfireDataset

    images = tmp_path / "images"
    masks = tmp_path / "masks"
    images.mkdir()
    masks.mkdir()
    transform = from_origin(500000.0, 4200000.0, 10.0, 10.0)
    shapes = [(40, 40), (40, 40), (50, 45), (40, 40)]
    for i, (h, w) in enumerate(shapes):
        name = f"frame_2024060{i + 1}_120000.tif"
        _write_image(images / name, h, w, transform=transform)
        _write_mask(masks / name, h, w, transform=transform)

    with pytest.raises(ValueError, match="unaligned multi-frame"):
        WildfireDataset(
            images_dir=images,
            masks_dir=masks,
            sequence_length=2,
            patch_size=16,
            max_patches=2,
        )


def test_unaligned_shapes_opt_in_crop(tmp_path: Path):
    from wildfire_front.ml.dataset import WildfireDataset

    images = tmp_path / "images"
    masks = tmp_path / "masks"
    images.mkdir()
    masks.mkdir()
    transform = from_origin(500000.0, 4200000.0, 10.0, 10.0)
    shapes = [(40, 40), (42, 41), (40, 40), (40, 40)]
    for i, (h, w) in enumerate(shapes):
        name = f"frame_2024060{i + 1}_120000.tif"
        _write_image(images / name, h, w, transform=transform)
        _write_mask(masks / name, h, w, transform=transform)

    ds = WildfireDataset(
        images_dir=images,
        masks_dir=masks,
        sequence_length=2,
        patch_size=16,
        max_patches=2,
        allow_unaligned_crop=True,
    )
    assert ds.height == 40
    assert ds.width == 40
