#!/usr/bin/env python3
"""Continue the sealed RCDA paper protocol after GCP VAL-only stage 2."""

from __future__ import annotations

import argparse
import json
import re
import shutil
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
    validate_tuning_report,
)
from scripts.evaluate_rcda_paper_metrics import evaluate_final_checkpoints  # noqa: E402
from scripts.push_rcda_paper_final_kaggle import (  # noqa: E402
    stage_kernel as stage_final_kernel,
)
from scripts.push_rcda_paper_stage2_kaggle import (  # noqa: E402
    stage_kernel as stage_stage2_kernel,
)
from scripts.summarize_rcda_paper_final import build_scorecard  # noqa: E402
from scripts.summarize_rcda_validation import build_validation_scorecard  # noqa: E402


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_state(path: Path, **fields: Any) -> None:
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(fields)
    existing["updated_at"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _run(
    arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=check, capture_output=True, text=True)


def _one_json(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one {name} below {root}, found {matches}")
    return matches[0]


def best_validation_score(summary_paths: list[Path]) -> float:
    """Return the best candidate score only after enforcing VAL isolation."""

    reports: list[dict[str, Any]] = []
    for path in summary_paths:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            document.get("schema") != "wfd_rcda_paper_tune_v1"
            or document.get("selection_split") != "val"
            or document.get("test_evaluated") is not False
        ):
            raise ValueError(f"non-VAL tuning summary in conditional gate: {path}")
        document_reports = list(document.get("reports") or [])
        for report in document_reports:
            validate_tuning_report(report)
        reports.extend(document_reports)
    if not reports:
        raise ValueError("conditional gate received no tuning reports")
    return max(float(report["val"]["selected"]["event_macro_iou"]) for report in reports)


def validate_final_summary(summary_path: Path, frozen: dict[str, Any]) -> dict[str, Any]:
    """Reject any remote result that diverges from the locally frozen protocol."""

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if summary.get("schema") != "wfd_rcda_paper_final_v1":
        raise ValueError("unexpected GCP final summary schema")
    if summary.get("frozen_recipe") != frozen:
        raise ValueError("GCP final summary does not embed the exact frozen recipe")
    if summary.get("selection_split") != "val":
        raise ValueError("GCP final selection split is not VAL")
    if summary.get("test_used_for_selection") is not False:
        raise ValueError("GCP final result used TEST for selection")
    expected = set(frozen["final_evaluation"]["seeds"])
    reports = list(summary.get("reports") or [])
    observed = {int(report["config"]["seed"]) for report in reports}
    if observed != expected or len(reports) != len(expected):
        raise ValueError("GCP final reports do not match preregistered seeds")
    for report in reports:
        if report.get("threshold_selected_on") != "val":
            raise ValueError("a final threshold was not selected on VAL")
        if report.get("test_used_for_selection") is not False:
            raise ValueError("a final report used TEST for selection")
        if report.get("test_evaluated") is not True or "test_once" not in report:
            raise ValueError("a final report did not contain its single TEST evaluation")
        checkpoint_sha256 = str(report.get("checkpoint_sha256") or "")
        if len(checkpoint_sha256) != 64:
            raise ValueError("a final report does not identify its checkpoint by SHA-256")
    ensemble = summary.get("ensemble") or {}
    expected_ensemble = (frozen.get("final_evaluation") or {}).get(
        "secondary_probability_ensemble"
    ) or {}
    if expected_ensemble and (
            ensemble.get("aggregation") != expected_ensemble.get("aggregation")
            or ensemble.get("threshold_selected_on") != "val"
            or ensemble.get("test_used_for_selection") is not False
            or ensemble.get("test_evaluated") is not True
            or "test_once" not in ensemble
    ):
        raise ValueError("GCP final ensemble violates its frozen VAL/TEST contract")
    return summary


def _gcloud_base(args: argparse.Namespace) -> list[str]:
    return ["--project", args.project, "--zone", args.zone, "--quiet"]


def _ssh(
    args: argparse.Namespace, command: str, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            args.gcloud,
            "compute",
            "ssh",
            args.instance,
            *_gcloud_base(args),
            "--command",
            command,
        ],
        check=check,
    )


def _stop_instance(args: argparse.Namespace) -> None:
    _run(
        [
            args.gcloud,
            "compute",
            "instances",
            "stop",
            args.instance,
            *_gcloud_base(args),
        ],
        check=False,
    )


def _instance_status(args: argparse.Namespace) -> str:
    result = _run(
        [
            args.gcloud,
            "compute",
            "instances",
            "describe",
            args.instance,
            *_gcloud_base(args),
            "--format=value(status)",
        ],
        check=False,
    )
    return result.stdout.strip().upper()


def _restart_instance(args: argparse.Namespace, deadline: float) -> None:
    _run(
        [
            args.gcloud,
            "compute",
            "instances",
            "start",
            args.instance,
            *_gcloud_base(args),
        ]
    )
    _wait_for_ssh(args, min(deadline, time.monotonic() + 600))


def _wait_for_stage2(
    state_path: Path, *, deadline: float, poll_seconds: int
) -> None:
    while True:
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            phase = state.get("phase")
            if phase == "complete" and state.get("instance_stopped") is True:
                return
            if phase == "error":
                raise RuntimeError(f"GCP stage 2 failed: {state.get('error')}")
        if time.monotonic() >= deadline:
            raise TimeoutError("deadline exceeded while waiting for GCP stage 2")
        time.sleep(max(30, poll_seconds))


def _wait_for_ssh(args: argparse.Namespace, deadline: float) -> None:
    while time.monotonic() < deadline:
        probe = _ssh(args, "echo ready", check=False)
        if probe.returncode == 0 and "ready" in probe.stdout:
            return
        time.sleep(15)
    raise TimeoutError("GCP instance did not become reachable over SSH")


def _run_additional_stage(
    args: argparse.Namespace,
    *,
    state_path: Path,
    deadline: float,
    run_name: str,
    phase: str,
    local_output: Path,
    remote_output: str,
    log_name: str,
) -> Path:
    """Run one registered VAL-only continuation after the long job."""

    continuation_state = local_output / "STATE.json"
    local_output.mkdir(parents=True, exist_ok=True)
    staged = stage_stage2_kernel()
    runner = staged / "run_rcda_paper_stage2.py"
    bootstrap = ROOT / "scripts/gcp_run_rcda_stage2.sh"
    _run(
        [
            args.gcloud,
            "compute",
            "instances",
            "start",
            args.instance,
            *_gcloud_base(args),
        ]
    )
    _wait_for_ssh(args, min(deadline, time.monotonic() + 600))
    _run(
        [
            args.gcloud,
            "compute",
            "scp",
            str(runner),
            str(bootstrap),
            f"{args.instance}:/home/Mariano/",
            *_gcloud_base(args),
        ]
    )
    _ssh(
        args,
        (
            f"rm -rf {remote_output} && mkdir -p {remote_output} && "
            "chmod +x /home/Mariano/gcp_run_rcda_stage2.sh && "
            f"RCDA_STAGE2_RUNS={run_name} "
            f"RCDA_STAGE2_OUTPUT={remote_output} "
            "setsid -f bash /home/Mariano/gcp_run_rcda_stage2.sh "
            f"> /home/Mariano/{log_name} 2>&1 < /dev/null"
        ),
    )
    _write_state(
        state_path,
        status="running",
        phase=phase,
        stage2_long_complete=True,
        active_validation_run=run_name,
        active_seed=None,
        checkpoint_epoch=None,
        train_loss=None,
        val_f1_at_0_5=None,
        val_event_macro_iou=None,
        val_selection_threshold=None,
    )
    time.sleep(5)
    spot_restarts = 0
    while True:
        probe = _ssh(
            args,
            (
                f"if test -f {remote_output}/TUNING_SUMMARY.json; then echo complete; "
                "elif test -f /home/Mariano/stage2.pid && "
                "kill -0 $(cat /home/Mariano/stage2.pid) 2>/dev/null; "
                f"then grep -E '^\\[' /home/Mariano/{log_name} | tail -1 || true; "
                "echo running; else echo error; fi"
            ),
            check=False,
        )
        lines = probe.stdout.strip().splitlines()
        status = (
            lines[-1]
            if probe.returncode == 0 and probe.stdout.strip()
            else "unreachable"
        )
        progress: dict[str, Any] = {}
        if status == "running" and len(lines) > 1:
            match = re.search(
                r"seed=(\d+)\] epoch (\d+) loss=([0-9.]+) val_f1=([0-9.]+)"
                r"(?: val_event_macro=([0-9.]+) val_thr=([0-9.]+))?",
                lines[-2],
            )
            if match:
                progress = {
                    "active_seed": int(match.group(1)),
                    "checkpoint_epoch": int(match.group(2)),
                    "train_loss": float(match.group(3)),
                    "val_f1_at_0_5": float(match.group(4)),
                }
                if match.group(5):
                    progress["val_event_macro_iou"] = float(match.group(5))
                    progress["val_selection_threshold"] = float(match.group(6))
        _write_state(
            continuation_state,
            phase=status,
            instance=args.instance,
            updated_at=_utc_now(),
            spot_restarts=spot_restarts,
            **progress,
        )
        _write_state(
            state_path,
            status="running",
            phase=phase,
            active_validation_run=run_name,
            spot_restarts=spot_restarts,
            **progress,
        )
        _run([sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")], check=False)
        if status == "complete":
            break
        if status == "unreachable" and _instance_status(args) == "TERMINATED":
            if spot_restarts >= args.max_spot_restarts:
                raise RuntimeError(f"GCP continuation {run_name} exceeded Spot restart budget")
            _restart_instance(args, deadline)
            _ssh(
                args,
                (
                    f"RCDA_STAGE2_RUNS={run_name} "
                    f"RCDA_STAGE2_OUTPUT={remote_output} "
                    "setsid -f bash /home/Mariano/gcp_run_rcda_stage2.sh "
                    f"> /home/Mariano/{log_name} 2>&1 < /dev/null"
                ),
            )
            spot_restarts += 1
            _write_state(
                continuation_state,
                phase="restarted_after_spot_preemption",
                instance=args.instance,
                spot_restarts=spot_restarts,
            )
            time.sleep(10)
            continue
        if status == "error":
            log = _ssh(args, f"tail -100 /home/Mariano/{log_name}", check=False)
            raise RuntimeError(
                f"GCP continuation {run_name} ended without a summary: "
                + (log.stdout or log.stderr)
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"deadline exceeded during GCP continuation {run_name}")
        time.sleep(max(30, args.poll_seconds))
    _run(
        [
            args.gcloud,
            "compute",
            "scp",
            "--recurse",
            f"{args.instance}:{remote_output}",
            str(local_output),
            *_gcloud_base(args),
        ]
    )
    summary_path = _one_json(local_output, "TUNING_SUMMARY.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    reports = list(summary.get("reports") or [])
    if (
        summary.get("selection_split") != "val"
        or summary.get("test_evaluated") is not False
        or len(reports) != 1
        or reports[0]["config"]["run_name"] != run_name
    ):
        raise ValueError(f"GCP continuation {run_name} violates its VAL-only contract")
    _stop_instance(args)
    _write_state(
        continuation_state,
        phase="complete",
        instance=args.instance,
        instance_stopped=True,
        summary=str(summary_path),
        test_evaluated=False,
        spot_restarts=spot_restarts,
    )
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gcloud",
        default=shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud",
    )
    parser.add_argument("--project", default="project-89d8567f-49f2-48bc-a00")
    parser.add_argument("--zone", default="europe-west4-a")
    parser.add_argument("--instance", default="wfd-rcda-nightwatch-20260819")
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--max-hours", type=float, default=18.0)
    parser.add_argument("--max-spot-restarts", type=int, default=2)
    parser.add_argument(
        "--stage2-state",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_stage2_20260819/STATE.json",
    )
    parser.add_argument(
        "--stage2-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_stage2_20260819",
    )
    parser.add_argument(
        "--precision-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_precision_20260819",
    )
    parser.add_argument(
        "--low-lr-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_low_lr_20260819",
    )
    parser.add_argument(
        "--growth-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_growth_20260819",
    )
    parser.add_argument(
        "--event-balanced-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_event_balanced_20260819",
    )
    parser.add_argument(
        "--uniform-events-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_uniform_events_20260819",
    )
    parser.add_argument(
        "--film-output",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_gcp_film_20260819",
    )
    parser.add_argument(
        "--phase1-summary",
        type=Path,
        default=(
            ROOT
            / "outputs/ml_eval/rcda_paper_nightwatch_20260819/tuning_output"
            / "rcda_paper_tune/TUNING_SUMMARY.json"
        ),
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819",
    )
    args = parser.parse_args()
    deadline = time.monotonic() + args.max_hours * 3600
    state_path = args.work_root / "STATE.json"
    final_remote = "/kaggle/working/rcda_paper_final"
    try:
        _write_state(
            state_path,
            status="running",
            phase="validation_only_stage2_gcp",
            error=None,
            kernel=None,
            kernel_status=None,
        )
        _wait_for_stage2(
            args.stage2_state,
            deadline=deadline,
            poll_seconds=args.poll_seconds,
        )
        precision_summary = _run_additional_stage(
            args,
            state_path=state_path,
            deadline=deadline,
            run_name="resunet_hybrid_precision_v3",
            phase="validation_only_stage2_precision_gcp",
            local_output=args.precision_output,
            remote_output="/kaggle/working/rcda_paper_stage2_precision",
            log_name="precision.log",
        )
        stage2_summary = _one_json(args.stage2_output, "TUNING_SUMMARY.json")
        tuning_paths = [args.phase1_summary, stage2_summary, precision_summary]
        best_val_before_low_lr = best_validation_score(tuning_paths)
        if best_val_before_low_lr < 0.20:
            low_lr_summary = _run_additional_stage(
                args,
                state_path=state_path,
                deadline=deadline,
                run_name="resunet_hybrid_low_lr_v2",
                phase="validation_only_stage2_low_lr_gcp",
                local_output=args.low_lr_output,
                remote_output="/kaggle/working/rcda_paper_stage2_low_lr",
                log_name="low_lr.log",
            )
            tuning_paths.append(low_lr_summary)
        best_val_before_growth = best_validation_score(tuning_paths)
        if best_val_before_growth < 0.20:
            growth_summary = _run_additional_stage(
                args,
                state_path=state_path,
                deadline=deadline,
                run_name="resunet_growth_v1",
                phase="validation_only_stage2_growth_gcp",
                local_output=args.growth_output,
                remote_output="/kaggle/working/rcda_paper_stage2_growth",
                log_name="growth.log",
            )
            tuning_paths.append(growth_summary)
        best_val_before_event_balance = best_validation_score(tuning_paths)
        if best_val_before_event_balance < 0.20:
            event_balanced_summary = _run_additional_stage(
                args,
                state_path=state_path,
                deadline=deadline,
                run_name="resunet_hybrid_event_balanced_v1",
                phase="validation_only_stage2_event_balanced_gcp",
                local_output=args.event_balanced_output,
                remote_output="/kaggle/working/rcda_paper_stage2_event_balanced",
                log_name="event_balanced.log",
            )
            tuning_paths.append(event_balanced_summary)
        best_val_before_uniform_events = best_validation_score(tuning_paths)
        if best_val_before_uniform_events < 0.20:
            uniform_events_summary = _run_additional_stage(
                args,
                state_path=state_path,
                deadline=deadline,
                run_name="resunet_hybrid_uniform_events_v1",
                phase="validation_only_stage2_uniform_events_gcp",
                local_output=args.uniform_events_output,
                remote_output="/kaggle/working/rcda_paper_stage2_uniform_events",
                log_name="uniform_events.log",
            )
            tuning_paths.append(uniform_events_summary)
        best_val_before_film = best_validation_score(tuning_paths)
        if best_val_before_film < 0.20:
            film_summary = _run_additional_stage(
                args,
                state_path=state_path,
                deadline=deadline,
                run_name="film_growth_v1",
                phase="validation_only_stage2_film_gcp",
                local_output=args.film_output,
                remote_output="/kaggle/working/rcda_paper_stage2_film",
                log_name="film.log",
            )
            tuning_paths.append(film_summary)
        combined_path = args.work_root / "COMBINED_TUNING_SUMMARY.json"
        merge_tuning_summaries(
            tuning_paths,
            combined_path,
        )
        build_validation_scorecard(
            [combined_path],
            args.work_root / "VALIDATION_SCORECARD.json",
        )
        frozen_path = args.work_root / "FROZEN_RECIPE.json"
        frozen = freeze_recipe(combined_path, frozen_path)
        _write_state(
            state_path,
            status="running",
            phase="recipe_frozen",
            frozen_recipe=str(frozen_path),
            winner=frozen["winner"],
        )

        staged = stage_final_kernel(frozen_path)
        final_runner = staged / "run_rcda_paper_final.py"
        bootstrap = ROOT / "scripts/gcp_run_rcda_final.sh"
        _run(
            [
                args.gcloud,
                "compute",
                "instances",
                "start",
                args.instance,
                *_gcloud_base(args),
            ]
        )
        _wait_for_ssh(args, min(deadline, time.monotonic() + 600))
        _run(
            [
                args.gcloud,
                "compute",
                "scp",
                str(final_runner),
                str(bootstrap),
                f"{args.instance}:/home/Mariano/",
                *_gcloud_base(args),
            ]
        )
        launch = _ssh(
            args,
            (
                f"rm -rf {final_remote} && mkdir -p {final_remote} && "
                "chmod +x /home/Mariano/gcp_run_rcda_final.sh && "
                "setsid -f bash /home/Mariano/gcp_run_rcda_final.sh "
                "> /home/Mariano/final.log 2>&1 < /dev/null"
            ),
        )
        if launch.returncode != 0:
            raise RuntimeError(f"failed to launch GCP final: {launch.stderr}")
        _write_state(
            state_path,
            status="running",
            phase="preregistered_final_test_gcp",
            final_seeds=frozen["final_evaluation"]["seeds"],
            active_validation_run=None,
            active_seed=None,
            checkpoint_epoch=None,
            train_loss=None,
            val_f1_at_0_5=None,
            val_event_macro_iou=None,
            val_selection_threshold=None,
        )

        spot_restarts = 0
        while True:
            probe = _ssh(
                args,
                (
                    f"if test -f {final_remote}/FINAL_SUMMARY.json; then echo complete; "
                    "elif test -f /home/Mariano/final.pid && "
                    "kill -0 $(cat /home/Mariano/final.pid) 2>/dev/null; "
                    "then grep -E '^\\[' /home/Mariano/final.log | tail -1 || true; "
                    "echo running; else echo error; fi"
                ),
                check=False,
            )
            lines = probe.stdout.strip().splitlines()
            status = (
                lines[-1]
                if probe.returncode == 0 and probe.stdout.strip()
                else "unreachable"
            )
            progress = {}
            if status == "running" and len(lines) > 1:
                match = re.search(
                    r"seed=(\d+)\] epoch (\d+) loss=([0-9.]+) val_f1=([0-9.]+)"
                    r"(?: val_event_macro=([0-9.]+) val_thr=([0-9.]+))?",
                    lines[-2],
                )
                if match:
                    progress = {
                        "active_seed": int(match.group(1)),
                        "checkpoint_epoch": int(match.group(2)),
                        "train_loss": float(match.group(3)),
                        "val_f1_at_0_5": float(match.group(4)),
                    }
                    if match.group(5):
                        progress["val_event_macro_iou"] = float(match.group(5))
                        progress["val_selection_threshold"] = float(match.group(6))
            _write_state(
                state_path,
                status="running",
                phase="preregistered_final_test_gcp",
                remote_status=status,
                spot_restarts=spot_restarts,
                **progress,
            )
            _run(
                [sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")],
                check=False,
            )
            if status == "complete":
                break
            if status == "unreachable" and _instance_status(args) == "TERMINATED":
                if spot_restarts >= args.max_spot_restarts:
                    raise RuntimeError("GCP final exceeded Spot restart budget")
                _restart_instance(args, deadline)
                _ssh(
                    args,
                    (
                        "setsid -f bash /home/Mariano/gcp_run_rcda_final.sh "
                        "> /home/Mariano/final.log 2>&1 < /dev/null"
                    ),
                )
                spot_restarts += 1
                _write_state(
                    state_path,
                    status="running",
                    phase="preregistered_final_test_gcp",
                    remote_status="restarted_after_spot_preemption",
                    spot_restarts=spot_restarts,
                )
                time.sleep(10)
                continue
            if status == "error":
                log = _ssh(args, "tail -100 /home/Mariano/final.log", check=False)
                raise RuntimeError(
                    "GCP final ended without a summary: " + (log.stdout or log.stderr)
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline exceeded during GCP final evaluation")
            time.sleep(max(30, args.poll_seconds))

        final_output = args.work_root / "final_output_gcp"
        final_output.mkdir(parents=True, exist_ok=True)
        _run(
            [
                args.gcloud,
                "compute",
                "scp",
                "--recurse",
                f"{args.instance}:{final_remote}",
                str(final_output),
                *_gcloud_base(args),
            ]
        )
        final_summary = _one_json(final_output, "FINAL_SUMMARY.json")
        validate_final_summary(final_summary, frozen)
        checkpoint_dirs = {
            path.parent for path in final_output.rglob("*.pt") if path.is_file()
        }
        if len(checkpoint_dirs) != 1:
            raise FileNotFoundError(
                f"expected one final checkpoint directory, found {checkpoint_dirs}"
            )
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
        _stop_instance(args)
        _write_state(
            state_path,
            status="complete",
            phase="complete",
            instance_stopped=True,
            scorecard=str(args.work_root / "PAPER_SCORECARD.json"),
            result_status=scorecard["status"],
            primary=scorecard["primary"],
            spot_restarts=spot_restarts,
        )
        _run([sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")])
        return 0
    except Exception as exc:
        _stop_instance(args)
        _write_state(
            state_path,
            status="error",
            phase="error",
            instance_stop_requested=True,
            error=repr(exc),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
