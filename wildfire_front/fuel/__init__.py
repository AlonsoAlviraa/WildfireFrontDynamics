"""Fuel–terrain stack and Rothermel-lite physics prior (ops product layer).

Separates three ROS concepts (see docs/MEGA_PLAN_PREDICCION_ROS_VEGETACION_TERRENO.md):

* **observed** — measured from thermal / ops perimeters (front_dynamics)
* **physics potential** — Rothermel-lite + Mediterranean fuel models
* **hybrid predictive** — α·obs + (1−α)·physics with ABSTAIN gates

Never sells physics-only ROS as tactical dispatch without uncertainty + ABSTAIN.

Envelope / scorecard symbols (PR-β) are **lazy-exported** so a PR-α land of the
core fuel package can import without requiring envelope modules at import time.
"""

from __future__ import annotations

from typing import Any

from .calibration import (
    CalibrationRecipe,
    CalibrationRefusedError,
    apply_calibration,
    fit_sector_scale_factors,
    load_recipe,
    residual_metrics,
    save_recipe,
)
from .fuel_map import (
    FuelMapProduct,
    FuelMapUnavailableError,
    resolve_fuel_map,
)
from .dem import (
    DEFAULT_CRS,
    TOBARRA_BBOX_WGS84,
    DemFetchError,
    DemProduct,
    DemUnavailableError,
    load_dem_geotiff,
    resolve_dem,
    synthetic_dem_product,
)
from .hybrid import hybrid_ros_prior
from .models import FUEL_CATALOG, FuelModel, get_fuel, list_fuel_ids
from .rothermel_lite import (
    PhysicsPriorResult,
    estimate_sector_ros_from_fuel_map,
    estimate_sector_ros_physics,
    midflame_wind_ms,
    physics_prior_report,
    ros_potential_m_min,
)
from .sector_fuels import (
    SectorFuelSummary,
    SectorTerrainSummary,
    majority_fuel_id,
    sector_fuel_summary_from_grid,
    sector_fuel_summary_from_product,
    sector_slope_summary_from_grid,
)
from .stack import (
    FuelTerrainStack,
    build_stack_from_dem,
    build_synthetic_tobarra_stack,
    stack_summary,
)
from .terrain import TerrainSample, slope_factor_phi_s, slope_from_rise_run
from .weather import (
    WeatherScenario,
    build_aemet_weather_for_fire_day,
    load_aemet_api_key,
    load_dotenv,
    load_weather_scenario,
    merge_weather_drivers,
    resolve_weather_for_stack,
    tobarra_20240802_default_scenario,
    weather_scenario_from_aemet_daily,
)

# PR-β envelope symbols — resolved on first attribute access (lazy)
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "PRODUCT_V3": (".envelope", "PRODUCT_V3"),
    "compute_hybrid_envelope": (".envelope", "compute_hybrid_envelope"),
    "envelope_decision_reasons": (".envelope", "envelope_decision_reasons"),
    "extract_sector_ros": (".envelope", "extract_sector_ros"),
    "radii_from_sector_ros": (".envelope", "radii_from_sector_ros"),
    "attach_envelope_to_decision_card": (
        ".envelope_scorecard",
        "attach_envelope_to_decision_card",
    ),
    "build_tobarra_envelope_scorecard": (
        ".envelope_scorecard",
        "build_tobarra_envelope_scorecard",
    ),
}


def __getattr__(name: str) -> Any:
    """Lazy-load PR-β envelope exports so PR-α core imports stay light."""
    if name in _LAZY_EXPORTS:
        import importlib

        mod_name, attr = _LAZY_EXPORTS[name]
        mod = importlib.import_module(mod_name, __name__)
        value = getattr(mod, attr)
        globals()[name] = value  # cache
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(__all__))


__all__ = [
    "DEFAULT_CRS",
    "FUEL_CATALOG",
    "TOBARRA_BBOX_WGS84",
    "CalibrationRecipe",
    "CalibrationRefusedError",
    "DemFetchError",
    "DemProduct",
    "DemUnavailableError",
    "FuelMapProduct",
    "FuelMapUnavailableError",
    "FuelModel",
    "FuelTerrainStack",
    "PRODUCT_V3",
    "PhysicsPriorResult",
    "SectorFuelSummary",
    "SectorTerrainSummary",
    "TerrainSample",
    "WeatherScenario",
    "apply_calibration",
    "attach_envelope_to_decision_card",
    "build_aemet_weather_for_fire_day",
    "build_stack_from_dem",
    "build_synthetic_tobarra_stack",
    "build_tobarra_envelope_scorecard",
    "compute_hybrid_envelope",
    "envelope_decision_reasons",
    "estimate_sector_ros_from_fuel_map",
    "estimate_sector_ros_physics",
    "extract_sector_ros",
    "fit_sector_scale_factors",
    "get_fuel",
    "hybrid_ros_prior",
    "list_fuel_ids",
    "load_aemet_api_key",
    "load_dem_geotiff",
    "load_dotenv",
    "load_recipe",
    "load_weather_scenario",
    "majority_fuel_id",
    "merge_weather_drivers",
    "midflame_wind_ms",
    "physics_prior_report",
    "radii_from_sector_ros",
    "residual_metrics",
    "resolve_dem",
    "resolve_fuel_map",
    "resolve_weather_for_stack",
    "ros_potential_m_min",
    "save_recipe",
    "sector_fuel_summary_from_grid",
    "sector_fuel_summary_from_product",
    "sector_slope_summary_from_grid",
    "slope_factor_phi_s",
    "slope_from_rise_run",
    "stack_summary",
    "synthetic_dem_product",
    "tobarra_20240802_default_scenario",
    "weather_scenario_from_aemet_daily",
]
