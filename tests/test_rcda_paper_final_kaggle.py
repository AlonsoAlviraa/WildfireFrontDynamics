"""Tests for the preregistered RCDA paper final job."""

from __future__ import annotations

from scripts.push_rcda_paper_final_kaggle import _validated_frozen, self_contained_final_kernel


def test_final_kernel_embeds_frozen_recipe_and_preregistered_seeds() -> None:
    frozen = {
        "schema": "wfd_rcda_paper_frozen_recipe_v1",
        "test_observed_during_tuning": False,
        "data_contract": {
            "rcda_archive_md5": "d7856d77dcb823d0bdb5e10c6bac4f87",
            "event_split_seed": "wfd_rcda_event_split_v1",
            "normalization_fit_split": "train",
            "protocol_sha256": {
                "train.json": "a" * 64,
                "val.json": "b" * 64,
                "test.json": "c" * 64,
                "normalization_train_only.json": "d" * 64,
            },
            "pretest_decision_log_sha256": "f" * 64,
        },
        "winner": {
            "config": {
                "run_name": "winner",
                "model_name": "unet",
                "target_mode": "growth",
                "epochs": 2,
                "batch_size": 2,
                "lr": 0.001,
                "weight_decay": 0.0001,
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
                "weighted_sampling": True,
            }
        },
        "final_evaluation": {
            "seeds": [11, 29, 47],
            "recipe_changes_after_test_forbidden": True,
            "secondary_probability_ensemble": {
                "aggregation": "mean_seed_probability",
                "threshold_selected_on": "val",
                "test_evaluated_once_after_threshold_freeze": True,
                "changes_primary_endpoint_or_gate": False,
            },
            "secondary_spatial_decoder": {
                "role": "preregistered_secondary_spatial_decoder",
                "applied_to": "mean_seed_probability",
                "source_artifact_sha256": "e" * 64,
                "threshold": 0.8,
                "dilation_radius_px": 1,
                "require_t0_connection": True,
                "threshold_and_geometry_selected_on": "val",
                "changes_primary_endpoint_or_gate": False,
            },
        },
    }
    source = self_contained_final_kernel(frozen)
    compile(source, "run_rcda_paper_final.py", "exec")
    assert "evaluate_test=True" in source
    assert '"seeds": [' in source
    assert "11," in source and "29," in source and "47" in source
    assert '"test_used_for_selection": False' in source
    assert "compute_paper_metrics=False" in source
    assert "report_path.is_file()" in source
    assert "invalid resumable final report" in source
    assert "ProbabilityAveragingEnsemble" in source
    assert '"threshold_selected_on": "val"' in source
    assert '"ensemble": {' in source
    assert "ensemble_test = evaluate_split" in source
    assert "decoder_test = evaluate_split_postprocessed" in source
    assert '"decoder": decoder_report' in source
    assert "event_balance_power" in source
    assert "sampling_strategy" in source
    assert "checkpoint_sha256" in source


def test_frozen_recipe_validator_requires_data_and_ensemble_contracts(tmp_path) -> None:
    frozen = {
        "schema": "wfd_rcda_paper_frozen_recipe_v1",
        "test_observed_during_tuning": False,
        "data_contract": {
            "rcda_archive_md5": "d7856d77dcb823d0bdb5e10c6bac4f87",
            "event_split_seed": "wfd_rcda_event_split_v1",
            "normalization_fit_split": "train",
            "protocol_sha256": dict.fromkeys(
                ("train", "val", "test", "norm"), "a" * 64
            ),
            "pretest_decision_log_sha256": "f" * 64,
        },
        "final_evaluation": {
            "seeds": [11, 29, 47],
            "recipe_changes_after_test_forbidden": True,
            "secondary_probability_ensemble": {
                "aggregation": "mean_seed_probability",
                "threshold_selected_on": "val",
                "changes_primary_endpoint_or_gate": False,
            },
        },
    }
    path = tmp_path / "frozen.json"
    path.write_text(__import__("json").dumps(frozen), encoding="utf-8")
    assert _validated_frozen(path) == frozen
