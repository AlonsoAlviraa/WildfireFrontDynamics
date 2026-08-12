"""Tests for ROS calibration recipe fit/apply (engineering k factors)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wildfire_front.fuel.calibration import (
    CalibrationRefusedError,
    apply_calibration,
    fit_sector_scale_factors,
    load_recipe,
    residual_metrics,
    save_recipe,
)
from wildfire_front.fuel.hybrid import hybrid_ros_prior
from wildfire_front.fuel.rothermel_lite import (
    estimate_sector_ros_physics,
    physics_prior_report,
)


@pytest.fixture
def raw_prior():
    return estimate_sector_ros_physics(
        fuel="MED_MAQUIS_LOW",
        wind_10m_ms=4.4,
        slope_deg=5.0,
        dead_fmc_pct=7.0,
        wind_from_deg=270.0,
    )


class TestFitApply:
    def test_per_sector_without_targets_stamps_mode_effective(self, raw_prior) -> None:
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            mode="per_sector",
            dem_binding={"dem_source": "synthetic"},
        )
        assert recipe.mode == "uniform_from_head"
        assert recipe.metrics.get("mode_requested") == "per_sector"
        assert recipe.metrics.get("mode_effective") == "uniform_from_head"
        assert any("mode_effective=uniform_from_head" in n for n in recipe.honesty_notes)

    def test_refuse_dem_source_unspecified(self, raw_prior) -> None:
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "copernicus_glo30"},
        )
        with pytest.raises(CalibrationRefusedError) as ei:
            apply_calibration(raw_prior, recipe, current_dem_source=None)
        assert ei.value.status == "dem_source_unspecified"
        # force still allowed
        cal = apply_calibration(raw_prior, recipe, current_dem_source=None, force=True)
        assert cal.calibration_applied is True

    def test_fit_uniform_to_obs(self, raw_prior) -> None:
        assert raw_prior.status == "estimated"
        assert raw_prior.ros_head_m_min and raw_prior.ros_head_m_min > 0
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            vp_anchor_m_min=7.0,
            vp_status="confirmed",
            dem_binding={"dem_source": "synthetic"},
        )
        assert recipe.mode == "uniform_from_head"
        assert "k_head" in recipe.factors
        k = recipe.factors["k_head"]
        assert 0.05 <= k <= 5.0
        assert recipe.metrics.get("kpi_cal_engineering_ok") is True
        # raw gap still reported honestly
        assert recipe.metrics.get("raw_rel_err_head_vs_obs", 0) > 0.5
        assert recipe.metrics.get("kpi_raw_rel_err_lt_0_5") is False

    def test_apply_scales_head(self, raw_prior) -> None:
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "synthetic"},
        )
        cal = apply_calibration(raw_prior, recipe, current_dem_source="synthetic")
        assert cal.calibration_applied is True
        assert cal.product_claim == "physics_potential_calibrated"
        assert cal.ros_head_raw_m_min == raw_prior.ros_head_m_min
        assert cal.ros_head_m_min is not None
        assert abs(cal.ros_head_m_min - 5.71) < 0.05
        assert cal.no_tactical_dispatch is True

    def test_refuse_extreme_k(self, raw_prior) -> None:
        with pytest.raises(CalibrationRefusedError) as ei:
            fit_sector_scale_factors(
                raw_prior,
                observed_ros_head_m_min=0.001,  # tiny → huge k inverse actually small k
            )
        # tiny target / large raw → k very small < 0.05
        assert ei.value.status == "calibration_refused_extreme_k"

    def test_refuse_dem_mismatch(self, raw_prior) -> None:
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "copernicus_glo30"},
        )
        with pytest.raises(CalibrationRefusedError) as ei:
            apply_calibration(raw_prior, recipe, current_dem_source="synthetic")
        assert ei.value.status == "dem_source_mismatch"
        # force ok
        cal = apply_calibration(raw_prior, recipe, current_dem_source="synthetic", force=True)
        assert cal.calibration_applied is True

    def test_save_load_recipe(self, raw_prior, tmp_path: Path) -> None:
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "synthetic"},
        )
        p = save_recipe(recipe, tmp_path / "recipe.json")
        loaded = load_recipe(p)
        assert loaded.recipe_id == recipe.recipe_id
        assert loaded.factors["k_head"] == recipe.factors["k_head"]


class TestPhysicsReportHonesty:
    def test_calibration_key_always_raw(self, raw_prior) -> None:
        rep = physics_prior_report(
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            observed_ros_m_min=5.71,
            vp_anchor_m_min=7.0,
            fit_calibration=True,
            dem_source="synthetic",
            dem_binding={"dem_source": "synthetic"},
        )
        assert rep["calibration"] is not None
        # raw ratio ~2.x not ~1.0
        ratio = rep["calibration"]["ratio_physics_head_to_obs"]
        assert ratio > 1.5
        assert rep["calibration"].get("basis") == "raw_pre_k"
        assert rep["product_claim"] == "physics_potential_calibrated"
        assert rep["calibration_recipe"] is not None
        assert abs(rep["ros_head_m_min"] - 5.71) < 0.05
        assert rep["physics_raw"]["ros_head_m_min"] == pytest.approx(
            raw_prior.ros_head_m_min, rel=1e-3
        )


class TestHybridStability:
    def test_sectors_stable_with_without_recipe(self, raw_prior) -> None:
        h0 = hybrid_ros_prior(
            5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
        )
        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "synthetic"},
        )
        h1 = hybrid_ros_prior(
            5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            slope_deg=5.0,
            dead_fmc_pct=7.0,
            calibration_recipe=recipe,
            dem_source="synthetic",
        )
        assert h0["sectors"]["head_m_min"] == pytest.approx(h1["sectors"]["head_m_min"], abs=1e-6)
        assert h1["physics"]["calibration_applied"] is True
        assert h1["physics_raw"] is not None


class TestResidualMetrics:
    def test_split_raw_cal(self) -> None:
        m = residual_metrics(
            ros_head_raw=12.83,
            ros_head_cal=5.71,
            observed_ros_head_m_min=5.71,
            vp_anchor_m_min=7.0,
        )
        assert m["kpi_raw_rel_err_lt_0_5"] is False
        assert m["kpi_cal_engineering_ok"] is True


class TestCliCalibrationRefuse:
    def test_cli_exit_4_on_extreme_k_no_recipe_write(self, tmp_path: Path) -> None:
        """PR-5 DoD: CalibrationRefusedError → exit 4; recipe file not written."""
        import subprocess
        import sys

        out = tmp_path / "stack_out"
        out.mkdir()
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "build_fuel_terrain_stack.py"),
            "--fire",
            "tobarra",
            "--with-physics",
            "--fit-calibration",
            "--obs-ros",
            "0.001",  # → extreme k refuse
            "--allow-synthetic",
            "--allow-fuel-synthetic",
            "--n",
            "12",
            "--out",
            str(out),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
            timeout=120,
        )
        assert proc.returncode == 4, (
            f"expected exit 4, got {proc.returncode}\n"
            f"stdout={proc.stdout[-500:]}\nstderr={proc.stderr[-500:]}"
        )
        recipe = out / "ros_calibration_recipe.json"
        assert not recipe.is_file(), "refused calibration must not write recipe"

    def test_cli_exit_4_on_recipe_dem_mismatch(self, raw_prior, tmp_path: Path) -> None:
        """Bound recipe expects glo30; isolated empty cache forces synthetic DEM → dem mismatch.

        Must not depend on workspace ``data/dem/tobarra`` cache (would match glo30 and
        exit 4 only via incidental fuel_id_mismatch). Empty ``--cache-dir`` isolates.
        """
        import subprocess
        import sys

        recipe = fit_sector_scale_factors(
            raw_prior,
            observed_ros_head_m_min=5.71,
            dem_binding={"dem_source": "copernicus_glo30"},
        )
        recipe_path = save_recipe(recipe, tmp_path / "bound_recipe.json")
        out = tmp_path / "stack_out"
        out.mkdir()
        # Empty dirs: no local DEM / fuel cache → synthetic dem_source under --allow-synthetic
        dem_cache = tmp_path / "empty_dem_cache"
        fuel_cache = tmp_path / "empty_fuel_cache"
        dem_cache.mkdir()
        fuel_cache.mkdir()
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "build_fuel_terrain_stack.py"),
            "--fire",
            "tobarra",
            "--with-physics",
            "--calibration-recipe",
            str(recipe_path),
            "--allow-synthetic",
            "--allow-fuel-synthetic",
            "--cache-dir",
            str(dem_cache),
            "--fuel-cache-dir",
            str(fuel_cache),
            "--no-spatial-fuels",  # single fuel; refuse must be dem not fuel-first noise
            "--n",
            "12",
            "--out",
            str(out),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
            timeout=120,
        )
        assert proc.returncode == 4, (
            f"expected exit 4, got {proc.returncode}\n"
            f"stdout={proc.stdout[-500:]}\nstderr={proc.stderr[-500:]}"
        )
        combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
        assert "dem_source_mismatch" in combined, (
            "expected dem_source_mismatch refuse (not fuel_id_mismatch from cache DEM); "
            f"stderr={proc.stderr[-800:]}"
        )
        # CLI only writes recipe on successful --fit-calibration; refuse path must not
        assert not (out / "ros_calibration_recipe.json").is_file()
