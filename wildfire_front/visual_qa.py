"""Visual quality-assurance previews for LWIR wildfire frames.

This module generates per-frame thumbnail overlays and a contact sheet so a
human reviewer can quickly scan a sequence of reprojected GeoTIFFs and spot
obvious problems (empty alpha, saturated thermal band, temporal gaps).

Design principles:
- Read-only over the source rasters: we never mutate the inputs.
- Deterministic output: same inputs -> same PNG bytes.
- No GUI dependencies at import time; matplotlib is imported lazily so that
  headless environments can still import the module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from .real_if import FrameManifestRow

THUMBNAIL_MAX_SIDE = 256
CONTACT_SHEET_COLS = 6
THUMBNAIL_BORDER_PX = 2
BACKGROUND_RGB = (32, 32, 32)
BORDER_OK_RGB = (40, 200, 80)
BORDER_REVIEW_RGB = (240, 180, 0)
BORDER_REJECTED_RGB = (220, 60, 60)
EMPTY_ALPHA_THRESHOLD = 0.01


@dataclass(frozen=True)
class FramePreviewResult:
    """Result of generating a thumbnail for a single frame."""

    source: str
    thumbnail_path: Path
    qa_status: str
    alpha_valid_fraction: float
    thermal_mean: float
    thermal_std: float


def _qa_border_color(qa_status: str) -> tuple[int, int, int]:
    if qa_status == "ok":
        return BORDER_OK_RGB
    if qa_status == "review":
        return BORDER_REVIEW_RGB
    return BORDER_REJECTED_RGB


def _normalize_band(band: np.ndarray) -> np.ndarray:
    """Stretch a single band to 0-255 uint8, robust to NaN/Inf."""
    finite = band[np.isfinite(band)]
    if finite.size == 0:
        return np.zeros_like(band, dtype=np.uint8)
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return np.zeros_like(band, dtype=np.uint8)
    scaled = ((band - lo) / (hi - lo) * 255.0)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=255.0, neginf=0.0)
    return np.clip(scaled, 0, 255).astype(np.uint8)


def _make_thumbnail_rgb(geotiff_path: Path) -> tuple[np.ndarray, float, float, float]:
    """Read a GeoTIFF and return (rgb_uint8, alpha_fraction, thermal_mean, thermal_std)."""
    with rasterio.open(geotiff_path) as dataset:
        band_count = dataset.count
        # Downscale for thumbnail
        h = min(dataset.height, THUMBNAIL_MAX_SIDE)
        w = min(dataset.width, THUMBNAIL_MAX_SIDE)
        if dataset.height > THUMBNAIL_MAX_SIDE or dataset.width > THUMBNAIL_MAX_SIDE:
            out_shape = (1, h, w)
        else:
            out_shape = None

        thermal = dataset.read(1, out_shape=out_shape, masked=True)
        # Convert to float64 before filling so np.nan is valid (numpy >= 2.0).
        thermal_filled = thermal.astype(np.float64).filled(np.nan)
        thermal_mean = float(np.nanmean(thermal_filled)) if np.isfinite(thermal_filled).any() else 0.0
        thermal_std = float(np.nanstd(thermal_filled)) if np.isfinite(thermal_filled).any() else 0.0

        red = _normalize_band(thermal_filled)

        # Try to use band 2 as green for false-color, else reuse thermal
        if band_count >= 2:
            green_data = dataset.read(2, out_shape=out_shape, masked=True).astype(np.float64).filled(np.nan)
            green = _normalize_band(green_data)
        else:
            green = red.copy()

        blue = np.zeros_like(red, dtype=np.uint8)
        rgb = np.dstack([red, green, blue])

        alpha_fraction = 1.0
        if band_count >= 4:
            alpha = dataset.read(4, out_shape=out_shape)
            alpha_fraction = float(np.mean(alpha > 0))
            mask = alpha > 0
            rgb[~mask] = 0

    return rgb, alpha_fraction, thermal_mean, thermal_std


def render_frame_thumbnail(
    row: FrameManifestRow,
    output_dir: Path,
) -> FramePreviewResult | None:
    """Render a single frame thumbnail PNG. Returns None if no GeoTIFF."""
    if not row.geotiff_path:
        return None
    geotiff_path = Path(row.geotiff_path)
    if not geotiff_path.exists():
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    rgb, alpha_frac, thermal_mean, thermal_std = _make_thumbnail_rgb(geotiff_path)

    border_color = _qa_border_color(row.qa_status)
    bordered = _add_border(rgb, border_color)
    thumb_path = output_dir / (geotiff_path.stem + "_thumb.png")
    Image.fromarray(bordered).save(thumb_path)

    return FramePreviewResult(
        source=str(geotiff_path),
        thumbnail_path=thumb_path,
        qa_status=row.qa_status,
        alpha_valid_fraction=alpha_frac,
        thermal_mean=thermal_mean,
        thermal_std=thermal_std,
    )


def _add_border(rgb: np.ndarray, border_color: tuple[int, int, int]) -> np.ndarray:
    """Add a colored border around an RGB image."""
    h, w, _ = rgb.shape
    new_h = h + 2 * THUMBNAIL_BORDER_PX
    new_w = w + 2 * THUMBNAIL_BORDER_PX
    out = np.full((new_h, new_w, 3), 0, dtype=np.uint8)
    out[:, :, 0] = border_color[0]
    out[:, :, 1] = border_color[1]
    out[:, :, 2] = border_color[2]
    out[THUMBNAIL_BORDER_PX : THUMBNAIL_BORDER_PX + h, THUMBNAIL_BORDER_PX : THUMBNAIL_BORDER_PX + w] = rgb
    return out


def render_contact_sheet(
    rows: list[FrameManifestRow] | tuple[FrameManifestRow, ...],
    output_path: Path,
    *,
    columns: int = CONTACT_SHEET_COLS,
) -> list[FramePreviewResult]:
    """Render a contact sheet of all frames into a single PNG.

    Frames without a GeoTIFF are skipped. The layout uses a fixed number of
    columns and as many rows as needed. Each thumbnail is bordered by a color
    indicating its QA status.
    """
    rows_list = [r for r in rows if r.geotiff_path and Path(r.geotiff_path).exists()]
    if not rows_list:
        raise ValueError("no frames with a readable GeoTIFF to render")

    results: list[FramePreviewResult] = []
    thumbs: list[np.ndarray] = []
    for row in rows_list:
        rgb, alpha_frac, thermal_mean, thermal_std = _make_thumbnail_rgb(Path(row.geotiff_path))
        border_color = _qa_border_color(row.qa_status)
        thumbs.append(_add_border(rgb, border_color))
        results.append(
            FramePreviewResult(
                source=row.geotiff_path,
                thumbnail_path=output_path,  # placeholder, filled below
                qa_status=row.qa_status,
                alpha_valid_fraction=alpha_frac,
                thermal_mean=thermal_mean,
                thermal_std=thermal_std,
            )
        )

    # All thumbnails have the same padded dimensions, so compute the grid.
    th = max(t.shape[0] for t in thumbs)
    tw = max(t.shape[1] for t in thumbs)
    n = len(thumbs)
    cols = min(columns, n)
    grid_cols = cols
    grid_rows = math.ceil(n / grid_cols)

    sheet_w = grid_cols * tw
    sheet_h = grid_rows * th
    sheet = np.full((sheet_h, sheet_w, 3), BACKGROUND_RGB[0], dtype=np.uint8)
    sheet[:, :, 0] = BACKGROUND_RGB[0]
    sheet[:, :, 1] = BACKGROUND_RGB[1]
    sheet[:, :, 2] = BACKGROUND_RGB[2]

    for idx, thumb in enumerate(thumbs):
        r = idx // grid_cols
        c = idx % grid_cols
        y0 = r * th
        x0 = c * tw
        th_h, th_w = thumb.shape[:2]
        sheet[y0 : y0 + th_h, x0 : x0 + th_w] = thumb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(output_path)
    return results