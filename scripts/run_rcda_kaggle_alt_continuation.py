#!/usr/bin/env python3
"""Run the sealed RCDA continuation on a private alternate Kaggle GPU account."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_rcda_paper_tuning import (  # noqa: E402
    freeze_recipe,
    merge_tuning_summaries,
)
from scripts.evaluate_rcda_paper_metrics import evaluate_final_checkpoints  # noqa: E402
from scripts.push_rcda_paper_final_kaggle import stage_kernel as stage_final_kernel  # noqa: E402
from scripts.push_rcda_paper_stage2_kaggle import self_contained_stage2_kernel  # noqa: E402
from scripts.register_rcda_pretest_decisions import register_pretest_decisions  # noqa: E402
from scripts.run_rcda_gcp_paper_continuation import (  # noqa: E402
    best_validation_score,
    validate_final_summary,
)
from scripts.summarize_rcda_paper_final import build_scorecard  # noqa: E402
from scripts.summarize_rcda_validation import build_validation_scorecard  # noqa: E402

ALT_OWNER = "alonsoalviraaaa"
DATASET_SOURCES = [
    "alonsoalvira/wfd-rcda-sealed",
    "alonsoalvira/wfd-rcda-archive",
]
RUNS: tuple[tuple[str, str, str], ...] = (
    ("resunet_hybrid_precision_v3", "wfd-rcda-precision-gpu-v1", "validation_only_stage2_precision_kaggle"),
    ("resunet_hybrid_low_lr_v2", "wfd-rcda-low-lr-gpu-v1", "validation_only_stage2_low_lr_kaggle"),
    ("resunet_growth_v1", "wfd-rcda-growth-gpu-v1", "validation_only_stage2_growth_kaggle"),
    ("resunet_growth_low_lr_v1", "wfd-rcda-growth-low-lr-gpu-v1", "validation_only_stage2_growth_low_lr_kaggle"),
    ("resunet_hybrid_event_balanced_v1", "wfd-rcda-event-balanced-gpu-v1", "validation_only_stage2_event_balanced_kaggle"),
    ("resunet_hybrid_uniform_events_v1", "wfd-rcda-uniform-events-gpu-v1", "validation_only_stage2_uniform_events_kaggle"),
    ("resunet_multitask_uniform_events_v1", "wfd-rcda-multitask-uniform-gpu-v1", "validation_only_stage2_multitask_uniform_kaggle"),
    ("resunet_multitask_front_ring_v1", "wfd-rcda-multitask-front-ring-gpu-v1", "validation_only_stage2_multitask_front_ring_kaggle"),
    ("film_growth_v1", "wfd-rcda-film-gpu-v1", "validation_only_stage2_film_kaggle"),
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def kaggle_env(config_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("KAGGLE_API_TOKEN", None)
    env.pop("KAGGLE_USERNAME", None)
    env.pop("KAGGLE_KEY", None)
    env["KAGGLE_CONFIG_DIR"] = str(config_dir)
    return env


def run(arguments: list[str], *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=check, capture_output=True, text=True, env=env)


def require_successful_kernel_push(
    result: subprocess.CompletedProcess[str],
    *,
    kernel: str,
) -> None:
    """Reject Kaggle CLI push errors even when the CLI incorrectly exits zero."""

    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "kernel push error:" in combined.lower():
        raise RuntimeError(f"Kaggle push failed for {kernel}: {combined[-1200:]}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def update_state(path: Path, **fields: Any) -> None:
    current: dict[str, Any] = {}
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    current.update(fields)
    current["updated_at"] = utc_now()
    write_json(path, current)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")],
        check=False,
        capture_output=True,
        text=True,
    )


def kernel_status(kernel: str, *, env: dict[str, str]) -> str:
    result = run(["kaggle", "kernels", "status", kernel], env=env, check=False)
    text = f"{result.stdout}\n{result.stderr}".upper()
    for status in ("COMPLETE", "ERROR", "CANCELLED", "RUNNING", "QUEUED"):
        if status in text:
            return status.lower()
    raise RuntimeError(f"cannot parse Kaggle status for {kernel}: {text[-500:]}")


def wait_for_kernel(
    kernel: str,
    *,
    phase: str,
    state_path: Path,
    env: dict[str, str],
    deadline: float,
    poll_seconds: int,
) -> None:
    while True:
        status = kernel_status(kernel, env=env)
        update_state(
            state_path,
            status="running",
            phase=phase,
            execution_backend="kaggle_alt_t4",
            kernel=kernel,
            kernel_status=status,
            test_used_for_selection=False,
            error=None,
            instance_stop_requested=False,
            active_validation_run=kernel.rsplit("/", 1)[-1],
            active_seed=None,
            checkpoint_epoch=None,
            train_loss=None,
            val_f1_at_0_5=None,
            val_event_macro_iou=None,
            val_selection_threshold=None,
            spot_restarts=0,
        )
        print(f"[{utc_now()}] {kernel}: {status}", flush=True)
        if status == "complete":
            return
        if status in {"error", "cancelled"}:
            raise RuntimeError(f"Kaggle kernel {kernel} ended with {status}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"deadline exceeded for {kernel}")
        time.sleep(max(30, poll_seconds))


def one_json(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one {name} below {root}, found {matches}")
    return matches[0]


def validate_single_run_val_summary(
    summary: dict[str, Any], expected_run: str
) -> bool:
    """Validate a single-run VAL artifact and normalize a legacy root flag.

    Early stage-2 runners recorded ``test_used_for_selection=False`` in the
    embedded report but omitted the same redundant flag at the summary root.
    Accept that legacy shape only when the sole embedded report independently
    proves that neither TEST evaluation nor TEST-based selection occurred.

    Returns ``True`` when the legacy root flag was added in memory.
    """
    ranking = summary.get("ranking") or []
    reports = summary.get("reports") or []
    if not (
        summary.get("selection_split") == "val"
        and summary.get("test_evaluated") is False
        and len(ranking) == 1
        and ranking[0].get("run_name") == expected_run
        and len(reports) == 1
        and reports[0].get("test_evaluated") is False
        and reports[0].get("test_used_for_selection") is False
        and reports[0].get("config", {}).get("run_name") == expected_run
    ):
        raise ValueError(f"invalid single-run VAL summary for {expected_run}")
    root_flag = summary.get("test_used_for_selection")
    if root_flag is False:
        return False
    if "test_used_for_selection" in summary:
        raise ValueError(f"TEST selection flag is not false for {expected_run}")
    summary["test_used_for_selection"] = False
    return True


def download_summary(
    kernel: str,
    output: Path,
    expected_run: str,
    *,
    env: dict[str, str],
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    run(["kaggle", "kernels", "output", kernel, "-p", str(output), "--force"], env=env)
    summary_path = one_json(output, "TUNING_SUMMARY.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    normalized = validate_single_run_val_summary(summary, expected_run)
    if normalized:
        write_json(summary_path, summary)
    return summary_path


def refresh_interim_validation(
    tuning_paths: list[Path], work_root: Path
) -> None:
    """Refresh VAL-only ranking after each completed candidate."""

    combined_path = work_root / "COMBINED_TUNING_SUMMARY_INTERIM.json"
    merge_tuning_summaries(tuning_paths, combined_path)
    build_validation_scorecard(
        [combined_path], work_root / "VALIDATION_SCORECARD.json"
    )


def single_run_source(run_name: str) -> str:
    source = self_contained_stage2_kernel()
    old = 'os.environ.get("RCDA_STAGE2_RUNS", "")'
    new = f'os.environ.get("RCDA_STAGE2_RUNS", "{run_name}")'
    if source.count(old) != 1:
        raise ValueError("stage-2 runner selection hook changed")
    return source.replace(old, new)


def single_seed_run_source(run_name: str, seed: int) -> str:
    """Build a VAL-only runner for a fixed replication seed."""

    if seed < 0:
        raise ValueError("RCDA replication seed must be non-negative")
    source = single_run_source(run_name)
    old = "            seed=0,"
    new = f"            seed={seed},"
    if source.count(old) != 1:
        raise ValueError("stage-2 runner seed hook changed")
    return source.replace(old, new)


def stage_seed_kernel(
    run_name: str,
    slug: str,
    *,
    seed: int = 0,
) -> tuple[str, str, Path]:
    stage = ROOT / "kaggle_job" / f"_alt_{slug.replace('-', '_')}"
    stage.mkdir(parents=True, exist_ok=True)
    runner = stage / "run_rcda_paper_stage2.py"
    runner.write_text(single_seed_run_source(run_name, seed), encoding="utf-8")
    kernel = f"{ALT_OWNER}/{slug}"
    metadata = {
        "id": kernel,
        "title": slug,
        "code_file": runner.name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": DATASET_SOURCES,
        "competition_sources": [],
        "kernel_sources": [],
    }
    (stage / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return kernel, sha256_file(runner), stage


def stage_and_push(
    run_name: str,
    slug: str,
    *,
    env: dict[str, str],
    seed: int = 0,
) -> tuple[str, str]:
    kernel, runner_sha256, stage = stage_seed_kernel(
        run_name,
        slug,
        seed=seed,
    )
    pushed = run(["kaggle", "kernels", "push", "-p", str(stage)], env=env, check=False)
    require_successful_kernel_push(pushed, kernel=kernel)
    return kernel, runner_sha256


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=30.0)
    parser.add_argument(
        "--recovered-summary",
        type=Path,
        action="append",
        default=[],
        help=(
            "VAL-only TUNING_SUMMARY from a finite checkpoint recovered after a "
            "kernel failure; may be passed more than once."
        ),
    )
    parser.add_argument(
        "--resume-run",
        action="append",
        default=[],
        help=(
            "Attach to an already queued/running/complete Kaggle run without "
            "pushing a new kernel; may be passed more than once."
        ),
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819",
    )
    parser.add_argument(
        "--long-summary",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_stage2_20260819/rcda_paper_stage2/TUNING_SUMMARY.json",
    )
    parser.add_argument(
        "--phase1-summary",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819/tuning_output/rcda_paper_tune/TUNING_SUMMARY.json",
    )
    args = parser.parse_args()
    env = kaggle_env(args.config_dir)
    deadline = time.monotonic() + args.max_hours * 3600
    state_path = args.work_root / "STATE.json"
    manifest_path = args.work_root / "KAGGLE_RUNTIME_MANIFEST.json"
    runtime_rows: list[dict[str, Any]] = []
    tuning_paths = [args.phase1_summary, args.long_summary]
    recovered_by_run: dict[str, Path] = {}
    known_runs = {run_name for run_name, _slug, _phase in RUNS}
    resume_runs = set(args.resume_run)
    unknown_resume_runs = resume_runs - known_runs
    if unknown_resume_runs:
        raise ValueError(f"unknown resumed runs: {sorted(unknown_resume_runs)}")
    for recovered_path in args.recovered_summary:
        recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
        ranking = recovered.get("ranking") or []
        if len(ranking) != 1:
            raise ValueError(f"invalid recovered VAL-only summary: {recovered_path}")
        recovered_run = str(ranking[0].get("run_name"))
        normalized = validate_single_run_val_summary(recovered, recovered_run)
        if normalized:
            write_json(recovered_path, recovered)
        recovered_by_run[recovered_run] = recovered_path

    try:
        for index, (run_name, slug, phase) in enumerate(RUNS):
            if index > 0 and best_validation_score(tuning_paths) >= 0.20:
                break
            if run_name in recovered_by_run:
                recovered_path = recovered_by_run[run_name]
                staged_runner = (
                    ROOT
                    / "kaggle_job"
                    / f"_alt_{slug.replace('-', '_')}"
                    / "run_rcda_paper_stage2.py"
                )
                if not staged_runner.is_file():
                    raise FileNotFoundError(
                        f"recovered run is missing its exact staged runner: {staged_runner}"
                    )
                tuning_paths.append(recovered_path)
                runtime_rows.append(
                    {
                        "run_name": run_name,
                        "kernel": f"{ALT_OWNER}/{slug}",
                        "runner_sha256": sha256_file(staged_runner),
                        "summary_sha256": sha256_file(recovered_path),
                        "selection_split": "val",
                        "test_evaluated": False,
                        "training_status": "truncated_after_nonfinite_optimization",
                        "recovered_finite_checkpoint": True,
                    }
                )
                write_json(
                    manifest_path,
                    {
                        "schema": "wfd_rcda_kaggle_runtime_manifest_v1",
                        "account": ALT_OWNER,
                        "dataset_sources": DATASET_SOURCES,
                        "test_evaluated": False,
                        "runs": runtime_rows,
                    },
                )
                update_state(
                    state_path,
                    status="running",
                    phase=phase,
                    kernel=f"{ALT_OWNER}/{slug}",
                    kernel_status="recovered_finite_checkpoint",
                    active_validation_run=run_name,
                    best_completed_val_event_macro_iou=best_validation_score(
                        tuning_paths
                    ),
                    error=None,
                )
                refresh_interim_validation(tuning_paths, args.work_root)
                continue
            kernel = f"{ALT_OWNER}/{slug}"
            resumed_existing = run_name in resume_runs
            if resumed_existing:
                staged_runner = (
                    ROOT
                    / "kaggle_job"
                    / f"_alt_{slug.replace('-', '_')}"
                    / "run_rcda_paper_stage2.py"
                )
                if not staged_runner.is_file():
                    raise FileNotFoundError(
                        f"resumed run is missing its exact staged runner: {staged_runner}"
                    )
                kernel = f"{ALT_OWNER}/{slug}"
                remote_status = kernel_status(kernel, env=env)
                if remote_status not in {"queued", "running", "complete"}:
                    raise RuntimeError(
                        f"cannot resume {kernel} from status {remote_status}"
                    )
                runner_sha256 = sha256_file(staged_runner)
            elif index == 0:
                staged_runner = (
                    ROOT
                    / "kaggle_job"
                    / f"_alt_{slug.replace('-', '_')}"
                    / "run_rcda_paper_stage2.py"
                )
                runner_sha256 = sha256_file(staged_runner)
            else:
                kernel, runner_sha256 = stage_and_push(run_name, slug, env=env)
            runtime_rows.append(
                {
                    "run_name": run_name,
                    "kernel": kernel,
                    "runner_sha256": runner_sha256,
                    "selection_split": "val",
                    "test_evaluated": False,
                    "resumed_existing_kernel": resumed_existing,
                }
            )
            write_json(
                manifest_path,
                {
                    "schema": "wfd_rcda_kaggle_runtime_manifest_v1",
                    "account": ALT_OWNER,
                    "dataset_sources": DATASET_SOURCES,
                    "test_evaluated": False,
                    "runs": runtime_rows,
                },
            )
            wait_for_kernel(
                kernel,
                phase=phase,
                state_path=state_path,
                env=env,
                deadline=deadline,
                poll_seconds=args.poll_seconds,
            )
            output = ROOT / "outputs/ml_eval" / f"rcda_kaggle_{run_name}_20260819"
            summary_path = download_summary(kernel, output, run_name, env=env)
            tuning_paths.append(summary_path)
            runtime_rows[-1].update(
                {
                    "summary_sha256": sha256_file(summary_path),
                    "training_status": "completed",
                }
            )
            write_json(
                manifest_path,
                {
                    "schema": "wfd_rcda_kaggle_runtime_manifest_v1",
                    "account": ALT_OWNER,
                    "dataset_sources": DATASET_SOURCES,
                    "test_evaluated": False,
                    "runs": runtime_rows,
                },
            )
            refresh_interim_validation(tuning_paths, args.work_root)
            best = best_validation_score(tuning_paths)
            update_state(
                state_path,
                status="running",
                phase=phase,
                kernel=kernel,
                kernel_status="complete",
                active_validation_run=run_name,
                best_completed_val_event_macro_iou=best,
            )

        register_pretest_decisions(
            work_root=args.work_root,
            output_path=args.work_root / "PRETEST_DECISION_LOG.json",
            numeric_recovery_summary=args.long_summary,
            kaggle_runtime_manifest=manifest_path,
        )
        combined_path = args.work_root / "COMBINED_TUNING_SUMMARY.json"
        merge_tuning_summaries(tuning_paths, combined_path)
        build_validation_scorecard(
            [combined_path], args.work_root / "VALIDATION_SCORECARD.json"
        )
        frozen_path = args.work_root / "FROZEN_RECIPE.json"
        frozen = freeze_recipe(combined_path, frozen_path)
        update_state(
            state_path,
            status="running",
            phase="recipe_frozen",
            frozen_recipe=str(frozen_path),
            winner=frozen["winner"],
        )

        canonical_final_stage = stage_final_kernel(frozen_path)
        final_stage = ROOT / "kaggle_job/_alt_rcda_paper_final"
        final_stage.mkdir(parents=True, exist_ok=True)
        final_runner = final_stage / "run_rcda_paper_final.py"
        final_runner.write_bytes((canonical_final_stage / "run_rcda_paper_final.py").read_bytes())
        final_kernel = f"{ALT_OWNER}/wfd-rcda-paper-final-gpu-v1"
        final_metadata = {
            "id": final_kernel,
            "title": "wfd-rcda-paper-final-gpu-v1",
            "code_file": final_runner.name,
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": False,
            "machine_shape": "NvidiaTeslaT4",
            "dataset_sources": DATASET_SOURCES,
            "competition_sources": [],
            "kernel_sources": [],
        }
        (final_stage / "kernel-metadata.json").write_text(
            json.dumps(final_metadata, indent=2) + "\n", encoding="utf-8"
        )
        pushed = run(["kaggle", "kernels", "push", "-p", str(final_stage)], env=env, check=False)
        require_successful_kernel_push(pushed, kernel=final_kernel)
        wait_for_kernel(
            final_kernel,
            phase="preregistered_final_test_kaggle",
            state_path=state_path,
            env=env,
            deadline=deadline,
            poll_seconds=args.poll_seconds,
        )
        final_output = args.work_root / "final_output_kaggle_alt"
        final_output.mkdir(parents=True, exist_ok=True)
        run(
            ["kaggle", "kernels", "output", final_kernel, "-p", str(final_output), "--force"],
            env=env,
        )
        final_summary = one_json(final_output, "FINAL_SUMMARY.json")
        validate_final_summary(final_summary, frozen)
        checkpoint_dirs = {path.parent for path in final_output.rglob("*.pt") if path.is_file()}
        if len(checkpoint_dirs) != 1:
            raise FileNotFoundError(f"expected one checkpoint directory: {checkpoint_dirs}")
        metrics_summary = args.work_root / "FINAL_SUMMARY_PAPER_METRICS.json"
        evaluate_final_checkpoints(
            final_summary,
            checkpoint_dirs.pop(),
            ROOT / "data/external/rcda_net_full/dataset",
            ROOT / "data/external/rcda_net_full/protocol",
            metrics_summary,
        )
        scorecard = build_scorecard(
            metrics_summary,
            ROOT / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json",
            args.work_root,
            ROOT / "outputs/ml_eval/rcda_sealed_baselines/learned_baselines.json",
        )
        update_state(
            state_path,
            status="complete",
            phase="complete",
            kernel=final_kernel,
            kernel_status="complete",
            scorecard=str(args.work_root / "PAPER_SCORECARD.json"),
            result_status=scorecard["status"],
            primary=scorecard["primary"],
        )
        return 0
    except Exception as exc:
        update_state(state_path, status="error", phase="error", error=repr(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
