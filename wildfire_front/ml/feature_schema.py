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

from typing import Any, Literal

import numpy as np

SchemaName = Literal[
    "legacy17",
    "clean12",
    "physics14",
    "physics15",
    "spatial_v1",
    "physics14_spatial",  # alias of spatial_v1
]

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

# ---------------------------------------------------------------------------
# spatial_v1 (E2-P2) — honest spatial re-emit from DEM / weather / fuel rasters
# ---------------------------------------------------------------------------
# Distinct from clean12_subset (E2-P1 projector on sealed legacy17).
# Channel layout matches physics14 names/order for residual train continuity,
# but build path requires spatial DEM for terrain and prefers per-cell weather
# rasters. Missing sources → GAP stamp + optional missing_mask; no fake
# physics14 claim on legacy17 tensors.

SPATIAL_V1_N_CHANNELS: int = 14
SPATIAL_V1_CHANNEL_STATS: list[tuple[float, float]] = list(PHYSICS14_CHANNEL_STATS)
SPATIAL_V1_NAMES: tuple[str, ...] = PHYSICS14_NAMES
SPATIAL_V1_SCHEMA_PATH_ID: str = "E2-P2"
SPATIAL_V1_HONESTY: str = (
    "spatial_v1 / physics14_spatial (E2-P2): re-emit from geotiff/source fields. "
    "DEM → elevation/slope/aspect_sin/aspect_cos via _terrain_from_elevation. "
    "Weather: AEMET/reanalysis rasters on patch grid when present; else GAP + "
    "missing_mask (no scalar-per-fire constant sold as spatial variance). "
    "Fuel/landcover spatial when maps exist. ERC/FFMC via compute_ffmc on "
    "weather grids — not constant fill. "
    "NOT clean12_subset projector; NOT physics14 claim on sealed legacy17."
)

# Channels allowed to be near-constant without blocking train (honesty stamped).
# Empty by default: spatial_v1 expects real variance on trained channels.
SPATIAL_V1_NEVER_ALLOWLIST_DEFAULT: frozenset[str] = frozenset()

# Signal labels (analyze_feature_signal / train gate)
SIGNAL_LABEL_ALWAYS = "always"  # alias of historical "must" for growth corr
SIGNAL_LABEL_MAYBE = "maybe"
SIGNAL_LABEL_NEVER = "never"
NEVER_STD_THRESHOLD: float = 1e-4
NEVER_FRAC_CONST_THRESHOLD: float = 0.99


def schema_channel_count(schema: SchemaName | str) -> int:
    if schema == "clean12":
        return 12
    if schema in ("physics14", "spatial_v1", "physics14_spatial"):
        return 14
    if schema == "physics15":
        return 15
    if schema == "legacy17":
        return 17
    if schema == "clean12_subset":
        return CLEAN12_SUBSET_N_CHANNELS
    raise ValueError(f"Unknown schema: {schema}")


def schema_channel_names(schema: SchemaName | str) -> tuple[str, ...]:
    if schema == "clean12":
        return CLEAN12_NAMES
    if schema in ("physics14", "spatial_v1", "physics14_spatial"):
        return PHYSICS14_NAMES if schema == "physics14" else SPATIAL_V1_NAMES
    if schema == "physics15":
        return PHYSICS15_NAMES
    if schema == "legacy17":
        return tuple(f"legacy_{i}" for i in range(17))
    if schema == "clean12_subset":
        return CLEAN12_SUBSET_NAMES
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


# Schemas that claim spatial / physics variance → never-channel gate ON by default.
# Sealed legacy17 / clean12_subset keep intentional constants → gate OFF unless forced.
SCHEMAS_NEVER_GATE_DEFAULT: frozenset[str] = frozenset(
    {"spatial_v1", "physics14_spatial", "physics14", "physics15"}
)


def never_gate_default_for_schema(feature_schema: str) -> bool:
    """True when train should refuse never channels for this schema by default."""
    return str(feature_schema) in SCHEMAS_NEVER_GATE_DEFAULT


def work_class_for_schema(
    feature_schema: str,
    *,
    schema_path_id: str | None = None,
    mix_policy: str | None = None,
) -> str:
    """Unified board stamp: recipe_t1_sealed | feature_spatial_v1 | data_mix_…"""
    if mix_policy == "estrella_floor_v1":
        return "data_mix_estrella_floor_v1"
    if feature_schema in ("spatial_v1", "physics14_spatial") or schema_path_id == "E2-P2":
        return "feature_spatial_v1"
    if feature_schema == "clean12_subset" or schema_path_id == "E2-P1":
        return "feature_clean12_subset_projector_low_ev"
    if feature_schema in ("physics14", "physics15"):
        return "feature_physics_schema"
    return "recipe_t1_sealed"


def build_spatial_v1_channels(
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
    *,
    weather_is_spatial: bool = True,
    fuel_is_spatial: bool = True,
    dem_is_spatial: bool = True,
    weather_field_spatial: dict[str, bool] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build spatial_v1 (physics14 layout) with honesty metadata.

    Terrain always derived from ``elevation`` via ``_terrain_from_elevation``.
    Callers must pass true DEM elevation (not synthetic flat) for dem_is_spatial=True.
    Weather / fuel / ERC grids should be per-cell when available; if only scalars
    were broadcast, pass weather_is_spatial=False / fuel_is_spatial=False so the
    provenance stamp records GAP (train gate may still block never channels).

    ``weather_field_spatial`` (optional) maps field names → whether that field
    came from a real raster (``tmin``, ``tmax``, ``humidity``, ``wind_speed``,
    ``wind_dir``, ``precip``, ``erc``). Scalar-filled slots are always marked in
    ``missing_mask`` even if other weather rasters exist.

    Returns
    -------
    channels : (14, H, W) float32 normalized
    meta : honesty + missing / spatial flags per channel group
    """
    elev_arr = np.asarray(elevation, dtype=np.float32)
    if elev_arr.ndim != 2:
        raise ValueError(f"elevation must be 2D, got shape {elev_arr.shape}")

    elev, slope, aspect = _terrain_from_elevation(elev_arr)
    max_temp = _as_celsius(max_temp)
    min_temp = _as_celsius(min_temp)
    temp_c = 0.5 * (np.asarray(min_temp, dtype=np.float32) + np.asarray(max_temp, dtype=np.float32))
    wind_sin, wind_cos = _wind_components(wind_speed, wind_dir)
    aspect_sin = np.sin(aspect).astype(np.float32)
    aspect_cos = np.cos(aspect).astype(np.float32)
    erc_arr = np.asarray(erc, dtype=np.float32)
    erc_norm = np.clip(erc_arr / 100.0, 0.0, 1.0)
    wind_kmh = np.asarray(wind_speed, dtype=np.float32) * 3.6
    # Per-cell FFMC when weather is on a grid (not a single scalar fill).
    ffmc = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)

    drought_or_ffmc = ffmc.astype(np.float32)
    if drought is not None:
        d = np.asarray(drought, dtype=np.float32)
        if float(np.nanstd(d)) > 1e-6:
            d_min, d_max = float(np.nanmin(d)), float(np.nanmax(d))
            d01 = np.clip((d - d_min) / (d_max - d_min + 1e-6), 0.0, 1.0)
            drought_or_ffmc = (d01 * 101.0).astype(np.float32)

    h, w = elev.shape
    raw = np.zeros((SPATIAL_V1_N_CHANNELS, h, w), dtype=np.float32)
    raw[0] = elev
    raw[1] = slope
    raw[2] = aspect_sin
    raw[3] = aspect_cos
    raw[4] = min_temp
    raw[5] = max_temp
    raw[6] = humidity
    raw[7] = wind_speed
    raw[8] = wind_sin
    raw[9] = wind_cos
    raw[10] = precip
    raw[11] = veg
    raw[12] = erc_norm
    raw[13] = drought_or_ffmc
    channels = normalize_with_stats(raw, SPATIAL_V1_CHANNEL_STATS)

    # missing_mask: 1.0 where channel is not spatially sourced
    missing_mask = np.zeros((SPATIAL_V1_N_CHANNELS, h, w), dtype=np.float32)
    gaps: list[str] = []
    if not dem_is_spatial or float(np.nanstd(elev)) < 1e-6:
        gaps.append("dem_spatial")
        missing_mask[0:4] = 1.0

    # Per-field weather honesty (BUG-2): scalar-filled slots always missing
    wfs = weather_field_spatial or {}
    # channel index → field key(s) that must be spatial
    weather_ch_fields: dict[int, tuple[str, ...]] = {
        4: ("tmin",),
        5: ("tmax",),
        6: ("humidity",),
        7: ("wind_speed",),
        8: ("wind_dir",),
        9: ("wind_dir",),
        10: ("precip",),
        13: ("tmin", "tmax", "humidity", "wind_speed", "precip"),  # FFMC inputs
    }
    if wfs:
        any_wx = any(
            wfs.get(k, False)
            for k in ("tmin", "tmax", "humidity", "wind_speed", "wind_dir", "precip")
        )
        all_core = all(
            wfs.get(k, False)
            for k in ("tmin", "tmax", "humidity", "wind_speed", "wind_dir", "precip")
        )
        weather_is_spatial = bool(all_core)
        if any_wx and not all_core:
            gaps.append("weather_partial_rasters")
        if not any_wx:
            gaps.append("weather_spatial")
        for ch_i, keys in weather_ch_fields.items():
            if not all(wfs.get(k, False) for k in keys):
                missing_mask[ch_i] = 1.0
        # ERC spatial only if erc raster OR full weather for FFMC proxy
        if wfs.get("erc", False):
            pass  # spatial
        elif all(wfs.get(k, False) for k in ("tmin", "tmax", "humidity", "wind_speed", "precip")):
            pass  # FFMC proxy is spatial
        else:
            missing_mask[12] = 1.0
            if "erc_or_ffmc_low_spatial" not in gaps:
                gaps.append("erc_or_ffmc_low_spatial")
    elif not weather_is_spatial:
        gaps.append("weather_spatial")
        for i in (4, 5, 6, 7, 8, 9, 10, 12, 13):
            missing_mask[i] = 1.0
    else:
        # bulk weather_is_spatial=True without per-field map (caller claim)
        if float(np.nanstd(erc_norm)) < 1e-6 and (
            drought is None or float(np.nanstd(np.asarray(drought, dtype=np.float32))) < 1e-6
        ):
            if "erc_or_ffmc_low_spatial" not in gaps:
                gaps.append("erc_or_ffmc_low_spatial")
            missing_mask[12] = 1.0

    if not fuel_is_spatial or float(np.nanstd(np.asarray(veg, dtype=np.float32))) < 1e-6:
        gaps.append("fuel_spatial")
        missing_mask[11] = 1.0

    meta: dict[str, Any] = {
        "feature_schema": "spatial_v1",
        "schema_path_id": SPATIAL_V1_SCHEMA_PATH_ID,
        "schema_alias": "physics14_spatial",
        "n_channels": SPATIAL_V1_N_CHANNELS,
        "channel_names": list(SPATIAL_V1_NAMES),
        "honesty": SPATIAL_V1_HONESTY,
        "dem_is_spatial": bool(dem_is_spatial and float(np.nanstd(elev)) >= 1e-6),
        "weather_is_spatial": bool(weather_is_spatial),
        "weather_field_spatial": dict(wfs) if wfs else None,
        "fuel_is_spatial": bool(
            fuel_is_spatial and float(np.nanstd(np.asarray(veg, dtype=np.float32))) >= 1e-6
        ),
        "gaps": gaps,
        "physics14_on_legacy17": False,
        "clean12_subset_projector": False,
        "full_reemit": True,
        "work_class": "feature_spatial_v1",
    }
    # Attach missing_mask summary (not a train channel by default)
    meta["missing_mask_frac"] = {
        SPATIAL_V1_NAMES[i]: float(missing_mask[i].mean()) for i in range(SPATIAL_V1_N_CHANNELS)
    }
    meta["missing_mask"] = missing_mask  # callers may drop before save
    return channels, meta


def spatial_v1_schema_map() -> dict[str, Any]:
    """Machine-readable E2-P2 schema stamp (training_summary / re-emit manifest)."""
    return {
        "feature_schema": "spatial_v1",
        "schema_alias": "physics14_spatial",
        "schema_path_id": SPATIAL_V1_SCHEMA_PATH_ID,
        "source_schema": "geotiff_reemit",
        "in_channels_features": SPATIAL_V1_N_CHANNELS,
        "in_channels_with_prev_fire": SPATIAL_V1_N_CHANNELS + 1,
        "channel_names": list(SPATIAL_V1_NAMES),
        "honesty": SPATIAL_V1_HONESTY,
        "physics14_claim_on_legacy17": False,
        "clean12_subset_projector": False,
        "full_clean12_reemit": False,
        "full_spatial_reemit": True,
        "never_allowlist_default": sorted(SPATIAL_V1_NEVER_ALLOWLIST_DEFAULT),
    }


def build_channels_from_fields(
    schema: SchemaName | str,
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
    if schema in ("spatial_v1", "physics14_spatial"):
        # Conservative spatial inference when flags not provided (SUGGESTION-3):
        # only claim spatial when arrays actually vary — no blanket True.
        elev_a = np.asarray(elevation, dtype=np.float32)
        dem_sp = float(np.nanstd(elev_a)) >= 1e-6
        wx_keys = (wind_dir, wind_speed, max_temp, min_temp, humidity, precip)
        wx_sp = all(float(np.nanstd(np.asarray(x, dtype=np.float32))) >= 1e-6 for x in wx_keys)
        fuel_sp = float(np.nanstd(np.asarray(veg, dtype=np.float32))) >= 1e-6
        ch, _meta = build_spatial_v1_channels(
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
            weather_is_spatial=wx_sp,
            fuel_is_spatial=fuel_sp,
            dem_is_spatial=dem_sp,
            weather_field_spatial={
                "tmin": float(np.nanstd(np.asarray(min_temp, dtype=np.float32))) >= 1e-6,
                "tmax": float(np.nanstd(np.asarray(max_temp, dtype=np.float32))) >= 1e-6,
                "humidity": float(np.nanstd(np.asarray(humidity, dtype=np.float32))) >= 1e-6,
                "wind_speed": float(np.nanstd(np.asarray(wind_speed, dtype=np.float32))) >= 1e-6,
                "wind_dir": float(np.nanstd(np.asarray(wind_dir, dtype=np.float32))) >= 1e-6,
                "precip": float(np.nanstd(np.asarray(precip, dtype=np.float32))) >= 1e-6,
                "erc": float(np.nanstd(np.asarray(erc, dtype=np.float32))) >= 1e-6,
            },
        )
        return ch
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


def label_channel_signal(
    *,
    std: float,
    frac_const: float,
    corr_growth: float = 0.0,
    corr_change: float = 0.0,
    growth_corr_threshold: float = 0.05,
) -> str:
    """Label a channel ``always`` / ``maybe`` / ``never`` (E2-P2 signal vocabulary).

    - ``always``: |corr_growth| or |corr_change| ≥ threshold (historical ``must``)
    - ``never``: std ~ 0 or frac_const > 0.99
    - ``maybe``: otherwise
    """
    if abs(corr_growth) >= growth_corr_threshold or abs(corr_change) >= growth_corr_threshold:
        return SIGNAL_LABEL_ALWAYS
    if std < NEVER_STD_THRESHOLD or frac_const > NEVER_FRAC_CONST_THRESHOLD:
        return SIGNAL_LABEL_NEVER
    return SIGNAL_LABEL_MAYBE


def channel_stats_from_tensor(channels: np.ndarray) -> list[dict[str, Any]]:
    """Per-channel mean/std/frac_const and signal label (no growth corr without targets)."""
    arr = np.asarray(channels, dtype=np.float64)
    if arr.ndim == 4:
        # (T, C, H, W) → last frame
        arr = arr[-1]
    if arr.ndim != 3:
        raise ValueError(f"expected (C,H,W) or (T,C,H,W), got {arr.shape}")
    out: list[dict[str, Any]] = []
    for i in range(arr.shape[0]):
        sample = arr[i].ravel()
        mean = float(np.mean(sample)) if sample.size else 0.0
        std = float(np.std(sample)) if sample.size else 0.0
        frac_const = float(np.mean(np.abs(sample - mean) < 1e-6)) if sample.size else 1.0
        label = label_channel_signal(std=std, frac_const=frac_const)
        out.append(
            {
                "index": i,
                "mean": mean,
                "std": std,
                "frac_near_constant": frac_const,
                "label": label,
            }
        )
    return out


class NeverChannelTrainError(RuntimeError):
    """Raised when train pack has never-label channels and no allowlist honesty."""


def assert_no_never_train_channels(
    channel_rows: list[dict[str, Any]],
    *,
    channel_names: tuple[str, ...] | list[str] | None = None,
    allowlist: frozenset[str] | set[str] | None = None,
    allowlist_honesty: str | None = None,
    raise_on_block: bool = True,
) -> dict[str, Any]:
    """Block train if any channel is labeled ``never`` unless allowlisted.

    Parameters
    ----------
    channel_rows
        Rows from analyze_feature_signal / channel_stats_from_tensor (need
        ``index``, ``label``; optional ``name``).
    allowlist
        Channel names (preferred) or ``ch{i}`` keys permitted despite never.
        Require non-empty ``allowlist_honesty`` stamp when allowlist used.
    """
    allow = set(allowlist or ())
    if allow and not (allowlist_honesty and str(allowlist_honesty).strip()):
        msg = "never-channel allowlist requires non-empty allowlist_honesty stamp"
        if raise_on_block:
            raise NeverChannelTrainError(msg)
        return {
            "ok": False,
            "blocked": True,
            "error": msg,
            "never_channels": [],
            "allowlist": sorted(allow),
        }

    never_blocked: list[dict[str, Any]] = []
    never_allowed: list[dict[str, Any]] = []
    for row in channel_rows:
        label = str(row.get("label", ""))
        # Only gate ``never`` (historical ``must`` maps to always — not blocked)
        if label != SIGNAL_LABEL_NEVER:
            continue
        idx = int(row.get("index", -1))
        name = str(row.get("name") or "")
        if not name and channel_names is not None and 0 <= idx < len(channel_names):
            name = str(channel_names[idx])
        keys = {name, f"ch{idx}", str(idx)} if name else {f"ch{idx}", str(idx)}
        entry = {
            "index": idx,
            "name": name or f"ch{idx}",
            "std": row.get("std"),
            "frac_near_constant": row.get("frac_near_constant"),
        }
        if keys & allow:
            never_allowed.append(entry)
        else:
            never_blocked.append(entry)

    ok = len(never_blocked) == 0
    result: dict[str, Any] = {
        "ok": ok,
        "blocked": not ok,
        "never_channels": never_blocked,
        "never_allowlisted": never_allowed,
        "allowlist": sorted(allow),
        "allowlist_honesty": allowlist_honesty,
        "policy": "block_never_train_channels_v1",
    }
    if not ok and raise_on_block:
        names = ", ".join(e["name"] for e in never_blocked)
        raise NeverChannelTrainError(
            f"train blocked: never-signal channels without allowlist: {names}. "
            f"Re-emit spatial sources or pass explicit allowlist + honesty stamp."
        )
    return result


# ---------------------------------------------------------------------------
# E2-P1: sealed legacy17 → clean12_subset projector (fixed channel map)
# ---------------------------------------------------------------------------
# Sealed CLM LOFO packs store already-normalized legacy17 tensors
# ``sequence`` shape (T, 17, H, W). Constants in legacy17 build are indices
# 7–10 (pressure/cloud/vis/dew) and 14–15 (zeros). We drop those and map
# remaining informative channels into a 12-slot clean12_subset tensor.
#
# Slot 0 (elevation) is **not** recoverable from sealed legacy17 → zeros
# with honesty flag. This is NOT full clean12 from raw geotiff fields, and
# is NOT physics14 (no true tmin/tmax split).

# clean12_subset output channel count (features only; trainer may +prev_fire)
CLEAN12_SUBSET_N_CHANNELS: int = 12

# legacy17 indices selected into clean12_subset slots 0..11
# None → zeros (missing semantic channel in sealed tensor)
LEGACY17_TO_CLEAN12_SUBSET: tuple[int | None, ...] = (
    None,  # 0 elevation — unavailable in sealed legacy17
    0,  # 1 slope
    1,  # 2 aspect (stored as aspect+pi; not aspect_sin)
    None,  # 3 aspect_cos — unavailable without re-derive from raw
    2,  # 4 temperature
    3,  # 5 humidity
    4,  # 6 wind_speed
    5,  # 7 wind_dir (proxy for wind_sin slot — honesty: not true sin)
    None,  # 8 wind_cos — unavailable
    6,  # 9 precipitation
    11,  # 10 vegetation
    12,  # 11 erc
)

# Dropped near-constant legacy17 indices (not mapped into subset)
LEGACY17_DROPPED_CONSTANT_INDICES: tuple[int, ...] = (7, 8, 9, 10, 13, 14, 15, 16)

CLEAN12_SUBSET_NAMES: tuple[str, ...] = (
    "elevation_missing_zero",
    "slope",
    "aspect_legacy",
    "aspect_cos_missing_zero",
    "temperature",
    "humidity",
    "wind_speed",
    "wind_dir_legacy_proxy",
    "wind_cos_missing_zero",
    "precipitation",
    "vegetation",
    "erc",
)

CLEAN12_SUBSET_HONESTY: str = (
    "clean12_subset from sealed legacy17 via fixed index map; "
    "elevation/aspect_cos/wind_cos zero-filled; wind_dir is not wind_sin; "
    "NOT full clean12 re-emit; NOT physics14 (no tmin/tmax). "
    "Prior clean12/physics14 Spain LOFO: NO PROMOTE — one shot then E3a."
)


def clean12_subset_channel_count() -> int:
    return CLEAN12_SUBSET_N_CHANNELS


def legacy17_to_clean12_subset_map() -> dict[str, Any]:
    """Machine-readable fixed map for E2-P1 projector + training_summary."""
    return {
        "feature_schema": "clean12_subset",
        "schema_path_id": "E2-P1",
        "source_schema": "legacy17",
        "in_channels_features": CLEAN12_SUBSET_N_CHANNELS,
        "in_channels_with_prev_fire": CLEAN12_SUBSET_N_CHANNELS + 1,
        "legacy17_to_clean12_subset": list(LEGACY17_TO_CLEAN12_SUBSET),
        "dropped_legacy17_indices": list(LEGACY17_DROPPED_CONSTANT_INDICES),
        "channel_names": list(CLEAN12_SUBSET_NAMES),
        "honesty": CLEAN12_SUBSET_HONESTY,
        "physics14_claim": False,
        "full_clean12_reemit": False,
    }


def project_legacy17_to_clean12_subset(channels: np.ndarray) -> np.ndarray:
    """Project legacy17 feature tensor → clean12_subset (fixed map).

    Accepts shapes:
    * ``(17, H, W)``
    * ``(T, 17, H, W)``
    * ``(B, T, 17, H, W)`` — rare; treated as leading dims preserved

    Returns same leading dims with channel axis replaced by 12.
    """
    arr = np.asarray(channels, dtype=np.float32)
    if arr.ndim < 3:
        raise ValueError(f"expected ≥3D channel tensor, got shape {arr.shape}")
    # Channel axis is the one with size 17 nearest the spatial dims.
    if arr.shape[-3] == 17:
        ch_axis = arr.ndim - 3
    elif arr.shape[0] == 17 and arr.ndim == 3:
        ch_axis = 0
    else:
        # search
        ch_axis = None
        for i, s in enumerate(arr.shape):
            if s == 17 and i < arr.ndim - 2:
                ch_axis = i
                break
        if ch_axis is None:
            raise ValueError(f"cannot find legacy17 channel axis in shape {arr.shape}")

    # Move channel axis to 0 for mapping
    moved = np.moveaxis(arr, ch_axis, 0)
    if moved.shape[0] < 17:
        raise ValueError(f"legacy17 needs ≥17 channels, got {moved.shape[0]} in {arr.shape}")
    spatial = moved.shape[1:]
    out = np.zeros((CLEAN12_SUBSET_N_CHANNELS, *spatial), dtype=np.float32)
    for dst, src in enumerate(LEGACY17_TO_CLEAN12_SUBSET):
        if src is None:
            continue
        out[dst] = moved[int(src)]
    # Restore channel axis position
    return np.moveaxis(out, 0, ch_axis)


def project_sequence_legacy17_to_clean12_subset(sequence: np.ndarray) -> np.ndarray:
    """Project NPZ ``sequence`` (T, 17, H, W) → (T, 12, H, W)."""
    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 4:
        raise ValueError(f"sequence must be (T,C,H,W), got {seq.shape}")
    if seq.shape[1] != 17:
        raise ValueError(f"E2-P1 expects sealed legacy17 C=17, got C={seq.shape[1]}")
    return project_legacy17_to_clean12_subset(seq)
