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
        },
    )

    status = build_research_status(tmp_path)

    assert status["validation_winner"]["run_name"] == "film_hybrid"
    assert status["final"]["model_event_macro_iou"] == 0.24
    assert status["final"]["gates"]["test_not_used_for_selection"] is True
    assert status["claims"]["paper_ready"] is True
    assert status["claims"]["external_generalization_proven"] is False


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
        tmp_path
        / "outputs/ml_eval/wfigs_domain_adaptation_20260819/WFIGS_ADAPTED_TEST_EVAL.json",
        {
            "summary": {
                "adapted_event_macro_iou_mean": 0.22,
                "ensemble_event_macro_iou": 0.23,
                "paired_event_analysis": {
                    "paired_delta": 0.05,
                    "paired_delta_event_bootstrap_95_ci": [0.01, 0.09],
                },
            }
        },
    )

    status = build_research_status(tmp_path)

    assert status["wfigs"]["tensors_training_ready"] == 80
    assert status["wfigs"]["train_tensors"] == 61
    assert status["wfigs"]["validation_tensors"] == 19
    assert status["wfigs"]["dataset_audit_status"] == "pass"
    assert status["wfigs"]["dataset_audit_issues"] == 0
    assert status["wfigs"]["adapted_evaluation_executed"] is True
    assert status["wfigs"]["adapted_summary"]["ensemble_event_macro_iou"] == 0.23


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
    assert "Masa por incendio" in html
    assert "WFIGS zero-shot" in html
    assert "Ensemble WFIGS" in html
    assert "Ensemble adaptado" in html
