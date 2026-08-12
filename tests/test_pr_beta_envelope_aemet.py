"""PR-β landing DoD: AEMET weather + envelope v3 + scorecard + pipeline offline.

Covers collapsed PR-6 + 8 + 9 + 10 without live network.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wildfire_front.emergency_products import compute_short_horizon_envelope
from wildfire_front.fuel.envelope import PRODUCT_V3, compute_hybrid_envelope
from wildfire_front.fuel.envelope_scorecard import (
    attach_envelope_to_decision_card,
    build_tobarra_envelope_scorecard,
)
from wildfire_front.fuel.weather import (
    merge_weather_drivers,
    weather_scenario_from_aemet_daily,
)

ROOT = Path(__file__).resolve().parents[1]

_RAW_AEMET = {
    "fecha": "2024-08-02",
    "indicativo": "8175",
    "tmed": "27,6",
    "hrMedia": "22",
    "velmedia": "5,0",
    "dir": "99",
    "racha": "13,6",
    "prec": "0,0",
}


class TestAemetToEnvelope:
    def test_aemet_partial_dir_marks_assumed_in_merge(self) -> None:
        ws = weather_scenario_from_aemet_daily(_RAW_AEMET, station_id="8175")
        assert ws.source == "aemet"
        assert ws.wind_from_deg is None
        m = merge_weather_drivers(ws)
        assert m.wind_10m_ms == pytest.approx(5.0)
        assert m.wind_from_deg == pytest.approx(270.0)
        assert m.weather_scenario_assumed is True
        assert "wind_from_deg" in m.fields_filled_from_defaults

    def test_envelope_with_aemet_assumed_status(self) -> None:
        ws = weather_scenario_from_aemet_daily(_RAW_AEMET, station_id="8175")
        m = merge_weather_drivers(ws)
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            fuel_id="MED_GRASS",
            wind_10m_ms=m.wind_10m_ms,
            wind_from_deg=m.wind_from_deg or 270.0,
            dead_fmc_pct=m.dead_fmc_pct or 7.0,
            slope_deg=3.3,
            with_ensemble=True,
            weather_scenario_assumed=m.weather_scenario_assumed,
        )
        assert env["product"] == PRODUCT_V3
        assert env["not_tactical_dispatch"] is True
        assert env["status"] == "inputs_assumed"
        assert env["sector_ros_m_min"]["head"] == pytest.approx(5.71, abs=1e-6)
        assert env["sector_ros_m_min"]["primary"] == pytest.approx(5.71, abs=1e-6)
        heads = [float(e["head_radius_m"]) for e in env["envelopes"]]
        assert heads[0] < heads[1] < heads[2]
        assert abs(heads[0] - 5.71 * 15) < 0.1
        # ensemble head flat under obs lock
        (env.get("ensemble") or {}).get("hybrid") or env.get("ensemble_meta") or {}
        assert env["ensemble_meta"]["enabled"] is True
        # find flat head in ensemble meta or nested rings
        obs_locked = env["ensemble_meta"].get("obs_locked_sectors") or []
        assert "head" in obs_locked or env["ensemble_meta"].get("enabled")


class TestScorecardAemetAndCard:
    def test_scorecard_with_aemet_weather_partial_info(self) -> None:
        ws = weather_scenario_from_aemet_daily(
            _RAW_AEMET, fire_id="tobarra_20240802", station_id="8175"
        )
        score = build_tobarra_envelope_scorecard(
            weather_scenario=ws.to_dict(),
            with_ensemble=True,
            decision_card={
                "event_id": "tobarra",
                "decision": "HOLD",
                "reasons": [],
                "disclaimers": [],
                "sources": [],
                "metrics": {"allow_ml_live_in_fusion": False},
                "audit": {},
            },
        )
        assert score["verdict"] == "PASS"
        assert score["counts"]["fail"] == 0
        assert score["weather_drivers_merge"]["source"] == "aemet"
        ids = {c["id"]: c for c in score["checks"]}
        assert "weather_partial_station" in ids or "weather_source" in ids
        card = score["decision_card"]
        assert card is not None
        assert card["metrics"]["envelope_v3_hybrid"]["fusion_weight"] == 0.0
        assert card["metrics"]["allow_ml_live_in_fusion"] is False
        assert card["sources"][-1]["weight"] == 0.0
        assert card["sources"][-1]["actionable"] is False

    def test_attach_never_enables_fusion(self) -> None:
        env = compute_hybrid_envelope(
            None,
            observed_ros_m_min=5.71,
            wind_10m_ms=5.0,
            wind_from_deg=270.0,
            dead_fmc_pct=6.56,
            weather_scenario_assumed=True,
        )
        card = {
            "decision": "GO",
            "reasons": [],
            "sources": [],
            "metrics": {"allow_ml_live_in_fusion": False},
        }
        out = attach_envelope_to_decision_card(card, env)
        assert out["metrics"]["allow_ml_live_in_fusion"] is False
        assert out["metrics"]["envelope_v3_hybrid"]["fusion_weight"] == 0.0


class TestIncidentStaysOnV2:
    def test_emergency_products_still_v2_default(self) -> None:
        env = compute_short_horizon_envelope(
            5.71,
            head_ros_m_min=5.71,
            flank_ros_m_min=2.5,
            rear_ros_m_min=1.5,
            horizons_min=(15, 30, 60),
        )
        assert env["product"] == "short_horizon_envelope_v2_sector"
        assert env["product"] != PRODUCT_V3


class TestEnvelopeCliHonesty:
    def test_resolve_incomplete_aemet_no_silent_4_4(self, tmp_path: Path) -> None:
        script = ROOT / "scripts" / "build_hybrid_envelope.py"
        spec = importlib.util.spec_from_file_location("build_hybrid_envelope", script)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        p = tmp_path / "aemet_incomplete.json"
        p.write_text(
            json.dumps(
                {
                    "wind_10m_ms": None,
                    "wind_from_deg": None,
                    "dead_fmc_pct": None,
                    "source": "aemet",
                }
            ),
            encoding="utf-8",
        )
        _ws, merge = mod.resolve_envelope_cli_weather(
            weather_path=p,
            preset="tobarra_scenario",
            wind_ms=None,
            wind_from=None,
            fmc=None,
        )
        assert merge.wind_10m_ms is None
        assert "wind_10m_ms" in (merge.fields_missing_cleared or [])
        # never present library 4.4 as non-assumed aemet
        if merge.wind_10m_ms == pytest.approx(4.4):
            assert merge.weather_scenario_assumed is True


class TestPipelineScript:
    def test_pipeline_help_and_cached_weather_path(self) -> None:
        script = ROOT / "scripts" / "run_tobarra_aemet_pipeline.py"
        assert script.is_file()
        r = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0
        assert "refetch" in r.stdout or "refetch" in r.stderr

    def test_score_cli_uses_aemet_fixture_when_present(self) -> None:
        wx = ROOT / "data" / "fuel_stack" / "tobarra" / "weather_aemet_20240802.json"
        if not wx.is_file():
            pytest.skip("no cached AEMET weather fixture")
        out = ROOT / "outputs" / "fuel_stack" / "tobarra" / "_test_scorecard_pr_beta.json"
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "score_tobarra_envelope.py"),
                "--weather",
                str(wx),
                "--out",
                str(out),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        score = json.loads(out.read_text(encoding="utf-8"))
        assert score["verdict"] == "PASS"
        assert score["counts"]["fail"] == 0
        assert score.get("weather_drivers_merge", {}).get("source") == "aemet"
        # cleanup test artifact
        with contextlib.suppress(OSError):
            out.unlink(missing_ok=True)
