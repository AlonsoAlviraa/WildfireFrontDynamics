"""Terrain helpers for fuel–terrain stack (slope, aspect, slope factor)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TerrainSample:
    """Point or sector terrain sample."""

    slope_deg: float
    aspect_deg: float | None = None  # 0=N, 90=E (downslope direction convention optional)
    elevation_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def slope_from_rise_run(rise_m: float, run_m: float) -> float:
    """Slope in degrees from rise/run."""
    run = max(1e-6, float(run_m))
    return float(math.degrees(math.atan(abs(float(rise_m)) / run)))


def slope_percent_to_deg(slope_pct: float) -> float:
    """Percent grade → degrees (100% = 45°)."""
    return float(math.degrees(math.atan(float(slope_pct) / 100.0)))


def slope_factor_phi_s(slope_deg: float, *, packing_ratio: float = 0.05) -> float:
    """Rothermel-style slope factor Φ_s (simplified).

    Classic form: Φ_s = 5.275 · β^{-0.3} · tan(φ)²
    with β packing ratio. Clamped for extreme slopes.
    """
    phi = math.radians(min(60.0, max(0.0, float(slope_deg))))
    tan_p = math.tan(phi)
    beta = max(1e-4, float(packing_ratio))
    return float(5.275 * (beta ** (-0.3)) * (tan_p**2))


def slope_array_from_dem(
    dem: np.ndarray,
    *,
    cell_size_m: float = 25.0,
) -> np.ndarray:
    """Estimate slope degrees from DEM via central differences.

    ``dem`` is elevation meters (H, W). Edge pixels use one-sided diffs.
    """
    z = np.asarray(dem, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError("dem must be 2D")
    dy, dx = np.gradient(z, cell_size_m)
    slope_rad = np.arctan(np.hypot(dx, dy))
    return np.degrees(slope_rad)


def aspect_array_from_dem(
    dem: np.ndarray,
    *,
    cell_size_m: float = 25.0,
) -> np.ndarray:
    """Aspect in degrees from north (0–360), -1 for flat."""
    z = np.asarray(dem, dtype=np.float64)
    dy, dx = np.gradient(z, cell_size_m)
    # aspect: direction of steepest descent
    aspect = (np.degrees(np.arctan2(dx, -dy)) + 360.0) % 360.0
    slope = np.hypot(dx, dy)
    aspect = np.where(slope < 1e-6, -1.0, aspect)
    return aspect


def upslope_alignment(
    spread_bearing_deg: float,
    aspect_deg: float | None,
) -> bool:
    """True if spread direction is upslope (toward higher elevation).

    Aspect here is **downslope direction** of the surface (standard GIS).
    Upslope is opposite aspect.
    """
    if aspect_deg is None or aspect_deg < 0:
        return True  # neutral — treat as upslope factor allowed
    up = (float(aspect_deg) + 180.0) % 360.0
    d = abs((float(spread_bearing_deg) - up + 180.0) % 360.0 - 180.0)
    return d <= 90.0
