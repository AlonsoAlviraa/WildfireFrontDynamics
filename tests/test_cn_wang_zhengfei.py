"""Tests for Chinese Wang Zhengfei / Mao ROS prior."""

from __future__ import annotations

import math

from wildfire_front.cn_cellular_ca import run_ca
from wildfire_front.cn_wang_zhengfei import (
    hybrid_polar_to_geojson_ring,
    hybrid_ros_prior,
    k_slope,
    k_wind,
    physics_prior_report,
    polar_ros_ring,
    r0_from_weather,
    ros_mao_8_directions,
    ros_wang_zhengfei,
)


def test_r0_positive():
    r0 = r0_from_weather(30, 3, 30)
    assert r0 > 0


def test_wind_boosts_downwind():
    r0 = 1.0
    down = ros_wang_zhengfei(r0, wind_ms=5.0, wind_to_spread_deg=0.0)
    upwind = ros_wang_zhengfei(r0, wind_ms=5.0, wind_to_spread_deg=180.0)
    assert down > upwind


def test_upslope_faster_than_downslope():
    r0 = 1.0
    up = ros_wang_zhengfei(r0, slope_deg=20.0, upslope=True)
    down = ros_wang_zhengfei(r0, slope_deg=20.0, upslope=False)
    assert up > down


def test_k_wind_at_zero():
    assert abs(k_wind(0.0, 0.0) - 1.0) < 1e-9


def test_k_slope_flat():
    assert abs(k_slope(0.0, upslope=True) - 1.0) < 1e-6


def test_mao_8_keys():
    d = ros_mao_8_directions(1.0, wind_ms=3.0, wind_from_deg=270.0, slope_deg=10.0)
    for k in ("N", "E", "S", "W", "head_wind"):
        assert k in d
        assert d[k] >= 0


def test_polar_ring_length():
    ring = polar_ros_ring(1.0, wind_ms=2.0, step_deg=30.0)
    assert len(ring) == 12


def test_prior_vs_obs_ratio():
    rep = physics_prior_report(observed_ros_m_min=5.71, wind_force=3)
    assert "ratio_obs_over_r0" in rep
    assert math.isfinite(rep["ratio_obs_over_r0"])


def test_ca_runs():
    out = run_ca(steps=10, rows=20, cols=20, seed=1)
    assert out["steps_run"] >= 1
    assert out["final"] is not None


def test_hybrid_ros_prior_tobarra_path():
    """Real hybrid path: observed magnitude × Wang/Mao shape (Tobarra-like)."""
    h = hybrid_ros_prior(5.71, wind_force=3.0, wind_from_deg=270.0, slope_deg=4.0)
    assert h["status"] == "ok"
    assert h["model"] == "wang_mao_hybrid_obs_magnitude"
    assert math.isfinite(h["scale_factor"]) and h["scale_factor"] > 0
    assert math.isfinite(h["ros_head_m_min"]) and h["ros_head_m_min"] > 0
    assert math.isfinite(h["ros_rear_m_min"]) and h["ros_rear_m_min"] >= 0
    assert h["ros_head_m_min"] >= h["ros_rear_m_min"]
    assert len(h["polar_calibrated"]) >= 12
    assert "15" in h["envelope_radii_m"]
    assert len(h["envelope_radii_m"]["15"]) == len(h["polar_calibrated"])
    # Mean-scale mode: mean of calibrated ≈ observed
    mean_c = sum(r for _, r in h["polar_calibrated"]) / len(h["polar_calibrated"])
    assert abs(mean_c - 5.71) < 0.05


def test_hybrid_polar_geojson_nonempty():
    h = hybrid_ros_prior(5.71)
    gj = hybrid_polar_to_geojson_ring(h, (500000.0, 4300000.0), horizon_min=15.0)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 1
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    assert len(ring) >= 13  # closed polygon
    assert gj["features"][0]["properties"]["not_dispatch"] is True


def test_hybrid_cli_entry(tmp_path, monkeypatch):
    """Drive shipped CLI entry point end-to-end."""
    import json
    import runpy
    import sys
    from pathlib import Path

    out = tmp_path / "hybrid.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_cn_physics_prior.py",
            "--obs-ros",
            "5.71",
            "--out",
            str(out),
            "--geojson-origin",
            "500000,4300000",
        ],
    )
    # Run as script from repo root path (SystemExit 0 is success from CLI)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_cn_physics_prior.py"
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        assert e.code in (0, None), f"CLI failed with {e.code}"
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    assert data["ros_head_m_min"] > data["ros_rear_m_min"]
    assert data["scale_factor"] > 0
    gj_path = out.with_name(out.stem + "_polar15.geojson")
    assert gj_path.is_file()
    gj = json.loads(gj_path.read_text(encoding="utf-8"))
    assert len(gj["features"][0]["geometry"]["coordinates"][0]) >= 13
