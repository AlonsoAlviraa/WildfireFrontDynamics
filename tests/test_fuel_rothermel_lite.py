"""Tests for fuel catalog, terrain stack, Rothermel-lite, hybrid prior."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.fuel.hybrid import hybrid_alpha, hybrid_ros_prior
from wildfire_front.fuel.models import FUEL_CATALOG, fuel_from_clc, get_fuel, list_fuel_ids
from wildfire_front.fuel.rothermel_lite import (
    estimate_sector_ros_physics,
    midflame_wind_ms,
    physics_prior_report,
    ros_potential_m_min,
)
from wildfire_front.fuel.stack import (
    build_synthetic_tobarra_stack,
    stack_summary,
    write_stack,
)
from wildfire_front.fuel.terrain import (
    slope_array_from_dem,
    slope_factor_phi_s,
    slope_from_rise_run,
)


class TestFuelCatalog:
    def test_med_maquis_present(self) -> None:
        f = get_fuel("MED_MAQUIS_LOW")
        assert f.id == "MED_MAQUIS_LOW"
        assert f.fuel_load > 0
        assert f.height_m >= 1.0

    def test_list_fuels_nonempty(self) -> None:
        ids = list_fuel_ids()
        assert "SH5" in ids
        assert "MED_MAQUIS_TALL" in ids
        assert "UNKNOWN" not in ids

    def test_clc_crosswalk_maquis(self) -> None:
        f = fuel_from_clc(323)
        assert f.family in {"MED", "SH", "GS"}
        assert f.id != "UNKNOWN"

    def test_unknown_fuel(self) -> None:
        f = get_fuel("UNKNOWN")
        assert f.fuel_load == 0


class TestTerrain:
    def test_slope_45_deg(self) -> None:
        assert abs(slope_from_rise_run(1.0, 1.0) - 45.0) < 0.01

    def test_phi_s_increases(self) -> None:
        assert slope_factor_phi_s(20.0) > slope_factor_phi_s(5.0)

    def test_slope_from_dem(self) -> None:
        dem = np.zeros((10, 10))
        dem[:, :] = np.arange(10)[None, :] * 5.0  # rise along x
        s = slope_array_from_dem(dem, cell_size_m=25.0)
        assert float(np.mean(s[:, 1:-1])) > 0


class TestRothermelLite:
    def test_abstain_unknown_fuel(self) -> None:
        r = ros_potential_m_min(
            fuel="UNKNOWN",
            wind_10m_ms=5.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
        )
        assert r["status"] == "abstained"

    def test_abstain_missing_wind(self) -> None:
        r = ros_potential_m_min(
            fuel="MED_MAQUIS_LOW",
            wind_10m_ms=None,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            require_wind=True,
        )
        assert r["status"] == "abstained"
        assert r["reason"] == "missing_wind"

    def test_ros_increases_with_wind(self) -> None:
        low = ros_potential_m_min(
            fuel="MED_MAQUIS_LOW",
            wind_10m_ms=2.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_to_spread_deg=0.0,
        )
        high = ros_potential_m_min(
            fuel="MED_MAQUIS_LOW",
            wind_10m_ms=12.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_to_spread_deg=0.0,
        )
        assert high["ros_m_min"] > low["ros_m_min"]

    def test_ros_increases_with_slope(self) -> None:
        flat = ros_potential_m_min(
            fuel="GS2",
            wind_10m_ms=5.0,
            slope_deg=0.0,
            dead_fmc_pct=7.0,
            upslope=True,
        )
        steep = ros_potential_m_min(
            fuel="GS2",
            wind_10m_ms=5.0,
            slope_deg=25.0,
            dead_fmc_pct=7.0,
            upslope=True,
        )
        assert steep["ros_m_min"] > flat["ros_m_min"]

    def test_grass_faster_than_litter_moderate(self) -> None:
        grass = ros_potential_m_min(
            fuel="MED_GRASS",
            wind_10m_ms=6.0,
            slope_deg=8.0,
            dead_fmc_pct=6.0,
            wind_to_spread_deg=0.0,
        )
        litter = ros_potential_m_min(
            fuel="MED_PINE_LITTER",
            wind_10m_ms=6.0,
            slope_deg=8.0,
            dead_fmc_pct=6.0,
            wind_to_spread_deg=0.0,
        )
        assert grass["ros_m_min"] > litter["ros_m_min"]

    def test_tobarra_order_of_magnitude(self) -> None:
        """Under moderate Med scrub conditions, head ROS should be O(1–40) m/min.

        Tobarra Vp anchor is 7 m/min; physics prior need not match exactly but
        must be in a literature-plausible band (not 0.01 or 200).
        """
        r = estimate_sector_ros_physics(
            fuel="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
        )
        assert r.status == "estimated"
        assert r.ros_head_m_min is not None
        assert 0.5 <= r.ros_head_m_min <= 60.0
        assert r.ros_head_m_min >= r.ros_rear_m_min  # type: ignore[operator]
        assert r.no_tactical_dispatch is True

    def test_calibration_report_vs_vp(self) -> None:
        rep = physics_prior_report(
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            observed_ros_m_min=5.71,
            vp_anchor_m_min=7.0,
        )
        assert rep["status"] == "estimated"
        assert rep["calibration"] is not None
        assert "ratio_physics_head_to_vp" in rep["calibration"]
        assert rep["no_tactical_dispatch"] is True

    def test_midflame_less_than_10m(self) -> None:
        mf = midflame_wind_ms(10.0, "MED_PINE_LITTER")
        assert mf < 10.0
        assert mf > 0


class TestHybrid:
    def test_alpha_decays_with_age(self) -> None:
        a0 = hybrid_alpha(has_observed_ros=True, age_minutes=0)
        a1 = hybrid_alpha(has_observed_ros=True, age_minutes=90)
        assert a0 > a1

    def test_hybrid_with_obs(self) -> None:
        h = hybrid_ros_prior(
            5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            vp_anchor_m_min=7.0,
            vp_status="confirmed",
        )
        assert h["status"] in {"estimated", "estimated_obs_only"}
        assert h["sectors"]["primary_m_min"] is not None
        assert 0 < h["alpha_obs"] <= 1
        assert h["no_tactical_dispatch"] is True
        # PR-7 DoD: with obs present, hybrid head is obs-locked
        assert h["sectors"]["head_m_min"] == pytest.approx(5.71, abs=1e-6)
        # Primary matches obs-locked head (not unscaled physics primary)
        assert h["sectors"]["primary_m_min"] == pytest.approx(
            h["sectors"]["head_m_min"], abs=1e-6
        )
        assert h.get("weather_scenario_assumed") is True
        assert h.get("weather_drivers_merge") is not None
        phys = h.get("physics") or {}
        assert phys.get("product_claim") == "physics_potential_orientation_only"

    def test_hybrid_obs_only_when_physics_abstains(self) -> None:
        """Issue 1: obs present + physics ABSTAIN still yields finite obs sectors."""
        from wildfire_front.fuel.weather import WeatherScenario

        ws = WeatherScenario(
            wind_10m_ms=None,
            wind_from_deg=None,
            dead_fmc_pct=None,
            source="observed",
            notes=["incomplete_station"],
        )
        h = hybrid_ros_prior(
            5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            weather_scenario=ws,
        )
        assert h["status"] == "estimated_obs_only"
        assert h["sectors"]["head_m_min"] == pytest.approx(5.71, abs=1e-6)
        assert h["sectors"]["flank_m_min"] == pytest.approx(5.71 * 0.5, abs=1e-6)
        assert h["sectors"]["rear_m_min"] == pytest.approx(5.71 * 0.3, abs=1e-6)
        assert h["sectors"]["primary_m_min"] == pytest.approx(5.71, abs=1e-6)
        assert "obs_only_sector_recipe" in (h.get("reasons") or [])
        assert "physics_abstained_obs_only" in (h.get("reasons") or [])
        assert (h.get("physics") or {}).get("status") == "abstained"

    def test_hybrid_abstain_no_inputs(self) -> None:
        h = hybrid_ros_prior(
            None,
            fuel_id="UNKNOWN",
            wind_10m_ms=None,
        )
        assert h["status"] == "abstained"


class TestStack:
    def test_synthetic_tobarra(self, tmp_path: Path) -> None:
        stack = build_synthetic_tobarra_stack(n=16, seed=1)
        assert stack.fire_id == "tobarra_20240802"
        assert stack.synthetic is True
        assert stack.n_rows == 16
        s = stack_summary(stack)
        assert s["fuel_id_dominant"]
        paths = write_stack(stack, tmp_path)
        assert Path(paths["meta"]).is_file()
        meta = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
        assert meta["protocol"] == "fuel_terrain_stack_v1"
        assert "grids_npz" in paths
        data = np.load(paths["grids_npz"])
        assert "slope_deg" in data.files
        assert data["dem_m"].shape == (16, 16)

    def test_catalog_size(self) -> None:
        # SB subset + Med custom
        assert len(FUEL_CATALOG) >= 15
