"""Wang Zhengfei (王正非) + Mao Xianmin (毛贤敏) fire-spread ROS — China classic.

Reference (Chinese forestry literature / patents, public formulas):
  R = R0 · K_w · K_s · K_φ

  Wind:   K_w = exp(0.1783 · V · cos θ)     V in m/s, θ angle wind→spread
  Slope:  K_s = exp(±3.533 · (tan φ)^1.2)  + upslope, − downslope
  Fuel:   K_φ tabulated coefficients

Mao Xianmin extends to 8 cardinal/intercardinal directions for wind×slope.

**Use in WFD:** physics *prior / comparison* vs observed aerial ROS — never
replaces measured front speeds without weather+fuel inputs. Label as
``physics_prior_cn``, not tactical dispatch.

Adapted conceptually from Chinese open tools (e.g. xllyll/fire-spread README
citing 王正非; academic CA+Wang papers). Reimplemented cleanly in Python —
not a copy of proprietary vendor binaries.
"""

from __future__ import annotations

import math
from typing import Any

# Beaufort-ish wind class → m/s mid (common CN tables use "风力级")
_BEAUFORT_MS = {
    0: 0.0,
    1: 0.9,
    2: 2.5,
    3: 4.4,
    4: 6.7,
    5: 9.4,
    6: 12.3,
    7: 15.5,
    8: 19.0,
}

# Fuel type K_φ (simplified Mediterranean/CLM-ish proxies; CN tables vary by species)
FUEL_K_PHI: dict[str, float] = {
    "grass": 1.2,
    "shrub": 1.0,
    "pine": 0.9,
    "hardwood": 0.75,
    "mixed": 0.95,
    "default": 1.0,
}


def r0_from_weather(
    temperature_c: float,
    wind_force: float,
    humidity_pct: float,
    *,
    a: float = 0.03,
    b: float = 0.05,
    c: float = 0.01,
) -> float:
    """Empirical initial ROS R0 (m/min) used widely in CN GIS demos.

    Classic textbook form (simplified, units m/min after scale):
      R0 ∝ T + wind_force + (100 − h)

    Coefficients are **tunable**; default order-of-magnitude for surface fire
    (~0.5–5 m/min on flat calm). Not calibrated for CLM fuels.
    """
    t = float(temperature_c)
    w = max(0.0, float(wind_force))
    h = min(100.0, max(0.0, float(humidity_pct)))
    # R0 in m/min (a,b,c chosen so T=30, W=3, h=30 → ~2 m/min)
    r0 = a * t + b * w + c * (100.0 - h)
    return max(0.01, float(r0))


def wind_ms_from_beaufort(force: float) -> float:
    f = int(round(force))
    if f in _BEAUFORT_MS:
        return _BEAUFORT_MS[f]
    if f < 0:
        return 0.0
    # linear extend past 8
    return 19.0 + 3.0 * (f - 8)


def k_wind(v_ms: float, angle_wind_to_spread_deg: float) -> float:
    """K_w = exp(0.1783 · V · cos θ). θ = angle between wind and spread direction."""
    th = math.radians(float(angle_wind_to_spread_deg))
    return float(math.exp(0.1783 * max(0.0, float(v_ms)) * math.cos(th)))


def k_slope(slope_deg: float, *, upslope: bool) -> float:
    """K_s with Mao/Wang slope correction; clamp extreme slopes."""
    phi = abs(math.radians(min(60.0, max(0.0, float(slope_deg)))))
    tan_p = math.tan(phi)
    base = math.exp(3.533 * (tan_p**1.2))
    if upslope:
        return float(base)
    return float(math.exp(-3.533 * (tan_p**1.2)))


def k_fuel(fuel: str = "default") -> float:
    return float(FUEL_K_PHI.get(fuel.lower(), FUEL_K_PHI["default"]))


def ros_wang_zhengfei(
    r0_m_min: float,
    *,
    wind_ms: float = 0.0,
    wind_to_spread_deg: float = 0.0,
    slope_deg: float = 0.0,
    upslope: bool = True,
    fuel: str = "default",
    k_phi: float | None = None,
) -> float:
    """Directional ROS (m/min) Wang Zhengfei core."""
    kw = k_wind(wind_ms, wind_to_spread_deg)
    ks = k_slope(slope_deg, upslope=upslope)
    kp = float(k_phi) if k_phi is not None else k_fuel(fuel)
    return max(0.0, float(r0_m_min) * kw * ks * kp)


def ros_mao_8_directions(
    r0_m_min: float,
    *,
    wind_ms: float,
    wind_from_deg: float,
    slope_deg: float = 0.0,
    aspect_downslope_deg: float = 0.0,
    fuel: str = "default",
) -> dict[str, float]:
    """Eight direction ROS (m/min) Mao-style wind×slope.

    Directions are *spread* bearings (0=N, 90=E). ``wind_from_deg`` is
    meteorological *from* direction (wind blows toward from+180).
    """
    wind_to = (float(wind_from_deg) + 180.0) % 360.0
    # Upslope direction ≈ aspect of maximum elevation rise = downslope + 180
    upslope_dir = (float(aspect_downslope_deg) + 180.0) % 360.0
    names_bearings = {
        "N": 0.0,
        "NE": 45.0,
        "E": 90.0,
        "SE": 135.0,
        "S": 180.0,
        "SW": 225.0,
        "W": 270.0,
        "NW": 315.0,
    }
    out: dict[str, float] = {}
    for name, brg in names_bearings.items():
        wind_angle = abs((brg - wind_to + 180.0) % 360.0 - 180.0)  # 0..180
        # component of slope along spread: cos(spread - upslope_dir)
        slope_align = math.cos(math.radians(brg - upslope_dir))
        up = slope_align >= 0.0
        # effective slope magnitude along this ray
        eff_slope = abs(float(slope_deg) * slope_align)
        out[name] = round(
            ros_wang_zhengfei(
                r0_m_min,
                wind_ms=wind_ms,
                wind_to_spread_deg=wind_angle,
                slope_deg=eff_slope,
                upslope=up,
                fuel=fuel,
            ),
            4,
        )
    out["head_wind"] = out[
        min(
            names_bearings.keys(),
            key=lambda n: abs((names_bearings[n] - wind_to + 180.0) % 360.0 - 180.0),
        )
    ]
    return out


def polar_ros_ring(
    r0_m_min: float,
    *,
    wind_ms: float = 0.0,
    wind_from_deg: float = 0.0,
    slope_deg: float = 0.0,
    aspect_downslope_deg: float = 0.0,
    fuel: str = "default",
    step_deg: float = 5.0,
) -> list[tuple[float, float]]:
    """List of (bearing_deg, ros_m_min) every ``step_deg`` — for envelope rays.

    Same idea as Chinese GeoJSON tools that cast 360° rays from ignition.
    """
    wind_to = (float(wind_from_deg) + 180.0) % 360.0
    upslope_dir = (float(aspect_downslope_deg) + 180.0) % 360.0
    ring: list[tuple[float, float]] = []
    a = 0.0
    while a < 360.0 - 1e-9:
        wind_angle = abs((a - wind_to + 180.0) % 360.0 - 180.0)
        slope_align = math.cos(math.radians(a - upslope_dir))
        up = slope_align >= 0.0
        eff_slope = abs(float(slope_deg) * slope_align)
        r = ros_wang_zhengfei(
            r0_m_min,
            wind_ms=wind_ms,
            wind_to_spread_deg=wind_angle,
            slope_deg=eff_slope,
            upslope=up,
            fuel=fuel,
        )
        ring.append((round(a, 2), round(r, 4)))
        a += step_deg
    return ring


def envelope_radii_m(
    polar_ros: list[tuple[float, float]],
    horizon_min: float,
    *,
    cap_m_min: float = 40.0,
) -> list[tuple[float, float]]:
    """(bearing, radius_m) for a horizon from polar ROS."""
    return [
        (b, round(min(r, cap_m_min) * float(horizon_min), 2)) for b, r in polar_ros
    ]


def physics_prior_report(
    *,
    temperature_c: float = 30.0,
    humidity_pct: float = 30.0,
    wind_force: float = 3.0,
    wind_from_deg: float = 270.0,
    slope_deg: float = 5.0,
    aspect_downslope_deg: float = 90.0,
    fuel: str = "mixed",
    observed_ros_m_min: float | None = None,
) -> dict[str, Any]:
    """Full prior pack for ops comparison / logging."""
    r0 = r0_from_weather(temperature_c, wind_force, humidity_pct)
    v = wind_ms_from_beaufort(wind_force)
    eight = ros_mao_8_directions(
        r0,
        wind_ms=v,
        wind_from_deg=wind_from_deg,
        slope_deg=slope_deg,
        aspect_downslope_deg=aspect_downslope_deg,
        fuel=fuel,
    )
    polar = polar_ros_ring(
        r0,
        wind_ms=v,
        wind_from_deg=wind_from_deg,
        slope_deg=slope_deg,
        aspect_downslope_deg=aspect_downslope_deg,
        fuel=fuel,
        step_deg=15.0,
    )
    head = max(r for _, r in polar) if polar else r0
    rear = min(r for _, r in polar) if polar else r0
    out: dict[str, Any] = {
        "model": "wang_zhengfei_mao_xianmin",
        "label_es": (
            "Prior físico CN (王正非/毛贤敏) — comparación, NO despacho táctico. "
            "Requiere calibración local de R0/combustible."
        ),
        "r0_m_min": round(r0, 4),
        "wind_ms": round(v, 3),
        "inputs": {
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
            "wind_force": wind_force,
            "wind_from_deg": wind_from_deg,
            "slope_deg": slope_deg,
            "aspect_downslope_deg": aspect_downslope_deg,
            "fuel": fuel,
        },
        "ros_8dir_m_min": eight,
        "ros_head_m_min": round(head, 4),
        "ros_rear_m_min": round(rear, 4),
        "ros_mean_polar_m_min": round(sum(r for _, r in polar) / max(1, len(polar)), 4),
        "polar_sample": polar[:8],
        "horizons_m": {
            str(h): envelope_radii_m(polar, h)[:4]  # sample
            for h in (15, 30, 60)
        },
    }
    if observed_ros_m_min is not None and math.isfinite(observed_ros_m_min):
        obs = float(observed_ros_m_min)
        out["observed_ros_m_min"] = round(obs, 4)
        out["ratio_obs_over_prior_head"] = round(obs / head, 4) if head > 1e-9 else None
        out["ratio_obs_over_r0"] = round(obs / r0, 4) if r0 > 1e-9 else None
        out["note_calibration"] = (
            "If ratio_obs/r0 >> 1, scale R0 or use observed ROS as primary "
            "(physics only shapes anisotropy)."
        )
    return out


def hybrid_ros_prior(
    observed_ros_m_min: float,
    *,
    temperature_c: float = 32.0,
    humidity_pct: float = 28.0,
    wind_force: float = 3.0,
    wind_from_deg: float = 270.0,
    slope_deg: float = 4.0,
    aspect_downslope_deg: float = 90.0,
    fuel: str = "mixed",
    step_deg: float = 10.0,
    scale_mode: str = "mean",
) -> dict[str, Any]:
    """Ops hybrid: **magnitude = observed ROS**, **shape = Wang/Mao polar**.

    ``scale_mode``:
      - ``mean``: scale so mean(polar) == observed (default; stable)
      - ``head``: scale so max(polar) == observed

    Returns non-empty structured result with calibrated head/rear, full polar,
    scale factor, and sample envelope radii at 15/30/60 min.
    """
    obs = float(observed_ros_m_min)
    if not math.isfinite(obs) or obs < 0:
        return {
            "status": "abstained",
            "reason": "invalid_observed_ros",
            "model": "wang_mao_hybrid_obs_magnitude",
        }

    base = physics_prior_report(
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        wind_force=wind_force,
        wind_from_deg=wind_from_deg,
        slope_deg=slope_deg,
        aspect_downslope_deg=aspect_downslope_deg,
        fuel=fuel,
        observed_ros_m_min=obs,
    )
    r0 = float(base["r0_m_min"])
    v = float(base["wind_ms"])
    polar = polar_ros_ring(
        r0,
        wind_ms=v,
        wind_from_deg=wind_from_deg,
        slope_deg=slope_deg,
        aspect_downslope_deg=aspect_downslope_deg,
        fuel=fuel,
        step_deg=step_deg,
    )
    if not polar:
        return {
            "status": "abstained",
            "reason": "empty_polar",
            "model": "wang_mao_hybrid_obs_magnitude",
        }

    vals = [r for _, r in polar]
    mean_p = sum(vals) / len(vals)
    head_p = max(vals)
    if scale_mode == "head":
        scale = (obs / head_p) if head_p > 1e-9 else 1.0
    else:
        scale = (obs / mean_p) if mean_p > 1e-9 else 1.0

    polar_cal = [(b, round(r * scale, 4)) for b, r in polar]
    cal_vals = [r for _, r in polar_cal]
    head = max(cal_vals)
    rear = min(cal_vals)
    flank = sorted(cal_vals)[len(cal_vals) // 2]

    return {
        "status": "ok",
        "model": "wang_mao_hybrid_obs_magnitude",
        "label_es": (
            "Híbrido CN: magnitud=ROS observada, forma=王正非/毛贤敏. "
            "NO despacho táctico validado."
        ),
        "observed_ros_m_min": round(obs, 4),
        "scale_factor": round(scale, 4),
        "scale_mode": scale_mode,
        "r0_m_min": round(r0, 4),
        "wind_ms": round(v, 3),
        "inputs": base["inputs"],
        "ros_head_m_min": round(head, 4),
        "ros_flank_m_min": round(flank, 4),
        "ros_rear_m_min": round(rear, 4),
        "ros_mean_calibrated_m_min": round(sum(cal_vals) / len(cal_vals), 4),
        "polar_calibrated": polar_cal,
        "ros_8dir_raw_m_min": base["ros_8dir_m_min"],
        "envelope_radii_m": {
            str(h): envelope_radii_m(polar_cal, h) for h in (15, 30, 60)
        },
        "raw_prior": {
            "ros_head_m_min": base["ros_head_m_min"],
            "ros_rear_m_min": base["ros_rear_m_min"],
            "ratio_obs_over_r0": base.get("ratio_obs_over_r0"),
        },
    }


def hybrid_polar_to_geojson_ring(
    hybrid: dict[str, Any],
    origin_xy: tuple[float, float],
    horizon_min: float = 15.0,
    *,
    crs_note: str = "projected_meters",
) -> dict[str, Any]:
    """Build a GeoJSON Polygon ring from calibrated polar radii around origin.

    ``origin_xy`` must be in a projected CRS in meters (e.g. UTM) for
    meter radii to be meaningful. Bearing 0 = north (+y), 90 = east (+x).
    """
    if hybrid.get("status") != "ok":
        return {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"status": hybrid.get("status"), "reason": hybrid.get("reason")},
        }
    polar = hybrid.get("polar_calibrated") or []
    ox, oy = float(origin_xy[0]), float(origin_xy[1])
    coords: list[list[float]] = []
    for bearing, ros in polar:
        rad_m = min(float(ros), 40.0) * float(horizon_min)
        br = math.radians(float(bearing))
        # 0=N → +y, 90=E → +x
        x = ox + rad_m * math.sin(br)
        y = oy + rad_m * math.cos(br)
        coords.append([round(x, 3), round(y, 3)])
    if coords:
        coords.append(coords[0])
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "product": "cn_hybrid_polar_envelope",
                    "horizon_min": int(horizon_min),
                    "model": hybrid.get("model"),
                    "scale_factor": hybrid.get("scale_factor"),
                    "ros_head_m_min": hybrid.get("ros_head_m_min"),
                    "ros_rear_m_min": hybrid.get("ros_rear_m_min"),
                    "crs_note": crs_note,
                    "label_es": hybrid.get("label_es"),
                    "not_dispatch": True,
                },
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        ],
    }
