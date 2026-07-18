"""Precise sector ROS from local normal-ray samples (angle_deg + speed)."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

# Plausible local ROS for aerial thermal sampling (m/min)
_MAX_LOCAL = 60.0
_MIN_LOCAL = 0.2


def _angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings (deg)."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def load_local_speed_rows(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("observable", "")).lower() not in {"true", "1", "yes"}:
                continue
            try:
                spd = float(r["speed_m_min"])
                ang = float(r["angle_deg"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (_MIN_LOCAL <= spd <= _MAX_LOCAL):
                continue
            rows.append(
                {
                    "speed_m_min": spd,
                    "angle_deg": ang % 360.0,
                    "time_start_s": r.get("time_start_s"),
                    "time_end_s": r.get("time_end_s"),
                }
            )
    return rows


def sector_ros_from_local_samples(
    samples: list[dict[str, Any]],
    *,
    expansion_bearing_deg: float | None,
    half_width_deg: float = 50.0,
    scale_to_primary_m_min: float | None = None,
) -> dict[str, Any]:
    """Median ROS in head / flank / rear from directed local samples.

    Head = samples within ±half_width of expansion bearing.
    Rear = within ±half_width of opposite bearing.
    Flank = remaining samples.

    If ``scale_to_primary_m_min`` is set (bulk multi-estimator ROS), sector
    values are scaled so the local overall median matches primary — keeps
    INFOCAM-calibrated scale while using directional structure from rays.
    """
    if not samples:
        return {
            "status": "abstained",
            "reason": "no_observable_local_speeds",
            "method": "local_normal_ray_sectors",
            "sectors": None,
            "n_samples": 0,
        }

    speeds = np.asarray([s["speed_m_min"] for s in samples], dtype=float)
    angles = np.asarray([s["angle_deg"] for s in samples], dtype=float)

    # If no expansion bearing, use circular mean of sample angles as head
    if expansion_bearing_deg is None:
        rad = np.deg2rad(angles)
        mean_sin = float(np.mean(np.sin(rad)))
        mean_cos = float(np.mean(np.cos(rad)))
        expansion_bearing_deg = float(np.rad2deg(math.atan2(mean_sin, mean_cos)) % 360.0)

    head_b = float(expansion_bearing_deg) % 360.0
    rear_b = (head_b + 180.0) % 360.0

    head_sp: list[float] = []
    rear_sp: list[float] = []
    flank_sp: list[float] = []
    for spd, ang in zip(speeds, angles, strict=False):
        if _angle_diff(float(ang), head_b) <= half_width_deg:
            head_sp.append(float(spd))
        elif _angle_diff(float(ang), rear_b) <= half_width_deg:
            rear_sp.append(float(spd))
        else:
            flank_sp.append(float(spd))

    def _med(vals: list[float]) -> float | None:
        if not vals:
            return None
        return float(np.median(np.asarray(vals, dtype=float)))

    head = _med(head_sp)
    rear = _med(rear_sp)
    flank = _med(flank_sp)
    overall = float(np.median(speeds))

    # Fill missing bins from overall (explicitly marked)
    filled = []
    if head is None:
        head = overall
        filled.append("head")
    if flank is None:
        flank = overall
        filled.append("flank")
    if rear is None:
        rear = min(overall * 0.6, flank)
        filled.append("rear")

    # Enforce guidance ordering when data-driven head < rear (rare noise)
    if head < rear:
        head, rear = max(head, rear), min(head, rear)

    scale = 1.0
    scaled = False
    if scale_to_primary_m_min is not None and scale_to_primary_m_min > 0 and overall > 0:
        scale = float(scale_to_primary_m_min) / overall
        head *= scale
        flank *= scale
        rear *= scale
        overall = float(scale_to_primary_m_min)
        scaled = True

    return {
        "status": "estimated",
        "method": "local_normal_ray_sectors" + ("_scaled_to_bulk" if scaled else ""),
        "half_width_deg": half_width_deg,
        "expansion_bearing_deg": round(head_b, 2),
        "scale_to_primary": round(scale, 4) if scaled else None,
        "n_samples": int(len(samples)),
        "n_head": len(head_sp),
        "n_flank": len(flank_sp),
        "n_rear": len(rear_sp),
        "filled_from_overall": filled,
        "sectors": {
            "head_m_min": round(head, 4),
            "flank_m_min": round(flank, 4),
            "rear_m_min": round(rear, 4),
            "primary_m_min": round(overall, 4),
            "head_bearing_deg": round(head_b, 2),
            "head_sector_deg": [
                round((head_b - half_width_deg) % 360, 2),
                round((head_b + half_width_deg) % 360, 2),
            ],
            "rear_bearing_deg": round(rear_b, 2),
        },
        "uncertainty_m_min": {
            "p25": round(float(np.percentile(speeds, 25)) * scale, 4),
            "p75": round(float(np.percentile(speeds, 75)) * scale, 4),
            "half_iqr": round(
                0.5 * (float(np.percentile(speeds, 75) - np.percentile(speeds, 25))) * scale,
                4,
            ),
            "n": int(len(samples)),
        },
        "label_es": (
            "ROS por sector desde rayos normales locales (ángulo de avance), "
            + ("escalado al ROS bulk multi-estimador. " if scaled else "")
            + "No es despacho táctico validado."
        ),
    }
