"""Tests for wildfire_front.ml.normalization — critical channel scaling."""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.ml.normalization import (
    _CHANNEL_STATS,
    normalize_channels,
    normalize_channels_inplace,
)

N_CHANNELS = 17


def _raw_channels(h: int = 8, w: int = 8) -> np.ndarray:
    """Synthetic raw 17-channel tensor with realistic magnitudes."""
    rng = np.random.default_rng(0)
    ch = np.zeros((N_CHANNELS, h, w), dtype=np.float32)
    ch[0] = rng.uniform(0.0, 1.5, size=(h, w))  # slope rad
    ch[1] = rng.uniform(-3.14, 3.14, size=(h, w))  # aspect
    ch[2] = rng.uniform(-5.0, 40.0, size=(h, w))  # temp C
    ch[3] = rng.uniform(10.0, 90.0, size=(h, w))  # humidity %
    ch[4] = rng.uniform(0.0, 25.0, size=(h, w))  # wind m/s
    ch[5] = rng.uniform(0.0, 360.0, size=(h, w))  # wind dir deg
    ch[6] = rng.uniform(0.0, 20.0, size=(h, w))  # precip
    ch[7] = rng.uniform(950.0, 1030.0, size=(h, w))  # pressure
    ch[8] = rng.uniform(0.0, 100.0, size=(h, w))  # cloud
    ch[9] = rng.uniform(0.0, 30.0, size=(h, w))  # visibility
    ch[10] = rng.uniform(-10.0, 20.0, size=(h, w))  # dew point
    ch[11] = rng.uniform(-1.0, 1.0, size=(h, w))  # NDVI-like
    for i in range(12, 16):
        ch[i] = rng.integers(0, 2, size=(h, w)).astype(np.float32)  # FSM one-hot
    ch[16] = rng.uniform(0.0, 101.0, size=(h, w))  # FFMC
    return ch


class TestNormalizeChannels:
    def test_output_shape_and_dtype(self):
        raw = _raw_channels()
        out = normalize_channels(raw)
        assert out.shape == raw.shape
        assert out.dtype == np.float32

    def test_does_not_mutate_input(self):
        raw = _raw_channels()
        snapshot = raw.copy()
        _ = normalize_channels(raw)
        np.testing.assert_array_equal(raw, snapshot)

    def test_finite_output(self):
        raw = _raw_channels()
        out = normalize_channels(raw)
        assert np.isfinite(out).all()

    def test_clamp_to_plus_minus_10(self):
        raw = np.full((N_CHANNELS, 4, 4), 1.0e6, dtype=np.float32)
        out = normalize_channels(raw)
        assert out.max() <= 10.0
        assert out.min() >= -10.0

    def test_nan_inf_sanitized_to_zero_before_norm(self):
        raw = _raw_channels()
        raw[2, 0, 0] = np.nan
        raw[7, 1, 1] = np.inf
        raw[16, 2, 2] = -np.inf
        out = normalize_channels(raw)
        # Sanitized zeros then affine: (0 - sub) / div, then ±10 clamp
        sub2, div2 = _CHANNEL_STATS[2]
        sub7, div7 = _CHANNEL_STATS[7]
        sub16, div16 = _CHANNEL_STATS[16]
        expected2 = float(np.clip((0.0 - sub2) / div2, -10.0, 10.0))
        expected7 = float(np.clip((0.0 - sub7) / div7, -10.0, 10.0))
        expected16 = float(np.clip((0.0 - sub16) / div16, -10.0, 10.0))
        assert out[2, 0, 0] == pytest.approx(expected2)
        assert out[7, 1, 1] == pytest.approx(expected7)
        assert out[16, 2, 2] == pytest.approx(expected16)
        assert np.isfinite(out).all()

    def test_affine_formula_per_channel(self):
        raw = np.zeros((N_CHANNELS, 2, 2), dtype=np.float32)
        for i, (sub, div) in enumerate(_CHANNEL_STATS):
            raw[i] = float(sub + div)  # → normalized 1.0 before clamp
        out = normalize_channels(raw)
        for i in range(N_CHANNELS):
            np.testing.assert_allclose(out[i], 1.0, rtol=1e-5)

    def test_channel_stats_count(self):
        assert len(_CHANNEL_STATS) == N_CHANNELS
        for _sub, div in _CHANNEL_STATS:
            assert div != 0.0


class TestNormalizeChannelsInplace:
    def test_inplace_matches_copy_api(self):
        raw = _raw_channels()
        expected = normalize_channels(raw)
        inplace = raw.copy()
        result = normalize_channels_inplace(inplace)
        assert result is inplace
        np.testing.assert_allclose(inplace, expected, rtol=1e-5)

    def test_inplace_sanitizes_nan(self):
        raw = _raw_channels()
        raw[0, 0, 0] = np.nan
        normalize_channels_inplace(raw)
        assert np.isfinite(raw).all()
