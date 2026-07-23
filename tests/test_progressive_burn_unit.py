"""L0 unit tests for Progressive Synthetic Burn."""

from __future__ import annotations

import math

import pytest
from shapely.geometry import MultiPolygon, Point, box

from wildfire_front.progressive_burn.engines import fraction_band_ok
from wildfire_front.progressive_burn.geometry import (
    area_ha,
    nested_within,
    safe_homothety_center,
)
from wildfire_front.progressive_burn.metrics import assert_all_invariants, evaluate_invariants
from wildfire_front.progressive_burn.pipeline import ProgressiveBurnConfig, build_stage_sequence
from wildfire_front.progressive_burn.schedules import fraction_schedule, validate_n_stages
from wildfire_front.progressive_burn.schemas import (
    ATTRIBUTION_REDIAM,
    HONESTY_LIMITATIONS,
    N_STAGES_MAX,
    N_STAGES_MIN,
    REQUIRED_STAGE_PROPS,
)
from wildfire_front.progressive_burn.to_observations import (
    run_psb_front_dynamics,
    stages_to_observations,
    wrap_sector_ros_synthetic,
)
from wildfire_front.scientific_ops import MAX_PLAUSIBLE_SPEED_M_MIN


def _circle_poly(cx=0.0, cy=0.0, r=1000.0, n=64):
    # Approximate circle as polygon in metric space
    coords = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        coords.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    coords.append(coords[0])
    from shapely.geometry import Polygon

    return Polygon(coords)


def test_n_stages_validation():
    assert validate_n_stages(12) == 12
    with pytest.raises(ValueError):
        validate_n_stages(2)
    with pytest.raises(ValueError):
        validate_n_stages(N_STAGES_MAX + 1)
    with pytest.raises(ValueError):
        validate_n_stages(N_STAGES_MIN - 1)


def test_schedules_end_at_one_and_increasing():
    for name in ("linear", "sqrt", "early_fast", "late_fast", "logistic"):
        fr = fraction_schedule(name, 12)
        assert fr[-1] == 1.0
        assert all(fr[i] <= fr[i + 1] + 1e-12 for i in range(len(fr) - 1))
        assert fr[0] > 0


def test_early_fast_power_half():
    fr = fraction_schedule("early_fast", 4)
    # ((i+1)/4)^0.5
    assert abs(fr[0] - (0.25 ** 0.5)) < 1e-9
    assert abs(fr[1] - (0.5 ** 0.5)) < 1e-9


def test_honesty_constants():
    assert "not_real_lwir" in HONESTY_LIMITATIONS
    assert "no_tactical_vp" in HONESTY_LIMITATIONS
    assert "attribution" in REQUIRED_STAGE_PROPS
    assert "REDIAM" in ATTRIBUTION_REDIAM
    assert MAX_PLAUSIBLE_SPEED_M_MIN == 60.0


def test_safe_homothety_center_inside_multipolygon():
    # Two lobes; multipolygon centroid may fall outside
    a = box(0, 0, 10, 10)
    b = box(100, 0, 110, 10)
    mp = MultiPolygon([a, b])
    cx, cy = safe_homothety_center(mp)
    assert mp.contains(Point(cx, cy)) or mp.covers(Point(cx, cy))
    # centroid of multipolygon is roughly mid-gap — outside
    c = mp.centroid
    assert not mp.contains(c)


def test_area_fraction_circle_terminal_identity():
    poly = _circle_poly(r=500.0)
    # source_crs = metric (identity) via EPSG:6933 pretends coords are already metric
    cfg = ProgressiveBurnConfig(
        n_stages=6,
        engine="area_fraction",
        schedule="linear",
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
        seed=1,
    )
    seq = build_stage_sequence(poly, cfg, source_crs="EPSG:6933")
    assert seq.stages[-1].geom_metric.wkt == seq.final_metric.wkt
    assert seq.stages[-1].area_fraction_actual == pytest.approx(1.0)
    n = assert_all_invariants(seq)
    assert n >= 10


def test_buffer_rings_nested():
    poly = box(0, 0, 2000, 1000)
    cfg = ProgressiveBurnConfig(
        n_stages=5,
        engine="buffer_rings",
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
    )
    seq = build_stage_sequence(poly, cfg, source_crs="EPSG:6933")
    for i in range(seq.n_stages - 1):
        assert nested_within(seq.stages[i].geom_metric, seq.stages[i + 1].geom_metric)
    assert seq.stages[-1].geom_metric.wkt == seq.final_metric.wkt


def test_dual_lobe_multipolygon_mode_a():
    a = box(0, 0, 800, 600)
    b = box(1200, 0, 2000, 600)
    mp = MultiPolygon([a, b])
    cfg = ProgressiveBurnConfig(
        n_stages=8,
        engine="area_fraction",
        schedule="sqrt",
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
        min_component_area_ha=0.001,
    )
    seq = build_stage_sequence(mp, cfg, source_crs="EPSG:6933")
    assert seq.final_n_parts == 2
    assert_all_invariants(seq)
    m = evaluate_invariants(seq)
    assert m["verdict"] in ("GO_PROGRESSIVE_SYNTHETIC", "PARTIAL")
    assert m["vp_tactical"] is None


def test_fraction_band_helper():
    assert fraction_band_ok(0.10, 0.10)
    assert fraction_band_ok(0.12, 0.10)  # within 0.02 abs
    assert not fraction_band_ok(0.50, 0.10)


def test_to_observations_and_front_dynamics():
    poly = _circle_poly(r=800.0)
    cfg = ProgressiveBurnConfig(
        n_stages=4,
        engine="area_fraction",
        schedule="linear",
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
        total_duration_s=24 * 3600,
    )
    seq = build_stage_sequence(poly, cfg, source_crs="EPSG:6933")
    obs = stages_to_observations(seq)
    assert len(obs) >= 2
    assert all(o.coordinate_system == "projected_metric" for o in obs)
    assert all(o.resolution_m and o.resolution_m > 0 for o in obs)
    fd = run_psb_front_dynamics(seq)
    assert fd["vp_tactical"] is None
    assert fd["enable_coreg"] is False
    for pair in fd.get("pairs") or []:
        assert pair["pair_quality"] != "A"
        assert pair["primary_method"] in (
            "area_isotropic",
            "equiv_radius",
            "abstained",
        )


def test_sector_ros_wrap():
    sector = {"method": "bulk_ros_quartile_split", "head": 1.0}
    w = wrap_sector_ros_synthetic(sector)
    assert w["method"] == "bulk_ros_quartile_split_synthetic"
    assert w["synthetic"] is True
    assert w["not_official_perimeter"] is True


def test_empty_geom_errors():
    from shapely.geometry import Polygon

    with pytest.raises(ValueError):
        build_stage_sequence(
            Polygon(),
            ProgressiveBurnConfig(source_crs="EPSG:6933", metric_crs="EPSG:6933"),
            source_crs="EPSG:6933",
        )


def test_ops_cap_constant_aligned():
    assert MAX_PLAUSIBLE_SPEED_M_MIN == 60.0
