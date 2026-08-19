#!/usr/bin/env python3
"""Freeze an auditable decision log before the new RCDA model touches TEST."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def register_pretest_decisions(
    *,
    work_root: Path,
    output_path: Path,
    repository_root: Path = ROOT,
    active_gcp_runner_sha256: str | None = None,
    active_gcp_bootstrap_sha256: str | None = None,
    numeric_recovery_summary: Path | None = None,
    kaggle_runtime_manifest: Path | None = None,
) -> dict[str, Any]:
    work_root = Path(work_root)
    final_artifacts = [
        work_root / "FINAL_SUMMARY.json",
        work_root / "FINAL_SUMMARY_PAPER_METRICS.json",
        work_root / "PAPER_SCORECARD.json",
    ]
    observed_final = [str(path) for path in final_artifacts if path.is_file()]
    if observed_final:
        raise ValueError(f"cannot register pre-TEST decisions after final artifacts: {observed_final}")
    phase1_matches = list(work_root.rglob("TUNING_SUMMARY.json"))
    if len(phase1_matches) != 1:
        raise FileNotFoundError(f"expected one phase-1 summary, found {phase1_matches}")
    phase1 = read_json(phase1_matches[0])
    ensemble_path = work_root / "PHASE1_VAL_ENSEMBLES.json"
    sampler_path = work_root / "TRAIN_SAMPLER_AUDIT.json"
    ensemble = read_json(ensemble_path)
    sampler = read_json(sampler_path)
    if phase1.get("test_evaluated") is not False:
        raise ValueError("phase-1 summary is not TEST-isolated")
    if not (
        ensemble.get("selection_split") == "val"
        and ensemble.get("test_evaluated") is False
        and ensemble.get("test_used_for_selection") is False
    ):
        raise ValueError("ensemble decision is not VAL-only")
    if not (
        sampler.get("analysis_split") == "train"
        and sampler.get("validation_evaluated") is False
        and sampler.get("test_evaluated") is False
    ):
        raise ValueError("sampler decision is not TRAIN-only")

    code_relpaths = (
        "wildfire_front/ml/rcda_sealed.py",
        "scripts/salvage_rcda_numeric_failure.py",
        "scripts/gcp_salvage_rcda_numeric_failure.sh",
        "scripts/run_rcda_kaggle_alt_continuation.py",
        "scripts/push_rcda_paper_stage2_kaggle.py",
        "scripts/run_rcda_gcp_paper_continuation.py",
        "scripts/analyze_rcda_paper_tuning.py",
        "scripts/push_rcda_paper_final_kaggle.py",
        "wildfire_front/ml/wfigs_domain_adapt.py",
        "wildfire_front/ml/wfigs_external_eval.py",
    )
    code_hashes = {
        path: sha256_file(Path(repository_root) / path) for path in code_relpaths
    }
    recovery = None
    if numeric_recovery_summary is not None:
        numeric_recovery_summary = Path(numeric_recovery_summary)
        recovery_summary = read_json(numeric_recovery_summary)
        if not (
            recovery_summary.get("selection_split") == "val"
            and recovery_summary.get("test_evaluated") is False
            and recovery_summary.get("test_used_for_selection") is False
        ):
            raise ValueError("numeric recovery summary is not VAL-only")
        recovery = {
            "summary_sha256": sha256_file(numeric_recovery_summary),
            "numeric_failure": recovery_summary.get("numeric_failure"),
            "ranking": recovery_summary.get("ranking"),
        }
    kaggle_runtime = None
    if kaggle_runtime_manifest is not None:
        kaggle_runtime_manifest = Path(kaggle_runtime_manifest)
        runtime_document = read_json(kaggle_runtime_manifest)
        runtime_rows = runtime_document.get("runs") or []
        if not (
            runtime_document.get("test_evaluated") is False
            and runtime_rows
            and all(
                row.get("selection_split") == "val"
                and row.get("test_evaluated") is False
                and row.get("runner_sha256")
                for row in runtime_rows
            )
        ):
            raise ValueError("Kaggle runtime manifest is not VAL-only")
        kaggle_runtime = {
            "manifest_sha256": sha256_file(kaggle_runtime_manifest),
            "account": runtime_document.get("account"),
            "runs": runtime_rows,
        }
    decision = ensemble.get("decision") or {}
    strategies = {
        str(row.get("name")): row for row in sampler.get("strategies") or []
    }
    report = {
        "schema": "wfd_rcda_pretest_decision_log_v1",
        "registered_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "new_candidate_test_evaluated": False,
        "test_used_for_model_selection": False,
        "known_test_context": (
            "Historical learned and geometric comparator TEST scores predate this "
            "campaign; no new candidate checkpoint has been evaluated on TEST."
        ),
        "evidence": {
            "phase1_summary_sha256": sha256_file(phase1_matches[0]),
            "val_ensemble_sha256": sha256_file(ensemble_path),
            "train_sampler_audit_sha256": sha256_file(sampler_path),
            "phase1_val_leader": (phase1.get("ranking") or [{}])[0],
            "ensemble_decision": decision,
            "default_event_mass_cv": (
                strategies.get("default_size_event_half") or {}
            ).get("event_probability_mass_cv"),
            "uniform_event_mass_cv": (
                strategies.get("uniform_events") or {}
            ).get("event_probability_mass_cv"),
            "train_samples_with_any_t0_loss": (
                sampler.get("transition_geometry") or {}
            ).get("samples_with_any_t0_loss"),
            "numeric_failure_recovery": recovery,
            "kaggle_validation_runtime": kaggle_runtime,
        },
        "conditional_validation_sequence": [
            "resunet_hybrid_long_v2",
            "resunet_hybrid_precision_v3",
            "resunet_hybrid_low_lr_v2 if best VAL < 0.20",
            "resunet_growth_v1 if best VAL < 0.20",
            "resunet_hybrid_event_balanced_v1 if best VAL < 0.20",
            "resunet_hybrid_uniform_events_v1 if best VAL < 0.20",
            "film_growth_v1 if best VAL < 0.20",
        ],
        "decisions": {
            "cross_architecture_ensemble": "rejected_on_validation",
            "uniform_event_sampler": "registered_as_conditional_validation_ablation",
            "adapted_wfigs_seed_ensemble": "secondary_analysis_only",
            "numeric_stability_hotfix": {
                "trigger": "non-finite training loss observed at long-run epoch 16",
                "data_finiteness_scan": "13002 TRAIN NPY files; zero non-finite files",
                "recovery": "retain and VAL-re-evaluate last finite checkpoint",
                "future_runs": "stop optimization immediately on non-finite loss, retain only a verified finite VAL checkpoint, fail on non-finite CPU gradients, let GradScaler skip AMP overflow steps, and clip gradient norm at 5.0",
                "test_evaluated": False,
            },
            "rcda_final_seeds": [11, 29, 47],
            "rcda_final_primary_endpoint": "mean_seed_event_macro_growth_iou",
        },
        "code_sha256": code_hashes,
        "active_gcp_runtime_sha256": {
            "run_rcda_paper_stage2.py": active_gcp_runner_sha256,
            "gcp_run_rcda_stage2.sh": active_gcp_bootstrap_sha256,
        },
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819",
    )
    parser.add_argument("--active-gcp-runner-sha256")
    parser.add_argument("--active-gcp-bootstrap-sha256")
    parser.add_argument(
        "--numeric-recovery-summary",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_gcp_stage2_20260819/rcda_paper_stage2/TUNING_SUMMARY.json",
    )
    parser.add_argument("--kaggle-runtime-manifest", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "outputs/ml_eval/rcda_paper_nightwatch_20260819/PRETEST_DECISION_LOG.json",
    )
    args = parser.parse_args()
    report = register_pretest_decisions(
        work_root=args.work_root,
        output_path=args.output,
        active_gcp_runner_sha256=args.active_gcp_runner_sha256,
        active_gcp_bootstrap_sha256=args.active_gcp_bootstrap_sha256,
        numeric_recovery_summary=args.numeric_recovery_summary,
        kaggle_runtime_manifest=args.kaggle_runtime_manifest,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
