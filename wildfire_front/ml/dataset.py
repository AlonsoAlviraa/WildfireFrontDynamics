"""PyTorch Dataset for Wildfire Front Propagation.

Constructs 16-channel spatiotemporal tensors from GeoTIFF inputs, aligning
topographic and meteorological features, and partitioning them into 30x30 patches
for the A3C-LSTM architecture.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

from ..ingestion.geotiff import TIFF_EXTENSIONS, _find_mask, read_raster_band, infer_timestamp


class WildfireDataset(Dataset):
    """
    Spatiotemporal dataset for wildfire front prediction.

    Loads sequences of images and masks, aligns them into 16-channel feature tensors,
    and extracts 30x30 spatial patches for training/fine-tuning.
    """

    def __init__(
        self,
        images_dir: Path,
        masks_dir: Path,
        sequence_length: int = 3,
        patch_size: int = 30,
        dem_path: Path | None = None,
        ndvi_path: Path | None = None,
        fsm_path: Path | None = None,
        weather_data: dict[str, float] | None = None,
    ) -> None:
        """
        Args:
            images_dir: Directory containing input GeoTIFF images.
            masks_dir: Directory containing binary mask GeoTIFFs.
            sequence_length: Number of timesteps per sequence (default: 3).
            patch_size: Size of spatial windows (default: 30).
            dem_path: Optional path to a DEM GeoTIFF.
            ndvi_path: Optional path to an NDVI GeoTIFF.
            fsm_path: Optional path to an FSM GeoTIFF.
            weather_data: Optional dictionary with custom weather variables.
        """
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.sequence_length = sequence_length
        self.patch_size = patch_size
        self.dem_path = dem_path
        self.ndvi_path = ndvi_path
        self.fsm_path = fsm_path
        self.weather_data = weather_data or {
            "temp": 25.0,
            "humidity": 40.0,
            "wind_speed": 15.0,
            "wind_dir": 90.0,
            "precip": 0.0,
            "pressure": 1013.0,
            "cloud": 10.0,
            "visibility": 10.0,
            "dew_point": 12.0,
        }

        # Identify and match all image and mask pairs
        image_paths = sorted(path for path in self.images_dir.iterdir() if path.suffix.lower() in TIFF_EXTENSIONS)
        self.samples: list[tuple[Path, Path, str]] = []
        for img_path in image_paths:
            mask_path = _find_mask(img_path, self.masks_dir)
            if mask_path and mask_path.exists():
                timestamp = infer_timestamp(img_path)
                self.samples.append((img_path, mask_path, timestamp))

        if len(self.samples) < self.sequence_length + 1:
            raise ValueError(
                f"insufficient valid sequences. Found {len(self.samples)} matched pairs, "
                f"need at least {self.sequence_length + 1}."
            )

        # Pre-load static maps (DEM, NDVI, FSM) to match the spatial resolution of the first image
        with rasterio.open(self.samples[0][0]) as src:
            self.height = src.height
            self.width = src.width
            self.transform = src.transform
            self.crs = src.crs

        self.dem_slope, self.dem_aspect = self._load_or_synthesize_dem()
        self.ndvi = self._load_or_synthesize_ndvi()
        self.fsm = self._load_or_synthesize_fsm()

        # Build spatiotemporal sequence index patches
        self.patches = self._generate_sequence_patches()

    def _load_or_synthesize_dem(self) -> tuple[np.ndarray, np.ndarray]:
        if self.dem_path and self.dem_path.exists():
            with rasterio.open(self.dem_path) as src:
                dem = src.read(1, out_shape=(self.height, self.width)).astype(float)
                # Compute slope and aspect from DEM elevation using gradients
                dy, dx = np.gradient(dem)
                slope = np.arctan(np.sqrt(dx**2 + dy**2))
                aspect = np.arctan2(-dy, dx)
                return slope, aspect
        # Synthesize a smooth gradient slope and aspect
        y, x = np.mgrid[:self.height, :self.width]
        slope = (x / self.width) * 0.1
        aspect = (y / self.height) * 2 * np.pi
        return slope, aspect

    def _load_or_synthesize_ndvi(self) -> np.ndarray:
        if self.ndvi_path and self.ndvi_path.exists():
            with rasterio.open(self.ndvi_path) as src:
                return src.read(1, out_shape=(self.height, self.width)).astype(float)
        return np.full((self.height, self.width), 0.6, dtype=float)

    def _load_or_synthesize_fsm(self) -> np.ndarray:
        if self.fsm_path and self.fsm_path.exists():
            with rasterio.open(self.fsm_path) as src:
                # Expecting up to 4 channels or categorical
                fsm = src.read(out_shape=(4, self.height, self.width)).astype(float)
                if fsm.shape[0] < 4:
                    pad = np.zeros((4 - fsm.shape[0], self.height, self.width))
                    fsm = np.vstack((fsm, pad))
                return fsm[:4]
        # One-hot representation: class 0 (channel 0) active everywhere
        fsm = np.zeros((4, self.height, self.width), dtype=float)
        fsm[0] = 1.0
        return fsm

    def _build_16_channels(self, img_path: Path) -> np.ndarray:
        """Construct the 16-channel array for a single timestep."""
        channels = np.zeros((16, self.height, self.width), dtype=np.float32)

        # 0-1: DEM (slope, aspect)
        channels[0] = self.dem_slope
        channels[1] = self.dem_aspect

        # 2-10: Weather
        channels[2] = self.weather_data["temp"]
        channels[3] = self.weather_data["humidity"]
        channels[4] = self.weather_data["wind_speed"]
        channels[5] = self.weather_data["wind_dir"]
        channels[6] = self.weather_data["precip"]
        channels[7] = self.weather_data["pressure"]
        channels[8] = self.weather_data["cloud"]
        channels[9] = self.weather_data["visibility"]
        channels[10] = self.weather_data["dew_point"]

        # 11: NDVI
        channels[11] = self.ndvi

        # 12-15: FSM
        channels[12:16] = self.fsm

        # Note: If the source image has thermal bands, we can overlay them onto channels if needed.
        # Here we prioritize the standard 16 features required by config.json.
        return channels

    def _generate_sequence_patches(self) -> list[dict[str, int]]:
        """Identify all spatial patches containing active fire sequences."""
        patches = []
        # Loop through all possible sequence starting indices
        for i in range(len(self.samples) - self.sequence_length):
            # Target is the next step immediately following the sequence
            target_idx = i + self.sequence_length
            
            # Slide windows of patch_size x patch_size
            for row in range(0, self.height - self.patch_size + 1, self.patch_size // 2):
                for col in range(0, self.width - self.patch_size + 1, self.patch_size // 2):
                    # Quick check: Is there fire active in the target patch?
                    # This filters out massive empty background patches
                    with rasterio.open(self.samples[target_idx][1]) as mask_src:
                        patch_mask = mask_src.read(
                            1,
                            window=rasterio.windows.Window(col, row, self.patch_size, self.patch_size)
                        )
                        if np.sum(patch_mask) > 0:
                            patches.append({
                                "start_idx": i,
                                "target_idx": target_idx,
                                "row": row,
                                "col": col
                            })
        return patches

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        patch_info = self.patches[idx]
        start_idx = patch_info["start_idx"]
        target_idx = patch_info["target_idx"]
        row = patch_info["row"]
        col = patch_info["col"]

        # 1. Build the input sequence of shape (seq_len, 16, patch_size, patch_size)
        sequence_data = np.zeros(
            (self.sequence_length, 16, self.patch_size, self.patch_size),
            dtype=np.float32
        )
        for t in range(self.sequence_length):
            img_path, _, _ = self.samples[start_idx + t]
            channels = self._build_16_channels(img_path)
            # Crop to the spatial patch
            sequence_data[t] = channels[:, row:row+self.patch_size, col:col+self.patch_size]

        # 2. Get the current fire mask at the end of the sequence
        _, last_mask_path, _ = self.samples[target_idx - 1]
        with rasterio.open(last_mask_path) as src:
            current_fire = src.read(
                1,
                window=rasterio.windows.Window(col, row, self.patch_size, self.patch_size)
            ).astype(np.float32)

        # 3. Get the target fire mask (ground truth for next step spread)
        _, target_mask_path, _ = self.samples[target_idx]
        with rasterio.open(target_mask_path) as src:
            target_fire = src.read(
                1,
                window=rasterio.windows.Window(col, row, self.patch_size, self.patch_size)
            ).astype(np.float32)

        # Convert to PyTorch tensors
        sequence_tensor = torch.from_numpy(sequence_data)
        current_fire_tensor = torch.from_numpy(current_fire)
        target_fire_tensor = torch.from_numpy(target_fire)

        return sequence_tensor, current_fire_tensor, target_fire_tensor
