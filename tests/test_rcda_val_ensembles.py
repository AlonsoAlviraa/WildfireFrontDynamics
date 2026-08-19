"""Tests for the sealed-VAL-only RCDA ensemble audit."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.tune_rcda_val_ensembles import (
    paired_event_bootstrap,
    parse_combinations,
    parse_named_paths,
    selected_event_ious,
    summarize_confusions,
)


def test_summarize_confusions_selects_event_macro_not_pooled_iou() -> None:
    # Threshold 0.5 has a lower pooled IoU but treats the two fires equally
    # well; threshold 0.8 is dominated by the much larger first fire.
    pooled = np.asarray(
        [
            [55, 100, 45, 45],
            [90, 100, 10, 100],
        ],
        dtype=np.int64,
    )
    by_event = {
        "small-fire": np.asarray([[5, 10, 5, 5], [0, 10, 0, 10]]),
        "large-fire": np.asarray([[50, 90, 40, 40], [90, 90, 10, 90]]),
    }
    ranking = summarize_confusions(
        pooled,
        by_event,
        (0.5, 0.8),
        samples=12,
    )
    assert ranking[0]["threshold"] == 0.5
    assert ranking[0]["events"] == 2
    assert ranking[0]["samples"] == 12
    assert ranking[0]["event_macro_iou"] > ranking[1]["event_macro_iou"]
    assert ranking[0]["pooled_iou"] < ranking[1]["pooled_iou"]


def test_explicit_ensemble_cli_values_are_parsed() -> None:
    checkpoints = parse_named_paths(["low=low.pt", "phase1=phase1.pt"])
    combinations = parse_combinations(
        ["low_only=low", "low_phase1=low,phase1"]
    )

    assert checkpoints["low"].name == "low.pt"
    assert combinations["low_phase1"] == ("low", "phase1")


def test_selected_event_ious_and_paired_bootstrap_are_event_level() -> None:
    by_event = {
        "fire-a": np.asarray([[4, 4, 0, 1], [3, 4, 1, 2]]),
        "fire-b": np.asarray([[1, 2, 1, 3], [2, 2, 0, 2]]),
    }
    selected = selected_event_ious(by_event, (0.4, 0.6), 0.4)
    assert set(selected) == {"fire-a", "fire-b"}

    paired = paired_event_bootstrap(
        {"fire-a": 0.5, "fire-b": 0.2},
        {"fire-a": 0.7, "fire-b": 0.1},
        n_resamples=2_000,
        seed=7,
    )
    assert paired["events"] == 2
    assert paired["mean_delta_iou"] == pytest.approx(0.05)
    assert paired["wins_event_fraction"] == pytest.approx(0.5)
    assert paired["ties_event_fraction"] == pytest.approx(0.0)
