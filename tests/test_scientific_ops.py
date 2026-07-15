"""Tests for observatory-grade scientific operators."""

from __future__ import annotations

import numpy as np

from wildfire_front.scientific_ops import (
    clean_binary_mask,
    filter_components_main_front,
    quality_grade,
)


def test_clean_binary_mask_drops_flecks_keeps_main() -> None:
    mask = np.zeros((128, 128), dtype=np.uint8)
    mask[40:80, 40:80] = 1  # main blob
    mask[5, 5] = 1
    mask[6, 7] = 1
    mask[100, 100] = 1
    cleaned = clean_binary_mask(
        mask,
        min_component_pixels=50,
        morph_close_pixels=1,
        max_components=2,
        min_area_fraction=0.01,
    )
    assert cleaned[50, 50] == 1
    assert cleaned[5, 5] == 0
    assert int(cleaned.sum()) >= 50


def test_filter_components_main_front() -> None:
    big = tuple((float(x), float(y)) for x, y in [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    small = tuple((float(x), float(y)) for x, y in [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    kept = filter_components_main_front((small, big), max_components=1, min_area_m2=10.0)
    assert len(kept) == 1
    assert kept[0] == big


def test_quality_grade_penalizes_fragmentation() -> None:
    good = quality_grade(
        {
            "num_observations": 6,
            "speed_n_observable": 40,
            "component_count_median": 2,
            "area_non_monotonic": False,
            "speed_defendable": True,
        }
    )
    bad = quality_grade(
        {
            "num_observations": 2,
            "speed_n_observable": 2,
            "component_count_median": 500,
            "area_non_monotonic": True,
            "speed_defendable": False,
        }
    )
    assert good["quality_grade"] in {"A", "B"}
    assert bad["quality_grade"] == "C"
    assert good["quality_score"] > bad["quality_score"]
