from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.research_status import build_research_status


def test_research_status_labels_gcp_continuation(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    work.mkdir(parents=True)
    (work / "STATE.json").write_text(
        json.dumps(
            {
                "phase": "validation_only_stage2_gcp",
                "status": "running",
                "updated_at": "2026-08-19T03:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    gcp = tmp_path / "outputs/ml_eval/rcda_gcp_stage2_20260819"
    gcp.mkdir(parents=True)
    (gcp / "STATE.json").write_text(
        json.dumps(
            {
                "phase": "running",
                "checkpoint_epoch": 3,
                "train_loss": 0.61,
                "val_f1_at_0_5": 0.18,
                "spot_restarts": 0,
            }
        ),
        encoding="utf-8",
    )
    status = build_research_status(tmp_path)
    assert status["training_live"] is True
    assert status["execution_backend"] == "gcp_cpu_spot"
    assert "GCP" in status["phase_label"]
    assert status["training_progress"]["epoch"] == 3


def test_research_status_does_not_carry_long_epoch_into_next_recipe(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    work.mkdir(parents=True)
    _write(
        work / "STATE.json",
        {
            "phase": "validation_only_stage2_precision_gcp",
            "status": "running",
            "active_validation_run": "resunet_hybrid_precision_v3",
            "checkpoint_epoch": None,
        },
    )
    _write(
        tmp_path / "outputs/ml_eval/rcda_gcp_stage2_20260819/STATE.json",
        {"phase": "complete", "checkpoint_epoch": 40, "val_f1_at_0_5": 0.25},
    )
    status = build_research_status(tmp_path)
    assert status["training_progress"]["run"] == "resunet_hybrid_precision_v3"
    assert status["training_progress"]["epoch"] is None


def test_research_status_surfaces_kaggle_runtime_without_fake_epoch(
    tmp_path: Path,
) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(
        work / "STATE.json",
        {
            "phase": "validation_only_stage2_low_lr_kaggle",
            "status": "running",
            "kernel_status": "running",
            "kernel": "alonsoalviraaaa/wfd-rcda-low-lr-gpu-v1",
            "best_completed_val_event_macro_iou": 0.1802,
        },
    )
    _write(
        work / "KAGGLE_RUNTIME_MANIFEST.json",
        {
            "test_evaluated": False,
            "runs": [
                {
                    "run_name": "resunet_hybrid_precision_v3",
                    "recovered_finite_checkpoint": True,
                },
                {
                    "run_name": "resunet_hybrid_low_lr_v2",
                    "kernel": "alonsoalviraaaa/wfd-rcda-low-lr-gpu-v1",
                },
            ],
        },
    )

    status = build_research_status(tmp_path)
    progress = status["training_progress"]
    assert status["execution_backend"] == "kaggle_gpu"
    assert progress["run"] == "resunet_hybrid_low_lr_v2"
    assert progress["epoch"] is None
    assert progress["best_completed_val_event_macro_iou"] == 0.1802
    assert progress["registered_runs"] == 2
    assert progress["recovered_runs"] == 1
    assert progress["test_evaluated"] is False
    assert len(status["experiment_queue"]) == 9
    assert status["experiment_queue"][0]["status"] == "recovered"
    assert status["experiment_queue"][1]["status"] == "active"
    assert status["experiment_queue"][2]["status"] == "planned"


def test_research_status_uses_val_scorecard_to_complete_experiment_queue(
    tmp_path: Path,
) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(
        work / "STATE.json",
        {
            "phase": "validation_only_stage2_multitask_front_ring_kaggle",
            "status": "running",
            "kernel_status": "running",
            "kernel": "alonsoalviraaaa/wfd-rcda-multitask-front-ring-gpu-v1",
        },
    )
    _write(
        work / "KAGGLE_RUNTIME_MANIFEST.json",
        {
            "test_evaluated": False,
            "runs": [
                {
                    "run_name": "resunet_multitask_front_ring_v1",
                    "kernel": "alonsoalviraaaa/wfd-rcda-multitask-front-ring-gpu-v1",
                }
            ],
        },
    )
    _write(
        work / "VALIDATION_SCORECARD.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "ranking": [
                {
                    "rank": 1,
                    "run_name": "resunet_hybrid_uniform_events_v1",
                    "event_macro_iou": 0.189,
                }
            ],
        },
    )

    status = build_research_status(tmp_path)
    queue = {row["run_name"]: row for row in status["experiment_queue"]}
    assert status["execution_backend"] == "kaggle_gpu"
    assert "frente activo" in status["phase_label"]
    assert queue["resunet_hybrid_uniform_events_v1"]["status"] == "completed"
    assert queue["resunet_multitask_front_ring_v1"]["status"] == "active"
    assert queue["film_growth_v1"]["status"] == "planned"


def test_research_status_surfaces_provisional_validation_leader(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    tuning = work / "tuning_output/rcda_paper_tune/TUNING_SUMMARY.json"
    tuning.parent.mkdir(parents=True)
    (work / "STATE.json").write_text(
        json.dumps({"phase": "validation_only_stage2_gcp", "status": "running"}),
        encoding="utf-8",
    )
    tuning.write_text(
        json.dumps(
            {
                "ranking": [
                    {
                        "run_name": "resunet_hybrid_v1",
                        "val_event_macro_iou": 0.1802,
                        "val_pooled_iou": 0.1403,
                        "threshold": 0.6,
                        "best_epoch": 24,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    status = build_research_status(tmp_path)
    assert status["validation_winner"]["run_name"] == "resunet_hybrid_v1"
    assert status["validation_winner"]["frozen"] is False
    assert status["artifacts"]["tuning_summary"].endswith("TUNING_SUMMARY.json")


def test_research_status_exposes_only_isolated_val_leaderboard(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(work / "STATE.json", {"phase": "validation_only_stage2", "status": "running"})
    _write(
        work / "VALIDATION_SCORECARD.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "events": 106,
            "bootstrap_resamples": 10_000,
            "uncertainty_unit": "fire_event",
            "ranking": [
                {
                    "rank": 1,
                    "run_name": "low_lr",
                    "event_macro_iou": 0.194,
                    "event_bootstrap_95_ci": [0.17, 0.22],
                    "leader_minus_candidate_paired_delta": 0.0,
                    "selected_threshold": 0.05,
                    "best_epoch": 27,
                },
                {
                    "rank": 2,
                    "run_name": "phase1",
                    "event_macro_iou": 0.180,
                    "leader_minus_candidate_paired_delta": 0.014,
                    "selected_threshold": 0.6,
                    "best_epoch": 24,
                },
            ],
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_winner"]["run_name"] == "low_lr"
    assert status["validation_candidates"][0]["event_macro_iou"] == 0.194
    assert status["validation_evidence"]["events"] == 106
    assert status["validation_evidence"]["test_evaluated"] is False
    assert status["training_progress"]["best_completed_val_event_macro_iou"] == 0.194

    scorecard = json.loads((work / "VALIDATION_SCORECARD.json").read_text())
    scorecard["test_evaluated"] = True
    _write(work / "VALIDATION_SCORECARD.json", scorecard)
    assert build_research_status(tmp_path)["validation_candidates"] == []


def test_research_status_surfaces_val_only_postprocess_delta(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(work / "STATE.json", {"phase": "validation_only_stage2", "status": "running"})
    _write(
        work / "VALIDATION_SCORECARD.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "ranking": [
                {
                    "rank": 1,
                    "run_name": "low_lr",
                    "event_macro_iou": 0.194,
                    "selected_threshold": 0.05,
                    "best_epoch": 27,
                }
            ],
        },
    )
    _write(
        work / "LOW_LR_POSTPROCESS_VAL.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "checkpoint": "low_lr_seed0_best.pt",
            "best": {
                "event_macro_iou": 0.201,
                "pooled_iou": 0.15,
                "threshold": 0.1,
                "dilation_radius_px": 1,
                "require_t0_connection": True,
            },
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_postprocess"]["event_macro_iou"] == 0.201
    assert round(status["validation_postprocess"]["delta_vs_raw"], 3) == 0.007
    assert status["validation_postprocess"]["test_evaluated"] is False


def test_research_status_surfaces_exact_val_reproducibility(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(
        work / "LOW_LR_REPRODUCIBILITY.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "run_name": "resunet_hybrid_low_lr_v2",
            "events": 106,
            "checkpoint_exact": True,
            "metrics_exact": True,
            "reproducible": True,
            "max_absolute_event_iou_difference": 0.0,
            "checkpoint_sha256": {"first": "abc123", "rerun": "abc123"},
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_reproducibility"]["reproducible"] is True
    assert status["validation_reproducibility"]["events"] == 106
    assert status["validation_reproducibility"]["test_evaluated"] is False


def test_research_status_surfaces_only_val_strata(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(
        work / "LOW_LR_VALIDATION_STRATA.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "run_name": "low_lr",
            "events": 106,
            "duration_spearman": {"rho": 0.10, "p_value": 0.30},
            "growth_support_spearman": {"rho": -0.005, "p_value": 0.96},
            "duration_strata": [],
            "growth_strata": [
                {"label": "Q1", "event_macro_iou": 0.21},
                {"label": "Q3", "event_macro_iou": 0.17},
            ],
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_strata"]["events"] == 106
    assert status["validation_strata"]["growth_support_spearman"]["rho"] == -0.005
    assert status["validation_strata"]["test_evaluated"] is False
    assert status["artifacts"]["validation_strata"].endswith(
        "LOW_LR_VALIDATION_STRATA.json"
    )


def test_research_status_surfaces_only_nonleaky_validation_ensemble(tmp_path: Path) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(
        work / "STATE.json",
        {"phase": "validation_only_stage2_gcp", "status": "running"},
    )
    _write(
        work / "PHASE1_VAL_ENSEMBLES.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "decision": {
                "best_multi_minus_individual": -0.01,
                "preregister_multi_model_ensemble": False,
            },
            "ranking": [
                {
                    "name": "res_unet",
                    "members": ["res", "unet"],
                    "event_macro_iou": 0.19,
                    "threshold": 0.45,
                }
            ],
        },
    )
    _write(
        work / "TRAIN_SAMPLER_AUDIT.json",
        {
            "analysis_split": "train",
            "validation_evaluated": False,
            "test_evaluated": False,
            "samples": 100,
            "events": 20,
            "observed_zero_growth_fraction": 0.01,
            "transition_geometry": {"samples_with_any_t0_loss": 0},
            "strategies": [
                {
                    "name": "default_size_event_half",
                    "event_probability_mass_cv": 0.65,
                },
                {"name": "uniform_events", "event_probability_mass_cv": 0.0},
            ],
        },
    )
    _write(
        work / "LOW_LR_WEIGHTED_VAL_ENSEMBLES_PAIRED.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "decision": {
                "paired_validation": {
                    "events": 106,
                    "event_bootstrap_95_ci": [-0.00004, 0.00681],
                    "wins_event_fraction": 0.4906,
                }
            },
        },
    )
    _write(
        work / "PRETEST_DECISION_LOG.json",
        {
            "new_candidate_test_evaluated": False,
            "test_used_for_model_selection": False,
            "evidence": {
                "numeric_failure_recovery": {
                    "numeric_failure": {
                        "failed_epoch": 16,
                        "checkpoint_epoch": 13,
                        "test_evaluated": False,
                        "train_npy_finiteness_scan": {
                            "files": 13002,
                            "nonfinite_files": 0,
                        },
                    },
                    "ranking": [{"val_event_macro_iou": 0.1677}],
                }
            },
            "decisions": {"numeric_stability_hotfix": {"future_runs": "clip"}},
        },
    )
    status = build_research_status(tmp_path)
    assert status["validation_ensemble"]["name"] == "res_unet"
    assert status["validation_ensemble"]["event_macro_iou"] == 0.19
    assert status["validation_ensemble"]["delta_vs_best_individual"] == -0.01
    assert status["validation_ensemble"]["preregistered"] is False
    assert status["validation_ensemble"]["paired_delta_95_ci"] == [
        -0.00004,
        0.00681,
    ]
    assert status["validation_ensemble"]["paired_events"] == 106
    assert status["validation_ensemble"]["paired_wins_event_fraction"] == 0.4906
    assert status["training_sampler_audit"]["default_event_mass_cv"] == 0.65
    assert status["training_sampler_audit"]["uniform_event_mass_cv"] == 0.0
    assert status["training_sampler_audit"]["samples_with_any_t0_loss"] == 0
    assert status["protocol"]["pretest_decisions_registered"] is True
    assert status["numeric_stability"]["failure_recovered"] is True
    assert status["numeric_stability"]["checkpoint_epoch"] == 13
    assert status["numeric_stability"]["nonfinite_train_files"] == 0
    assert status["numeric_stability"]["max_grad_norm"] == 5.0
    assert status["artifacts"]["pretest_decision_log"].endswith(
        "PRETEST_DECISION_LOG.json"
    )
    assert status["validation_ensemble"]["test_evaluated"] is False
    assert status["artifacts"]["validation_ensemble"].endswith(
        "PHASE1_VAL_ENSEMBLES.json"
    )
    assert status["artifacts"]["validation_ensemble_paired"].endswith(
        "LOW_LR_WEIGHTED_VAL_ENSEMBLES_PAIRED.json"
    )

    _write(
        work / "PHASE1_VAL_ENSEMBLES.json",
        {
            "selection_split": "val",
            "test_evaluated": True,
            "test_used_for_selection": False,
            "ranking": [{"name": "leaky", "event_macro_iou": 0.99}],
        },
    )
    assert build_research_status(tmp_path)["validation_ensemble"] is None


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sealed_protocol(root: Path) -> None:
    protocol = root / "data/external/rcda_net_full/protocol"
    for name, events, samples in (
        ("train", ["A", "B"], 20),
        ("val", ["C"], 8),
        ("test", ["D", "E"], 12),
    ):
        _write(
            protocol / f"{name}.json",
            {
                "split": name,
                "event_disjoint": True,
                "events": events,
                "n_events": len(events),
                "n_samples": samples,
            },
        )
    _write(protocol / "normalization_train_only.json", {"fit_split": "train"})


def test_research_status_reports_live_validation_without_inventing_test(tmp_path: Path):
    _sealed_protocol(tmp_path)
    baseline = tmp_path / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json"
    _write(
        baseline,
        {
            "test": {
                "events": 2,
                "event_macro_growth_iou": 0.12,
                "growth_ring_result": {"iou": 0.11},
            }
        },
    )
    _write(
        tmp_path / "outputs/ml_eval/rcda_sealed_baselines/learned_baselines.json",
        {
            "reports": [
                {
                    "model_name": "unet",
                    "test": {"event_macro_iou": 0.16},
                }
            ]
        },
    )
    state = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819/STATE.json"
    _write(
        state,
        {
            "phase": "validation_only_tuning",
            "kernel_status": "running",
            "updated_at": "2026-08-19T00:00:00Z",
        },
    )

    status = build_research_status(tmp_path)

    assert status["training_live"] is True
    assert status["protocol"]["samples"] == 40
    assert status["protocol"]["events"] == 5
    assert status["protocol"]["event_disjoint"] is True
    assert status["protocol"]["normalization_train_only"] is True
    assert status["protocol"]["test_used_for_selection"] is False
    assert status["baseline"]["event_macro_iou"] == 0.12
    assert status["baseline"]["strongest_learned"]["name"] == "unet"
    assert status["baseline"]["strongest_learned"]["event_macro_iou"] == 0.16
    assert status["wfigs"]["external_evaluation_executed"] is False
    assert status["validation_winner"] is None
    assert status["final"] is None
    assert status["claims"]["paper_ready"] is False


def test_research_status_surfaces_frozen_winner_and_final_gates(tmp_path: Path):
    _sealed_protocol(tmp_path)
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(work / "STATE.json", {"phase": "complete", "status": "complete"})
    _write(
        work / "FROZEN_RECIPE.json",
        {
            "winner": {
                "val_event_macro_iou": 0.23,
                "val_pooled_iou": 0.22,
                "selected_threshold": 0.35,
                "best_epoch": 17,
                "config": {"run_name": "film_hybrid", "model_name": "film_unet"},
            }
        },
    )
    _write(
        work / "PAPER_SCORECARD.json",
        {
            "status": "paper_model_candidate",
            "events": 2,
            "primary": {
                "model_mean": 0.24,
                "dilated_copy": 0.12,
                "paired_delta": 0.12,
                "paired_delta_event_bootstrap_95_ci": [0.05, 0.18],
            },
            "gate": {"test_not_used_for_selection": True},
            "ensemble": {
                "role": "preregistered_secondary_probability_ensemble",
                "event_macro_iou": 0.25,
            },
            "decoder": {
                "role": "preregistered_secondary_spatial_decoder",
                "event_macro_iou": 0.26,
            },
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_winner"]["run_name"] == "film_hybrid"
    assert status["final"]["model_event_macro_iou"] == 0.24
    assert status["final"]["gates"]["test_not_used_for_selection"] is True
    assert status["final"]["ensemble_event_macro_iou"] == 0.25
    assert status["final"]["decoder_event_macro_iou"] == 0.26
    assert status["claims"]["paper_ready"] is True
    assert status["claims"]["external_generalization_proven"] is False


def test_research_status_separates_postfreeze_val_leader_from_test_recipe(
    tmp_path: Path,
) -> None:
    work = tmp_path / "outputs/ml_eval/rcda_paper_nightwatch_20260819"
    _write(work / "STATE.json", {"phase": "complete", "status": "complete"})
    _write(
        work / "FROZEN_RECIPE.json",
        {
            "winner": {
                "val_event_macro_iou": 0.208,
                "selected_threshold": 0.45,
                "best_epoch": 28,
                "config": {"run_name": "frozen_old"},
            }
        },
    )
    _write(
        work / "VALIDATION_SCORECARD.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "ranking": [
                {
                    "rank": 1,
                    "run_name": "new_front_ring",
                    "event_macro_iou": 0.22,
                    "selected_threshold": 0.7,
                    "best_epoch": 21,
                },
                {
                    "rank": 2,
                    "run_name": "frozen_old",
                    "event_macro_iou": 0.208,
                    "leader_minus_candidate_paired_delta": 0.012,
                },
            ],
        },
    )
    _write(work / "PAPER_SCORECARD.json", {"status": "continue_model_improvement"})

    status = build_research_status(tmp_path)
    assert status["validation_winner"]["run_name"] == "new_front_ring"
    assert status["validation_winner"]["frozen"] is False
    assert status["validation_winner"]["post_freeze_candidate"] is True
    assert status["frozen_test_recipe"]["run_name"] == "frozen_old"
    assert status["frozen_test_recipe"]["tested"] is True
    assert status["frozen_test_recipe"]["superseded_on_validation"] is True


def test_research_status_surfaces_wfigs_dataset_audit(tmp_path: Path):
    dataset = tmp_path / "outputs/ml_eval/wfigs_tensor_dataset_20260819"
    _write(
        dataset / "DATASET_REPORT.json",
        {
            "counts": {
                "samples_written": 80,
                "by_split": {"train": 61, "validation": 19},
            }
        },
    )
    _write(
        dataset / "DATASET_AUDIT.json",
        {
            "status": "pass",
            "counts": {"samples_audited": 80, "issues": 0},
            "checks": {
                "event_disjoint": True,
                "normalization_recomputed_from_train_only": True,
            },
        },
    )
    _write(
        tmp_path / "outputs/ml_eval/wfigs_test_campaign_20260819/STATE.json",
        {"groups_complete": 7, "groups_total": 19},
    )
    _write(
        dataset / "EXTERNAL_NIGHTWATCH_STATE.json",
        {"phase": "materializing_untouched_wfigs_test"},
    )
    _write(
        tmp_path / "outputs/ml_eval/wfigs_domain_adaptation_20260819/STATE.json",
        {"phase": "training_on_wfigs_train_val_only"},
    )
    _write(
        dataset / "WFIGS_EXTERNAL_EVAL.json",
        {
            "protocol": {"wfigs_test_used_for_selection": False},
            "summary": {
                "ensemble_event_macro_iou": 0.10,
                "paired_event_analysis": {
                    "paired_delta": -0.02,
                    "paired_delta_event_bootstrap_95_ci": [-0.04, -0.01],
                },
            },
        },
    )
    _write(
        tmp_path
        / "outputs/ml_eval/wfigs_domain_adaptation_20260819/WFIGS_ADAPTED_TEST_EVAL.json",
        {
            "protocol": {"wfigs_test_used_for_selection": False},
            "summary": {
                "adapted_event_macro_iou_mean": 0.22,
                "ensemble_event_macro_iou": 0.23,
                "adapted_transfer_signal_gate": False,
                "paired_event_analysis": {
                    "paired_delta": 0.05,
                    "paired_delta_event_bootstrap_95_ci": [0.01, 0.09],
                },
                "ensemble_paired_event_analysis": {
                    "paired_delta": 0.06,
                    "paired_delta_event_bootstrap_95_ci": [-0.01, 0.11],
                },
            }
        },
    )

    status = build_research_status(tmp_path)

    assert status["wfigs"]["tensors_materialized"] == 80
    assert status["wfigs"]["tensors_training_ready"] == 80
    assert status["wfigs"]["train_tensors"] == 61
    assert status["wfigs"]["validation_tensors"] == 19
    assert status["wfigs"]["dataset_audit_status"] == "pass"
    assert status["wfigs"]["dataset_audit_issues"] == 0
    assert status["wfigs"]["adapted_evaluation_executed"] is True
    assert status["wfigs"]["adapted_summary"]["ensemble_event_macro_iou"] == 0.23
    assert status["wfigs"]["external_test_used_for_selection"] is False
    assert status["wfigs"]["adapted_test_used_for_selection"] is False
    assert status["wfigs"]["test_groups_complete"] == 7
    assert status["wfigs"]["test_groups_total"] == 19
    assert status["wfigs"]["test_materialization_phase"] == (
        "materializing_untouched_wfigs_test"
    )
    assert status["wfigs"]["adaptation_phase"] == (
        "training_on_wfigs_train_val_only"
    )


def test_research_status_keeps_sealed_external_result_during_scaleup(
    tmp_path: Path,
) -> None:
    sealed = tmp_path / "outputs/ml_eval/wfigs_tensor_dataset_20260819"
    _write(sealed / "DATASET_REPORT.json", {"counts": {"samples_written": 101}})
    _write(
        sealed / "WFIGS_EXTERNAL_EVAL.json",
        {
            "protocol": {"wfigs_test_used_for_selection": False},
            "summary": {"ensemble_event_macro_iou": 0.09},
        },
    )
    scaleup = tmp_path / "outputs/ml_eval/wfigs_tensor_dataset_scaleup_20260820"
    _write(scaleup / "NIGHTWATCH_STATE.json", {"phase": "expanding_train_campaign"})

    status = build_research_status(tmp_path)["wfigs"]

    assert status["external_evaluation_executed"] is True
    assert status["external_summary"]["ensemble_event_macro_iou"] == 0.09
    assert status["dataset_phase"] == "expanding_train_campaign"
    assert status["campaign_running"] is True


def test_spa_contains_research_panel_and_accessible_tabs(tmp_path: Path):
    payload = build_product_app_payload(repo=tmp_path, scan=False, live=False)
    html = render_product_app_html(payload)

    assert payload["research_status"]["schema"] == "wfd_rcda_research_status_v1"
    assert 'data-tab="modelo"' in html
    assert 'data-marker="research-status"' in html
    assert "renderResearchStatus" in html
    assert 'class="skip-link"' in html
    assert "setAttribute('role', 'tabpanel')" in html
    assert "aria-selected" in html
    assert "Aún no es un claim de paper" in html
    assert "WFIGS auditados" in html
    assert "Telemetría de entrenamiento" in html
    assert "Delta vs 2º VAL" in html
    assert "Mejor ensemble VAL" in html
    assert "Decoder TEST" in html
    assert "Postproceso VAL" in html
    assert "Rango estratos VAL" in html
    assert "Dependencia del tamaño" in html
    assert "validation_evidence.svg?research=" in html
    assert "Evidencia sÃ³lo VAL" in html
    assert "Masa por incendio" in html
    assert "WFIGS zero-shot" in html
    assert "Ensemble WFIGS" in html
    assert "Ensemble adaptado" in html
    assert "Clasificacion VAL" in html
    assert "Cola nocturna de experimentos" in html
    assert "research-pipeline" in html
    assert "Escalado WFIGS" in html
    assert "Lift por adaptación" in html
    assert "Señal externa" in html
    assert "WFIGS TEST" in html
    assert "IC95% modelo" in html
    assert "Ensemble vs rival" in html
    assert "TEST SELLADO" in html
    assert "refreshResearchStatus" in html
    assert "app_payload.json?research=" in html
