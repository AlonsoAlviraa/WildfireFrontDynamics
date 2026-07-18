"""Tests for clean12 / legacy17 feature schemas."""

from __future__ import annotations

import numpy as np

from wildfire_front.ml.feature_schema import (
    CLEAN12_NAMES,
    PHYSICS14_NAMES,
    build_channels_from_fields,
    count_constant_channels,
    schema_channel_count,
)


def _synthetic_fields(h: int = 16, w: int = 16) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:h, 0:w]
    elevation = 400.0 + 0.5 * xx + 0.2 * yy
    wind_dir = np.full((h, w), 45.0, dtype=np.float32)
    wind_speed = np.full((h, w), 5.0, dtype=np.float32)
    max_temp = np.full((h, w), 305.0, dtype=np.float32)  # Kelvin
    min_temp = np.full((h, w), 290.0, dtype=np.float32)
    humidity = np.full((h, w), 30.0, dtype=np.float32)
    precip = np.zeros((h, w), dtype=np.float32)
    veg = np.clip(0.3 + 0.01 * xx, 0, 1).astype(np.float32)
    erc = np.full((h, w), 55.0, dtype=np.float32)
    return {
        "elevation": elevation.astype(np.float32),
        "wind_dir": wind_dir,
        "wind_speed": wind_speed,
        "max_temp": max_temp,
        "min_temp": min_temp,
        "humidity": humidity,
        "precip": precip,
        "veg": veg,
        "erc": erc,
    }


def test_clean12_shape_and_no_dead_channels_with_variation() -> None:
    fields = _synthetic_fields()
    # Spatially varying wind direction so sin/cos are not all equal across map
    # (still may be constant per-channel if uniform dir — use gradient)
    h, w = 16, 16
    fields["wind_dir"] = (np.linspace(0, 350, h * w).reshape(h, w)).astype(np.float32)
    fields["wind_speed"] = (2.0 + 0.1 * np.arange(h)[:, None] * np.ones((h, w))).astype(np.float32)
    ch = build_channels_from_fields("clean12", **fields)
    assert ch.shape == (12, 16, 16)
    assert schema_channel_count("clean12") == 12
    assert len(CLEAN12_NAMES) == 12
    # Elevation/slope/temp etc. should not be all-dead
    dead = count_constant_channels(ch)
    assert dead < 6, f"too many constant channels in clean12: {dead}"


def test_legacy17_has_constant_placeholders() -> None:
    fields = _synthetic_fields()
    ch = build_channels_from_fields("legacy17", **fields)
    assert ch.shape == (17, 16, 16)
    # Channels 7-10 and 14-15 are designed constants in raw space; after norm
    # they remain spatially constant.
    dead = count_constant_channels(ch)
    assert dead >= 4


def test_clean12_finite_and_clipped() -> None:
    fields = _synthetic_fields()
    fields["elevation"][0, 0] = np.nan
    ch = build_channels_from_fields("clean12", **fields)
    assert np.isfinite(ch).all()
    assert float(ch.max()) <= 10.0
    assert float(ch.min()) >= -10.0


def test_wind_vector_changes_with_direction() -> None:
    fields_a = _synthetic_fields()
    fields_b = _synthetic_fields()
    fields_a["wind_dir"] = np.full((16, 16), 0.0, dtype=np.float32)
    fields_b["wind_dir"] = np.full((16, 16), 90.0, dtype=np.float32)
    a = build_channels_from_fields("clean12", **fields_a)
    b = build_channels_from_fields("clean12", **fields_b)
    # wind_sin / wind_cos channels differ
    assert not np.allclose(a[7], b[7]) or not np.allclose(a[8], b[8])


def test_physics14_shape_and_names() -> None:
    fields = _synthetic_fields()
    h, w = 16, 16
    fields["wind_dir"] = (np.linspace(0, 350, h * w).reshape(h, w)).astype(np.float32)
    fields["min_temp"] = np.full((h, w), 280.0, dtype=np.float32)
    fields["max_temp"] = np.full((h, w), 305.0, dtype=np.float32)
    ch = build_channels_from_fields("physics14", **fields)
    assert ch.shape == (14, 16, 16)
    assert schema_channel_count("physics14") == 14
    assert len(PHYSICS14_NAMES) == 14
    assert np.isfinite(ch).all()
    # tmin/tmax not identical after norm when inputs differ
    assert not np.allclose(ch[4], ch[5])


def test_physics15_adds_upslope_channel() -> None:
    fields = _synthetic_fields()
    fields["wind_dir"] = np.full((16, 16), 45.0, dtype=np.float32)
    fields["wind_speed"] = np.full((16, 16), 8.0, dtype=np.float32)
    ch = build_channels_from_fields("physics15", **fields)
    assert ch.shape[0] == 15
    assert schema_channel_count("physics15") == 15
    assert np.isfinite(ch[14]).all()


def test_physics14_drought_slot_varies_with_ffmc_inputs() -> None:
    fields_wet = _synthetic_fields()
    fields_dry = _synthetic_fields()
    fields_wet["precip"] = np.full((16, 16), 20.0, dtype=np.float32)
    fields_dry["precip"] = np.zeros((16, 16), dtype=np.float32)
    fields_wet["humidity"] = np.full((16, 16), 90.0, dtype=np.float32)
    fields_dry["humidity"] = np.full((16, 16), 15.0, dtype=np.float32)
    wet = build_channels_from_fields("physics14", **fields_wet)
    dry = build_channels_from_fields("physics14", **fields_dry)
    # drought_or_ffmc channel index 13
    assert not np.allclose(wet[13], dry[13])
