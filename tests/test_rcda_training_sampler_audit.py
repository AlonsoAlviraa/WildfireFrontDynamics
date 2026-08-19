"""Tests for the TRAIN-only RCDA sampler audit."""

from __future__ import annotations

import numpy as np

from scripts.audit_rcda_training_sampler import (
    size_weight,
    summarize_strategy,
    support_band,
)


def test_support_bands_match_registered_sampler_boundaries() -> None:
    assert [support_band(value) for value in (0, 1, 99, 100, 499, 500, 1999, 2000)] == [
        "zero",
        "1_99",
        "1_99",
        "100_499",
        "100_499",
        "500_1999",
        "500_1999",
        "2000_plus",
    ]
    assert [size_weight(value) for value in (0, 1, 100, 500, 2000)] == [
        4.0,
        3.0,
        1.5,
        1.0,
        2.0,
    ]


def test_uniform_events_equalizes_event_probability_mass() -> None:
    event_ids = ["long", "long", "long", "short"]
    bands = ["zero", "1_99", "100_499", "500_1999"]
    weights = np.asarray([1 / 3, 1 / 3, 1 / 3, 1.0])
    row = summarize_strategy("uniform_events", weights, event_ids, bands)
    assert row["event_probability_mass_cv"] == 0.0
    assert row["event_probability_mass_min"] == 0.5
    assert row["event_probability_mass_max"] == 0.5

