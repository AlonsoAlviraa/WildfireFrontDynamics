"""Tests for freezing an RCDA paper recipe without TEST leakage."""

from __future__ import annotations

import json

import pytest

from scripts.analyze_rcda_paper_tuning import freeze_recipe, merge_tuning_summaries


def _report(name: str, score: float, *, touched_test: bool = False) -> dict:
    return {
        "config": {
            "run_name": name,
            "model_name": "unet",
            "target_mode": "growth",
            "lr": 0.001,
            "weight_decay": 0.0001,
            "epochs": 2,
            "batch_size": 2,
            "patience": 1,
            "loss_name": "focal_tversky",
            "tversky_alpha": 0.3,
            "tversky_beta": 0.7,
            "tversky_gamma": 0.75,
            "extent_loss_weight": 0.35,
            "growth_loss_weight": 0.65,
            "base_channels": 32,
            "scheduler_name": "cosine",
            "selection_metric": "event_macro_iou",
        },
        "best_epoch": 1,
        "selected_threshold": 0.5,
        "threshold_selected_on": "val",
        "val": {"selected": {"event_macro_iou": score, "iou": score - 0.01}},
        "test_evaluated": touched_test,
        "test_used_for_selection": False,
        **({"test_once": {"iou": 0.9}} if touched_test else {}),
    }


def test_freeze_selects_only_highest_validation_recipe(tmp_path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "reports": [_report("a", 0.2), _report("b", 0.3)],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "PRETEST_DECISION_LOG.json").write_text(
        json.dumps({"new_candidate_test_evaluated": False}), encoding="utf-8"
    )
    (tmp_path / "LOW_LR_POSTPROCESS_VAL.json").write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_val_postprocess_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "run_name": "b",
                "model_name": "unet",
                "target_mode": "growth",
                "best": {
                    "threshold": 0.8,
                    "dilation_radius_px": 1,
                    "require_t0_connection": True,
                },
            }
        ),
        encoding="utf-8",
    )
    frozen = freeze_recipe(source, tmp_path / "frozen.json")
    assert frozen["winner"]["config"]["run_name"] == "b"
    assert frozen["final_evaluation"]["seeds"] == [11, 29, 47]
    assert (
        frozen["final_evaluation"]["secondary_probability_ensemble"][
            "threshold_selected_on"
        ]
        == "val"
    )
    decoder = frozen["final_evaluation"]["secondary_spatial_decoder"]
    assert decoder["role"] == "preregistered_secondary_spatial_decoder"
    assert decoder["applied_to"] == "mean_seed_probability"
    assert decoder["source_run_name"] == "b"
    assert decoder["threshold"] == 0.8
    assert decoder["dilation_radius_px"] == 1
    assert decoder["require_t0_connection"] is True
    assert decoder["threshold_and_geometry_selected_on"] == "val"
    assert decoder["changes_primary_endpoint_or_gate"] is False
    assert len(
        frozen["final_evaluation"]["secondary_spatial_decoder"][
            "source_artifact_sha256"
        ]
    ) == 64
    assert frozen["test_observed_during_tuning"] is False
    assert frozen["winner"]["config"]["event_balance_power"] == 0.5
    assert frozen["winner"]["config"]["sampling_strategy"] == "size_event_power"
    assert frozen["data_contract"]["rcda_archive_md5"] == "d7856d77dcb823d0bdb5e10c6bac4f87"
    assert frozen["data_contract"]["event_split_seed"] == "wfd_rcda_event_split_v1"
    assert len(frozen["data_contract"]["protocol_sha256"]) == 4
    assert len(frozen["data_contract"]["pretest_decision_log_sha256"]) == 64


def test_freeze_refuses_any_tuning_report_that_touched_test(tmp_path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "reports": [_report("leaky", 0.9, touched_test=True)],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="evaluated TEST"):
        freeze_recipe(source, tmp_path / "frozen.json")


def test_merge_stages_ranks_all_validation_reports_without_test(tmp_path) -> None:
    paths = []
    for index, report in enumerate((_report("stage1", 0.2), _report("stage2", 0.3))):
        path = tmp_path / f"stage{index}.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "wfd_rcda_paper_tune_v1",
                    "selection_split": "val",
                    "test_evaluated": False,
                    "reports": [report],
                }
            ),
            encoding="utf-8",
        )
        paths.append(path)
    merged = merge_tuning_summaries(paths, tmp_path / "combined.json")
    assert merged["test_evaluated"] is False
    assert merged["test_used_for_selection"] is False
    assert merged["ranking"][0]["run_name"] == "stage2"
    assert len(merged["reports"]) == 2
