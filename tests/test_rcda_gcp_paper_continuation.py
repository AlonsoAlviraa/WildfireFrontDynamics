"""Tests for the sealed GCP RCDA paper continuation."""

from __future__ import annotations

import copy
import json

import pytest

from scripts.run_rcda_gcp_paper_continuation import (
    best_validation_score,
    validate_final_summary,
)


def _frozen() -> dict:
    return {
        "schema": "wfd_rcda_paper_frozen_recipe_v1",
        "selection_split": "val",
        "test_observed_during_tuning": False,
        "winner": {"config": {"run_name": "winner"}},
        "final_evaluation": {
            "seeds": [11, 29, 47],
            "secondary_probability_ensemble": {
                "aggregation": "mean_seed_probability",
            },
        },
    }


def _summary(frozen: dict) -> dict:
    return {
        "schema": "wfd_rcda_paper_final_v1",
        "frozen_recipe": frozen,
        "selection_split": "val",
        "test_used_for_selection": False,
        "ensemble": {
            "aggregation": "mean_seed_probability",
            "threshold_selected_on": "val",
            "test_used_for_selection": False,
            "test_evaluated": True,
            "test_once": {"event_macro_iou": 0.21},
        },
        "reports": [
            {
                "config": {"seed": seed},
                "threshold_selected_on": "val",
                "test_used_for_selection": False,
                "test_evaluated": True,
                "test_once": {"event_macro_iou": 0.2},
                "checkpoint_sha256": "a" * 64,
            }
            for seed in (11, 29, 47)
        ],
    }


def test_validate_final_summary_requires_exact_frozen_recipe(tmp_path) -> None:
    frozen = _frozen()
    path = tmp_path / "FINAL_SUMMARY.json"
    path.write_text(json.dumps(_summary(frozen)), encoding="utf-8")
    result = validate_final_summary(path, frozen)
    assert len(result["reports"]) == 3

    changed = copy.deepcopy(frozen)
    changed["winner"]["config"]["run_name"] = "post_test_change"
    with pytest.raises(ValueError, match="exact frozen recipe"):
        validate_final_summary(path, changed)


def test_validate_final_summary_rejects_missing_seed_or_test(tmp_path) -> None:
    frozen = _frozen()
    summary = _summary(frozen)
    summary["reports"].pop()
    path = tmp_path / "FINAL_SUMMARY.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="preregistered seeds"):
        validate_final_summary(path, frozen)

    summary = _summary(frozen)
    summary["reports"][0]["test_evaluated"] = False
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="single TEST"):
        validate_final_summary(path, frozen)


def test_validate_final_summary_rejects_ensemble_test_leakage(tmp_path) -> None:
    frozen = _frozen()
    summary = _summary(frozen)
    summary["ensemble"]["threshold_selected_on"] = "test"
    path = tmp_path / "FINAL_SUMMARY.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="ensemble violates"):
        validate_final_summary(path, frozen)


def test_validate_final_summary_rejects_missing_checkpoint_hash(tmp_path) -> None:
    frozen = _frozen()
    summary = _summary(frozen)
    del summary["reports"][0]["checkpoint_sha256"]
    path = tmp_path / "FINAL_SUMMARY.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_final_summary(path, frozen)


def test_conditional_low_lr_gate_reads_validation_only(tmp_path) -> None:
    summary = tmp_path / "TUNING_SUMMARY.json"
    summary.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "reports": [
                    {
                        "threshold_selected_on": "val",
                        "test_used_for_selection": False,
                        "test_evaluated": False,
                        "val": {"selected": {"event_macro_iou": 0.199}},
                    },
                    {
                        "threshold_selected_on": "val",
                        "test_used_for_selection": False,
                        "test_evaluated": False,
                        "val": {"selected": {"event_macro_iou": 0.181}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assert best_validation_score([summary]) == pytest.approx(0.199)
    leaked = json.loads(summary.read_text(encoding="utf-8"))
    leaked["test_evaluated"] = True
    summary.write_text(json.dumps(leaked), encoding="utf-8")
    with pytest.raises(ValueError, match="non-VAL"):
        best_validation_score([summary])

    leaked["test_evaluated"] = False
    leaked["reports"][0]["test_evaluated"] = True
    summary.write_text(json.dumps(leaked), encoding="utf-8")
    with pytest.raises(ValueError, match="evaluated TEST"):
        best_validation_score([summary])
