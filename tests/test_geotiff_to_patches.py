"""Tests for the GeoTIFF → .npz training-patch exporter (pipeline stage 5)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from wildfire_front.ml.dataset import NpzWildfireDataset


def _write_tiff(path: Path, data: np.ndarray) -> None:
    array = data if data.ndim == 3 else data[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[2],
        height=array.shape[1],
        count=array.shape[0],
        dtype=array.dtype,
        crs="EPSG:32630",
        transform=from_origin(500000.0, 4100000.0, 10.0, 10.0),
    ) as dataset:
        dataset.write(array)


def _make_fire_sequence(root: Path, num_frames: int = 4) -> tuple[Path, Path]:
    """Create a minimal but valid image+mask sequence with expanding fire.

    Each frame is 60x60 so at least one 30x30 patch with fire is guaranteed.
    """
    images = root / "images"
    masks = root / "masks"
    images.mkdir()
    masks.mkdir()
    for i in range(num_frames):
        timestamp = f"20260709_{1200 + i:02d}00"
        image = np.zeros((60, 60), dtype=np.uint16)
        mask = np.zeros((60, 60), dtype=np.uint8)
        size = 4 + i * 2
        image[20 : 20 + size, 20 : 20 + size] = 1200 + i * 100
        mask[20 : 20 + size, 20 : 20 + size] = 1
        _write_tiff(images / f"frame_{timestamp}.tif", image)
        _write_tiff(masks / f"frame_{timestamp}.tif", mask)
    return images, masks


class GeotiffToPatchesTests:
    def test_export_produces_npz_with_correct_contract(self) -> None:
        from scripts.geotiff_to_training_patches import export_patches

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, masks = _make_fire_sequence(root, num_frames=4)
            output_dir = root / "patches"

            manifest = export_patches(
                images_dir=images,
                masks_dir=masks,
                output_dir=output_dir,
                sequence_length=3,
                patch_size=30,
                fire_name="test_fire",
            )

            assert manifest["num_patches"] > 0
            npz_files = sorted(output_dir.glob("*.npz"))
            assert manifest["num_patches"] == len(npz_files)

            with np.load(npz_files[0]) as data:
                assert data["sequence"].shape == (3, 17, 30, 30)
                assert data["current_fire"].shape == (30, 30)
                assert data["target_fire"].shape == (30, 30)
                assert data["sequence"].dtype == np.float32
                assert data["target_fire"].max() in (0, 1)

            manifest_file = output_dir / "manifest.json"
            assert manifest_file.exists()
            loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
            assert loaded["fire_name"] == "test_fire"
            assert loaded["sequence_length"] == 3

    def test_npz_files_load_into_npz_dataset(self) -> None:
        from scripts.geotiff_to_training_patches import export_patches

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, masks = _make_fire_sequence(root, num_frames=4)
            output_dir = root / "patches"

            export_patches(
                images_dir=images,
                masks_dir=masks,
                output_dir=output_dir,
                sequence_length=3,
                patch_size=30,
            )

            dataset = NpzWildfireDataset(output_dir)
            assert len(dataset) > 0
            sequence, current_fire, target_fire = dataset[0]
            assert sequence.shape == (3, 17, 30, 30)
            assert current_fire.shape == (30, 30)
            assert target_fire.shape == (30, 30)

    def test_max_patches_limits_output(self) -> None:
        from scripts.geotiff_to_training_patches import export_patches

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, masks = _make_fire_sequence(root, num_frames=4)
            output_dir = root / "patches"

            manifest = export_patches(
                images_dir=images,
                masks_dir=masks,
                output_dir=output_dir,
                sequence_length=3,
                patch_size=30,
                max_patches=1,
            )
            assert manifest["num_patches"] == 1
            assert len(list(output_dir.glob("*.npz"))) == 1
