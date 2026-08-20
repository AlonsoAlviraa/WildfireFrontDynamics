"""Compact, honest status surface for the sealed RCDA paper experiment.

The product SPA consumes this module as read-only evidence.  It deliberately
does not start jobs, select models, or infer missing scores.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PHASE_LABELS = {
    "validation_only_tuning": "Fase 1 · arquitecturas en VAL",
    "validation_only_stage2": "Fase 2 · ablaciones en VAL",
    "validation_only_stage2_gcp": "Fase 2 · continuación adaptativa en VAL (GCP)",
    "validation_only_stage2_precision_gcp": "Fase 2 · balance precisión/recall en VAL (GCP)",
    "validation_only_stage2_low_lr_gcp": "Fase 2 · continuación LR bajo en VAL (GCP)",
    "validation_only_stage2_growth_gcp": "Fase 2 · ablación growth-only en VAL (GCP)",
    "validation_only_stage2_event_balanced_gcp": "Fase 2 · muestreo por incendio en VAL (GCP)",
    "validation_only_stage2_uniform_events_gcp": "Fase 2 · masa uniforme por incendio en VAL (GCP)",
    "validation_only_stage2_film_gcp": "Fase 2 · condicionamiento físico FiLM en VAL (GCP)",
    "validation_only_stage2_precision_kaggle": "Fase 2 · balance precisión/recall en VAL (Kaggle T4)",
    "validation_only_stage2_low_lr_kaggle": "Fase 2 · LR bajo en VAL (Kaggle T4)",
    "validation_only_stage2_growth_kaggle": "Fase 2 · growth-only en VAL (Kaggle T4)",
    "validation_only_stage2_growth_low_lr_kaggle": "Fase 2 · growth-only con LR bajo en VAL (Kaggle T4)",
    "validation_only_stage2_event_balanced_kaggle": "Fase 2 · muestreo por incendio en VAL (Kaggle T4)",
    "validation_only_stage2_uniform_events_kaggle": "Fase 2 · masa uniforme por incendio en VAL (Kaggle T4)",
    "validation_only_stage2_multitask_uniform_kaggle": "Fase 2 · crecimiento/extensión multitarea en VAL (Kaggle T4)",
    "validation_only_stage2_multitask_front_ring_kaggle": "Fase 2 · frente activo multitarea en VAL (Kaggle T4)",
    "validation_only_stage2_film_kaggle": "Fase 2 · condicionamiento físico FiLM en VAL (Kaggle T4)",
    "recipe_frozen": "Receta congelada",
    "preregistered_final_test": "TEST final · semillas preregistradas",
    "preregistered_final_test_gcp": "TEST final · 3 semillas preregistradas (GCP)",
    "preregistered_final_test_kaggle": "TEST final · 3 semillas preregistradas (Kaggle T4)",
    "complete": "Evaluación final terminada",
}

VALIDATION_RUN_ORDER = (
    "resunet_hybrid_precision_v3",
    "resunet_hybrid_low_lr_v2",
    "resunet_growth_v1",
    "resunet_growth_low_lr_v1",
    "resunet_hybrid_event_balanced_v1",
    "resunet_hybrid_uniform_events_v1",
    "resunet_multitask_uniform_events_v1",
    "resunet_multitask_front_ring_v1",
    "film_growth_v1",
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _relative(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


def _latest_nightwatch(root: Path) -> Path | None:
    candidates = sorted((root / "outputs" / "ml_eval").glob("rcda_paper_nightwatch_*"))
    return candidates[-1] if candidates else None


def _manifest_summary(root: Path) -> dict[str, Any]:
    protocol = root / "data" / "external" / "rcda_net_full" / "protocol"
    splits: dict[str, dict[str, int]] = {}
    all_events: set[str] = set()
    disjoint = True
    for name in ("train", "val", "test"):
        document = _read_json(protocol / f"{name}.json") or {}
        events = {str(event) for event in document.get("events") or []}
        if all_events.intersection(events):
            disjoint = False
        all_events.update(events)
        splits[name] = {
            "events": int(document.get("n_events") or len(events)),
            "samples": int(document.get("n_samples") or 0),
        }
        disjoint = disjoint and document.get("event_disjoint") is True
    normalization = _read_json(protocol / "normalization_train_only.json") or {}
    return {
        "splits": splits,
        "events": sum(row["events"] for row in splits.values()),
        "samples": sum(row["samples"] for row in splits.values()),
        "event_disjoint": disjoint,
        "normalization_train_only": normalization.get("fit_split") == "train",
    }


def _baseline_summary(root: Path) -> dict[str, Any] | None:
    path = root / "outputs" / "ml_eval" / "rcda_sealed_baselines" / "dilated_copy.json"
    document = _read_json(path)
    if not document:
        return None
    test = document.get("test") or {}
    growth = test.get("growth_ring_result") or {}
    learned_path = root / "outputs/ml_eval/rcda_sealed_baselines/learned_baselines.json"
    learned = _read_json(learned_path) or {}
    learned_rows = []
    for report in learned.get("reports") or []:
        learned_test = report.get("test") or {}
        if learned_test.get("event_macro_iou") is not None:
            learned_rows.append(
                {
                    "name": str(report.get("model_name") or "learned"),
                    "event_macro_iou": float(learned_test["event_macro_iou"]),
                }
            )
    strongest = max(learned_rows, key=lambda row: row["event_macro_iou"], default=None)
    return {
        "name": "Copia dilatada",
        "event_macro_iou": test.get("event_macro_growth_iou"),
        "pooled_iou": growth.get("iou"),
        "events": test.get("events"),
        "path": _relative(path, root),
        "strongest_learned": strongest,
        "learned_reproduced": bool(learned_rows),
        "learned_path": _relative(learned_path, root) if learned_rows else None,
    }


def _experiment_queue(
    runtime_runs: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    status: str,
    phase: str,
    completed_run_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    completed_run_names = completed_run_names or set()
    by_name = {
        str(row.get("run_name")): row
        for row in runtime_runs
        if isinstance(row, dict) and row.get("run_name")
    }
    active_name = next(
        (
            name
            for name, row in by_name.items()
            if row.get("kernel") == state.get("kernel")
            and status in {"running", "queued"}
        ),
        None,
    )
    active_index = (
        VALIDATION_RUN_ORDER.index(active_name)
        if active_name in VALIDATION_RUN_ORDER
        else None
    )
    validation_finished = phase in {
        "recipe_frozen",
        "preregistered_final_test",
        "preregistered_final_test_gcp",
        "preregistered_final_test_kaggle",
        "complete",
    }
    queue = []
    for index, run_name in enumerate(VALIDATION_RUN_ORDER):
        row = by_name.get(run_name) or {}
        if run_name == active_name:
            run_status = "active"
        elif row.get("recovered_finite_checkpoint"):
            run_status = "recovered"
        elif run_name in completed_run_names:
            run_status = "completed"
        elif not row:
            run_status = "planned"
        elif validation_finished or (active_index is not None and index < active_index):
            run_status = "completed"
        else:
            run_status = "submitted"
        queue.append(
            {
                "run_name": run_name,
                "kernel": row.get("kernel"),
                "status": run_status,
                "test_evaluated": False,
            }
        )
    return queue


def _wfigs_summary(root: Path) -> dict[str, Any]:
    history = root / "data/open_if/wfigs_history_2020_2026"
    enrichment_path = history / "enrichment/INVENTORY.json"
    enrichment = _read_json(enrichment_path) or {}
    enrichment_counts = enrichment.get("counts") or {}
    campaigns = sorted((root / "outputs/ml_eval").glob("wfigs_training_campaign_*"))
    campaign_root = campaigns[-1] if campaigns else None
    campaign_path = campaign_root / "INVENTORY.json" if campaign_root else None
    campaign = _read_json(campaign_path) if campaign_path else None
    state_path = campaign_root / "STATE.json" if campaign_root else None
    campaign_state = _read_json(state_path) if state_path else None
    counts = (campaign or {}).get("counts") or {}
    state_rows = (campaign_state or {}).get("rows") or []
    state_materialized = sum(
        int((row.get("counts") or {}).get("pairs_materialized") or 0)
        for row in state_rows
    )
    state_ready = sum(
        int((row.get("counts") or {}).get("training_ready") or 0)
        for row in state_rows
    )
    dataset_roots = sorted((root / "outputs/ml_eval").glob("wfigs_tensor_dataset_*"))
    complete_dataset_roots = [
        candidate
        for candidate in dataset_roots
        if (candidate / "DATASET_REPORT.json").is_file()
    ]
    dataset_root = (
        complete_dataset_roots[-1]
        if complete_dataset_roots
        else (dataset_roots[-1] if dataset_roots else None)
    )
    active_dataset_root = dataset_roots[-1] if dataset_roots else None
    data_state_path = (
        active_dataset_root / "NIGHTWATCH_STATE.json"
        if active_dataset_root
        else None
    )
    data_state = _read_json(data_state_path) if data_state_path else None
    dataset_report_path = dataset_root / "DATASET_REPORT.json" if dataset_root else None
    dataset_report = _read_json(dataset_report_path) if dataset_report_path else None
    dataset_counts = (dataset_report or {}).get("counts") or {}
    dataset_by_split = dataset_counts.get("by_split") or {}
    audit_path = dataset_root / "DATASET_AUDIT.json" if dataset_root else None
    audit = _read_json(audit_path) if audit_path else None
    audit_counts = (audit or {}).get("counts") or {}
    audit_checks = (audit or {}).get("checks") or {}
    external_roots = [
        candidate
        for candidate in dataset_roots
        if (candidate / "WFIGS_EXTERNAL_EVAL.json").is_file()
        or (candidate / "EXTERNAL_NIGHTWATCH_STATE.json").is_file()
    ]
    external_root = external_roots[-1] if external_roots else dataset_root
    external_path = (
        external_root / "WFIGS_EXTERNAL_EVAL.json" if external_root else None
    )
    external = _read_json(external_path) if external_path else None
    external_state_path = (
        external_root / "EXTERNAL_NIGHTWATCH_STATE.json" if external_root else None
    )
    external_state = _read_json(external_state_path) if external_state_path else None
    test_campaigns = sorted(
        (root / "outputs/ml_eval").glob("wfigs_test_campaign_*")
    )
    test_campaign_root = test_campaigns[-1] if test_campaigns else None
    test_state_path = test_campaign_root / "STATE.json" if test_campaign_root else None
    test_state = _read_json(test_state_path) if test_state_path else None
    adaptation_roots = sorted((root / "outputs/ml_eval").glob("wfigs_domain_adaptation_*"))
    adaptation_root = adaptation_roots[-1] if adaptation_roots else None
    adaptation_state_path = adaptation_root / "STATE.json" if adaptation_root else None
    adaptation_state = (
        _read_json(adaptation_state_path) if adaptation_state_path else None
    )
    adapted_path = adaptation_root / "WFIGS_ADAPTED_TEST_EVAL.json" if adaptation_root else None
    adapted = _read_json(adapted_path) if adapted_path else None
    external_protocol = (external or {}).get("protocol") or {}
    adapted_protocol = (adapted or {}).get("protocol") or {}
    campaign_incomplete = bool(campaign_state) and int(
        (campaign_state or {}).get("groups_complete") or 0
    ) < int((campaign_state or {}).get("groups_total") or 0)
    data_active = bool(data_state) and (data_state or {}).get("phase") != "complete"
    return {
        "pairs_enriched": int(enrichment_counts.get("pairs") or 0),
        "pairs_hrrr_space_time_valid": int(
            enrichment_counts.get("pairs_hrrr_available_by_t0_and_full_window") or 0
        ),
        "pairs_outside_hrrr_conus": int(
            enrichment_counts.get("pairs_outside_hrrr_conus_domain") or 0
        ),
        "spatial_weather_contract": bool(
            (enrichment.get("contracts") or {}).get(
                "hrrr_spatial_domain_verified_from_t0_bbox"
            )
        ),
        "campaign_running": campaign_incomplete or data_active,
        "campaign_groups_complete": int((campaign_state or {}).get("groups_complete") or 0),
        "campaign_groups_total": int((campaign_state or {}).get("groups_total") or 0),
        "tensors_materialized": max(
            int(counts.get("pairs_materialized") or 0), state_materialized
        ),
        "tensors_training_ready": max(
            int(counts.get("pairs_training_ready") or 0),
            state_ready,
            int(dataset_counts.get("samples_written") or 0),
        ),
        "train_tensors": int(dataset_by_split.get("train") or 0),
        "validation_tensors": int(dataset_by_split.get("validation") or 0),
        "test_tensors": int(dataset_by_split.get("test") or 0),
        "test_groups_complete": int((test_state or {}).get("groups_complete") or 0),
        "test_groups_total": int((test_state or {}).get("groups_total") or 0),
        "test_materialization_phase": (external_state or {}).get("phase"),
        "dataset_phase": (data_state or {}).get("phase"),
        "adaptation_phase": (adaptation_state or {}).get("phase"),
        "dataset_audit_status": (audit or {}).get("status"),
        "dataset_audit_samples": int(audit_counts.get("samples_audited") or 0),
        "dataset_audit_issues": int(audit_counts.get("issues") or 0),
        "dataset_event_disjoint": audit_checks.get("event_disjoint"),
        "dataset_normalization_train_only": audit_checks.get(
            "normalization_recomputed_from_train_only"
        ),
        "external_evaluation_executed": bool(external),
        "external_test_used_for_selection": external_protocol.get(
            "wfigs_test_used_for_selection"
        ),
        "external_summary": (external or {}).get("summary"),
        "adapted_evaluation_executed": bool(adapted),
        "adapted_test_used_for_selection": adapted_protocol.get(
            "wfigs_test_used_for_selection"
        ),
        "adapted_summary": (adapted or {}).get("summary"),
        "enrichment_artifact": _relative(enrichment_path, root),
        "campaign_artifact": _relative(
            campaign_path if campaign_path and campaign_path.is_file() else state_path,
            root,
        ),
        "dataset_artifact": _relative(
            dataset_report_path
            if dataset_report_path and dataset_report_path.is_file()
            else data_state_path,
            root,
        ),
        "dataset_audit_artifact": _relative(
            audit_path if audit_path and audit_path.is_file() else None,
            root,
        ),
        "external_artifact": _relative(
            external_path if external_path and external_path.is_file() else None,
            root,
        ),
        "adapted_artifact": _relative(
            adapted_path if adapted_path and adapted_path.is_file() else None,
            root,
        ),
    }


def build_research_status(repo_root: Path | str) -> dict[str, Any]:
    """Return a small UI-safe snapshot of the latest paper experiment."""

    root = Path(repo_root)
    work = _latest_nightwatch(root)
    state_path = work / "STATE.json" if work else None
    state = _read_json(state_path) if state_path else None
    state = state or {}
    gcp_stage_roots = sorted((root / "outputs/ml_eval").glob("rcda_gcp_stage2_*"))
    gcp_stage_state = (
        _read_json(gcp_stage_roots[-1] / "STATE.json") if gcp_stage_roots else None
    ) or {}
    frozen_path = work / "FROZEN_RECIPE.json" if work else None
    frozen = _read_json(frozen_path) if frozen_path else None
    tuning_paths = list(work.rglob("TUNING_SUMMARY.json")) if work else []
    tuning_path = tuning_paths[0] if len(tuning_paths) == 1 else None
    tuning = _read_json(tuning_path) if tuning_path else None
    validation_scorecard_path = work / "VALIDATION_SCORECARD.json" if work else None
    if validation_scorecard_path and not validation_scorecard_path.is_file():
        validation_scorecard_path = work / "PHASE1_VALIDATION_SCORECARD.json"
    validation_scorecard = (
        _read_json(validation_scorecard_path) if validation_scorecard_path else None
    )
    if validation_scorecard and not (
        validation_scorecard.get("selection_split") == "val"
        and validation_scorecard.get("test_evaluated") is False
        and validation_scorecard.get("test_used_for_selection") is False
    ):
        validation_scorecard = None
    validation_ranking = (validation_scorecard or {}).get("ranking") or []
    validation_leader = validation_ranking[0] if validation_ranking else {}
    validation_runner_up = validation_ranking[1] if len(validation_ranking) > 1 else {}
    validation_ensemble_path = (
        work / "LOW_LR_WEIGHTED_VAL_ENSEMBLES.json" if work else None
    )
    if validation_ensemble_path and not validation_ensemble_path.is_file():
        validation_ensemble_path = work / "LOW_LR_VAL_ENSEMBLES.json"
    if validation_ensemble_path and not validation_ensemble_path.is_file():
        validation_ensemble_path = work / "PHASE1_VAL_ENSEMBLES.json"
    validation_ensemble_report = (
        _read_json(validation_ensemble_path) if validation_ensemble_path else None
    )
    if validation_ensemble_report and not (
        validation_ensemble_report.get("selection_split") == "val"
        and validation_ensemble_report.get("test_evaluated") is False
        and validation_ensemble_report.get("test_used_for_selection") is False
    ):
        validation_ensemble_report = None
    validation_ensemble_ranking = (
        (validation_ensemble_report or {}).get("ranking") or []
    )
    validation_ensemble_best = next(
        (
            row
            for row in validation_ensemble_ranking
            if len(row.get("members") or []) > 1
        ),
        None,
    )
    validation_ensemble_decision = (
        (validation_ensemble_report or {}).get("decision") or {}
    )
    validation_ensemble_paired_path = (
        work / "LOW_LR_WEIGHTED_VAL_ENSEMBLES_PAIRED.json" if work else None
    )
    validation_ensemble_paired_report = (
        _read_json(validation_ensemble_paired_path)
        if validation_ensemble_paired_path
        and validation_ensemble_paired_path.is_file()
        else None
    )
    if validation_ensemble_paired_report and not (
        validation_ensemble_paired_report.get("selection_split") == "val"
        and validation_ensemble_paired_report.get("test_evaluated") is False
        and validation_ensemble_paired_report.get("test_used_for_selection") is False
    ):
        validation_ensemble_paired_report = None
    validation_ensemble_paired = (
        (validation_ensemble_paired_report or {}).get("decision", {}).get(
            "paired_validation"
        )
        or {}
    )
    validation_postprocess_path = work / "LOW_LR_POSTPROCESS_VAL.json" if work else None
    validation_postprocess = (
        _read_json(validation_postprocess_path) if validation_postprocess_path else None
    )
    if validation_postprocess and not (
        validation_postprocess.get("selection_split") == "val"
        and validation_postprocess.get("test_evaluated") is False
    ):
        validation_postprocess = None
    validation_postprocess_best = (validation_postprocess or {}).get("best") or {}
    validation_reproducibility_path = (
        work / "LOW_LR_REPRODUCIBILITY.json" if work else None
    )
    validation_reproducibility = (
        _read_json(validation_reproducibility_path)
        if validation_reproducibility_path
        else None
    )
    if validation_reproducibility and not (
        validation_reproducibility.get("selection_split") == "val"
        and validation_reproducibility.get("test_evaluated") is False
        and validation_reproducibility.get("test_used_for_selection") is False
    ):
        validation_reproducibility = None
    validation_strata_path = (
        work / "LOW_LR_VALIDATION_STRATA.json" if work else None
    )
    validation_strata = (
        _read_json(validation_strata_path) if validation_strata_path else None
    )
    if validation_strata and not (
        validation_strata.get("selection_split") == "val"
        and validation_strata.get("test_evaluated") is False
        and validation_strata.get("test_used_for_selection") is False
    ):
        validation_strata = None
    postprocess_checkpoint = str((validation_postprocess or {}).get("checkpoint") or "")
    postprocess_source = next(
        (
            row
            for row in validation_ranking
            if str(row.get("run_name") or "") in postprocess_checkpoint
        ),
        {},
    )
    train_sampler_path = work / "TRAIN_SAMPLER_AUDIT.json" if work else None
    train_sampler_report = _read_json(train_sampler_path) if train_sampler_path else None
    if train_sampler_report and not (
        train_sampler_report.get("analysis_split") == "train"
        and train_sampler_report.get("validation_evaluated") is False
        and train_sampler_report.get("test_evaluated") is False
    ):
        train_sampler_report = None
    train_sampler_strategies = {
        str(row.get("name")): row
        for row in (train_sampler_report or {}).get("strategies") or []
    }
    pretest_decision_path = work / "PRETEST_DECISION_LOG.json" if work else None
    pretest_decision = _read_json(pretest_decision_path) if pretest_decision_path else None
    pretest_registered = bool(
        pretest_decision
        and pretest_decision.get("new_candidate_test_evaluated") is False
        and pretest_decision.get("test_used_for_model_selection") is False
    )
    numeric_recovery = (
        ((pretest_decision or {}).get("evidence") or {}).get(
            "numeric_failure_recovery"
        )
        or {}
    )
    numeric_failure = numeric_recovery.get("numeric_failure") or {}
    numeric_ranking = numeric_recovery.get("ranking") or []
    numeric_hotfix = (
        ((pretest_decision or {}).get("decisions") or {}).get(
            "numeric_stability_hotfix"
        )
        or {}
    )
    runtime_manifest_path = work / "KAGGLE_RUNTIME_MANIFEST.json" if work else None
    runtime_manifest = (
        _read_json(runtime_manifest_path) if runtime_manifest_path else None
    ) or {}
    runtime_runs = runtime_manifest.get("runs") or []
    active_runtime = next(
        (
            row
            for row in reversed(runtime_runs)
            if isinstance(row, dict) and row.get("kernel") == state.get("kernel")
        ),
        {},
    )
    scorecard_path = work / "PAPER_SCORECARD.json" if work else None
    scorecard = _read_json(scorecard_path) if scorecard_path else None
    validation_figure_path = (
        root / "docs/figures/rcda_validation_evidence_20260819.svg"
    )

    phase = str(state.get("phase") or "not_started")
    winner = (frozen or {}).get("winner") or state.get("winner") or None
    if winner is None and validation_leader:
        winner = {
            "val_event_macro_iou": validation_leader.get("event_macro_iou"),
            "val_pooled_iou": validation_leader.get("pooled_iou"),
            "selected_threshold": validation_leader.get("selected_threshold"),
            "best_epoch": validation_leader.get("best_epoch"),
            "config": {"run_name": validation_leader.get("run_name")},
        }
    elif winner is None and tuning:
        leader = ((tuning.get("ranking") or [None])[0])
        if isinstance(leader, dict):
            winner = {
                "val_event_macro_iou": leader.get("val_event_macro_iou"),
                "val_pooled_iou": leader.get("val_pooled_iou"),
                "selected_threshold": leader.get("threshold"),
                "best_epoch": leader.get("best_epoch"),
                "config": {"run_name": leader.get("run_name")},
            }
    primary = (scorecard or {}).get("primary") or None
    ensemble = (scorecard or {}).get("ensemble") or None
    decoder = (scorecard or {}).get("decoder") or None
    gates = (scorecard or {}).get("gate") or None
    status = str(state.get("status") or state.get("kernel_status") or "pending")
    if scorecard:
        status = str(scorecard.get("status") or "complete")
    completed_val_scores = [
        float(value)
        for value in (
            state.get("best_completed_val_event_macro_iou"),
            validation_leader.get("event_macro_iou"),
        )
        if value is not None
    ]
    best_completed_val = max(completed_val_scores) if completed_val_scores else None

    wfigs = _wfigs_summary(root)
    progress_state = gcp_stage_state if phase == "validation_only_stage2_gcp" else state
    return {
        "schema": "wfd_rcda_research_status_v1",
        "available": bool(work),
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, "Experimento aún no iniciado"),
        "status": status,
        "updated_at": state.get("updated_at"),
        "training_live": status in {"running", "queued"},
        "execution_backend": (
            "gcp_cpu_spot"
            if phase
            in {
                "validation_only_stage2_gcp",
                "validation_only_stage2_precision_gcp",
                "validation_only_stage2_low_lr_gcp",
                "validation_only_stage2_growth_gcp",
                "validation_only_stage2_event_balanced_gcp",
                "validation_only_stage2_uniform_events_gcp",
                "validation_only_stage2_film_gcp",
                "preregistered_final_test_gcp",
            }
            else "kaggle_gpu"
            if phase in {
                "validation_only_tuning",
                "validation_only_stage2",
                "preregistered_final_test",
                "validation_only_stage2_precision_kaggle",
                "validation_only_stage2_low_lr_kaggle",
                "validation_only_stage2_growth_kaggle",
                "validation_only_stage2_growth_low_lr_kaggle",
                "validation_only_stage2_event_balanced_kaggle",
                "validation_only_stage2_uniform_events_kaggle",
                "validation_only_stage2_multitask_uniform_kaggle",
                "validation_only_stage2_multitask_front_ring_kaggle",
                "validation_only_stage2_film_kaggle",
                "preregistered_final_test_kaggle",
            }
            else None
        ),
        "training_progress": (
            {
                "run": active_runtime.get("run_name")
                or state.get("active_validation_run"),
                "seed": progress_state.get("active_seed"),
                "epoch": progress_state.get("checkpoint_epoch"),
                "train_loss": progress_state.get("train_loss"),
                "val_f1_at_0_5": progress_state.get("val_f1_at_0_5"),
                "val_event_macro_iou": progress_state.get("val_event_macro_iou"),
                "val_selection_threshold": progress_state.get(
                    "val_selection_threshold"
                ),
                "spot_restarts": progress_state.get("spot_restarts", 0),
                "remote_status": state.get("kernel_status"),
                "best_completed_val_event_macro_iou": state.get(
                    "best_completed_val_event_macro_iou"
                )
                if best_completed_val is None
                else best_completed_val,
                "registered_runs": len(runtime_runs),
                "recovered_runs": sum(
                    bool(row.get("recovered_finite_checkpoint"))
                    for row in runtime_runs
                    if isinstance(row, dict)
                ),
                "test_evaluated": runtime_manifest.get("test_evaluated"),
            }
            if phase
            in {
                "validation_only_tuning",
                "validation_only_stage2",
                "validation_only_stage2_gcp",
                "validation_only_stage2_precision_gcp",
                "validation_only_stage2_low_lr_gcp",
                "validation_only_stage2_growth_gcp",
                "validation_only_stage2_event_balanced_gcp",
                "validation_only_stage2_uniform_events_gcp",
                "validation_only_stage2_film_gcp",
                "validation_only_stage2_precision_kaggle",
                "validation_only_stage2_low_lr_kaggle",
                "validation_only_stage2_growth_kaggle",
                "validation_only_stage2_growth_low_lr_kaggle",
                "validation_only_stage2_event_balanced_kaggle",
                "validation_only_stage2_uniform_events_kaggle",
                "validation_only_stage2_multitask_uniform_kaggle",
                "validation_only_stage2_multitask_front_ring_kaggle",
                "validation_only_stage2_film_kaggle",
                "preregistered_final_test_gcp",
                "preregistered_final_test_kaggle",
            }
            and (state or gcp_stage_state)
            else None
        ),
        "protocol": {
            **_manifest_summary(root),
            "selection_split": "val",
            "test_used_for_selection": False,
            "final_seeds": [11, 29, 47],
            "pretest_decisions_registered": pretest_registered,
        },
        "baseline": _baseline_summary(root),
        "wfigs": wfigs,
        "validation_winner": (
            {
                "run_name": ((winner.get("config") or {}).get("run_name")),
                "model_name": ((winner.get("config") or {}).get("model_name")),
                "event_macro_iou": winner.get("val_event_macro_iou"),
                "pooled_iou": winner.get("val_pooled_iou"),
                "threshold": winner.get("selected_threshold"),
                "best_epoch": winner.get("best_epoch"),
                "frozen": bool(frozen),
                "event_bootstrap_95_ci": validation_leader.get("event_bootstrap_95_ci"),
                "delta_vs_runner_up": validation_runner_up.get(
                    "leader_minus_candidate_paired_delta"
                ),
                "delta_vs_runner_up_95_ci": validation_runner_up.get(
                    "leader_minus_candidate_bootstrap_95_ci"
                ),
            }
            if isinstance(winner, dict)
            else None
        ),
        "validation_candidates": [
            {
                "rank": row.get("rank"),
                "run_name": row.get("run_name"),
                "event_macro_iou": row.get("event_macro_iou"),
                "event_median_iou": row.get("event_median_iou"),
                "event_bootstrap_95_ci": row.get("event_bootstrap_95_ci") or [],
                "delta_from_leader": row.get(
                    "leader_minus_candidate_paired_delta"
                ),
                "delta_from_leader_95_ci": row.get(
                    "leader_minus_candidate_bootstrap_95_ci"
                )
                or [],
                "leader_wins_event_fraction": row.get(
                    "leader_wins_event_fraction"
                ),
                "threshold": row.get("selected_threshold"),
                "best_epoch": row.get("best_epoch"),
            }
            for row in validation_ranking[:8]
            if isinstance(row, dict)
        ],
        "validation_evidence": {
            "events": (validation_scorecard or {}).get("events"),
            "candidate_count": len(validation_ranking),
            "bootstrap_resamples": (validation_scorecard or {}).get(
                "bootstrap_resamples"
            ),
            "uncertainty_unit": (validation_scorecard or {}).get(
                "uncertainty_unit"
            ),
            "selection_split": "val",
            "test_evaluated": False,
        },
        "experiment_queue": _experiment_queue(
            runtime_runs,
            state,
            status=status,
            phase=phase,
            completed_run_names={
                str(row.get("run_name"))
                for row in validation_ranking
                if isinstance(row, dict) and row.get("run_name")
            },
        ),
        "validation_ensemble": (
            {
                "name": validation_ensemble_best.get("name"),
                "members": validation_ensemble_best.get("members") or [],
                "event_macro_iou": validation_ensemble_best.get(
                    "event_macro_iou"
                ),
                "threshold": validation_ensemble_best.get("threshold"),
                "delta_vs_best_individual": validation_ensemble_decision.get(
                    "best_multi_minus_individual"
                ),
                "preregistered": validation_ensemble_decision.get(
                    "preregister_multi_model_ensemble"
                ),
                "paired_delta_95_ci": validation_ensemble_paired.get(
                    "event_bootstrap_95_ci"
                ),
                "paired_wins_event_fraction": validation_ensemble_paired.get(
                    "wins_event_fraction"
                ),
                "paired_events": validation_ensemble_paired.get("events"),
                "selection_split": "val",
                "test_evaluated": False,
            }
            if isinstance(validation_ensemble_best, dict)
            else None
        ),
        "validation_postprocess": (
            {
                "event_macro_iou": validation_postprocess_best.get(
                    "event_macro_iou"
                ),
                "pooled_iou": validation_postprocess_best.get("pooled_iou"),
                "threshold": validation_postprocess_best.get("threshold"),
                "dilation_radius_px": validation_postprocess_best.get(
                    "dilation_radius_px"
                ),
                "require_t0_connection": validation_postprocess_best.get(
                    "require_t0_connection"
                ),
                "delta_vs_raw": (
                    float(validation_postprocess_best["event_macro_iou"])
                    - float(postprocess_source["event_macro_iou"])
                    if validation_postprocess_best.get("event_macro_iou") is not None
                    and postprocess_source.get("event_macro_iou") is not None
                    else None
                ),
                "selection_split": "val",
                "test_evaluated": False,
            }
            if isinstance(validation_postprocess_best, dict)
            and validation_postprocess_best
            else None
        ),
        "validation_reproducibility": (
            {
                "run_name": validation_reproducibility.get("run_name"),
                "events": validation_reproducibility.get("events"),
                "checkpoint_exact": validation_reproducibility.get(
                    "checkpoint_exact"
                ),
                "metrics_exact": validation_reproducibility.get("metrics_exact"),
                "reproducible": validation_reproducibility.get("reproducible"),
                "max_absolute_event_iou_difference": validation_reproducibility.get(
                    "max_absolute_event_iou_difference"
                ),
                "checkpoint_sha256": (
                    validation_reproducibility.get("checkpoint_sha256") or {}
                ).get("first"),
                "selection_split": "val",
                "test_evaluated": False,
            }
            if validation_reproducibility
            else None
        ),
        "validation_strata": (
            {
                "run_name": validation_strata.get("run_name"),
                "events": validation_strata.get("events"),
                "duration_spearman": validation_strata.get(
                    "duration_spearman"
                ),
                "growth_support_spearman": validation_strata.get(
                    "growth_support_spearman"
                ),
                "duration_strata": validation_strata.get("duration_strata") or [],
                "growth_strata": validation_strata.get("growth_strata") or [],
                "selection_split": "val",
                "test_evaluated": False,
            }
            if validation_strata
            else None
        ),
        "training_sampler_audit": (
            {
                "samples": train_sampler_report.get("samples"),
                "events": train_sampler_report.get("events"),
                "zero_growth_fraction": train_sampler_report.get(
                    "observed_zero_growth_fraction"
                ),
                "samples_with_any_t0_loss": (
                    train_sampler_report.get("transition_geometry") or {}
                ).get("samples_with_any_t0_loss"),
                "default_event_mass_cv": (
                    train_sampler_strategies.get("default_size_event_half") or {}
                ).get("event_probability_mass_cv"),
                "uniform_event_mass_cv": (
                    train_sampler_strategies.get("uniform_events") or {}
                ).get("event_probability_mass_cv"),
                "validation_evaluated": False,
                "test_evaluated": False,
            }
            if isinstance(train_sampler_report, dict)
            else None
        ),
        "numeric_stability": {
            "failure_recovered": bool(numeric_recovery),
            "failed_epoch": numeric_failure.get("failed_epoch"),
            "checkpoint_epoch": numeric_failure.get("checkpoint_epoch"),
            "recovered_val_event_macro_iou": (
                numeric_ranking[0].get("val_event_macro_iou")
                if numeric_ranking and isinstance(numeric_ranking[0], dict)
                else None
            ),
            "train_files_scanned": (
                numeric_failure.get("train_npy_finiteness_scan") or {}
            ).get("files"),
            "nonfinite_train_files": (
                numeric_failure.get("train_npy_finiteness_scan") or {}
            ).get("nonfinite_files"),
            "max_grad_norm": 5.0 if numeric_hotfix else None,
            "future_runs_fail_fast": bool(numeric_hotfix),
            "test_evaluated": numeric_failure.get("test_evaluated"),
        },
        "final": (
            {
                "status": scorecard.get("status"),
                "events": scorecard.get("events"),
                "model_event_macro_iou": primary.get("model_mean"),
                "baseline_event_macro_iou": primary.get("dilated_copy"),
                "paired_delta": primary.get("paired_delta"),
                "paired_delta_ci": primary.get("paired_delta_event_bootstrap_95_ci"),
                "model_event_macro_ci": primary.get("event_bootstrap_95_ci"),
                "gates": gates,
                "ensemble_event_macro_iou": ensemble.get("event_macro_iou")
                if isinstance(ensemble, dict)
                else None,
                "ensemble_event_macro_ci": ensemble.get("event_bootstrap_95_ci")
                if isinstance(ensemble, dict)
                else None,
                "ensemble_vs_strongest_delta": (
                    (ensemble.get("vs_strongest_baseline") or {}).get(
                        "paired_delta"
                    )
                    if isinstance(ensemble, dict)
                    else None
                ),
                "ensemble_vs_strongest_delta_ci": (
                    (ensemble.get("vs_strongest_baseline") or {}).get(
                        "paired_delta_event_bootstrap_95_ci"
                    )
                    if isinstance(ensemble, dict)
                    else None
                ),
                "ensemble_role": ensemble.get("role")
                if isinstance(ensemble, dict)
                else None,
                "decoder_event_macro_iou": decoder.get("event_macro_iou")
                if isinstance(decoder, dict)
                else None,
                "decoder_role": decoder.get("role")
                if isinstance(decoder, dict)
                else None,
            }
            if scorecard and isinstance(primary, dict)
            else None
        ),
        "claims": {
            "paper_ready": bool(scorecard and scorecard.get("status") == "paper_model_candidate"),
            "external_generalization_proven": False,
            "wfigs_external_validation_pending": not wfigs[
                "external_evaluation_executed"
            ],
        },
        "artifacts": {
            "state": _relative(state_path, root),
            "tuning_summary": _relative(tuning_path, root),
            "validation_scorecard": _relative(
                validation_scorecard_path
                if validation_scorecard_path and validation_scorecard_path.is_file()
                else None,
                root,
            ),
            "validation_ensemble": _relative(
                validation_ensemble_path
                if validation_ensemble_path and validation_ensemble_path.is_file()
                else None,
                root,
            ),
            "validation_ensemble_paired": _relative(
                validation_ensemble_paired_path
                if validation_ensemble_paired_path
                and validation_ensemble_paired_path.is_file()
                else None,
                root,
            ),
            "validation_postprocess": _relative(
                validation_postprocess_path
                if validation_postprocess_path
                and validation_postprocess_path.is_file()
                else None,
                root,
            ),
            "validation_reproducibility": _relative(
                validation_reproducibility_path
                if validation_reproducibility_path
                and validation_reproducibility_path.is_file()
                else None,
                root,
            ),
            "validation_strata": _relative(
                validation_strata_path
                if validation_strata_path and validation_strata_path.is_file()
                else None,
                root,
            ),
            "validation_figure": _relative(
                validation_figure_path if validation_figure_path.is_file() else None,
                root,
            ),
            "training_sampler_audit": _relative(
                train_sampler_path
                if train_sampler_path and train_sampler_path.is_file()
                else None,
                root,
            ),
            "pretest_decision_log": _relative(
                pretest_decision_path
                if pretest_decision_path and pretest_decision_path.is_file()
                else None,
                root,
            ),
            "frozen_recipe": _relative(frozen_path, root)
            if frozen_path and frozen_path.is_file()
            else None,
            "scorecard": _relative(scorecard_path, root)
            if scorecard_path and scorecard_path.is_file()
            else None,
        },
    }


__all__ = ["build_research_status"]
