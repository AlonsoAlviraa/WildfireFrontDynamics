"""NDWS feature schemas for wildfire spread models.

Schemas:

* ``legacy17`` — historical 17-channel tensor with constant placeholders
  (pressure/cloud/visibility/dewpoint) kept for checkpoint compatibility.
* ``clean12`` — informative channels only: elevation, terrain, meteo,
  wind vectors, vegetation, ERC. No constant padding.
* ``physics14`` — preferred for v25+: tmin/tmax split + drought/FFMC slot.

The trainer always appends ``prev_fire`` as an extra input channel.
See ``docs/ML_FEATURE_METHODOLOGY.md``.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

SchemaName = Literal["legacy17", "clean12", "physics14", "physics15"]

# Per-channel (subtract, divide) for clean12 — maps roughly to ~[0, 1] or [-1, 1].
CLEAN12_CHANNEL_STATS: list[tuple[float, float]] = [
    (500.0, 1500.0),  # 0 elevation m
    (0.0, 1.5708),  # 1 slope rad
    (0.0, 1.0),  # 2 aspect_sin
    (0.0, 1.0),  # 3 aspect_cos
    (15.0, 20.0),  # 4 temperature C
    (0.0, 100.0),  # 5 humidity %
    (0.0, 20.0),  # 6 wind speed m/s
    (0.0, 1.0),  # 7 wind_sin
    (0.0, 1.0),  # 8 wind_cos
    (0.0, 10.0),  # 9 precipitation mm
    (0.0, 1.0),  # 10 vegetation / NDVI
    (0.0, 1.0),  # 11 ERC normalized
]

# Historical 17-channel stats (must stay aligned with normalization.py).
LEGACY17_CHANNEL_STATS: list[tuple[float, float]] = [
    (0.0, 1.5708),
    (3.14159, 6.28318),
    (15.0, 20.0),
    (0.0, 100.0),
    (0.0, 20.0),
    (0.0, 360.0),
    (0.0, 10.0),
    (1000.0, 50.0),
    (0.0, 100.0),
    (0.0, 20.0),
    (5.0, 15.0),
    (0.0, 1.0),
    (0.0, 1.0),
    (0.0, 1.0),
    (0.0, 1.0),
    (0.0, 1.0),
    (50.0, 51.0),
]

CLEAN12_NAMES: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect_sin",
    "aspect_cos",
    "temperature",
    "humidity",
    "wind_speed",
    "wind_sin",
    "wind_cos",
    "precipitation",
    "vegetation",
    "erc",
)

# physics14: separate tmin/tmax + drought_or_ffmc (no constant padding).
PHYSICS14_CHANNEL_STATS: list[tuple[float, float]] = [
    (500.0, 1500.0),  # 0 elevation
    (0.0, 1.5708),  # 1 slope
    (0.0, 1.0),  # 2 aspect_sin
    (0.0, 1.0),  # 3 aspect_cos
    (15.0, 20.0),  # 4 tmin C
    (15.0, 20.0),  # 5 tmax C
    (0.0, 100.0),  # 6 humidity
    (0.0, 20.0),  # 7 wind_speed
    (0.0, 1.0),  # 8 wind_sin
    (0.0, 1.0),  # 9 wind_cos
    (0.0, 10.0),  # 10 precip
    (0.0, 1.0),  # 11 vegetation
    (0.0, 1.0),  # 12 erc
    (50.0, 51.0),  # 13 drought_or_ffmc (FFMC scale default; PDSI mapped to ~[0,1] then *101)
]

PHYSICS14_NAMES: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect_sin",
    "aspect_cos",
    "tmin",
    "tmax",
    "humidity",
    "wind_speed",
    "wind_sin",
    "wind_cos",
    "precipitation",
    "vegetation",
    "erc",
    "drought_or_ffmc",
)

# physics15 = physics14 + wind_upslope interaction (wind aligned with slope aspect).
PHYSICS15_CHANNEL_STATS: list[tuple[float, float]] = PHYSICS14_CHANNEL_STATS + [
    (0.0, 1.0),  # 14 wind_upslope in [-1,1] approx
]
PHYSICS15_NAMES: tuple[str, ...] = PHYSICS14_NAMES + ("wind_upslope",)


def schema_channel_count(schema: SchemaName) -> int:
    if schema == "clean12":
        return 12
    if schema == "physics14":
        return 14
    if schema == "physics15":
        return 15
    if schema == "legacy17":
        return 17
    raise ValueError(f"Unknown schema: {schema}")


def schema_channel_names(schema: SchemaName) -> tuple[str, ...]:
    if schema == "clean12":
        return CLEAN12_NAMES
    if schema == "physics14":
        return PHYSICS14_NAMES
    if schema == "physics15":
        return PHYSICS15_NAMES
    if schema == "legacy17":
        return tuple(f"legacy_{i}" for i in range(17))
    raise ValueError(f"Unknown schema: {schema}")


def normalize_with_stats(
    channels: np.ndarray,
    stats: list[tuple[float, float]],
) -> np.ndarray:
    """Affine normalize each channel and sanitize non-finite values."""
    channels = np.where(np.isfinite(channels), channels, 0.0).astype(np.float32, copy=False)
    out = channels.copy()
    n = min(out.shape[0], len(stats))
    for ci in range(n):
        sub, div = stats[ci]
        out[ci] = (out[ci] - sub) / div
    return np.clip(out, -10.0, 10.0).astype(np.float32)


def _as_celsius(temp: np.ndarray) -> np.ndarray:
    temp = np.asarray(temp, dtype=np.float32)
    if float(np.nanmax(temp)) > 200:
        return temp - 273.15
    return temp


def _wind_components(
    wind_speed: np.ndarray, wind_dir_deg: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Convert meteorological wind direction (degrees) to sin/cos components.

    Direction is "from which the wind blows". Components are unitless direction
    factors scaled later by wind speed only in the speed channel (sin/cos keep
    direction only) so CNN discontinuities at 0/360 disappear.
    """
    rad = np.deg2rad(np.asarray(wind_dir_deg, dtype=np.float32))
    return np.sin(rad).astype(np.float32), np.cos(rad).astype(np.float32)


def _terrain_from_elevation(elevation: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    elev = np.asarray(elevation, dtype=np.float32)
    dy, dx = np.gradient(elev)
    slope = np.arctan(np.sqrt(dx**2 + dy**2)).astype(np.float32)
    aspect = np.arctan2(-dy, dx).astype(np.float32)  # [-pi, pi]
    return elev, slope, aspect


def compute_ffmc(
    temp_c: np.ndarray,
    rh: np.ndarray,
    wind_kmh: np.ndarray,
    precip_mm: np.ndarray,
    prev_ffmc: float = 85.0,
) -> np.ndarray:
    """Fine Fuel Moisture Code (Van Wagner 1987), range [0, 101]."""
    temp_c = np.asarray(temp_c, dtype=np.float64)
    rh = np.asarray(rh, dtype=np.float64)
    wind_kmh = np.asarray(wind_kmh, dtype=np.float64)
    precip_mm = np.asarray(precip_mm, dtype=np.float64)
    prev = np.full_like(temp_c, prev_ffmc, dtype=np.float64)

    rf = np.where(precip_mm > 0.5, precip_mm - 0.5, 0.0)
    mo_prev = 147.2 * (101.0 - prev) / (59.5 + prev)
    mo_rain = mo_prev + 100.0 * rf / (10.0 + rf) * np.exp(
        -100.0 / (25.04 - 0.0759 * rf) - 8.62 / (1.0 + rf)
    )
    mo_rain = np.clip(mo_rain, 0.0, 250.0)

    ed = (
        0.942 * np.power(rh, 0.679)
        + 11.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp_c) * (1.0 - np.exp(-0.115 * rh))
    )
    ew = (
        0.618 * np.power(rh, 0.753)
        + 10.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp_c) * (1.0 - np.exp(-0.115 * rh))
    )

    is_drying = mo_rain > ed
    ko = np.where(is_drying, 1.0, ew / np.maximum(ed, 1e-6))
    k0 = 0.424 * (1.0 - np.power(rh / 100.0, 1.7)) + 0.0694 * np.sqrt(np.maximum(wind_kmh, 0.0)) * (
        1.0 - np.power(rh / 100.0, 8.0)
    )
    kd = ko * k0 * 0.581 * np.exp(21.06 - 0.0495 * mo_rain)
    mo_new = np.where(
        is_drying,
        ed + (mo_rain - ed) * np.power(10.0, -kd),
        ew - (ew - mo_rain) * np.power(10.0, -kd),
    )
    mo_new = np.clip(mo_new, 0.0, 250.0)
    ffmc = 59.5 * (250.0 - mo_new) / (147.2 + mo_new)
    return np.clip(ffmc, 0.0, 101.0).astype(np.float32)


def build_legacy17_channels(
    elevation: np.ndarray,
    wind_dir: np.ndarray,
    wind_speed: np.ndarray,
    max_temp: np.ndarray,
    min_temp: np.ndarray,
    humidity: np.ndarray,
    precip: np.ndarray,
    veg: np.ndarray,
    erc: np.ndarray,
) -> np.ndarray:
    """Build historical 17-channel tensor (includes constant placeholders)."""
    elev, slope, aspect = _terrain_from_elevation(elevation)
    max_temp = _as_celsius(max_temp)
    min_temp = _as_celsius(min_temp)
    temp_c = 0.5 * (min_temp + max_temp)
    wind_kmh = np.asarray(wind_speed, dtype=np.float32) * 3.6
    ffmc = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)

    channels = np.zeros((17, elev.shape[0], elev.shape[1]), dtype=np.float32)
    channels[0] = slope
    # Fix: map aspect [-pi, pi] -> [0, 1] via (aspect + pi) / 2pi.
    # Stored pre-norm as aspect + pi so legacy stats (sub=pi, div=2pi) stay valid.
    channels[1] = aspect + np.pi
    channels[2] = temp_c
    channels[3] = humidity
    channels[4] = wind_speed
    channels[5] = wind_dir
    channels[6] = precip
    channels[7] = 1013.0
    channels[8] = 10.0
    channels[9] = 10.0
    channels[10] = 12.0
    channels[11] = veg
    erc_norm = np.clip(np.asarray(erc, dtype=np.float32) / 100.0, 0.0, 1.0)
    channels[12] = erc_norm
    channels[13] = 1.0 - erc_norm
    channels[14] = 0.0
    channels[15] = 0.0
    channels[16] = ffmc
    return normalize_with_stats(channels, LEGACY17_CHANNEL_STATS)


def build_clean12_channels(
    elevation: np.ndarray,
    wind_dir: np.ndarray,
    wind_speed: np.ndarray,
    max_temp: np.ndarray,
    min_temp: np.ndarray,
    humidity: np.ndarray,
    precip: np.ndarray,
    veg: np.ndarray,
    erc: np.ndarray,
    drought: np.ndarray | None = None,
) -> np.ndarray:
    """Build clean 12-channel tensor with no constant padding."""
    elev, slope, aspect = _terrain_from_elevation(elevation)
    max_temp = _as_celsius(max_temp)
    min_temp = _as_celsius(min_temp)
    temp_c = 0.5 * (min_temp + max_temp)
    wind_sin, wind_cos = _wind_components(wind_speed, wind_dir)
    aspect_sin = np.sin(aspect).astype(np.float32)
    aspect_cos = np.cos(aspect).astype(np.float32)
    erc_norm = np.clip(np.asarray(erc, dtype=np.float32) / 100.0, 0.0, 1.0)
    if drought is not None:
        # Optional: blend drought into ERC slot when ERC missing/constant.
        d = np.asarray(drought, dtype=np.float32)
        if float(np.nanstd(erc_norm)) < 1e-6 and float(np.nanstd(d)) > 0:
            erc_norm = np.clip(
                (d - float(np.nanmin(d))) / (float(np.nanmax(d) - np.nanmin(d)) + 1e-6), 0, 1
            )

    h, w = elev.shape
    channels = np.zeros((12, h, w), dtype=np.float32)
    channels[0] = elev
    channels[1] = slope
    channels[2] = aspect_sin
    channels[3] = aspect_cos
    channels[4] = temp_c
    channels[5] = humidity
    channels[6] = wind_speed
    channels[7] = wind_sin
    channels[8] = wind_cos
    channels[9] = precip
    channels[10] = veg
    channels[11] = erc_norm
    return normalize_with_stats(channels, CLEAN12_CHANNEL_STATS)


def build_physics14_channels(
    elevation: np.ndarray,
    wind_dir: np.ndarray,
    wind_speed: np.ndarray,
    max_temp: np.ndarray,
    min_temp: np.ndarray,
    humidity: np.ndarray,
    precip: np.ndarray,
    veg: np.ndarray,
    erc: np.ndarray,
    drought: np.ndarray | None = None,
) -> np.ndarray:
    """Build 14-channel physics schema: tmin/tmax + drought_or_ffmc."""
    elev, slope, aspect = _terrain_from_elevation(elevation)
    max_temp = _as_celsius(max_temp)
    min_temp = _as_celsius(min_temp)
    temp_c = 0.5 * (min_temp + max_temp)
    wind_sin, wind_cos = _wind_components(wind_speed, wind_dir)
    aspect_sin = np.sin(aspect).astype(np.float32)
    aspect_cos = np.cos(aspect).astype(np.float32)
    erc_norm = np.clip(np.asarray(erc, dtype=np.float32) / 100.0, 0.0, 1.0)
    wind_kmh = np.asarray(wind_speed, dtype=np.float32) * 3.6
    ffmc = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)

    # Prefer varying drought (PDSI-like); else FFMC in physical units for norm stats.
    drought_or_ffmc = ffmc.astype(np.float32)
    if drought is not None:
        d = np.asarray(drought, dtype=np.float32)
        if float(np.nanstd(d)) > 1e-6:
            d_min, d_max = float(np.nanmin(d)), float(np.nanmax(d))
            d01 = np.clip((d - d_min) / (d_max - d_min + 1e-6), 0.0, 1.0)
            drought_or_ffmc = (d01 * 101.0).astype(np.float32)

    h, w = elev.shape
    channels = np.zeros((14, h, w), dtype=np.float32)
    channels[0] = elev
    channels[1] = slope
    channels[2] = aspect_sin
    channels[3] = aspect_cos
    channels[4] = min_temp
    channels[5] = max_temp
    channels[6] = humidity
    channels[7] = wind_speed
    channels[8] = wind_sin
    channels[9] = wind_cos
    channels[10] = precip
    channels[11] = veg
    channels[12] = erc_norm
    channels[13] = drought_or_ffmc
    return normalize_with_stats(channels, PHYSICS14_CHANNEL_STATS)


def build_physics15_channels(
    elevation: np.ndarray,
    wind_dir: np.ndarray,
    wind_speed: np.ndarray,
    max_temp: np.ndarray,
    min_temp: np.ndarray,
    humidity: np.ndarray,
    precip: np.ndarray,
    veg: np.ndarray,
    erc: np.ndarray,
    drought: np.ndarray | None = None,
) -> np.ndarray:
    """physics14 + wind_upslope = cos(wind_dir - aspect) * wind_speed_norm proxy."""
    base = build_physics14_channels(
        elevation,
        wind_dir,
        wind_speed,
        max_temp,
        min_temp,
        humidity,
        precip,
        veg,
        erc,
        drought=drought,
    )
    # Recompute terrain aspect for interaction in raw space before norm of extra ch
    _, slope, aspect = _terrain_from_elevation(elevation)
    wind_rad = np.deg2rad(np.asarray(wind_dir, dtype=np.float32))
    # Upslope factor: alignment of wind-from direction with downslope aspect
    align = np.cos(wind_rad - aspect).astype(np.float32)
    ws = np.asarray(wind_speed, dtype=np.float32)
    ws_n = np.clip(ws / 20.0, 0.0, 2.0)
    wind_upslope = align * ws_n * np.clip(slope / 1.5708, 0.0, 1.0)
    out = np.zeros((15, base.shape[1], base.shape[2]), dtype=np.float32)
    out[:14] = base
    out[14] = np.clip(wind_upslope, -2.0, 2.0)
    return out


def build_channels_from_fields(
    schema: SchemaName,
    *,
    elevation: np.ndarray,
    wind_dir: np.ndarray,
    wind_speed: np.ndarray,
    max_temp: np.ndarray,
    min_temp: np.ndarray,
    humidity: np.ndarray,
    precip: np.ndarray,
    veg: np.ndarray,
    erc: np.ndarray,
    drought: np.ndarray | None = None,
) -> np.ndarray:
    if schema == "physics15":
        return build_physics15_channels(
            elevation,
            wind_dir,
            wind_speed,
            max_temp,
            min_temp,
            humidity,
            precip,
            veg,
            erc,
            drought=drought,
        )
    if schema == "physics14":
        return build_physics14_channels(
            elevation,
            wind_dir,
            wind_speed,
            max_temp,
            min_temp,
            humidity,
            precip,
            veg,
            erc,
            drought=drought,
        )
    if schema == "clean12":
        return build_clean12_channels(
            elevation,
            wind_dir,
            wind_speed,
            max_temp,
            min_temp,
            humidity,
            precip,
            veg,
            erc,
            drought=drought,
        )
    if schema == "legacy17":
        return build_legacy17_channels(
            elevation,
            wind_dir,
            wind_speed,
            max_temp,
            min_temp,
            humidity,
            precip,
            veg,
            erc,
        )
    raise ValueError(f"Unknown schema: {schema}")


def count_constant_channels(channels: np.ndarray, atol: float = 1e-6) -> int:
    """Count channels that are spatially constant (feature dead-on-arrival)."""
    dead = 0
    for i in range(channels.shape[0]):
        if float(np.nanstd(channels[i])) <= atol:
            dead += 1
    return dead
