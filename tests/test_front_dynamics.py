"""Structural front dynamics engine tests."""

from __future__ import annotations

import numpy as np

from wildfire_front.coreg import rasterize_main
from wildfire_front.front_dynamics import (
    estimate_coreg_translation,
    perimeter_m,
    run_front_dynamics,
)
from wildfire_front.models import FrontObservation


def _square(cx: float, cy: float, half: float) -> tuple:
    return (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
        (cx - half, cy - half),
    )


def _obs(t: float, half: float, cx: float = 0.0, cy: float = 0.0) -> FrontObservation:
    return FrontObservation(
        observation_id=f"o{t}",
        event_id="e",
        sensor_id="s",
        time_s=t,
        observed_at=f"t{t}",
        components=(_square(cx, cy, half),),
        estimated_error_m=1.0,
        coordinate_system="projected_metric",
        resolution_m=1.0,
        crs="EPSG:32630",
        method="test",
    )


def test_perimeter_square() -> None:
    # half=10 → side 20 → perimeter 80
    p = perimeter_m(_square(0, 0, 10))
    assert abs(p - 80.0) < 1e-6


def test_growing_front_positive_area_ros() -> None:
    # Grow from half=10 to half=16 over 2 minutes → isotropic ROS > 0
    obs = [_obs(0.0, 10.0), _obs(120.0, 16.0)]
    result = run_front_dynamics(obs, enable_coreg=False)
    assert result.summary["primary_ros_m_min"] is not None
    assert result.summary["primary_ros_m_min"] > 0
    assert result.summary["structural_grade"] in {"A", "B"}
    area_med = result.summary["ros_area"]["median"]
    assert area_med is not None and area_med > 0


def test_coreg_detects_translation() -> None:
    prev = _obs(0.0, 12.0, cx=0.0, cy=0.0)
    curr = _obs(60.0, 12.0, cx=20.0, cy=0.0)  # same size, shifted +20 m east
    coreg = estimate_coreg_translation(prev, curr, resolution_m=2.0, max_shift_m=40.0)
    # Should recover ~-20 m on current to align (or +20 depending sign convention)
    assert abs(coreg["dx_m"]) >= 10.0
    assert coreg["peak_iou"] > 0.1


def test_rasterize_soft_fill_adds_mass() -> None:
    """H1 regression: bbox soft-fill must add occupancy vs vertex stamps alone."""
    obs = _obs(0.0, 12.0)
    origin = (-40.0, -40.0)
    g_soft = rasterize_main(obs, origin, 2.0, (50, 50), soft_fill=0.3)
    g_hard = rasterize_main(obs, origin, 2.0, (50, 50), soft_fill=0.0)
    assert g_soft.dtype == np.float32
    assert (g_soft > 0).sum() > (g_hard > 0).sum()
    assert (g_soft == 0.3).any()


def test_engine_fuses_without_crash_on_shrink() -> None:
    obs = [_obs(0.0, 20.0), _obs(60.0, 10.0)]
    result = run_front_dynamics(obs, enable_coreg=False)
    assert "structural_grade" in result.summary
    assert result.summary["n_pairs"] == 1
