#!/usr/bin/env python3
"""Production loop: monitor Kaggle experiment + refresh deploy artifacts.

Steps per cycle:
  1. Poll active kernel in experiment_queue.json (status=running)
  2. On COMPLETE: download training_summary.json, update queue
  3. Re-export TorchScript if production weights exist
  4. Optionally verify Docker inference image

Usage:
    python scripts/run_production_loop.py
    python scripts/run_production_loop.py --once
    python scripts/run_production_loop.py --export-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / "scripts" / "experiment_queue.json"
KAGGLE_USER = "alonsoalviraaaa"


def _load_queue() -> list[dict]:
    return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))


def _save_queue(queue: list[dict]) -> None:
    QUEUE_FILE.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")


def _kernel_status(slug: str) -> str:
    out = subprocess.run(
        ["kaggle", "kernels", "status", slug],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (out.stdout or out.stderr or "").strip()
    if "COMPLETE" in line:
        return "complete"
    if "RUNNING" in line or "QUEUED" in line:
        return "running"
    if "ERROR" in line or "FAILED" in line:
        return "failed"
    return "unknown"


def _download_summary(version: str, slug: str) -> dict | None:
    out_dir = PROJECT_ROOT / f"kaggle_outputs_{version}" / "_top"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", slug, "-p", str(out_dir)],
        check=False,
    )
    for candidate in [
        out_dir / "training_summary.json",
        out_dir / "WildfireFrontDynamics" / "training_summary.json",
    ]:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def _export_artifacts() -> None:
    weights = PROJECT_ROOT / "models" / "production" / "weights_v21_best.pt"
    if not weights.is_file():
        subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "install_production_weights.py")], check=False)
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "export_production_model.py")],
        check=True,
    )


def _docker_smoke() -> bool:
    image = "wildfire-front-inference:local"
    build = subprocess.run(
        ["docker", "build", "--target", "inference", "-t", image, str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        print(build.stderr[-500:] if build.stderr else "docker build failed")
        return False
    run = subprocess.run(
        ["docker", "run", "--rm", image, "python", "-c",
         "from wildfire_front.ml.spread_predictor import SpreadPredictor; print('ok')"],
        capture_output=True,
        text=True,
    )
    return run.returncode == 0


def run_cycle(*, docker: bool) -> None:
    queue = _load_queue()
    running = [e for e in queue if e.get("status") == "running"]
    if not running:
        print("[loop] No running experiments in queue")
    for exp in running:
        version = exp["version"]
        slug = exp.get("kernel_slug", f"{KAGGLE_USER}/wildfire-front-training-{version}")
        status = _kernel_status(slug)
        print(f"[loop] {version}: {status}")
        if status == "complete":
            summary = _download_summary(version, slug)
            if summary:
                exp["status"] = "completed"
                exp["results"] = {
                    "iou_full": round(float(summary.get("test_iou", 0)), 4),
                    "improvement_vs_copy_iou": round(
                        float(summary.get("improvement_vs_copy_iou", 0)), 4
                    ),
                    "improvement_vs_copy_iou_changed": round(
                        float(summary.get("improvement_vs_copy_iou_changed", 0)), 4
                    ),
                }
                print(f"[loop] {version} results: {exp['results']}")
            else:
                print(f"[loop] {version} complete but summary not found")
        elif status == "failed":
            exp["status"] = "failed"
    _save_queue(queue)

    print("[loop] Exporting TorchScript production artifacts...")
    _export_artifacts()

    if docker:
        print("[loop] Docker inference smoke...")
        ok = _docker_smoke()
        print(f"[loop] Docker smoke: {'OK' if ok else 'SKIP/FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Production monitoring + deploy loop")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--docker", action="store_true", help="Build and smoke-test inference image")
    parser.add_argument("--interval", type=int, default=120, help="Seconds between polls")
    args = parser.parse_args()

    if args.export_only:
        _export_artifacts()
        return 0

    if args.once:
        run_cycle(docker=args.docker)
        return 0

    while True:
        run_cycle(docker=args.docker)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
