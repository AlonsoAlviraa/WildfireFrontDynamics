#!/usr/bin/env python3
"""Monitor RCDA tuning, freeze VAL winner, run final TEST, and build paper scorecard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_rcda_paper_tuning import (  # noqa: E402
    freeze_recipe,
    merge_tuning_summaries,
)
from scripts.evaluate_rcda_paper_metrics import evaluate_final_checkpoints  # noqa: E402
from scripts.summarize_rcda_paper_final import build_scorecard  # noqa: E402

TUNE_KERNEL = "alonsoalvira/wfd-rcda-paper-tune-v1"
FINAL_KERNEL = "alonsoalvira/wfd-rcda-paper-final-v1"
STAGE2_KERNEL = "alonsoalvira/wfd-rcda-paper-stage2-v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_state(path: Path, **fields) -> None:
    existing = {}
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


def _status(kernel: str) -> str:
    result = subprocess.run(
        ["kaggle", "kernels", "status", kernel],
        check=True,
        capture_output=True,
        text=True,
    )
    text = result.stdout + result.stderr
    for status in ("COMPLETE", "ERROR", "CANCELLED", "RUNNING", "QUEUED"):
        if status in text.upper():
            return status.lower()
    raise RuntimeError(f"unrecognized Kaggle status: {text}")


def _download(kernel: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", kernel, "-p", str(output), "--force"],
        check=True,
    )


def _wait(
    kernel: str,
    *,
    state_path: Path,
    phase: str,
    poll_seconds: int,
    deadline: float,
) -> None:
    while True:
        status = _status(kernel)
        _write_state(state_path, phase=phase, kernel=kernel, kernel_status=status)
        print(f"[{_utc_now()}] {phase}: {status}", flush=True)
        if status == "complete":
            return
        if status in {"error", "cancelled"}:
            raise RuntimeError(f"Kaggle kernel {kernel} ended with {status}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"nightwatch deadline exceeded during {phase}")
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=14.0)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_paper_nightwatch_20260819",
    )
    args = parser.parse_args()
    work = args.work_root
    state = work / "STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600.0
    try:
        _wait(
            TUNE_KERNEL,
            state_path=state,
            phase="validation_only_tuning",
            poll_seconds=args.poll_seconds,
            deadline=deadline,
        )
        tune_output = work / "tuning_output"
        _download(TUNE_KERNEL, tune_output)
        summaries = list(tune_output.rglob("TUNING_SUMMARY.json"))
        if len(summaries) != 1:
            raise FileNotFoundError(f"expected one TUNING_SUMMARY.json, found {summaries}")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/push_rcda_paper_stage2_kaggle.py")],
            cwd=ROOT,
            check=True,
        )
        _wait(
            STAGE2_KERNEL,
            state_path=state,
            phase="validation_only_stage2",
            poll_seconds=args.poll_seconds,
            deadline=deadline,
        )
        stage2_output = work / "stage2_output"
        _download(STAGE2_KERNEL, stage2_output)
        stage2_summaries = list(stage2_output.rglob("TUNING_SUMMARY.json"))
        if len(stage2_summaries) != 1:
            raise FileNotFoundError(
                f"expected one stage-2 TUNING_SUMMARY.json, found {stage2_summaries}"
            )
        combined_path = work / "COMBINED_TUNING_SUMMARY.json"
        merge_tuning_summaries([summaries[0], stage2_summaries[0]], combined_path)
        frozen_path = work / "FROZEN_RECIPE.json"
        frozen = freeze_recipe(combined_path, frozen_path)
        _write_state(
            state,
            phase="recipe_frozen",
            frozen_recipe=str(frozen_path),
            winner=frozen["winner"],
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/push_rcda_paper_final_kaggle.py"),
                str(frozen_path),
            ],
            cwd=ROOT,
            check=True,
        )
        _wait(
            FINAL_KERNEL,
            state_path=state,
            phase="preregistered_final_test",
            poll_seconds=args.poll_seconds,
            deadline=deadline,
        )
        final_output = work / "final_output"
        _download(FINAL_KERNEL, final_output)
        final_summaries = list(final_output.rglob("FINAL_SUMMARY.json"))
        if len(final_summaries) != 1:
            raise FileNotFoundError(f"expected one FINAL_SUMMARY.json, found {final_summaries}")
        checkpoint_dirs = [path.parent for path in final_output.rglob("*.pt") if path.is_file()]
        if not checkpoint_dirs:
            raise FileNotFoundError("final Kaggle output contains no checkpoints")
        metrics_summary = work / "FINAL_SUMMARY_PAPER_METRICS.json"
        evaluate_final_checkpoints(
            final_summaries[0],
            checkpoint_dirs[0],
            ROOT / "data/external/rcda_net_full/dataset",
            ROOT / "data/external/rcda_net_full/protocol",
            metrics_summary,
        )
        scorecard = build_scorecard(
            metrics_summary,
            ROOT / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json",
            work,
            ROOT / "outputs/ml_eval/rcda_sealed_baselines/learned_baselines.json",
        )
        _write_state(
            state,
            phase="complete",
            status="complete",
            scorecard=str(work / "PAPER_SCORECARD.json"),
            result_status=scorecard["status"],
            primary=scorecard["primary"],
        )
        print(json.dumps(scorecard["primary"], indent=2), flush=True)
        return 0
    except Exception as exc:
        _write_state(state, status="error", error=repr(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
