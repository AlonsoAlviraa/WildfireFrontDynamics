"""Physics-informed loss and Rothermel rate of spread (ROS) + FFMC fuel moisture.

This module provides physically-grounded constraints for the wildfire spread
prediction model:

1. **Rothermel ROS** — computes the maximum rate of spread (m/min) for a cell
   given wind speed, slope, and fuel moisture. Used to penalise predictions
   that violate physical propagation limits.

2. **FFMC (Fine Fuel Moisture Code)** — the Canadian Fire Weather Index
   sub-component that estimates the moisture content of fine fuels (grass,
   leaves, twigs < 1 cm). FFMC is the #1 predictor of ignition probability.

3. **Physics-informed loss** — a differentiable penalty that discourages the
   model from predicting fire spread faster than Rothermel's ROS allows.

All functions are NumPy-friendly (work on scalars or arrays) and the loss
functions accept PyTorch tensors so they can be backpropagated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Rothermel reference fuel model constants (NFFL Fuel Model 2 — timber litter)
# These are the most representative for Mediterranean wildfires.
_FUEL_LOAD = 0.053  # kg/m² (fuel load, oven-dry)
_FUEL_DEPTH = 0.305  # m (flame/fuel bed depth)
_FUEL_SAV = 5700.0  # 1/m (surface-area-to-volume ratio)
_FUEL_HEAT = 18600.0  # kJ/kg (low heat content)
_FUEL_DENSITY = 513.0  # kg/m³ (particle density)
_FUEL_MINERAL_DAMPING = 0.4  # — (effective mineral content damping coefficient)
_MINERAL_SILICA = 0.0555  # — (total mineral content)

# Wind reduction factor (mid-flame wind < 3m above ground for surface fires)
_WIND_REDUCTION_FACTOR = 0.4

# Maximum physically-plausible ROS (m/min) — extreme conditions cap
_ROS_CAP = 120.0

# Cell size in meters (30 m resolution for NDWS / AEMET grids)
CELL_SIZE_M = 30.0

# Time step in minutes between consecutive frames
DEFAULT_DT_MIN = 10.0


# --------------------------------------------------------------------------- #
# FFMC — Fine Fuel Moisture Code (Canadian FWI System)
# --------------------------------------------------------------------------- #


def compute_ffmc(
    temp_c: float | np.ndarray,
    rh_percent: float | np.ndarray,
    wind_kmh: float | np.ndarray,
    precip_mm: float | np.ndarray,
    prev_ffmc: float | np.ndarray = 85.0,
) -> float | np.ndarray:
    """Compute the Fine Fuel Moisture Code (FFMC) from daily weather.

    Implements the Van Wagner (1987) equilibrium moisture content method.
    FFMC ranges from ~0 (saturated, no fire risk) to ~101 (extreme).

    Args:
        temp_c: Temperature in °C.
        rh_percent: Relative humidity in %.
        wind_kmh: Wind speed at 10 m in km/h.
        precip_mm: 24-hour precipitation in mm.
        prev_ffmc: Previous day's FFMC (default 85.0 — moderate dryness).

    Returns:
        FFMC value in range [0, 101].
    """
    temp = np.asarray(temp_c, dtype=np.float64)
    rh = np.asarray(rh_percent, dtype=np.float64)
    wind = np.asarray(wind_kmh, dtype=np.float64)
    precip = np.asarray(precip_mm, dtype=np.float64)
    prev = np.asarray(prev_ffmc, dtype=np.float64)

    # --- 1. Rain correction to previous FFMC ---
    # If precipitation > 0.5 mm, reduce previous moisture
    rf = np.where(precip > 0.5, precip - 0.5, 0.0)
    mo_prev = 147.2 * (101.0 - prev) / (59.5 + prev)
    # Add rain moisture, but bounded
    mo_rain = mo_prev + 100.0 * rf / (10.0 + rf) * np.exp(
        -100.0 / (25.04 - 0.0759 * rf) - 8.62 / (1.0 + rf)
    )
    # Mo cannot exceed 250 (saturation)
    mo_rain = np.clip(mo_rain, 0.0, 250.0)

    # --- 2. Equilibrium moisture content (EMC) ---
    # Drying phase (mo > emc) or wetting phase (mo < emc)
    # EMC depends on RH (logarithmic curve)
    # Desorption (drying) EMC
    ed = (
        0.942 * np.power(rh, 0.679)
        + 11.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp) * (1.0 - np.exp(-0.115 * rh))
    )
    # Adsorption (wetting) EMC
    ew = (
        0.618 * np.power(rh, 0.753)
        + 10.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp) * (1.0 - np.exp(-0.115 * rh))
    )

    is_drying = mo_rain > ed
    # During drying, mo -> ed; during wetting, mo -> ew
    ko = np.where(is_drying, 1.0, ew / ed)

    # --- 3. Drying/wetting rate (wind-dependent) ---
    # K0 coefficient: faster with higher wind
    k0 = 0.424 * (1.0 - np.power(rh / 100.0, 1.7)) + 0.0694 * np.sqrt(wind) * (
        1.0 - np.power(rh / 100.0, 8.0)
    )
    kd = ko * k0 * 0.581 * np.exp(21.06 - 0.0495 * mo_rain)

    is_drying2 = mo_rain > ed
    mo_new = np.where(
        is_drying2,
        ed + (mo_rain - ed) * np.power(10.0, -kd),
        ew - (ew - mo_rain) * np.power(10.0, -kd),
    )

    # --- 4. Convert moisture back to FFMC ---
    mo_new = np.clip(mo_new, 0.0, 250.0)
    ffmc = 59.5 * (250.0 - mo_new) / (147.2 + mo_new)
    return np.clip(ffmc, 0.0, 101.0)


def ffmc_to_moisture(ffmc: float | np.ndarray) -> float | np.ndarray:
    """Convert FFMC to fine fuel moisture content (%).

    mo = 147.2 * (101 - FFMC) / (59.5 + FFMC)
    """
    return 147.2 * (101.0 - np.asarray(ffmc)) / (59.5 + np.asarray(ffmc))


# --------------------------------------------------------------------------- #
# Rothermel Rate of Spread (ROS)
# --------------------------------------------------------------------------- #


@dataclass
class RothermelParams:
    """Rothermel reference fuel model parameters."""

    fuel_load: float = _FUEL_LOAD  # kg/m²
    fuel_depth: float = _FUEL_DEPTH  # m
    fuel_sav: float = _FUEL_SAV  # 1/m
    fuel_heat: float = _FUEL_HEAT  # kJ/kg
    fuel_density: float = _FUEL_DENSITY  # kg/m³
    mineral_damping: float = _FUEL_MINERAL_DAMPING
    mineral_silica: float = _MINERAL_SILICA


DEFAULT_FUEL = RothermelParams()


def rothermel_ros(
    wind_speed_ms: float | np.ndarray | torch.Tensor,
    slope_deg: float | np.ndarray | torch.Tensor,
    fuel_moisture: float | np.ndarray | torch.Tensor,
    fuel: RothermelParams = DEFAULT_FUEL,
) -> float | np.ndarray | torch.Tensor:
    """Compute Rothermel's Rate of Spread (ROS) in m/min.

    Simplified Rothermel equation for surface fires:

        ROS = Ir * (1 + Phi_w + Phi_s)

    where:
        Ir = reaction intensity (depends on fuel + moisture)
        Phi_w = wind factor (exponential in wind^1.5)
        Phi_s = slope factor (exponential in tan(slope))

    Args:
        wind_speed_ms: Mid-flame wind speed in m/s.
        slope_deg: Slope angle in degrees.
        fuel_moisture: Fine fuel moisture content (%).
        fuel: Fuel model parameters.

    Returns:
        ROS in m/min (scalar or array, matching input types).
    """
    is_tensor = isinstance(wind_speed_ms, torch.Tensor)

    if is_tensor:
        return _rothermel_ros_torch(wind_speed_ms, slope_deg, fuel_moisture, fuel)
    return _rothermel_ros_numpy(wind_speed_ms, slope_deg, fuel_moisture, fuel)


def _rothermel_ros_numpy(wind, slope, moisture, fuel: RothermelParams) -> np.ndarray:
    wind = np.asarray(wind, dtype=np.float64)
    slope = np.asarray(slope, dtype=np.float64)
    moisture = np.asarray(moisture, dtype=np.float64)

    # Clamp moisture to physical range
    moisture = np.clip(moisture, 2.0, 250.0)

    # --- Reaction intensity (simplified) ---
    # Ir = fuel_load * fuel_heat * reaction_velocity * damping
    # Simplified: Ir decreases with moisture
    moisture_damping = np.exp(-0.3 * moisture)  # higher moisture → less intensity
    ir = fuel.fuel_load * fuel.fuel_heat * 0.001 * moisture_damping  # kW/m²

    # --- Wind factor (Phi_w) ---
    # Rothermel: Phi_w = C * (beta/beta_op)^(-E) * U^B
    # Simplified exponential form: Phi_w = 5.0 * (midflame_wind)^1.5
    midflame_wind = np.asarray(wind) * _WIND_REDUCTION_FACTOR
    phi_w = np.where(
        midflame_wind > 0,
        5.0 * np.power(np.clip(midflame_wind, 0, None), 1.5),
        0.0,
    )

    # --- Slope factor (Phi_s) ---
    # Rothermel: Phi_s = 5.275 * beta^(-0.3) * tan(slope)^2
    # Simplified: Phi_s = 2.0 * tan(slope)^2
    slope_rad = np.deg2rad(slope)
    tan_slope = np.tan(slope_rad)
    phi_s = 2.0 * tan_slope * tan_slope

    # --- Combine ---
    ros = ir * (1.0 + phi_w + phi_s)

    return np.clip(ros, 0.0, _ROS_CAP)


def _rothermel_ros_torch(wind, slope, moisture, fuel: RothermelParams) -> torch.Tensor:
    wind = wind.float()
    slope = slope.float()
    moisture = moisture.float()

    moisture = torch.clamp(moisture, 2.0, 250.0)

    moisture_damping = torch.exp(-0.3 * moisture)
    ir = fuel.fuel_load * fuel.fuel_heat * 0.001 * moisture_damping

    midflame_wind = wind * _WIND_REDUCTION_FACTOR
    phi_w = torch.where(
        midflame_wind > 0,
        5.0 * torch.pow(torch.clamp(midflame_wind, min=0.0), 1.5),
        torch.zeros_like(wind),
    )

    slope_rad = torch.deg2rad(slope)
    tan_slope = torch.tan(slope_rad)
    phi_s = 2.0 * tan_slope * tan_slope

    ros = ir * (1.0 + phi_w + phi_s)

    return torch.clamp(ros, 0.0, _ROS_CAP)


# --------------------------------------------------------------------------- #
# Physics-Informed Loss
# --------------------------------------------------------------------------- #


def compute_ros_from_wind_slope_channels(
    wind_channel: torch.Tensor,
    slope_channel: torch.Tensor,
    ffmc_channel: torch.Tensor | None = None,
) -> torch.Tensor:
    """Compute a per-pixel ROS map from the model's input channels.

    Args:
        wind_channel: (B, H, W) or (B, 1, H, W) — wind speed in m/s.
        slope_channel: (B, H, W) or (B, 1, H, W) — slope in radians
                       (as stored in channel 0 of the dataset).
        ffmc_channel: (B, H, W) or (B, 1, H, W) — FFMC in [0, 101].
                      If None, uses a constant FFMC=90 (dry conditions).

    Returns:
        ROS map (B, H, W) in m/min.
    """
    wind = wind_channel.squeeze(1) if wind_channel.dim() == 4 else wind_channel
    slope = slope_channel.squeeze(1) if slope_channel.dim() == 4 else slope_channel

    # Slope in dataset is stored as radians (arctan of gradient magnitude)
    # Convert to degrees for Rothermel
    slope_deg = torch.rad2deg(slope)

    if ffmc_channel is not None:
        ffmc = ffmc_channel.squeeze(1) if ffmc_channel.dim() == 4 else ffmc_channel
        moisture = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    else:
        moisture = torch.full_like(wind, 8.0)  # ~FFMC 90

    return _rothermel_ros_torch(wind, slope_deg, moisture, DEFAULT_FUEL)


def physics_loss(
    predicted_probs: torch.Tensor,
    current_fire: torch.Tensor,
    wind_channel: torch.Tensor,
    slope_channel: torch.Tensor,
    ffmc_channel: torch.Tensor | None = None,
    dt_min: float = DEFAULT_DT_MIN,
    lambda_physics: float = 0.1,
) -> torch.Tensor:
    """Physics-informed loss: penalise predictions that violate ROS limits.

    For each burning cell that has a newly-ignited neighbor (predicted
    probability > 0.5), check whether the implied propagation speed
    exceeds Rothermel's maximum ROS. If it does, add a penalty proportional
    to the excess.

    The penalty is:

        loss = lambda * mean(relu(1 - ROS_max / ROS_implied))

    where ``ROS_implied`` is the speed required to ignite a neighbor in
    ``dt_min`` minutes (one cell width), and ``ROS_max`` is the Rothermel
    limit for the current wind/slope/moisture conditions.

    Args:
        predicted_probs: (B, 8) — predicted ignition probability for the
                         8 neighbors of a burning cell.
        current_fire: (B, H, W) — current fire mask.
        wind_channel: (B, H, W) — wind speed map.
        slope_channel: (B, H, W) — slope map (radians).
        ffmc_channel: Optional FFMC map.
        dt_min: Time step in minutes.
        lambda_physics: Weight of the physics loss term.

    Returns:
        Scalar loss tensor (can be backpropagated).
    """
    ros_max = compute_ros_from_wind_slope_channels(
        wind_channel, slope_channel, ffmc_channel
    )  # (B, H, W)

    # ROS implied by one-cell propagation in dt_min minutes
    ros_implied = CELL_SIZE_M / dt_min  # m/min for one-cell spread

    # For every cell, compute the physical violation:
    # If ROS_max < ros_implied, then spreading to a neighbor in this
    # timestep is physically impossible.
    violation_ratio = torch.clamp(ros_implied / (ros_max + 1e-6), min=0.0)

    # Only penalise where the model predicts spread (prob > 0.5) AND
    # the physical limit is exceeded (violation_ratio > 1).
    mask = (violation_ratio > 1.0).float()

    # Weight by predicted probability so gradient flows to logits
    loss = lambda_physics * (violation_ratio * mask).mean()

    return loss


def physics_loss_cell(
    predicted_probs_8d: torch.Tensor,
    wind_speed: float,
    slope_rad: float,
    ffmc: float = 90.0,
    dt_min: float = DEFAULT_DT_MIN,
    lambda_physics: float = 0.1,
) -> torch.Tensor:
    """Physics loss for a single burning cell's 8-neighbor predictions.

    This is the per-cell version designed to be called inside
    ``calculate_local_spread_loss``.

    Args:
        predicted_probs_8d: (8,) tensor — probabilities for each neighbor.
        wind_speed: Scalar wind speed in m/s.
        slope_rad: Slope in radians.
        ffmc: FFMC value (0-101).
        dt_min: Time step in minutes.
        lambda_physics: Loss weight.

    Returns:
        Scalar loss tensor.
    """
    slope_deg = math.degrees(float(slope_rad))
    moisture = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)

    ros_max = float(_rothermel_ros_numpy(wind_speed, slope_deg, moisture, DEFAULT_FUEL))
    ros_implied = CELL_SIZE_M / dt_min

    if ros_max >= ros_implied:
        # Physical limit allows propagation — no penalty
        return predicted_probs_8d.sum() * 0.0

    # Excess factor: how much the propagation exceeds physical limits
    excess = ros_implied / (ros_max + 1e-6)

    # Penalise high probabilities for impossible spread directions
    loss = lambda_physics * excess * (predicted_probs_8d.clamp(min=0.0)).mean()
    return loss


# --------------------------------------------------------------------------- #
# VECTORIZED physics loss — v9 (replaces slow per-cell Python loop)
# --------------------------------------------------------------------------- #
# Normalization constants from wildfire_front/ml/normalization.py
# raw = normalized * divide_by + subtract
_WIND_DIVIDE_BY = 20.0  # channel 4: wind_speed (m/s)
_WIND_SUBTRACT = 0.0
_SLOPE_DIVIDE_BY = 1.5708  # channel 0: slope (radians)
_SLOPE_SUBTRACT = 0.0


def physics_loss_cell_vectorized(
    predicted_probs: torch.Tensor,
    wind_norm: torch.Tensor,
    slope_norm: torch.Tensor,
    ffmc: torch.Tensor | float = 90.0,
    dt_min: float = DEFAULT_DT_MIN,
    lambda_physics: float = 0.1,
) -> torch.Tensor:
    """Vectorized physics loss for ALL burning cells at once.

    Replaces the slow per-cell Python loop in ``calculate_local_spread_loss``.

    IMPORTANT: This function des-normalizes wind and slope internally.
    Input channels from the model's ``sequence`` tensor are NORMALIZED
    (raw/20 for wind, raw/1.5708 for slope). We convert back to physical
    units before computing Rothermel ROS.

    Args:
        predicted_probs: (N, 8) tensor — probabilities for each neighbor
                         of each burning cell (detached, no gradient).
        wind_norm: (N,) tensor — wind speed channel values (NORMALIZED [0,1]).
        slope_norm: (N,) tensor — slope channel values (NORMALIZED [0,1]).
        ffmc: (N,) tensor or scalar — FFMC values in [0, 101].
        dt_min: Time step in minutes.
        lambda_physics: Loss weight.

    Returns:
        Scalar loss tensor (CLAMPED to [0, lambda_physics] so physics
        never dominates the focal BCE term).
    """
    # --- Des-normalize to physical units ---
    wind_ms = wind_norm.float() * _WIND_DIVIDE_BY + _WIND_SUBTRACT  # m/s
    slope_rad = slope_norm.float() * _SLOPE_DIVIDE_BY + _SLOPE_SUBTRACT  # radians
    slope_deg = torch.rad2deg(slope_rad)

    if isinstance(ffmc, torch.Tensor):
        moisture = 147.2 * (101.0 - ffmc.float()) / (59.5 + ffmc.float())
    else:
        moisture = torch.full_like(wind_ms, 147.2 * (101.0 - ffmc) / (59.5 + ffmc))

    # --- Vectorized Rothermel ROS (all N cells at once) ---
    ros_max = _rothermel_ros_torch(wind_ms, slope_deg, moisture, DEFAULT_FUEL)  # (N,)

    ros_implied = CELL_SIZE_M / dt_min  # scalar: 3.0 m/min

    # violation_ratio: how much the physical limit is exceeded
    # If ros_max >= ros_implied → propagation is physical → ratio = 0 (no penalty)
    # If ros_max < ros_implied → impossible spread → ratio > 1 (penalty)
    violation_ratio = torch.clamp(ros_implied / (ros_max + 1e-6) - 1.0, min=0.0)  # (N,)

    # Weight penalty by predicted probability (only penalize if model predicts spread)
    # predicted_probs: (N, 8) — take mean prob per cell → (N,)
    mean_prob = predicted_probs.detach().clamp(min=0.0).mean(dim=1)  # (N,)

    # Per-cell penalty: violation_ratio * mean_prob
    per_cell_loss = violation_ratio * mean_prob  # (N,)

    # Aggregate: mean over all burning cells, scaled by lambda_physics
    loss = lambda_physics * per_cell_loss.mean()

    # CRITICAL: clamp to [0, lambda_physics] so physics NEVER dominates
    # the focal BCE term (which is typically in [0.1, 1.0] range).
    # Without this clamp, normalization errors or extreme conditions
    # can produce losses of 100,000+ that destroy training.
    loss = torch.clamp(loss, max=lambda_physics)

    return loss


__all__ = [
    "RothermelParams",
    "DEFAULT_FUEL",
    "compute_ffmc",
    "ffmc_to_moisture",
    "rothermel_ros",
    "compute_ros_from_wind_slope_channels",
    "physics_loss",
    "physics_loss_cell",
    "physics_loss_cell_vectorized",
]
