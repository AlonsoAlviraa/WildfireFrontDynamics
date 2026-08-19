"""Paired event-level RCDA paper scorecard tests."""

from __future__ import annotations

import json

import pytest

from scripts.summarize_rcda_paper_final import build_scorecard


def test_scorecard_uses_preregistered_seeds_and_paired_events(tmp_path) -> None:
    events = {"fire-a": {"iou": 0.1}, "fire-b": {"iou": 0.2}}
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "protocol": {"test_used_for_selection": False},
                "validation": {
                    "selected_radius_pixels": 6,
                    "selection_metric": "event_macro_growth_iou",
                    "test_used_for_selection": False,
                },
                "test": {"events": 2, "per_event_growth": events},
            }
        ),
        encoding="utf-8",
    )
    reports = []
    for seed, values in ((11, (0.3, 0.4)), (29, (0.4, 0.5)), (47, (0.5, 0.6))):
        reports.append(
            {
                "config": {"seed": seed},
                "checkpoint_sha256": f"{seed:064x}",
                "best_epoch": 2,
                "selected_threshold": 0.5,
                "test_used_for_selection": False,
                "test_once": {
                    "event_macro_iou": sum(values) / 2,
                    "iou": 0.4,
                    "far_gt_10_5px_recall": 0.2,
                    "per_event": {
                        "fire-a": {"iou": values[0]},
                        "fire-b": {"iou": values[1]},
                    },
                    "paper_metrics": {
                        "model_growth_average_precision_macro": 0.5,
                        "model_growth_fcer_iou": 0.6,
                        "model_growth_fcer_ece_macro": 0.08,
                        "model_growth_fcer_selective_error_80_macro": 0.12,
                        "model_growth_fcer_aurc_macro": 0.10,
                        "observed_growth_fcer_capture_macro": 0.72,
                        "model_front_boundary_f1_macro": 0.4,
                    },
                },
            }
        )
    final = tmp_path / "final.json"
    final.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_final_v1",
                "test_used_for_selection": False,
                "frozen_recipe": {
                    "final_evaluation": {"seeds": [11, 29, 47]},
                },
                "ensemble": {
                    "aggregation": "mean_seed_probability",
                    "threshold_selected_on": "val",
                    "selected_threshold": 0.45,
                    "test_used_for_selection": False,
                    "test_evaluated": True,
                    "test_once": {
                        "event_macro_iou": 0.5,
                        "iou": 0.46,
                        "per_event": {
                            "fire-a": {"iou": 0.45},
                            "fire-b": {"iou": 0.55},
                        },
                    },
                },
                "decoder": {
                    "role": "preregistered_secondary_spatial_decoder",
                    "applied_to": "mean_seed_probability",
                    "threshold_and_geometry_selected_on": "val",
                    "threshold": 0.8,
                    "dilation_radius_px": 1,
                    "require_t0_connection": True,
                    "test_used_for_selection": False,
                    "test_evaluated": True,
                    "test_once": {
                        "event_macro_iou": 0.53,
                        "iou": 0.48,
                        "per_event": {
                            "fire-a": {"iou": 0.48},
                            "fire-b": {"iou": 0.58},
                        },
                    },
                },
                "reports": reports,
            }
        ),
        encoding="utf-8",
    )
    learned = tmp_path / "learned.json"
    learned.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_learned_baselines_v1",
                "test_used_for_selection": False,
                "reports": [
                    {
                        "model_name": "unet",
                        "test_used_for_selection": False,
                        "test": {
                            "per_event": {
                                "fire-a": {"iou": 0.25},
                                "fire-b": {"iou": 0.30},
                            }
                        },
                    },
                    {
                        "model_name": "rcda",
                        "test_used_for_selection": False,
                        "test": {
                            "per_event": {
                                "fire-a": {"iou": 0.20},
                                "fire-b": {"iou": 0.25},
                            }
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    scorecard = build_scorecard(final, baseline, tmp_path / "out", learned)
    assert scorecard["status"] == "paper_model_candidate"
    assert scorecard["primary"]["model_mean"] == pytest.approx(0.45)
    assert scorecard["primary"]["paired_delta"] > 0.0
    assert scorecard["strongest_baseline"]["id"] == "unet"
    assert scorecard["baseline_contract"]["selected_radius_pixels"] == 6
    assert scorecard["gate"]["learned_baselines_reproduced"] is True
    assert scorecard["gate"]["paired_bootstrap_delta_vs_strongest_ci_above_zero"] is True
    assert scorecard["secondary"]["growth_fcer_ece_macro"]["mean"] == pytest.approx(0.08)
    assert scorecard["ensemble"]["event_macro_iou"] == pytest.approx(0.5)
    assert scorecard["ensemble"]["threshold_selected_on"] == "val"
    assert scorecard["ensemble"]["vs_strongest_baseline"]["paired_delta"] > 0.0
    assert scorecard["decoder"]["event_macro_iou"] == pytest.approx(0.53)
    assert scorecard["decoder"]["threshold_and_geometry_selected_on"] == "val"
    assert scorecard["decoder"]["vs_strongest_baseline"]["paired_delta"] > 0.0
    assert scorecard["claims"]["wfigs_external_validation_pending"] is True
