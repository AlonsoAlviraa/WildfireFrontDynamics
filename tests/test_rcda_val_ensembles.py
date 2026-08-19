"""Tests for the sealed-VAL-only RCDA ensemble audit."""

from __future__ import annotations

import numpy as np

from scripts.tune_rcda_val_ensembles import (
    parse_combinations,
    parse_named_paths,
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
