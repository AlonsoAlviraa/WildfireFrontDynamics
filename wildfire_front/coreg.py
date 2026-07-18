"""Residual coregistration between consecutive front observations.

Estimates a translation that maximises coarse mask IoU so georef drift does
not inflate ROS. Raster helpers stamp vertices and soft-fill component bboxes
to provide correlation mass for structural alignment.
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
) -> np.ndarray:
    """Coarse raster of main component(s) for correlation.

    Fills each component bounding box with ``soft_fill`` mass, then stamps
    polygon vertices and a small centroid neighbourhood at 1.0 so alignment
    has both extent and structural peaks.
    """
    h, w = shape
    grid = np.zeros((h, w), dtype=np.float32)
    ox, oy = origin
    fill = float(soft_fill)
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
            # Soft bbox fill for correlation mass (was no-op np.maximum(..., 0)).
            if fill > 0:
                grid[r0:r1, c0:c1] = np.maximum(grid[r0:r1, c0:c1], fill)
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


def estimate_coreg_translation(
    previous: FrontObservation,
    current: FrontObservation,
    *,
    resolution_m: float = 4.0,
    max_shift_m: float = 60.0,
) -> dict[str, float]:
    """Estimate translation (dx, dy) to apply to *current* to align with previous.

    Maximises coarse IoU of rasterised fronts. Structural fix for residual
    georeferencing drift between consecutive drone orthos.
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

    def _iou_at(dx: int, dy: int) -> float:
        shifted = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
        if dy > 0:
            shifted[:dy, :] = 0
        elif dy < 0:
            shifted[dy:, :] = 0
        if dx > 0:
            shifted[:, :dx] = 0
        elif dx < 0:
            shifted[:, dx:] = 0
        inter = np.logical_and(a > 0, shifted > 0).sum()
        union = np.logical_or(a > 0, shifted > 0).sum()
        return float(inter) / float(union) if union else 0.0

    iou0 = _iou_at(0, 0)
    max_pix = int(math.ceil(max_shift_m / resolution_m))
    best_iou = iou0
    best = (0, 0)
    # Coarse search every 2 pixels then refine
    step = 2 if max_pix > 6 else 1
    for dy in range(-max_pix, max_pix + 1, step):
        for dx in range(-max_pix, max_pix + 1, step):
            iou = _iou_at(dx, dy)
            if iou > best_iou:
                best_iou = iou
                best = (dx, dy)

    # Local refine
    cx, cy = best
    for dy in range(cy - step, cy + step + 1):
        for dx in range(cx - step, cx + step + 1):
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
