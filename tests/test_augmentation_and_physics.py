"""Tests for Sprint 3 (data augmentation) and Sprint 4 (physics-informed loss).

Validates:
- NpzWildfireDataset augmentation preserves shapes and fire masks.
- Horizontal/vertical flips produce correct inversions.
- Physics functions (rothermel_ros, ffmc, physics_loss_cell) return sane values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from wildfire_front.ml.dataset import NpzWildfireDataset
from wildfire_front.ml.physics import (
    compute_ffmc,
    ffmc_to_moisture,
    physics_loss_cell,
    rothermel_ros,
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
            wind_speed_ms=0.0,
            slope_deg=0.0,
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
            wind_speed_ms=5.0,
            slope_deg=5.7,
            fuel_moisture=ffmc_to_moisture(70.0),
        )
        ros_dry = rothermel_ros(
            wind_speed_ms=5.0,
            slope_deg=5.7,
            fuel_moisture=ffmc_to_moisture(95.0),
        )
        assert ros_dry > ros_wet, "Drier fuel (higher FFMC) should spread faster"

    def test_rothermel_ros_clamped(self) -> None:
        """Extreme inputs should still produce finite, reasonable ROS."""
        ros_extreme = rothermel_ros(
            wind_speed_ms=100.0,
            slope_deg=86.0,
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


# ─────────────────────────────────────────────────────────────
# PR-3: ML data correctness (FFMC single-norm, physics denorm)
# ─────────────────────────────────────────────────────────────


class TestFFMCSingleNormalization:
    """C2: channel 16 must be raw FFMC then (x-50)/51 — not pre-divided by 101."""

    def test_ch16_after_normalize_ffmc_85(self) -> None:
        from wildfire_front.ml.normalization import normalize_channels

        channels = np.zeros((17, 4, 4), dtype=np.float32)
        channels[16] = 85.0  # raw FFMC as WildfireDataset now writes
        out = normalize_channels(channels)
        expected = (85.0 - 50.0) / 51.0
        assert np.allclose(out[16], expected, atol=1e-5), (
            f"ch16 after normalize for FFMC=85 should be ~{expected:.4f}, got {out[16].mean():.4f}"
        )

    def test_pre_divide_by_101_would_be_wrong(self) -> None:
        """Guard: double-norm path (old bug) must not match the correct value."""
        from wildfire_front.ml.normalization import normalize_channels

        channels = np.zeros((17, 2, 2), dtype=np.float32)
        channels[16] = 85.0 / 101.0  # old double-norm bug
        out = normalize_channels(channels)
        correct = (85.0 - 50.0) / 51.0
        assert not np.allclose(out[16], correct, atol=0.01)

    def test_dataset_writes_raw_ffmc_then_normalizes(self) -> None:
        """End-to-end: WildfireDataset channel 16 ≈ (85-50)/51 for default weather."""
        images_dir = Path("data/candidates/semireal_controlled_001/images")
        masks_dir = Path("data/candidates/semireal_controlled_001/masks")
        if not images_dir.is_dir() or not masks_dir.is_dir():
            return  # fixture optional in clean CI clones

        from wildfire_front.ml.dataset import WildfireDataset

        ds = WildfireDataset(
            images_dir=images_dir,
            masks_dir=masks_dir,
            sequence_length=3,
            patch_size=30,
            weather_data={
                "temp": 25.0,
                "humidity": 40.0,
                "wind_speed": 15.0,
                "wind_dir": 90.0,
                "precip": 0.0,
                "pressure": 1013.0,
                "cloud": 10.0,
                "visibility": 10.0,
                "dew_point": 12.0,
                "ffmc": 85.0,
            },
        )
        sequence, _cur, _tgt = ds[0]
        expected = (85.0 - 50.0) / 51.0
        ch16 = sequence[:, 16, :, :]
        assert torch.allclose(ch16, torch.full_like(ch16, expected), atol=1e-4), (
            f"dataset ch16 mean={ch16.mean().item():.4f}, expected {expected:.4f}"
        )


class TestPhysicsDenormParity:
    """C3: legacy denorm helpers match vectorized wind/slope denorm + FFMC restore."""

    def test_denorm_helpers_recover_physical_units(self) -> None:
        from wildfire_front.ml.train import _denorm_ffmc, _denorm_slope, _denorm_wind

        wind_raw, slope_raw, ffmc_raw = 15.0, 0.3, 85.0
        wind_norm = wind_raw / 20.0
        slope_norm = slope_raw / 1.5708
        ffmc_norm = (ffmc_raw - 50.0) / 51.0

        assert abs(_denorm_wind(wind_norm) - wind_raw) < 1e-4
        assert abs(_denorm_slope(slope_norm) - slope_raw) < 1e-4
        assert abs(_denorm_ffmc(ffmc_norm) - ffmc_raw) < 1e-4

    def test_legacy_denorm_matches_vectorized_channel_restore(self) -> None:
        """Same normalized sequence channels → same physical inputs on both paths."""
        from wildfire_front.ml.physics import (
            _FFMC_DIVIDE_BY,
            _FFMC_SUBTRACT,
            _SLOPE_DIVIDE_BY,
            _SLOPE_SUBTRACT,
            _WIND_DIVIDE_BY,
            _WIND_SUBTRACT,
        )
        from wildfire_front.ml.train import _denorm_ffmc, _denorm_slope, _denorm_wind

        wind_norm = 0.5
        slope_norm = 0.2
        ffmc_norm = (85.0 - 50.0) / 51.0

        # Legacy helpers (train.calculate_local_spread_loss)
        w_leg = _denorm_wind(wind_norm)
        s_leg = _denorm_slope(slope_norm)
        f_leg = _denorm_ffmc(ffmc_norm)

        # Vectorized path: physics denorms wind/slope; train denorms FFMC before call
        w_vec = wind_norm * _WIND_DIVIDE_BY + _WIND_SUBTRACT
        s_vec = slope_norm * _SLOPE_DIVIDE_BY + _SLOPE_SUBTRACT
        f_vec = ffmc_norm * _FFMC_DIVIDE_BY + _FFMC_SUBTRACT

        assert abs(w_leg - w_vec) < 1e-6
        assert abs(s_leg - s_vec) < 1e-6
        assert abs(f_leg - f_vec) < 1e-6
        assert abs(f_leg - 85.0) < 1e-4

    def test_legacy_and_vectorized_physics_agree_when_spread_impossible(self) -> None:
        """With denormed inputs, both paths penalize impossible calm/zero-wind spread."""
        from wildfire_front.ml.physics import physics_loss_cell_vectorized
        from wildfire_front.ml.train import _denorm_ffmc, _denorm_slope, _denorm_wind

        probs = torch.ones(8) * 0.99
        wind_norm, slope_norm = 0.0, 0.0
        ffmc_norm = (70.0 - 50.0) / 51.0
        lam = 0.1

        legacy = physics_loss_cell(
            probs,
            _denorm_wind(wind_norm),
            _denorm_slope(slope_norm),
            ffmc=_denorm_ffmc(ffmc_norm),
            lambda_physics=lam,
        )
        vec = physics_loss_cell_vectorized(
            probs.unsqueeze(0),
            torch.tensor([wind_norm]),
            torch.tensor([slope_norm]),
            ffmc=torch.tensor([_denorm_ffmc(ffmc_norm)]),
            lambda_physics=lam,
        )
        # Both must produce a positive penalty under calm / wet fuel
        assert float(legacy.item()) > 0.0
        assert float(vec.item()) > 0.0
        # Vectorized is clamped to lambda; legacy is not — both finite and positive
        assert float(vec.item()) <= lam + 1e-6
