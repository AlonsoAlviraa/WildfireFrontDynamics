"""Residual coregistration between consecutive front observations.

Estimates a translation that maximises coarse mask IoU so georef drift does
not inflate ROS. Raster helpers stamp vertices and a **perimeter-band** soft
fill around component bounding boxes (not full AABB fill) for correlation
mass, reducing box-biased lock-on for elongated fronts.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry_speed import component_centroid
from .models import FrontObservation, Line

# Soft mass for bbox fill (vertices / centroid stamp at 1.0). Any non-zero
# contributes to binary IoU via logical_and/or.
SOFT_FILL_VALUE = 0.3


def shift_component(component: Line, dx: float, dy: float) -> Line:
    return tuple((float(x + dx), float(y + dy)) for x, y in component)


def shift_observation(obs: FrontObservation, dx: float, dy: float) -> FrontObservation:
    comps = tuple(shift_component(c, dx, dy) for c in obs.components)
    return FrontObservation(
        observation_id=obs.observation_id,
        event_id=obs.event_id,
        sensor_id=obs.sensor_id,
        time_s=obs.time_s,
        observed_at=obs.observed_at,
        components=comps,
        estimated_error_m=obs.estimated_error_m,
        status=obs.status,
        truth_components=obs.truth_components,
        crs=obs.crs,
        coordinate_system=obs.coordinate_system,
        resolution_m=obs.resolution_m,
        source_uri=obs.source_uri,
        source_sha256=obs.source_sha256,
        method=obs.method + "+coreg_shift",
        limitations=obs.limitations + ("coregistration_translation_applied",),
    )


def rasterize_main(
    obs: FrontObservation,
    origin: tuple[float, float],
    resolution: float,
    shape: tuple[int, int],
    *,
    soft_fill: float = SOFT_FILL_VALUE,
    soft_band: int = 2,
) -> np.ndarray:
    """Coarse raster of main component(s) for correlation.

    Soft mass is applied as a **perimeter band** around each component
    bounding box (not a full AABB fill) so elongated fronts align on shape
    rather than box geometry. Vertices and a small centroid neighbourhood
    stamp at 1.0 for structural peaks.
    """
    h, w = shape
    grid = np.zeros((h, w), dtype=np.float32)
    ox, oy = origin
    fill = float(soft_fill)
    band = max(1, int(soft_band))
    for comp in obs.components:
        pts = np.asarray(comp, dtype=float)
        if len(pts) < 3:
            continue
        min_x, min_y = pts.min(axis=0)
        max_x, max_y = pts.max(axis=0)
        c0 = int(math.floor((min_x - ox) / resolution))
        c1 = int(math.ceil((max_x - ox) / resolution))
        r0 = int(math.floor((min_y - oy) / resolution))
        r1 = int(math.ceil((max_y - oy) / resolution))
        c0, c1 = max(0, c0), min(w, c1)
        r0, r1 = max(0, r0), min(h, r1)
        if c1 > c0 and r1 > r0:
            # Perimeter band soft fill (reduces box-biased IoU lock-on).
            if fill > 0:
                top = slice(r0, min(r0 + band, r1))
                bot = slice(max(r1 - band, r0), r1)
                left = slice(c0, min(c0 + band, c1))
                right = slice(max(c1 - band, c0), c1)
                grid[top, c0:c1] = np.maximum(grid[top, c0:c1], fill)
                grid[bot, c0:c1] = np.maximum(grid[bot, c0:c1], fill)
                grid[r0:r1, left] = np.maximum(grid[r0:r1, left], fill)
                grid[r0:r1, right] = np.maximum(grid[r0:r1, right], fill)
            for x, y in pts:
                cc = int((x - ox) / resolution)
                rr = int((y - oy) / resolution)
                if 0 <= rr < h and 0 <= cc < w:
                    grid[rr, cc] = 1.0
            cx, cy = component_centroid(comp)
            cc = int((cx - ox) / resolution)
            rr = int((cy - oy) / resolution)
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    r2, c2 = rr + dr, cc + dc
                    if 0 <= r2 < h and 0 <= c2 < w:
                        grid[r2, c2] = 1.0
    return grid


def _shift_binary(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift binary occupancy with zero fill (no wrap)."""
    shifted = np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    if dy > 0:
        shifted[:dy, :] = 0
    elif dy < 0:
        shifted[dy:, :] = 0
    if dx > 0:
        shifted[:, :dx] = 0
    elif dx < 0:
        shifted[:, dx:] = 0
    return shifted


def _iou_binary(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum(dtype=np.int64)
    union = np.logical_or(a, b).sum(dtype=np.int64)
    return float(inter) / float(union) if union else 0.0


def _fft_peak_shift(a_bin: np.ndarray, b_bin: np.ndarray, max_pix: int) -> tuple[int, int]:
    """Coarse translation of *b* onto *a* via FFT cross-correlation peak."""
    wy = np.hanning(a_bin.shape[0]).astype(np.float32)
    wx = np.hanning(a_bin.shape[1]).astype(np.float32)
    win = wy[:, None] * wx[None, :]
    af = np.fft.rfft2(a_bin.astype(np.float32) * win)
    bf = np.fft.rfft2(b_bin.astype(np.float32) * win)
    corr = np.fft.irfft2(af * np.conj(bf), s=a_bin.shape)
    # Zero-lag is at [0,0]; shifts wrap. Search local window only.
    best = (0, 0)
    best_v = float(corr[0, 0])
    h, w = corr.shape
    for dy in range(-max_pix, max_pix + 1):
        for dx in range(-max_pix, max_pix + 1):
            v = float(corr[dy % h, dx % w])
            if v > best_v:
                best_v = v
                best = (dx, dy)
    return best


def estimate_coreg_translation(
    previous: FrontObservation,
    current: FrontObservation,
    *,
    resolution_m: float = 4.0,
    max_shift_m: float = 60.0,
) -> dict[str, float]:
    """Estimate translation (dx, dy) to apply to *current* to align with previous.

    Maximises coarse IoU of rasterised fronts via FFT coarse peak + local
    refine. Structural fix for residual georeferencing drift between
    consecutive drone orthos.
    """
    all_pts = []
    for obs in (previous, current):
        for c in obs.components:
            all_pts.append(np.asarray(c, dtype=float))
    if not all_pts:
        return {"dx_m": 0.0, "dy_m": 0.0, "peak_iou": 0.0, "applied": 0.0}
    stack = np.vstack(all_pts)
    pad = max_shift_m + resolution_m * 2
    min_x, min_y = stack.min(axis=0) - pad
    max_x, max_y = stack.max(axis=0) + pad
    w = max(8, int(math.ceil((max_x - min_x) / resolution_m)))
    h = max(8, int(math.ceil((max_y - min_y) / resolution_m)))
    # Cap grid size for speed
    while w * h > 250_000 and resolution_m < 32:
        resolution_m *= 2
        w = max(8, int(math.ceil((max_x - min_x) / resolution_m)))
        h = max(8, int(math.ceil((max_y - min_y) / resolution_m)))

    origin = (float(min_x), float(min_y))
    a = rasterize_main(previous, origin, resolution_m, (h, w))
    b = rasterize_main(current, origin, resolution_m, (h, w))
    if a.sum() == 0 or b.sum() == 0:
        return {"dx_m": 0.0, "dy_m": 0.0, "peak_iou": 0.0, "applied": 0.0, "iou0": 0.0}

    a_bin = a > 0
    b_bin = b > 0
    max_pix = int(math.ceil(max_shift_m / resolution_m))

    def _iou_at(dx: int, dy: int) -> float:
        return _iou_binary(a_bin, _shift_binary(b_bin, dx, dy))

    iou0 = _iou_at(0, 0)
    best_iou = iou0
    best = (0, 0)

    # FFT coarse peak when grid is large enough to amortize the transform.
    if max_pix > 2 and a_bin.size >= 256:
        try:
            cdx, cdy = _fft_peak_shift(a_bin, b_bin, max_pix)
            if abs(cdx) <= max_pix and abs(cdy) <= max_pix:
                iou = _iou_at(cdx, cdy)
                if iou > best_iou:
                    best_iou = iou
                    best = (cdx, cdy)
        except (ValueError, np.linalg.LinAlgError):
            pass

    # Coarse search in a small radius around identity + FFT peak (not full ±max_pix).
    step = 2 if max_pix > 6 else 1
    # Seeds store (dx, dy) — unpack as sdx, sdy.
    seeds: set[tuple[int, int]] = {(0, 0), best}
    # Radius grows modestly with max_pix but stays << full exhaustive grid.
    radius = max(step * 3, min(max_pix, max(4, max_pix // 3)))
    for sdx, sdy in list(seeds):
        for dy in range(max(-max_pix, sdy - radius), min(max_pix, sdy + radius) + 1, step):
            for dx in range(max(-max_pix, sdx - radius), min(max_pix, sdx + radius) + 1, step):
                iou = _iou_at(dx, dy)
                if iou > best_iou:
                    best_iou = iou
                    best = (dx, dy)

    # Local refine around best (dense neighbourhood)
    cx, cy = best  # (dx, dy)
    refine = max(step, 2)
    for dy in range(cy - refine, cy + refine + 1):
        for dx in range(cx - refine, cx + refine + 1):
            if abs(dx) > max_pix or abs(dy) > max_pix:
                continue
            iou = _iou_at(dx, dy)
            if iou > best_iou:
                best_iou = iou
                best = (dx, dy)

    dx_m = best[0] * resolution_m
    dy_m = best[1] * resolution_m
    # Apply only if IoU improves materially over identity (avoid spurious max-shift).
    improves = best_iou >= iou0 + 0.05 and best_iou >= 0.15
    nontrivial = abs(dx_m) >= resolution_m * 0.5 or abs(dy_m) >= resolution_m * 0.5
    apply = 1.0 if (improves and nontrivial) else 0.0
    if apply < 1.0:
        dx_m, dy_m = 0.0, 0.0
        best_iou = iou0
    return {
        "dx_m": float(dx_m),
        "dy_m": float(dy_m),
        "peak_iou": float(best_iou),
        "iou0": float(iou0),
        "resolution_m": float(resolution_m),
        "applied": apply,
    }
