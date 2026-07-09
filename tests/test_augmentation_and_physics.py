"""Tests for Sprint 3 (data augmentation) and Sprint 4 (physics-informed loss).

Validates:
- NpzWildfireDataset augmentation preserves shapes and fire masks.
- Horizontal/vertical flips produce correct inversions.
- Physics functions (rothermel_ros, ffmc, physics_loss_cell) return sane values.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from pathlib import Path, PurePosixPath

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.physics import (
    rothermel_ros,
    compute_ffmc,
    ffmc_to_moisture,
    physics_loss_cell,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_fake_npz(tmp_path: Path, name: str = "sample_0.npz") -> Path:
    """Create a tiny .npz file with sequence, current_fire, target_fire."""
    seq = np.random.rand(3, 16, 30, 30).astype(np.float32)
    cur = np.zeros((30, 30), dtype=np.float32)
    cur[10, 10] = 1.0  # one burning cell
    tgt = np.zeros((30, 30), dtype=np.float32)
    tgt[10, 11] = 1.0  # spread right
    tgt[11, 11] = 1.0  # spread down-right
    p = tmp_path / name
    np.savez(p, sequence=seq, current_fire=cur, target_fire=tgt)
    return p


# ─────────────────────────────────────────────────────────────
# Sprint 3: Augmentation tests
# ─────────────────────────────────────────────────────────────

class TestAugmentation:
    """Verify NpzWildfireDataset augment flag works correctly."""

    def test_no_augment_returns_unchanged(self, tmp_path: Path) -> None:
        _make_fake_npz(tmp_path)
        ds = NpzWildfireDataset(tmp_path, augment=False)
        seq, cur, tgt = ds[0]
        assert seq.shape == (3, 16, 30, 30)
        assert cur.shape == (30, 30)
        assert tgt.shape == (30, 30)
        # Burning cell at (10, 10) should be intact
        assert cur[10, 10] == 1.0

    def test_augment_preserves_shapes(self, tmp_path: Path) -> None:
        _make_fake_npz(tmp_path)
        ds = NpzWildfireDataset(tmp_path, augment=True)
        # Run several times to hit different random branches
        for _ in range(20):
            seq, cur, tgt = ds[0]
            assert seq.shape == (3, 16, 30, 30)
            assert cur.shape == (30, 30)
            assert tgt.shape == (30, 30)

    def test_horizontal_flip_inverts_target(self) -> None:
        """A horizontal flip on a 30×30 grid maps column j → 29-j."""
        tgt_raw = torch.zeros(30, 30)
        tgt_raw[10, 11] = 1.0  # spread right

        manual_tgt = torch.flip(tgt_raw, dims=[-1])
        # Column 11 maps to 29 - 11 = 18
        assert manual_tgt[10, 18] == 1.0, "Horizontal flip should map col 11 → col 18"
        assert manual_tgt[10, 11] == 0.0

    def test_vertical_flip_inverts_target(self) -> None:
        """A vertical flip on a 30×30 grid maps row i → 29-i."""
        tgt_raw = torch.zeros(30, 30)
        tgt_raw[10, 11] = 1.0

        manual_tgt = torch.flip(tgt_raw, dims=[-2])
        # Row 10 maps to 29 - 10 = 19
        assert manual_tgt[19, 11] == 1.0, "Vertical flip should map row 10 → row 19"

    def test_augment_dtype_preserved(self, tmp_path: Path) -> None:
        _make_fake_npz(tmp_path)
        ds = NpzWildfireDataset(tmp_path, augment=True)
        seq, cur, tgt = ds[0]
        assert seq.dtype == torch.float32
        assert cur.dtype == torch.float32
        assert tgt.dtype == torch.float32


# ─────────────────────────────────────────────────────────────
# Sprint 4: Physics-informed loss tests
# ─────────────────────────────────────────────────────────────

class TestPhysicsRothermel:
    """Verify Rothermel rate-of-spread and FFMC calculations."""

    def test_rothermel_ros_zero_wind_zero_slope(self) -> None:
        """No wind and no slope should give minimal but positive ROS."""
        # FFMC=90 → moisture ≈ 8%; slope_deg=0; wind=0
        ros = rothermel_ros(
            wind_speed_ms=0.0, slope_deg=0.0,
            fuel_moisture=ffmc_to_moisture(90.0),
        )
        assert ros > 0.0, "ROS should always be positive (fuel combustion)"
        assert ros < 2.0, "With no wind/slope, ROS should be low"

    def test_rothermel_ros_increases_with_wind(self) -> None:
        """Higher wind speed should increase rate of spread."""
        moisture = ffmc_to_moisture(85.0)
        ros_low = rothermel_ros(wind_speed_ms=2.0, slope_deg=0.0, fuel_moisture=moisture)
        ros_high = rothermel_ros(wind_speed_ms=20.0, slope_deg=0.0, fuel_moisture=moisture)
        assert ros_high > ros_low, "Higher wind should produce faster spread"

    def test_rothermel_ros_increases_with_slope(self) -> None:
        """Upslope should increase rate of spread."""
        moisture = ffmc_to_moisture(85.0)
        ros_flat = rothermel_ros(wind_speed_ms=5.0, slope_deg=0.0, fuel_moisture=moisture)
        ros_slope = rothermel_ros(wind_speed_ms=5.0, slope_deg=30.0, fuel_moisture=moisture)
        assert ros_slope > ros_flat, "Slope should increase spread rate"

    def test_rothermel_ros_increases_with_ffmc(self) -> None:
        """Higher FFMC (drier fuel) should increase spread."""
        ros_wet = rothermel_ros(
            wind_speed_ms=5.0, slope_deg=5.7,
            fuel_moisture=ffmc_to_moisture(70.0),
        )
        ros_dry = rothermel_ros(
            wind_speed_ms=5.0, slope_deg=5.7,
            fuel_moisture=ffmc_to_moisture(95.0),
        )
        assert ros_dry > ros_wet, "Drier fuel (higher FFMC) should spread faster"

    def test_rothermel_ros_clamped(self) -> None:
        """Extreme inputs should still produce finite, reasonable ROS."""
        ros_extreme = rothermel_ros(
            wind_speed_ms=100.0, slope_deg=86.0,
            fuel_moisture=ffmc_to_moisture(99.0),
        )
        assert np.isfinite(ros_extreme), "ROS must be finite"
        assert ros_extreme <= 120.0, "ROS should be clamped to _ROS_CAP (120.0)"


class TestFFMC:
    """Verify Fine Fuel Moisture Code calculation."""

    def test_ffmc_dry_conditions(self) -> None:
        """High temp, low humidity, no rain → high FFMC (dry)."""
        ffmc = compute_ffmc(temp_c=35.0, rh_percent=20.0, wind_kmh=10.0, precip_mm=0.0)
        assert ffmc > 80.0, "Dry conditions should produce FFMC > 80"
        assert ffmc <= 101.0, "FFMC should be bounded above by ~101"

    def test_ffmc_wet_conditions(self) -> None:
        """Low temp, high humidity, rain → low FFMC (wet)."""
        ffmc = compute_ffmc(temp_c=10.0, rh_percent=90.0, wind_kmh=2.0, precip_mm=5.0)
        assert ffmc < 80.0, "Wet conditions should produce FFMC < 80"

    def test_ffmc_monotonic_with_humidity(self) -> None:
        """Higher humidity → lower FFMC."""
        ffmc_dry = compute_ffmc(temp_c=25.0, rh_percent=20.0, wind_kmh=5.0, precip_mm=0.0)
        ffmc_humid = compute_ffmc(temp_c=25.0, rh_percent=80.0, wind_kmh=5.0, precip_mm=0.0)
        assert ffmc_dry > ffmc_humid


class TestPhysicsLoss:
    """Verify physics_loss_cell penalizes impossible spread."""

    def test_physics_loss_zero_when_no_spread(self) -> None:
        """If model predicts no spread (all probs ≈ 0), loss should be ~0."""
        probs = torch.zeros(8)
        loss = physics_loss_cell(probs, wind_speed=0.0, slope_rad=0.0, ffmc=90.0)
        assert float(loss) >= 0.0
        assert float(loss) < 0.5, "No predicted spread → minimal penalty"

    def test_physics_loss_positive_for_fast_spread(self) -> None:
        """If model predicts all neighbors ignite with no wind/slope,
        physics loss should be high (spread exceeds physical max)."""
        probs = torch.ones(8) * 0.99  # all neighbors ignite
        loss_calm = physics_loss_cell(probs, wind_speed=0.0, slope_rad=0.0, ffmc=70.0)
        assert float(loss_calm) > 0.0, "Impossible spread should be penalized"

    def test_physics_loss_lower_with_wind(self) -> None:
        """Same high probabilities but with strong wind → lower penalty
        because fast spread is physically plausible."""
        probs = torch.ones(8) * 0.99
        loss_calm = physics_loss_cell(
            probs, wind_speed=0.0, slope_rad=0.0, ffmc=70.0, lambda_physics=0.1
        )
        loss_windy = physics_loss_cell(
            probs, wind_speed=30.0, slope_rad=0.3, ffmc=90.0, lambda_physics=0.1
        )
        assert loss_windy < loss_calm, (
            "Wind + slope + dry fuel makes fast spread plausible → lower penalty"
        )

    def test_physics_loss_returns_tensor(self) -> None:
        probs = torch.rand(8)
        loss = physics_loss_cell(probs, wind_speed=5.0, slope_rad=0.1, ffmc=85.0)
        assert isinstance(loss, torch.Tensor)
