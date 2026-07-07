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
        max_patches: int | None = None,
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
        self.max_patches = max_patches

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

        # Read all images/masks to find the common intersection dimensions.
        # Tobarra LWIR frames have variable pixel dimensions (drone footprints
        # shift between captures), so we crop everything to the smallest
        # height/width across the sequence.
        raw_shapes: list[tuple[int, int]] = []
        for img_path, mask_path, _ in self.samples:
            with rasterio.open(mask_path) as src:
                raw_shapes.append((src.height, src.width))
        self.height = min(h for h, _ in raw_shapes)
        self.width = min(w for _, w in raw_shapes)
        self.transform = None
        self.crs = None

        self.dem_slope, self.dem_aspect = self._load_or_synthesize_dem()
        self.ndvi = self._load_or_synthesize_ndvi()
        self.fsm = self._load_or_synthesize_fsm()

        # Cache masks in memory to avoid thousands of rasterio.open calls.
        self._mask_cache: list[np.ndarray] = []
        for img_path, mask_path, _ in self.samples:
            with rasterio.open(mask_path) as src:
                full = src.read(1).astype(np.uint8)
            self._mask_cache.append(full[: self.height, : self.width])
            if self.crs is None:
                self.crs = src.crs
                self.transform = src.transform

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

    def _read_thermal_band(self, img_path: Path) -> np.ndarray | None:
        """Read band 1 from the source image and z-score normalize it.

        Returns ``None`` if the image cannot be read or has no finite data
        (e.g. when ``img_path`` is not a thermal raster). This makes the
        thermal injection opt-in and safe for synthetic-only datasets.
        """

        try:
            with rasterio.open(img_path) as src:
                # Read only the common intersection area so frames with larger
                # footprints (variable drone captures) are handled gracefully.
                band = src.read(1).astype(np.float32)
                band = band[: self.height, : self.width]
        except Exception:  # noqa: BLE001
            return None
        finite = band[np.isfinite(band)]
        if finite.size == 0:
            return None
        median = float(np.median(finite))
        mad = float(np.median(np.abs(finite - median)))
        robust_sigma = 1.4826 * mad if mad > 0 else float(np.std(finite))
        if robust_sigma < 1e-6:
            robust_sigma = 1.0
        return np.asarray((band - median) / robust_sigma, dtype=np.float32)

    def _build_16_channels(self, img_path: Path) -> np.ndarray:
        """Construct the 16-channel array for a single timestep.

        When the source image is a thermal LWIR raster (as is the case for the
        Tobarra dataset), band 1 is z-score normalized and injected into
        **channel 11**, replacing the constant NDVI fallback. This ensures the
        model sees real fire signal during both fine-tuning and inference.
        Channels 0-10 and 12-15 remain DEM/weather/FSM as defined by
        ``config.json``.
        """

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

        # 11: Thermal signal (LWIR z-score) if available, otherwise NDVI fallback
        thermal = self._read_thermal_band(img_path)
        if thermal is not None:
            channels[11] = thermal
        else:
            channels[11] = self.ndvi

        # 12-15: FSM
        channels[12:16] = self.fsm

        return channels

    def _generate_sequence_patches(self) -> list[dict[str, int]]:
        """Identify all spatial patches containing active fire sequences.

        Uses the in-memory ``_mask_cache`` instead of opening rasterio for
        every candidate window — a major speedup for thousands of patches.
        """
        patches = []
        half = self.patch_size // 2
        # Loop through all possible sequence starting indices
        for i in range(len(self.samples) - self.sequence_length):
            # Target is the next step immediately following the sequence
            target_idx = i + self.sequence_length
            target_mask = self._mask_cache[target_idx]

            # Slide windows of patch_size x patch_size
            for row in range(0, self.height - self.patch_size + 1, half):
                for col in range(0, self.width - self.patch_size + 1, half):
                    # Quick check: Is there fire active in the target patch?
                    patch = target_mask[row:row + self.patch_size, col:col + self.patch_size]
                    if patch.sum() > 0:
                        patches.append({
                            "start_idx": i,
                            "target_idx": target_idx,
                            "row": row,
                            "col": col,
                        })
                    if self.max_patches is not None and len(patches) >= self.max_patches:
                        return patches
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

        # 2. Get the current fire mask at the end of the sequence (from cache)
        current_fire = self._mask_cache[target_idx - 1][
            row:row + self.patch_size, col:col + self.patch_size
        ].astype(np.float32)

        # 3. Get the target fire mask (ground truth for next step spread, cache)
        target_fire = self._mask_cache[target_idx][
            row:row + self.patch_size, col:col + self.patch_size
        ].astype(np.float32)

        sequence_tensor = torch.from_numpy(sequence_data)
        current_fire_tensor = torch.from_numpy(current_fire)
        target_fire_tensor = torch.from_numpy(target_fire)

        return sequence_tensor, current_fire_tensor, target_fire_tensor


class NpzWildfireDataset(Dataset):
    """
    High-speed PyTorch dataset loading pre-processed .npz spatiotemporal sequences.
    Optimized for cloud container runs (like Kaggle) avoiding GIS/GDAL dependencies.
    """

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.files = sorted(list(self.directory.glob("*.npz")))

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        file_path = self.files[idx]
        with np.load(file_path) as data:
            sequence = torch.from_numpy(data["sequence"].astype(np.float32))
            current_fire = torch.from_numpy(data["current_fire"].astype(np.float32))
            target_fire = torch.from_numpy(data["target_fire"].astype(np.float32))
        return sequence, current_fire, target_fire
