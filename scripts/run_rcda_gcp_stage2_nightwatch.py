#!/usr/bin/env python3
"""Download a sealed GCP stage-2 result and stop its Spot VM safely."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.base import (  # noqa: E402
    _atomic_write_json,
    utc_now,
)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def _refresh_console() -> None:
    _run(
        [sys.executable, str(ROOT / "scripts/refresh_rcda_paper_console.py")],
        check=False,
    )


def parse_running_progress(lines: list[str]) -> dict[str, float | int | str]:
    """Parse latest log telemetry plus the VAL-selected checkpoint metadata."""

    progress: dict[str, float | int | str] = {}
    for line in reversed(lines):
        match = re.search(
            r"epoch (\d+) loss=([0-9.]+) val_f1=([0-9.]+)",
            line,
        )
        if match:
            progress.update(
                {
                    "checkpoint_epoch": int(match.group(1)),
                    "train_loss": float(match.group(2)),
                    "val_f1_at_0_5": float(match.group(3)),
                    "progress_line": line,
                }
            )
            break
    for line in reversed(lines):
        match = re.fullmatch(
            r"BEST\s+(\d+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)",
            line.strip(),
        )
        if match:
            progress.update(
                {
                    "best_checkpoint_epoch": int(match.group(1)),
                    "val_event_macro_iou": float(match.group(2)),
                    "val_selection_threshold": float(match.group(3)),
                }
            )
            break
    return progress


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gcloud",
        default=shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud",
        help="Path to the gcloud executable (useful for detached Windows processes).",
    )
    parser.add_argument("--project", default="project-89d8567f-49f2-48bc-a00")
    parser.add_argument("--zone", default="europe-west4-a")
    parser.add_argument("--instance", default="wfd-rcda-nightwatch-20260819")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/ml_eval/rcda_gcp_stage2_20260819")
    )
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--max-hours", type=float, default=8.0)
    parser.add_argument("--max-spot-restarts", type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600
    base = ["--project", args.project, "--zone", args.zone, "--quiet"]
    remote_summary = "/kaggle/working/rcda_paper_stage2/TUNING_SUMMARY.json"
    spot_restarts = 0
    try:
        while True:
            probe = _run(
                [
                    args.gcloud,
                    "compute",
                    "ssh",
                    args.instance,
                    *base,
                    "--command",
                    (
                        f"if test -f {remote_summary}; then echo complete; "
                        "elif test -f /home/Mariano/stage2.pid && "
                        "kill -0 $(cat /home/Mariano/stage2.pid) 2>/dev/null; "
                        "then latest=$(ls -t /home/Mariano/stage2*.log 2>/dev/null | "
                        "head -1); test -n \"$latest\" && grep -E '^\\[' \"$latest\" | "
                        "tail -1 || true; checkpoint=$(ls -t "
                        "/kaggle/working/rcda_paper_stage2/*_best.pt 2>/dev/null | "
                        "head -1); test -z \"$checkpoint\" || python3 -c 'import sys,torch; "
                        "c=torch.load(sys.argv[1],map_location=\"cpu\",weights_only=False); "
                        "print(\"BEST {} {} {}\".format(c.get(\"epoch\"), "
                        "c.get(\"epoch_selection_score\"), "
                        "c.get(\"epoch_selection_threshold\")))' \"$checkpoint\"; "
                        "echo running; else echo error; fi"
                    ),
                ],
                check=False,
            )
            lines = probe.stdout.strip().splitlines()
            status = lines[-1] if lines else "unreachable"
            progress: dict[str, float | int | str] = {}
            if status == "running" and len(lines) > 1:
                progress = parse_running_progress(lines[:-1])
            _atomic_write_json(
                state_path,
                {
                    "phase": status,
                    "updated_at": utc_now(),
                    "instance": args.instance,
                    "spot_restarts": spot_restarts,
                    **progress,
                },
            )
            _refresh_console()
            if status == "complete":
                _run(
                    [
                        args.gcloud,
                        "compute",
                        "scp",
                        "--recurse",
                        f"{args.instance}:/kaggle/working/rcda_paper_stage2",
                        str(args.output),
                        *base,
                    ]
                )
                summaries = list(args.output.rglob("TUNING_SUMMARY.json"))
                if len(summaries) != 1:
                    raise FileNotFoundError(f"expected one summary, found {summaries}")
                summary = json.loads(summaries[0].read_text(encoding="utf-8"))
                if summary.get("selection_split") != "val" or summary.get("test_evaluated") is not False:
                    raise ValueError("GCP stage-2 result violates VAL-only contract")
                _run(
                    [
                        args.gcloud,
                        "compute",
                        "instances",
                        "stop",
                        args.instance,
                        *base,
                    ]
                )
                _atomic_write_json(
                    state_path,
                    {
                        "phase": "complete",
                        "updated_at": utc_now(),
                        "instance": args.instance,
                        "instance_stopped": True,
                        "summary": str(summaries[0]),
                        "ranking": summary.get("ranking"),
                        "test_evaluated": False,
                        "spot_restarts": spot_restarts,
                    },
                )
                _refresh_console()
                return 0
            if status == "unreachable":
                instance = _run(
                    [
                        args.gcloud,
                        "compute",
                        "instances",
                        "describe",
                        args.instance,
                        *base,
                        "--format=value(status)",
                    ],
                    check=False,
                )
                if instance.stdout.strip().upper() == "TERMINATED":
                    if spot_restarts >= args.max_spot_restarts:
                        raise RuntimeError("GCP stage 2 exceeded Spot restart budget")
                    _run(
                        [
                            args.gcloud,
                            "compute",
                            "instances",
                            "start",
                            args.instance,
                            *base,
                        ]
                    )
                    for _attempt in range(40):
                        ready = _run(
                            [
                                args.gcloud,
                                "compute",
                                "ssh",
                                args.instance,
                                *base,
                                "--command",
                                "echo ready",
                            ],
                            check=False,
                        )
                        if ready.returncode == 0 and "ready" in ready.stdout:
                            break
                        time.sleep(15)
                    else:
                        raise TimeoutError("GCP stage-2 VM did not restore SSH")
                    _run(
                        [
                            args.gcloud,
                            "compute",
                            "ssh",
                            args.instance,
                            *base,
                            "--command",
                            (
                                "setsid -f bash /home/Mariano/gcp_run_rcda_stage2.sh "
                                "> /home/Mariano/stage2.restart.log 2>&1 < /dev/null"
                            ),
                        ]
                    )
                    spot_restarts += 1
                    _atomic_write_json(
                        state_path,
                        {
                            "phase": "restarted_after_spot_preemption",
                            "updated_at": utc_now(),
                            "instance": args.instance,
                            "spot_restarts": spot_restarts,
                        },
                    )
                    time.sleep(10)
                    continue
            if status == "error":
                raise RuntimeError("remote stage-2 process ended without a summary")
            if time.monotonic() >= deadline:
                raise TimeoutError("GCP stage-2 nightwatch deadline exceeded")
            time.sleep(max(30, args.poll_seconds))
    except Exception as exc:
        _run(
            [args.gcloud, "compute", "instances", "stop", args.instance, *base],
            check=False,
        )
        _atomic_write_json(
            state_path,
            {
                "phase": "error",
                "updated_at": utc_now(),
                "instance": args.instance,
                "instance_stop_requested": True,
                "error": repr(exc),
            },
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
