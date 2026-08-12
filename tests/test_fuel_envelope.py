"""Tests for hybrid short-horizon envelope v3."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.fuel.envelope import (
    PRODUCT_V3,
    compute_hybrid_envelope,
    ellipse_polar_ring,
    envelope_decision_reasons,
    extract_sector_ros,
    obs_only_sector_ros,
    radii_from_sector_ros,
    radius_at_bearing,
    write_hybrid_envelope_json,
)
from wildfire_front.fuel.hybrid import hybrid_ros_prior


class TestPureMath:
    def test_obs_only_recipe(self) -> None:
        s = obs_only_sector_ros(5.71)
        assert s["head"] == 5.71
        assert abs(s["flank"] - 2.855) < 1e-9
        assert abs(s["rear"] - 1.713) < 1e-9

    def test_radii_15_30_60(self) -> None:
        envs = radii_from_sector_ros(5.71, 2.63, 1.65, primary=5.71)
        assert len(envs) == 3
        assert envs[0]["horizon_min"] == 15
        assert envs[0]["head_radius_m"] == round(5.71 * 15, 2)
        assert envs[2]["horizon_min"] == 60
        assert envs[0]["head_radius_m"] > envs[0]["flank_radius_m"] >= envs[0]["rear_radius_m"]

    def test_cap_40(self) -> None:
        envs = radii_from_sector_ros(100.0, 50.0, 10.0)
        assert envs[0]["head_ros_m_min"] == 40.0
        assert envs[0]["head_radius_m"] == round(40.0 * 15, 2)

    def test_radius_at_bearing_edges(self) -> None:
        assert abs(radius_at_bearing(0.0, 10.0, 5.0, 2.0) - 10.0) < 1e-9
        assert abs(radius_at_bearing(90.0, 10.0, 5.0, 2.0) - 5.0) < 1e-9
        assert abs(radius_at_bearing(180.0, 10.0, 5.0, 2.0) - 2.0) < 1e-9
        assert abs(radius_at_bearing(-90.0, 10.0, 5.0, 2.0) - 5.0) < 1e-9

    def test_ellipse_ring_closed(self) -> None:
        ring = ellipse_polar_ring(0.0, 0.0, 100.0, 40.0, 20.0, 90.0, n=36)
        assert len(ring) == 37
        assert ring[0] == ring[-1]


class TestExtractSectors:
    def test_null_hybrid_repairs_from_obs(self) -> None:
        hybrid = {
            "status": "estimated_obs_only",
            "sectors": {
                "head_m_min": None,
                "flank_m_min": None,
                "rear_m_min": None,
                "primary_m_min": None,
            },
        }
        sec, reasons = extract_sector_ros(hybrid, observed_ros_m_min=5.71)
        assert sec is not None
        assert sec["head"] == 5.71
        assert "hybrid_sectors_null_obs_only" in reasons

    def test_no_obs_null_abstains(self) -> None:
        sec, reasons = extract_sector_ros(
            {"sectors": {"head_m_min": None}}, observed_ros_m_min=None
        )
        assert sec is None


class TestComputeEnvelope:
    def test_from_hybrid_with_obs(self) -> None:
        hybrid = hybrid_ros_prior(
            5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            slope_deg=3.3,
            dead_fmc_pct=7.0,
        )
        env = compute_hybrid_envelope(
            hybrid,
            observed_ros_m_min=5.71,
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            slope_deg=3.3,
            fire_id="tobarra_20240802",
            head_bearing_deg=90.0,
        )
        assert env["product"] == PRODUCT_V3
        assert env["status"] in ("ok", "inputs_assumed")
        assert env["not_tactical_dispatch"] is True
        assert len(env["envelopes"]) == 3
        h15 = env["envelopes"][0]
        assert abs(h15["head_radius_m"] - round(5.71 * 15, 2)) < 0.05
        assert env["sector_ros_m_min"]["head"] == pytest.approx(5.71, abs=0.05)

    def test_ensemble_flat_head_with_obs(self) -> None:
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            fuel_id="MED_MAQUIS_LOW",
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            slope_deg=3.3,
            dead_fmc_pct=7.0,
            with_ensemble=True,
            head_bearing_deg=90.0,
        )
        assert env["ensemble_meta"]["enabled"] is True
        ens = env["envelopes"][0]["ensemble"]
        head = ens["head_radius_m"]
        # flat when obs locks head
        assert abs(head["p10"] - head["p90"]) < 1e-6
        assert "head" in env["ensemble_meta"].get("obs_locked_sectors", [])
        # physics_only present and labeled
        epo = env["envelopes"][0]["ensemble_physics_only"]
        assert epo.get("not_product_p50") is True
        ph = epo["head_radius_m"]
        assert ph["p90"] >= ph["p10"]

    def test_ensemble_disabled_without_weather(self) -> None:
        hybrid = {
            "status": "estimated",
            "alpha_obs": 0.8,
            "sectors": {
                "head_m_min": 5.71,
                "flank_m_min": 2.8,
                "rear_m_min": 1.7,
                "primary_m_min": 5.71,
            },
            "physics": {"drivers": {}},
        }
        env = compute_hybrid_envelope(
            hybrid,
            observed_ros_m_min=5.71,
            with_ensemble=True,
            # no wind/fmc kwargs
        )
        assert env["status"] in ("ok", "inputs_assumed")
        assert env["ensemble_meta"]["enabled"] is False
        assert env["ensemble_meta"]["reason"] == "ensemble_missing_weather_inputs"
        assert "ensemble" not in env["envelopes"][0]

    def test_abstain_no_inputs(self) -> None:
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=None,
            wind_10m_ms=None,
            fuel_id="UNKNOWN",
        )
        assert env["status"] == "abstained"
        assert env["envelopes"] == []

    def test_write_json(self, tmp_path: Path) -> None:
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            slope_deg=3.0,
        )
        p = tmp_path / "env.json"
        write_hybrid_envelope_json(env, p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["product"] == PRODUCT_V3

    def test_decision_reasons(self) -> None:
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            with_ensemble=True,
        )
        reasons = envelope_decision_reasons(env)
        assert "not_tactical_dispatch" in reasons
        assert any("envelope" in r or "alpha" in r or "locked" in r for r in reasons)


class TestGeojson:
    def test_polar_geojson_features(self) -> None:
        from wildfire_front.fuel.envelope import hybrid_envelope_to_geojson

        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            wind_10m_ms=4.4,
            wind_from_deg=270.0,
            dead_fmc_pct=7.0,
            head_bearing_deg=90.0,
            origin_xy=(500000.0, 4270000.0),
            origin_source="cli",
        )
        gj = hybrid_envelope_to_geojson(env, center_xy=(500000.0, 4270000.0), include_polar=True)
        assert gj["properties"]["status"] in ("ok", "inputs_assumed")
        assert gj["properties"]["n_features"] > 0
        # closed rings
        for feat in gj["features"]:
            coords = feat["geometry"]["coordinates"][0]
            assert coords[0] == coords[-1]
            assert feat["properties"]["not_tactical_dispatch"] is True
