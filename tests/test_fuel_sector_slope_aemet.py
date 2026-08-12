"""Tests: sector DEM slopes + AEMET weather scenario conversion."""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.fuel.rothermel_lite import estimate_sector_ros_from_fuel_map
from wildfire_front.fuel.sector_fuels import sector_slope_summary_from_grid
from wildfire_front.fuel.weather import (
    aemet_dir_to_from_deg,
    weather_scenario_from_aemet_daily,
)


class TestSectorSlopes:
    def test_mean_slope_per_wedge(self) -> None:
        slope = np.zeros((20, 20), dtype=float)
        slope[:, 10:] = 15.0
        slope[:, :10] = 3.0
        # head to east (90°) → head wedge sees higher slope
        s = sector_slope_summary_from_grid(slope, head_bearing_deg=90.0)
        assert s.head_slope_deg > s.rear_slope_deg
        assert s.n_cells["head"] > 0

    def test_spatial_ros_uses_sector_slopes(self) -> None:
        grid = np.full((24, 24), "MED_GRASS", dtype=object)
        slope = np.full((24, 24), 2.0)
        slope[:, 12:] = 20.0  # steeper to the east
        flat = estimate_sector_ros_from_fuel_map(
            None,
            wind_10m_ms=5.0,
            slope_deg=2.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            head_bearing_deg=90.0,
            fuel_id_grid=grid,
            slope_deg_grid=None,
            fallback_fuel_id="MED_GRASS",
        )
        steep = estimate_sector_ros_from_fuel_map(
            None,
            wind_10m_ms=5.0,
            slope_deg=2.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            head_bearing_deg=90.0,
            fuel_id_grid=grid,
            slope_deg_grid=slope,
            fallback_fuel_id="MED_GRASS",
        )
        assert flat.status == "estimated" and steep.status == "estimated"
        assert steep.ros_head_m_min >= flat.ros_head_m_min
        assert steep.drivers.get("sector_slopes_deg") is not None
        assert "sector_slopes_from_dem" in (steep.reasons or [])


class TestAemetWeather:
    def test_dir_tens_of_deg(self) -> None:
        assert aemet_dir_to_from_deg(27) == 270.0
        assert aemet_dir_to_from_deg(270) == 270.0

    def test_scenario_from_daily_record(self) -> None:
        rec = {
            "fecha": "2024-08-02",
            "tmed": "35,0",
            "hrmedia": "10",
            "velmedia": "5,8",
            "dir": "27",
            "prec": "0,0",
        }
        ws = weather_scenario_from_aemet_daily(rec, fire_id="tobarra_20240802", station_id="8175")
        assert ws.source == "aemet"
        assert ws.wind_10m_ms == pytest.approx(5.8, abs=0.05)
        assert ws.wind_from_deg == pytest.approx(270.0)
        assert ws.temp_c == 35.0
        assert ws.rh_pct == 10.0
        assert ws.dead_fmc_pct is not None
        assert not ws.is_assumed
