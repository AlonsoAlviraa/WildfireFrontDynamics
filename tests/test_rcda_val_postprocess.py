"""Tests for validation-only RCDA spatial post-processing."""

from __future__ import annotations

import numpy as np

from scripts.tune_rcda_val_postprocess import (
    evaluate_postprocess_grid,
    postprocess_growth,
)


def test_dilation_never_repredicts_the_observed_t0_extent() -> None:
    previous = np.zeros((7, 7), dtype=bool)
    previous[3, 3] = True
    prediction = np.zeros_like(previous)
    prediction[3, 4] = True
    result = postprocess_growth(
        prediction,
        previous,
        dilation_radius=2,
        require_t0_connection=False,
    )
    assert result[3, 3] == 0
    assert result.sum() > prediction.sum()


def test_connection_filter_removes_isolated_growth_component() -> None:
    previous = np.zeros((7, 7), dtype=bool)
    previous[1, 1] = True
    prediction = np.zeros_like(previous)
    prediction[1, 2] = True
    prediction[6, 6] = True
    result = postprocess_growth(
        prediction,
        previous,
        dilation_radius=0,
        require_t0_connection=True,
    )
    assert result[1, 2]
    assert not result[6, 6]


def test_grid_selects_validation_configuration_by_event_macro_iou() -> None:
    probabilities = np.zeros((2, 5, 5), dtype=np.float32)
    targets = np.zeros_like(probabilities, dtype=bool)
    previous = np.zeros_like(probabilities, dtype=bool)
    previous[:, 2, 2] = True
    probabilities[:, 2, 3] = 0.8
    targets[:, 2, 3] = True
    ranking = evaluate_postprocess_grid(
        probabilities,
        targets,
        previous,
        ["fire-a", "fire-b"],
        thresholds=(0.5,),
        dilation_radii=(0, 1),
        connectivity_options=(False,),
    )
    assert ranking[0]["dilation_radius_px"] == 0
    assert ranking[0]["event_macro_iou"] == 1.0
