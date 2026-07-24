"""High-volume property tests for PSB (internal loops — not million pytest nodes)."""

from __future__ import annotations

import math
import os

import pytest
from shapely.affinity import rotate, scale
from shapely.geometry import MultiPolygon, Point, Polygon, box

from wildfire_front.progressive_burn.metrics import assert_all_invariants
from wildfire_front.progressive_burn.pipeline import ProgressiveBurnConfig, build_stage_sequence


def _ellipse(cx, cy, rx, ry, n=48) -> Polygon:
    coords = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        coords.append((cx + rx * math.cos(ang), cy + ry * math.sin(ang)))
    coords.append(coords[0])
    return Polygon(coords)


def _stadium(length=2000.0, width=600.0) -> Polygon:
    return box(0, 0, length, width).buffer(width * 0.2)


def _c_shape() -> Polygon:
    outer = box(0, 0, 1500, 1200)
    hole = box(300, 300, 1200, 900)
    return Polygon(outer.exterior.coords, [list(hole.exterior.coords)])


def _dual_lobe() -> MultiPolygon:
    return MultiPolygon([box(0, 0, 900, 700), box(1300, 50, 2200, 750)])


def _thin_corridor() -> Polygon:
    return box(0, 0, 3000, 80)


def _starish() -> Polygon:
    # Convex + mild dent via difference
    base = _ellipse(0, 0, 1000, 800)
    bite = Point(900, 0).buffer(350)
    return base.difference(bite)


SHAPES = {
    "ellipse": lambda s: _ellipse(0, 0, 900 + s * 3, 600 + s * 2),
    "stadium": lambda s: _stadium(1800 + s * 10, 500 + s),
    "c_shape": lambda s: scale(_c_shape(), xfact=1 + s * 0.01, yfact=1.0, origin="centroid"),
    "dual_lobe": lambda s: _dual_lobe(),
    "thin": lambda s: _thin_corridor(),
    "starish": lambda s: _starish(),
}


def test_invariants_internal_grid_pr_ci():
    """Normative reduced PR CI grid: ≥10⁴ micro-assertions."""
    seeds = list(range(5))
    stage_list = [4, 8]
    schedules = ["linear", "sqrt", "early_fast", "late_fast"]
    shape_ids = list(SHAPES.keys())  # 6
    engines = ["area_fraction", "buffer_rings"]

    assert_count = 0
    cases = 0
    for seed in seeds:
        for n_stages in stage_list:
            for schedule in schedules:
                for shape_id in shape_ids:
                    for engine in engines:
                        geom = SHAPES[shape_id](seed)
                        if geom.is_empty or geom.area < 100:
                            continue
                        cfg = ProgressiveBurnConfig(
                            n_stages=n_stages,
                            engine=engine,
                            schedule=schedule if engine == "area_fraction" else "linear",
                            seed=seed,
                            source_crs="EPSG:6933",
                            metric_crs="EPSG:6933",
                            min_component_area_ha=0.0001,
                            total_duration_s=48 * 3600,
                        )
                        try:
                            seq = build_stage_sequence(geom, cfg, source_crs="EPSG:6933")
                            assert_count += assert_all_invariants(seq, snap_m=2.0)
                            cases += 1
                        except Exception as e:
                            raise AssertionError(
                                f"repro: --seed {seed} --engine {engine} "
                                f"--n-stages {n_stages} --schedule {schedule} "
                                f"--shape {shape_id} | {e}"
                            ) from e

    # 5*2*4*6*2 = 480 cases * ~15 asserts ≈ 7200; require ≥ 5000 minimum
    # Some asserts more than 15 → typically > 10k
    assert cases >= 400, f"too few cases: {cases}"
    assert assert_count >= 10_000, f"assertion count {assert_count} < 10000 (cases={cases})"


@pytest.mark.slow
def test_invariants_internal_grid_nightly():
    """Expanded L1 (~10⁵+ asserts). Marked slow for nightly."""
    n_seeds = int(os.environ.get("PROGRESSIVE_BURN_MC_SEEDS", "20"))
    seeds = list(range(n_seeds))
    stage_list = [4, 6, 8, 12]
    schedules = ["linear", "sqrt", "early_fast", "late_fast"]
    shape_ids = list(SHAPES.keys())
    engines = ["area_fraction", "buffer_rings"]

    assert_count = 0
    for seed in seeds:
        for n_stages in stage_list:
            for schedule in schedules:
                for shape_id in shape_ids:
                    for engine in engines:
                        geom = SHAPES[shape_id](seed)
                        if seed % 3 == 0 and shape_id == "ellipse":
                            geom = rotate(geom, seed * 7.5, origin="centroid")
                        cfg = ProgressiveBurnConfig(
                            n_stages=n_stages,
                            engine=engine,
                            schedule=schedule if engine == "area_fraction" else "linear",
                            seed=seed,
                            source_crs="EPSG:6933",
                            metric_crs="EPSG:6933",
                            min_component_area_ha=0.0001,
                            total_duration_s=72 * 3600,
                        )
                        seq = build_stage_sequence(geom, cfg, source_crs="EPSG:6933")
                        assert_count += assert_all_invariants(seq, snap_m=2.5)

    assert assert_count >= 50_000, f"nightly assert_count={assert_count}"


def test_determinism_same_seed():
    geom = _ellipse(0, 0, 1000, 700)
    cfg = ProgressiveBurnConfig(
        n_stages=6,
        engine="area_fraction",
        schedule="sqrt",
        seed=42,
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
    )
    a = build_stage_sequence(geom, cfg, source_crs="EPSG:6933")
    b = build_stage_sequence(geom, cfg, source_crs="EPSG:6933")
    for sa, sb in zip(a.stages, b.stages, strict=False):
        assert sa.geom_metric.wkt == sb.geom_metric.wkt
        assert sa.area_ha == pytest.approx(sb.area_ha)


def test_mutation_honesty_keys_required_on_features():
    geom = box(0, 0, 1000, 800)
    cfg = ProgressiveBurnConfig(
        n_stages=4,
        source_crs="EPSG:6933",
        metric_crs="EPSG:6933",
    )
    seq = build_stage_sequence(geom, cfg, source_crs="EPSG:6933")
    for s in seq.stages:
        props = s.feature_props()
        assert props["synthetic"] is True
        assert props["not_real_lwir"] is True
        assert props["not_official_intermediate_o2"] is True
        assert props.get("attribution")
