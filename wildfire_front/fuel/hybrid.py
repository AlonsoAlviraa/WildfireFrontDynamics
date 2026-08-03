"""Hybrid ROS: blend observed thermal/ops ROS with physics potential.

α increases when recent observed ROS is available (high trust).
Physics alone never yields field_ops GO.

When a calibration recipe is present, nested physics is calibrated for audit;
hybrid sectors remain obs-scaled when observed ROS is present (design K1).

When a spatial fuel map is present, nested physics uses sector-majority fuels
(flank is fuel-map derived). Head remains obs-locked when observed ROS exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .rothermel_lite import (
    estimate_sector_ros_from_fuel_map,
    estimate_sector_ros_physics,
    physics_prior_report,
)


def hybrid_alpha(
    *,
    has_observed_ros: bool,
    age_minutes: float | None = None,
    max_age_for_full_obs: float = 45.0,
) -> float:
    """Weight on observed ROS in [0, 1]."""
    if not has_observed_ros:
        return 0.0
    if age_minutes is None:
        return 0.75
    age = max(0.0, float(age_minutes))
    if age >= max_age_for_full_obs * 2:
        return 0.25
    t = min(1.0, age / (max_age_for_full_obs * 2))
    return float(0.9 - 0.5 * t)


def hybrid_ros_prior(
    observed_ros_m_min: float | None,
    *,
    fuel_id: str = "MED_MAQUIS_LOW",
    wind_10m_ms: float | None = 4.4,
    slope_deg: float = 5.0,
    dead_fmc_pct: float = 7.0,
    wind_from_deg: float = 270.0,
    head_bearing_deg: float | None = None,
    obs_age_minutes: float | None = 20.0,
    vp_anchor_m_min: float | None = None,
    vp_status: str | None = None,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    force_recipe: bool = False,
    fuel_map: Any | None = None,
    sector_fuels: Any | None = None,
    slope_deg_grid: Any | None = None,
    weather_scenario: Any | None = None,
) -> dict[str, Any]:
    """Hybrid head/flank/rear ROS with audit α and ABSTAIN rules.

    Wind defaults (4.4 m/s, 270°) are **library engineering assumed** values for
    back-compat — not station-observed. Prefer ``weather_scenario`` or explicit
    CLI wind; report stamps ``weather_scenario_assumed`` when no scenario given.

    Incomplete ``source=observed|aemet`` with null wind does **not** inherit
    library 4.4 m/s while claiming non-assumed — wind is cleared to None
    (physics ABSTAIN missing_wind) or defaults are stamped assumed if filled.
    """
    from .weather import merge_weather_drivers

    weather_merge = merge_weather_drivers(
        weather_scenario,
        wind_10m_ms=wind_10m_ms,
        wind_from_deg=wind_from_deg,
        dead_fmc_pct=dead_fmc_pct,
    )
    wind_10m_ms = weather_merge.wind_10m_ms
    wind_from_filled_default = weather_merge.wind_from_deg is None
    wind_from_deg = (
        weather_merge.wind_from_deg
        if weather_merge.wind_from_deg is not None
        else 0.0
    )
    dead_fmc_pct = (
        weather_merge.dead_fmc_pct
        if weather_merge.dead_fmc_pct is not None
        else 7.0
    )

    use_spatial = fuel_map is not None or sector_fuels is not None
    if use_spatial:
        phys_raw = estimate_sector_ros_from_fuel_map(
            fuel_map,
            wind_10m_ms=wind_10m_ms,
            slope_deg=slope_deg,
            dead_fmc_pct=dead_fmc_pct,
            wind_from_deg=wind_from_deg,
            head_bearing_deg=head_bearing_deg,
            sector_fuels=sector_fuels,
            fallback_fuel_id=fuel_id,
            slope_deg_grid=slope_deg_grid,
        )
    else:
        phys_raw = estimate_sector_ros_physics(
            fuel=fuel_id,
            wind_10m_ms=wind_10m_ms,
            slope_deg=slope_deg,
            dead_fmc_pct=dead_fmc_pct,
            wind_from_deg=wind_from_deg,
            head_bearing_deg=head_bearing_deg,
        )
    phys_for_audit = phys_raw
    recipe_loaded = None
    if calibration_recipe is not None:
        from .calibration import CalibrationRecipe, apply_calibration, load_recipe

        if isinstance(calibration_recipe, (str, Path)):
            recipe_loaded = load_recipe(calibration_recipe)
        elif isinstance(calibration_recipe, CalibrationRecipe):
            recipe_loaded = calibration_recipe
        elif isinstance(calibration_recipe, dict):
            recipe_loaded = CalibrationRecipe.from_dict(calibration_recipe)
        else:
            raise TypeError("calibration_recipe type not supported")
        phys_for_audit = apply_calibration(
            phys_raw,
            recipe_loaded,
            current_dem_source=dem_source,
            force=force_recipe,
        )

    alpha = hybrid_alpha(
        has_observed_ros=observed_ros_m_min is not None and observed_ros_m_min > 0,
        age_minutes=obs_age_minutes,
    )

    if phys_raw.status == "abstained" and (observed_ros_m_min is None or observed_ros_m_min <= 0):
        return {
            "status": "abstained",
            "reason": "no_obs_and_physics_abstained",
            "physics": phys_for_audit.to_dict(),
            "physics_raw": phys_raw.to_dict() if recipe_loaded else None,
            "alpha_obs": alpha,
            "product_claim": "abstain",
            "no_tactical_dispatch": True,
        }

    def blend(obs: float | None, phy: float | None) -> float | None:
        if obs is not None and phy is not None:
            return round(alpha * float(obs) + (1.0 - alpha) * float(phy), 4)
        if obs is not None:
            return round(float(obs), 4)
        if phy is not None:
            return round(float(phy), 4)
        return None

    # Sector structure: use **raw** physics shape scaled to obs (stable w/ or w/o recipe).
    # When obs present but physics abstains / head missing, use obs-only recipe
    # (head=obs, flank=0.5·obs, rear=0.3·obs, primary=obs) — PR-α product path.
    obs = float(observed_ros_m_min) if observed_ros_m_min else None
    ph = phys_raw.ros_head_m_min
    pf = phys_raw.ros_flank_m_min
    pr = phys_raw.ros_rear_m_min

    status = "estimated"
    reasons: list[str] = []

    if obs is not None and ph is not None and float(ph) > 0:
        scale = obs / float(ph)
        head_p = float(ph) * scale
        flank_p = (float(pf) if pf is not None else float(ph) * 0.45) * scale
        rear_p = (float(pr) if pr is not None else float(ph) * 0.25) * scale
        head = blend(obs, head_p)
        flank = blend(obs * 0.5, flank_p)
        rear = blend(obs * 0.3, rear_p)
        # Obs-locked primary matches head (not unscaled physics primary)
        primary = head
    elif obs is not None:
        # Physics abstained or missing head — still product-facing obs sectors
        head = round(obs, 4)
        flank = round(obs * 0.5, 4)
        rear = round(obs * 0.3, 4)
        primary = head
        reasons.append("obs_only_sector_recipe")
        status = "estimated_obs_only"
    else:
        # no obs: pure physics path — use calibrated if available
        use = phys_for_audit
        head = blend(None, use.ros_head_m_min)
        flank = blend(None, use.ros_flank_m_min)
        rear = blend(None, use.ros_rear_m_min)
        primary = blend(None, use.ros_primary_m_min)

    if alpha < 0.35 and phys_raw.status == "estimated":
        reasons.append("low_obs_weight_physics_dominant")
    if phys_raw.status == "abstained" and obs is not None:
        if "physics_abstained_obs_only" not in reasons:
            reasons.append("physics_abstained_obs_only")
        status = "estimated_obs_only"
    elif phys_raw.status == "abstained" and obs is None:
        reasons.append("physics_abstained_obs_only")
        status = "estimated_obs_only"

    report_fuel = phys_raw.fuel_id or fuel_id
    # Reuse phys_raw — avoid double spatial/single physics evaluation
    report = physics_prior_report(
        fuel_id=report_fuel,
        wind_10m_ms=wind_10m_ms,
        slope_deg=slope_deg,
        dead_fmc_pct=dead_fmc_pct,
        wind_from_deg=wind_from_deg,
        head_bearing_deg=head_bearing_deg,
        observed_ros_m_min=observed_ros_m_min,
        vp_anchor_m_min=vp_anchor_m_min,
        vp_status=vp_status,
        calibration_recipe=recipe_loaded,
        dem_source=dem_source,
        force_recipe=force_recipe,
        fuel_map=None,
        sector_fuels=None,
        weather_scenario=weather_scenario,
        prior_raw=phys_raw,
    )

    if use_spatial:
        reasons = list(reasons) + ["physics_spatial_sector_fuels"]
        if "flank_fuel_map_derived" in (phys_raw.reasons or []):
            reasons.append("flank_fuel_map_derived")
    if wind_from_filled_default:
        reasons.append("wind_from_deg_defaulted_after_merge_null")

    out: dict[str, Any] = {
        "status": status,
        "method": (
            "hybrid_obs_physics_spatial_v1" if use_spatial else "hybrid_obs_physics_v1"
        ),
        "alpha_obs": round(alpha, 4),
        "sectors": {
            "head_m_min": head,
            "flank_m_min": flank,
            "rear_m_min": rear,
            "primary_m_min": primary,
        },
        "physics": phys_for_audit.to_dict(),
        "physics_raw": phys_raw.to_dict() if recipe_loaded else None,
        "physics_product_claim": phys_for_audit.product_claim,
        "physics_report_calibration": report.get("calibration"),
        "calibration_recipe": report.get("calibration_recipe"),
        "reasons": reasons,
        "product_claim": "hybrid_orientation_with_uncertainty",
        "no_tactical_dispatch": True,
        "calibration_note": (
            "nested physics may be calibrated; hybrid sectors remain obs-scaled "
            "when observed ROS is present"
            + (
                "; flank shape from fuel-map sector majority when spatial fuels used"
                if use_spatial
                else ""
            )
        ),
        "disclaimer": report["disclaimer"],
    }
    if report.get("sector_fuels") is not None:
        out["sector_fuels"] = report["sector_fuels"]
    if report.get("weather_scenario") is not None:
        out["weather_scenario"] = report["weather_scenario"]
    # Prefer honesty merge flag (may be True when observed had defaults filled)
    out["weather_scenario_assumed"] = bool(weather_merge.weather_scenario_assumed)
    out["weather_drivers_merge"] = weather_merge.to_audit_dict()
    if weather_merge.weather_partially_filled_from_defaults:
        out["reasons"] = list(out.get("reasons") or []) + [
            "weather_partially_filled_from_defaults"
        ]
    if weather_merge.fields_missing_cleared:
        out["reasons"] = list(out.get("reasons") or []) + [
            "weather_station_incomplete_wind_cleared"
        ]
    return out
