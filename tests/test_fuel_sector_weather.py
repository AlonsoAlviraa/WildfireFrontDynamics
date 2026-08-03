"""Tests: sector fuel majority, spatial sector ROS, weather scenario honesty."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.fuel.hybrid import hybrid_ros_prior
from wildfire_front.fuel.rothermel_lite import (
    estimate_sector_ros_from_fuel_map,
    estimate_sector_ros_physics,
    physics_prior_report,
)
from wildfire_front.fuel.sector_fuels import (
    classify_sector_mask,
    majority_fuel_id,
    sector_fuel_summary_from_grid,
)
from wildfire_front.fuel.weather import (
    WeatherScenario,
    kmh_to_ms,
    load_weather_scenario,
    resolve_weather_for_stack,
    tobarra_20240802_default_scenario,
)


class TestMajorityFuel:
    def test_simple_mode(self) -> None:
        assert majority_fuel_id(["A", "A", "B"]) == "A"

    def test_ignore_unknown_minority(self) -> None:
        ids = ["MED_GRASS"] * 5 + ["UNKNOWN"] * 3 + ["MED_MAQUIS_LOW"] * 2
        assert majority_fuel_id(ids) == "MED_GRASS"

    def test_unknown_only(self) -> None:
        assert majority_fuel_id(["UNKNOWN", "UNKNOWN"]) == "UNKNOWN"

    def test_unknown_strict_majority_kept(self) -> None:
        # UNKNOWN is strict majority → keep it
        ids = ["UNKNOWN"] * 5 + ["MED_GRASS"] * 2
        assert majority_fuel_id(ids) == "UNKNOWN"

    def test_unknown_tie_dropped(self) -> None:
        # equal UNKNOWN vs burnable → drop UNKNOWN (not only strict minority)
        ids = ["UNKNOWN"] * 3 + ["MED_GRASS"] * 3
        assert majority_fuel_id(ids) == "MED_GRASS"

    def test_empty_fallback(self) -> None:
        assert majority_fuel_id([], fallback="MED_GRASS") == "MED_GRASS"


class TestSectorFuelSummary:
    def test_east_head_grass_west_pine(self) -> None:
        # Grid: west half pine litter, east half grass; head bearing east (90°)
        h, w = 20, 20
        grid = np.empty((h, w), dtype=object)
        grid[:, : w // 2] = "MED_PINE_LITTER"
        grid[:, w // 2 :] = "MED_GRASS"
        summary = sector_fuel_summary_from_grid(grid, head_bearing_deg=90.0)
        assert summary.head_fuel_id == "MED_GRASS"
        assert summary.rear_fuel_id == "MED_PINE_LITTER"
        assert summary.n_cells["head"] > 0
        assert summary.n_cells["flank"] > 0
        assert summary.n_cells["rear"] > 0
        d = summary.to_dict()
        assert d["method"] == "wedge_majority_v1"
        assert "head_fuel_id" in d

    def test_unknown_ignored_when_minority_in_wedge(self) -> None:
        h, w = 12, 12
        grid = np.full((h, w), "MED_GRASS", dtype=object)
        # sprinkle UNKNOWN in head (east) but minority
        grid[5:7, 9:11] = "UNKNOWN"
        summary = sector_fuel_summary_from_grid(grid, head_bearing_deg=90.0)
        assert summary.head_fuel_id == "MED_GRASS"

    def test_classify_masks_cover_all(self) -> None:
        br = np.array([0.0, 90.0, 180.0, 270.0])
        labels = classify_sector_mask(br, 90.0)
        assert labels[1] == "head"  # 90
        assert labels[3] == "rear"  # 270 = rear of east head
        assert labels[0] == "flank" or labels[0] == "rear"  # N relative to E head


class TestSpatialSectorRos:
    def test_spatial_uses_different_fuels_and_orders(self) -> None:
        h, w = 24, 24
        grid = np.empty((h, w), dtype=object)
        # head (east) = grass (fast), rear (west) = pine litter (slower)
        grid[:, : w // 2] = "MED_PINE_LITTER"
        grid[:, w // 2 :] = "MED_GRASS"
        spatial = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=6.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,  # head bearing 90°
            head_bearing_deg=90.0,
            fallback_fuel_id="MED_GRASS",
        )
        assert spatial.status == "estimated"
        assert spatial.method == "rothermel_lite_sectors_spatial_v1"
        assert spatial.ros_head_m_min is not None
        assert spatial.ros_flank_m_min is not None
        assert spatial.ros_rear_m_min is not None
        assert spatial.ros_head_m_min >= spatial.ros_flank_m_min >= spatial.ros_rear_m_min
        drivers = spatial.drivers
        assert drivers.get("sector_fuel_mode") == "spatial_wedge_majority"
        assert "sector_fuels" in drivers
        assert drivers["sector_fuel_ids"]["head"] == "MED_GRASS"
        assert drivers["sector_fuel_ids"]["rear"] == "MED_PINE_LITTER"
        assert "flank_fuel_map_derived" in (spatial.reasons or [])

        # single dominant grass for comparison — head should be same family order
        single = estimate_sector_ros_physics(
            fuel="MED_GRASS",
            wind_10m_ms=6.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            head_bearing_deg=90.0,
        )
        assert single.ros_head_m_min is not None
        # spatial head (grass) close to single grass head
        assert abs(spatial.ros_head_m_min - single.ros_head_m_min) < 0.5

    def test_physics_prior_report_persists_sector_fuels(self) -> None:
        h, w = 16, 16
        grid = np.full((h, w), "MED_MAQUIS_LOW", dtype=object)
        grid[:, w // 2 :] = "MED_GRASS"
        rep = physics_prior_report(
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            sector_fuels=sector_fuel_summary_from_grid(grid, head_bearing_deg=90.0),
            observed_ros_m_min=5.71,
        )
        assert rep["status"] == "estimated"
        assert rep.get("sector_fuels") is not None
        assert "sector_fuels" in (rep.get("drivers") or {})

    def test_fallback_without_spatial(self) -> None:
        r = estimate_sector_ros_from_fuel_map(
            None,
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            fallback_fuel_id="MED_GRASS",
        )
        assert r.status == "estimated"
        assert r.method == "rothermel_lite_sectors_v1"
        assert r.fuel_id == "MED_GRASS"

    def test_hybrid_obs_lock_with_spatial(self) -> None:
        h, w = 16, 16
        grid = np.full((h, w), "MED_GRASS", dtype=object)
        grid[:, :4] = "MED_PINE_LITTER"
        sec = sector_fuel_summary_from_grid(grid, head_bearing_deg=90.0)
        h_out = hybrid_ros_prior(
            5.71,
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,
            slope_deg=3.3,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            sector_fuels=sec,
        )
        assert h_out["status"] in {"estimated", "estimated_obs_only"}
        assert h_out["sectors"]["head_m_min"] == pytest.approx(5.71, abs=1e-6)
        assert h_out["sectors"]["primary_m_min"] == pytest.approx(
            h_out["sectors"]["head_m_min"], abs=1e-6
        )
        assert "physics_spatial_sector_fuels" in h_out["reasons"]
        assert h_out.get("sector_fuels") is not None
        assert h_out.get("weather_drivers_merge") is not None


class TestWeatherScenario:
    def test_tobarra_map_default_assumed(self) -> None:
        ws = tobarra_20240802_default_scenario()
        assert ws.source == "scenario_assumed"
        assert ws.is_assumed is True
        assert ws.weather_scenario_assumed is True
        assert ws.wind_from_deg == 270.0
        assert ws.wind_10m_ms == pytest.approx(kmh_to_ms(21.0), rel=1e-3)
        assert ws.temp_c == 35.0
        assert ws.rh_pct == 10.0
        assert "not_aemet_station_observation" in ws.notes
        d = ws.to_dict()
        assert d["is_assumed"] is True

    def test_load_roundtrip(self, tmp_path: Path) -> None:
        ws = tobarra_20240802_default_scenario()
        p = tmp_path / "wx.json"
        p.write_text(json.dumps(ws.to_dict()), encoding="utf-8")
        loaded = load_weather_scenario(p)
        assert loaded.wind_10m_ms == pytest.approx(ws.wind_10m_ms)
        assert loaded.source == "scenario_assumed"
        assert loaded.is_assumed is True

    def test_observed_source_not_assumed(self, tmp_path: Path) -> None:
        p = tmp_path / "obs.json"
        p.write_text(
            json.dumps(
                {
                    "wind_10m_ms": 5.0,
                    "wind_from_deg": 250.0,
                    "dead_fmc_pct": 6.0,
                    "source": "observed",
                    "as_of": "2024-08-02T17:00:00",
                    "notes": ["station_X"],
                }
            ),
            encoding="utf-8",
        )
        ws = load_weather_scenario(p)
        assert ws.is_assumed is False
        assert ws.source == "observed"

    def test_resolve_none_without_wind(self) -> None:
        assert resolve_weather_for_stack() is None

    def test_resolve_does_not_invent_without_scenario(self) -> None:
        # no path, no map default, no wind → None (honest)
        r = resolve_weather_for_stack(
            weather_path=None,
            wind_10m_ms=None,
            wind_from_deg=None,
            use_tobarra_map_default=False,
        )
        assert r is None

    def test_physics_report_weather_audit(self) -> None:
        ws = WeatherScenario(
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            source="scenario_assumed",
            notes=["unit_test"],
        )
        rep = physics_prior_report(
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            weather_scenario=ws,
        )
        assert rep.get("weather_scenario_assumed") is True
        assert rep["drivers"]["weather_scenario"]["source"] == "scenario_assumed"

    def test_seeded_tobarra_file_if_present(self) -> None:
        p = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "fuel_stack"
            / "tobarra"
            / "weather_tobarra_20240802.json"
        )
        if not p.is_file():
            pytest.skip("seed weather file not present")
        ws = load_weather_scenario(p)
        assert ws.is_assumed is True
        assert ws.wind_from_deg == 270.0


class TestAbstainEdges:
    def test_spatial_missing_wind_abstains(self) -> None:
        grid = np.full((8, 8), "MED_GRASS", dtype=object)
        r = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=None,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            require_wind=True,
        )
        assert r.status == "abstained"
        assert "missing_wind" in r.reasons

    def test_all_unknown_abstains(self) -> None:
        grid = np.full((8, 8), "UNKNOWN", dtype=object)
        r = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=5.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
        )
        assert r.status == "abstained"
        assert "spatial_all_unknown" in r.reasons or "unknown_fuel_class" in r.reasons

    def test_all_unknown_with_fallback_still_abstains(self) -> None:
        """Issue 1: fallback must not produce estimated MED_GRASS with ROS=0."""
        grid = np.full((8, 8), "UNKNOWN", dtype=object)
        r = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=5.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            fallback_fuel_id="MED_GRASS",
        )
        assert r.status == "abstained"
        assert r.fuel_id == "UNKNOWN"
        assert r.ros_head_m_min is None
        assert "spatial_all_unknown" in r.reasons
        assert (r.drivers or {}).get("fallback_fuel_id_ignored") == "MED_GRASS"

    def test_head_unknown_substitutes_without_ros_fuel_desync(self) -> None:
        """Issue 2: head UNKNOWN, burnable rear/flank — no ROS swap desync."""
        h, w = 20, 20
        grid = np.empty((h, w), dtype=object)
        grid[:, : w // 2] = "MED_GRASS"  # west / rear of east head
        grid[:, w // 2 :] = "UNKNOWN"  # east / head
        r = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=6.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
            head_bearing_deg=90.0,
            fallback_fuel_id="MED_GRASS",
        )
        assert r.status == "estimated"
        assert r.ros_head_m_min is not None and r.ros_head_m_min > 0
        ids = (r.drivers or {}).get("sector_fuel_ids") or {}
        # audit: map_head stays UNKNOWN; ROS head fuel is substituted id
        assert ids.get("map_head") == "UNKNOWN"
        assert ids.get("head") == "MED_GRASS"
        assert r.fuel_id == "MED_GRASS"
        assert (r.drivers or {}).get("head_fuel_substitution")
        assert "head_fuel_substituted" in (r.reasons or [])

    def test_empty_fuel_grid_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            sector_fuel_summary_from_grid(
                np.array([]).reshape(0, 0), head_bearing_deg=90.0
            )

    def test_invalid_fuel_id_remapped(self) -> None:
        """Issue 3: garbage strings remapped via catalog check, not try/except."""
        grid = np.full((6, 6), "NOT_A_FUEL", dtype=object)
        summary = sector_fuel_summary_from_grid(
            grid, head_bearing_deg=90.0, dominant_fallback="MED_GRASS"
        )
        assert summary.head_fuel_id == "MED_GRASS"
        assert any("unknown_id_NOT_A_FUEL" in n for n in summary.notes)

    def test_missing_weather_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_weather_scenario(tmp_path / "no_such_weather.json")

    def test_preset_does_not_clobber_observed_assumed(self, tmp_path: Path) -> None:
        """Issue 4: --weather observed + --preset must keep is_assumed False."""
        # Mirror CLI logic: weather file first, then preset fills only missing fields
        p = tmp_path / "obs.json"
        p.write_text(
            json.dumps(
                {
                    "wind_10m_ms": 5.0,
                    "wind_from_deg": 250.0,
                    "dead_fmc_pct": 6.0,
                    "source": "observed",
                }
            ),
            encoding="utf-8",
        )
        ws = load_weather_scenario(p)
        assumed = bool(ws.is_assumed)
        weather_doc = ws.to_dict()
        # preset branch (as fixed): only set assumed when weather_doc is None
        preset = "tobarra_scenario"
        if preset == "tobarra_scenario":
            if weather_doc is None:
                assumed = True
            # else keep assumed from weather file
        assert assumed is False
        assert weather_doc["source"] == "observed"

    def test_physics_report_prior_raw_no_double_eval(self) -> None:
        """Issue 8: prior_raw reuse preserves sector drivers."""
        grid = np.full((12, 12), "MED_GRASS", dtype=object)
        raw = estimate_sector_ros_from_fuel_map(
            fuel_id_grid=grid,
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            wind_from_deg=270.0,
        )
        rep = physics_prior_report(
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,
            prior_raw=raw,
            observed_ros_m_min=5.71,
        )
        assert rep["status"] == "estimated"
        assert rep.get("drivers", {}).get("sector_fuel_mode") == "spatial_wedge_majority"

    def test_library_defaults_stamp_assumed_without_scenario(self) -> None:
        """Issue 7: no weather_scenario → weather_scenario_assumed stamped."""
        rep = physics_prior_report(
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
        )
        assert rep.get("weather_scenario_assumed") is True
        assert "library_wind_defaults_note" in (rep.get("drivers") or {})

    def test_observed_null_wind_does_not_keep_library_4_4(self) -> None:
        """Issue 9: source=observed + null wind must not silently use 4.4 as observed."""
        from wildfire_front.fuel.weather import merge_weather_drivers

        ws = WeatherScenario(
            wind_10m_ms=None,
            wind_from_deg=None,
            dead_fmc_pct=None,
            source="observed",
            notes=["incomplete_station"],
        )
        # Direct merge: wind cleared, not filled to 4.4
        m = merge_weather_drivers(
            ws, wind_10m_ms=4.4, wind_from_deg=270.0, dead_fmc_pct=7.0
        )
        assert m.wind_10m_ms is None
        assert "wind_10m_ms" in m.fields_missing_cleared
        # FMC may be filled → assumed True if any fill; wind still not invented
        assert m.wind_10m_ms is None

        h = hybrid_ros_prior(
            5.71,
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            weather_scenario=ws,
        )
        # Physics must not report observed-labeled 4.4 m/s
        phys_wind = ((h.get("physics") or {}).get("drivers") or {}).get("wind_10m_ms")
        assert phys_wind is None or phys_wind == 0.0 or h.get("physics", {}).get("status") == "abstained"
        assert (h.get("physics") or {}).get("status") == "abstained" or "missing_wind" in (
            (h.get("physics") or {}).get("reasons") or []
        )
        merge_audit = h.get("weather_drivers_merge") or {}
        assert merge_audit.get("wind_10m_ms") is None
        assert "wind_10m_ms" in (merge_audit.get("fields_missing_cleared") or [])
        # PR-α DoD: hybrid head remains obs-locked even when physics abstains
        assert h["status"] == "estimated_obs_only"
        assert h["sectors"]["head_m_min"] == pytest.approx(5.71, abs=1e-6)
        assert h["sectors"]["primary_m_min"] == pytest.approx(5.71, abs=1e-6)
        assert h["sectors"]["flank_m_min"] is not None

    def test_observed_partial_fmc_fill_stamps_assumed(self) -> None:
        """Issue 9: observed with wind but missing FMC → fill + assumed stamp."""
        from wildfire_front.fuel.weather import merge_weather_drivers

        ws = WeatherScenario(
            wind_10m_ms=5.0,
            wind_from_deg=250.0,
            dead_fmc_pct=None,
            source="observed",
        )
        m = merge_weather_drivers(ws, dead_fmc_pct=7.0)
        assert m.wind_10m_ms == pytest.approx(5.0)
        assert m.dead_fmc_pct == pytest.approx(7.0)
        assert "dead_fmc_pct" in m.fields_filled_from_defaults
        assert m.weather_scenario_assumed is True
        assert m.weather_partially_filled_from_defaults is True

        rep = physics_prior_report(
            fuel_id="MED_GRASS",
            wind_10m_ms=4.4,  # library default must not override scenario wind
            weather_scenario=ws,
        )
        assert rep.get("weather_scenario_assumed") is True
        assert (rep.get("drivers") or {}).get("weather_partially_filled_from_defaults") is True
        assert (rep.get("drivers") or {}).get("wind_10m_ms") == pytest.approx(5.0)

    def test_envelope_cli_incomplete_observed_plus_preset(self, tmp_path: Path) -> None:
        """Issue 11: build_hybrid_envelope resolve path — no 4.4 under assumed=False."""
        import importlib.util

        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "build_hybrid_envelope.py"
        )
        spec = importlib.util.spec_from_file_location("build_hybrid_envelope", script)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        p = tmp_path / "obs_incomplete.json"
        p.write_text(
            json.dumps(
                {
                    "wind_10m_ms": None,
                    "wind_from_deg": None,
                    "dead_fmc_pct": None,
                    "source": "observed",
                }
            ),
            encoding="utf-8",
        )
        # Probe of the honesty bug: incomplete observed + preset must not yield
        # wind=4.4 with weather_scenario_assumed=False
        _ws, merge = mod.resolve_envelope_cli_weather(
            weather_path=p,
            preset="tobarra_scenario",
            wind_ms=None,
            wind_from=None,
            fmc=None,
        )
        assert merge.wind_10m_ms is None
        assert "wind_10m_ms" in (merge.fields_missing_cleared or [])
        # Never: wind filled to 4.4 while claiming non-assumed without stamp
        if merge.wind_10m_ms == pytest.approx(4.4):
            assert merge.weather_scenario_assumed is True
        else:
            assert merge.wind_10m_ms is None

        # Pure preset still gets engineering 4.4 as assumed
        _ws2, merge2 = mod.resolve_envelope_cli_weather(
            weather_path=None,
            preset="tobarra_scenario",
            wind_ms=None,
            wind_from=None,
            fmc=None,
        )
        assert merge2.wind_10m_ms == pytest.approx(4.4)
        assert merge2.weather_scenario_assumed is True
