#!/usr/bin/env python3
"""Automated experiment loop runner for the wildfire prediction project.

This script automates the 10-step loop from LOOP_ENGINEERING_PLAN.md:

    1. HYPOTHESIS: Read next experiment from the queue
    2. PRE-CHECK: Run local smoke test (fail fast)
    3. COMMIT: git commit the experiment config
    4. PUSH: Push to GitHub (so Kaggle can clone latest)
    5. KAGGLE PUSH: Push kernel to Kaggle via kaggle CLI
    6. MONITOR: Poll kernel status until complete
    7. DOWNLOAD: Pull output metrics
    8. ANALYZE: Compare to baseline, decide keep/revert
    9. DOCUMENT: Append to EXPERIMENT_TRACKER.md
   10. ADVANCE: Move to next experiment in queue

It requires the Kaggle CLI (``pip install kaggle``) with API credentials
configured at ``~/.kaggle/kaggle.json``.

Usage:
    python scripts/run_experiment_loop.py                  # interactive
    python scripts/run_experiment_loop.py --auto           # run full queue
    python scripts/run_experiment_loop.py --list            # show queue
    python scripts/run_experiment_loop.py --run v14         # run specific
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER_FILE = REPO_ROOT / "docs" / "EXPERIMENT_TRACKER.md"
# Live mutable queue (archive/ holds historical snapshots only).
QUEUE_FILE = REPO_ROOT / "scripts" / "experiment_queue.json"
KAGGLE_USER = "alonsoalviraaaa"


def kernel_slug_for(exp: dict) -> str:
    """Resolve Kaggle kernel slug for an experiment."""
    if exp.get("kernel_slug"):
        return exp["kernel_slug"]
    version = exp["version"]
    if version == "v17":
        return f"{KAGGLE_USER}/wildfire-autonomous-research-v17"
    return f"{KAGGLE_USER}/wildfire-front-training-{version}"


# Acceptance criteria from LOOP_ENGINEERING_PLAN.md
ACCEPTANCE = {
    "iou": 0.15,
    "recall": 0.30,
    "precision": 0.30,
    "dice": 0.25,
    "best_epoch": 10,
    "val_loss": 0.20,
}


# --------------------------------------------------------------------------- #
# Experiment Queue Definition
# --------------------------------------------------------------------------- #
DEFAULT_QUEUE = [
    {
        "version": "v14",
        "name": "U-Net + Composite Loss (BCE+Dice+Tversky)",
        "hypothesis": "Composite loss with FN-heavy Tversky boosts recall over v13",
        "script": "kaggle_job/run_unet_training_v14.py",
        "flags": [
            "--model",
            "small",
            "--loss",
            "composite",
            "--epochs",
            "50",
            "--batch-size",
            "32",
            "--lr",
            "1e-3",
            "--pos-weight",
            "5.0",
        ],
        "expected": {"iou": "0.10-0.20", "recall": "0.15-0.30"},
        "status": "pending",
    },
    {
        "version": "v15",
        "name": "U-Net + SE Attention + Composite Loss",
        "hypothesis": "Channel attention improves feature selection on multi-modal input",
        "script": "kaggle_job/run_unet_training_v14.py",
        "flags": [
            "--model",
            "small",
            "--loss",
            "composite",
            "--se-attention",
            "--epochs",
            "50",
            "--batch-size",
            "32",
            "--lr",
            "1e-3",
        ],
        "expected": {"iou": "0.12-0.22", "recall": "0.20-0.35"},
        "depends_on": "v14",
        "status": "pending",
    },
    {
        "version": "v16",
        "name": "U-Net Full + Composite + EMA",
        "hypothesis": "Larger model capacity + EMA stabilizes training for higher IoU",
        "script": "kaggle_job/run_unet_training_v14.py",
        "flags": [
            "--model",
            "full",
            "--loss",
            "composite",
            "--ema-decay",
            "0.999",
            "--epochs",
            "50",
            "--batch-size",
            "16",
            "--grad-accum",
            "2",
            "--lr",
            "1e-3",
        ],
        "expected": {"iou": "0.15-0.25", "recall": "0.25-0.40"},
        "depends_on": "v15",
        "status": "pending",
    },
    {
        "version": "v17",
        "name": "U-Net Small + Focal Loss (gamma=3)",
        "hypothesis": "Focal loss with high gamma focuses on hardest fire pixels",
        "script": "kaggle_job/run_unet_training_v14.py",
        "flags": [
            "--model",
            "small",
            "--loss",
            "focal",
            "--pos-weight",
            "7.0",
            "--epochs",
            "50",
            "--batch-size",
            "32",
            "--lr",
            "1e-3",
        ],
        "expected": {"iou": "0.10-0.20", "recall": "0.20-0.40"},
        "status": "pending",
    },
    {
        "version": "v18",
        "name": "U-Net Small + Tversky Only (beta=0.7)",
        "hypothesis": "Pure Tversky loss maximizes recall without BCE interference",
        "script": "kaggle_job/run_unet_training_v14.py",
        "flags": [
            "--model",
            "small",
            "--loss",
            "tversky",
            "--epochs",
            "50",
            "--batch-size",
            "32",
            "--lr",
            "1e-3",
        ],
        "expected": {"iou": "0.08-0.18", "recall": "0.30-0.50"},
        "status": "pending",
    },
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def load_queue() -> list[dict]:
    """Load experiment queue, creating default if missing."""
    if not QUEUE_FILE.exists():
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps(DEFAULT_QUEUE, indent=2))
        print(f"[queue] Created default queue at {QUEUE_FILE}")
    return json.loads(QUEUE_FILE.read_text())


def save_queue(queue: list[dict]):
    QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def list_queue(queue: list[dict]):
    """Pretty-print the experiment queue."""
    print(f"\n{'=' * 80}")
    print(f"{'Ver':<6} {'Status':<10} {'Name':<50} {'Expected IoU':<15}")
    print(f"{'=' * 80}")
    for exp in queue:
        ver = exp["version"]
        status = exp.get("status", "pending")
        name = exp["name"][:48]
        exp_iou = exp.get("expected", {}).get("iou", "?")
        print(f"{ver:<6} {status:<10} {name:<50} {exp_iou:<15}")
    print(f"{'=' * 80}")
    print(f"Acceptance criteria: IoU>{ACCEPTANCE['iou']}, Recall>{ACCEPTANCE['recall']}\n")


def run_smoke_test() -> bool:
    """Run the local smoke test. Returns True on success.

    Historical v14 kernel smoke lives under ``kaggle_job/archive/`` (archived).
    Prefer product smoke via ``scripts/smoke_production_products.py`` / ``make smoke``.
    """
    print("\n[step] Running local smoke test...")
    script = REPO_ROOT / "kaggle_job" / "archive" / "smoke_test_v14.py"
    if not script.is_file():
        print(
            f"[SKIP] Archived v14 smoke not found at {script}\n"
            "  Product smoke: python scripts/smoke_production_products.py "
            "--products clm_v28,clm_ensemble_v34 --max-patches 12"
        )
        return False
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"[FAIL] Smoke test failed!\n{result.stdout}\n{result.stderr}")
        return False
    print("[OK] Smoke test passed.")
    # Show last few lines
    lines = result.stdout.strip().split("\n")
    for line in lines[-5:]:
        print(f"  {line}")
    return True


def git_commit_push(version: str, message: str):
    """Commit and push changes to GitHub so Kaggle can pull latest."""
    print(f"\n[step] Git commit + push for {version}...")
    subprocess.run(["git", "add", "-A"], cwd=str(REPO_ROOT), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"exp({version}): {message}"], cwd=str(REPO_ROOT), check=True
    )
    result = subprocess.run(["git", "push"], cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[WARN] git push failed: {result.stderr}")
    else:
        print("[OK] Pushed to GitHub.")


def kaggle_push_kernel(exp: dict) -> bool:
    """Push the kernel to Kaggle. Requires kaggle CLI configured."""
    script_path = REPO_ROOT / exp["script"]
    version = exp["version"]
    print(f"\n[step] Pushing kernel to Kaggle: {script_path}")

    meta_candidates = [
        REPO_ROOT / "kaggle_job" / f"kernel-metadata-{version}.json",
        REPO_ROOT / "kaggle_job" / "kernel-metadata.json",
    ]
    metadata_path = next((p for p in meta_candidates if p.exists()), meta_candidates[-1])
    meta = json.loads(metadata_path.read_text())
    meta["source_file"] = script_path.name
    meta["id"] = kernel_slug_for(exp)
    meta["language"] = "python"
    meta["kernel_type"] = "script"
    # kaggle CLI reads kernel-metadata.json in the push folder
    push_meta = REPO_ROOT / "kaggle_job" / "kernel-metadata.json"
    push_meta.write_text(json.dumps(meta, indent=2))

    result = subprocess.run(
        ["kaggle", "kernels", "push", "-p", str(REPO_ROOT / "kaggle_job")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"[FAIL] Kaggle push failed:\n{result.stdout}\n{result.stderr}")
        return False
    print("[OK] Kernel pushed to Kaggle.")
    print(f"  {result.stdout.strip()}")
    return True


def kaggle_monitor(kernel_slug: str, timeout: int = 14400, poll_interval: int = 120) -> bool:
    """Monitor kernel status until complete. Default timeout: 4 hours."""
    print(f"\n[step] Monitoring {kernel_slug} (timeout={timeout}s, poll={poll_interval}s)...")
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            ["kaggle", "kernels", "status", kernel_slug],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        output = result.stdout.strip()
        print(f"  [{int(time.time() - start)}s] {output}")

        if "complete" in output.lower() or "finished" in output.lower():
            return True
        if "error" in output.lower() or "cancelled" in output.lower():
            print(f"[FAIL] Kernel errored: {output}")
            return False
        time.sleep(poll_interval)

    print(f"[FAIL] Kernel timed out after {timeout}s")
    return False


def kaggle_pull_output(version: str, kernel_slug: str) -> dict | None:
    """Download kernel output and parse metrics."""
    print(f"\n[step] Downloading Kaggle output for {version}...")
    out_dir = REPO_ROOT / f"kaggle_outputs_{version}"
    out_dir.mkdir(exist_ok=True)

    result = subprocess.run(
        ["kaggle", "kernels", "output", kernel_slug, "-p", str(out_dir)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"[WARN] Download failed: {result.stderr}")
        return None

    summary_path = out_dir / "training_summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text())
    print(f"[WARN] training_summary.json not found in {out_dir}")
    return None


def analyze_results(version: str, results: dict, baseline: dict | None = None) -> dict:
    """Compare experiment results to baseline and acceptance criteria."""
    print(f"\n[step] Analyzing results for {version}...")
    test_metrics = results.get("test_metrics", {})
    thresh_05 = test_metrics.get("thresh_0.5", {})

    analysis = {
        "version": version,
        "iou": thresh_05.get("micro_iou", 0.0),
        "recall": thresh_05.get("micro_recall", 0.0),
        "precision": thresh_05.get("micro_precision", 0.0),
        "dice": thresh_05.get("micro_dice", 0.0),
        "best_epoch": results.get("best_epoch", 0),
        "val_loss": results.get("best_val_loss", 0.0),
    }

    # Check acceptance
    passes = []
    for key, threshold in ACCEPTANCE.items():
        val = analysis.get(key, 0)
        ok = val < threshold if key == "val_loss" else val > threshold
        passes.append(ok)
        symbol = "✅" if ok else "❌"
        comp = "<" if key == "val_loss" else ">"
        print(f"  {key}: {val:.4f} {comp} {threshold}  {symbol}")

    analysis["passes_acceptance"] = all(passes)

    # Compare to baseline
    if baseline:
        for key in ["iou", "recall", "precision", "dice"]:
            delta = analysis[key] - baseline.get(key, 0)
            symbol = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
            print(f"  Δ{key}: {delta:+.4f} vs baseline {symbol}")

    # Verdict
    if analysis["passes_acceptance"]:
        analysis["verdict"] = "✅ ACCEPTANCE MET"
    elif baseline and analysis["iou"] > baseline.get("iou", 0):
        analysis["verdict"] = "✅ Better than baseline"
    elif baseline:
        analysis["verdict"] = "❌ Worse than baseline → consider revert"
    else:
        analysis["verdict"] = "⚖️ First experiment, new baseline set"

    print(f"\n  VERDICT: {analysis['verdict']}")
    return analysis


def document_experiment(exp: dict, results: dict | None, analysis: dict | None):
    """Append experiment results to EXPERIMENT_TRACKER.md."""
    print(f"\n[step] Documenting {exp['version']} in EXPERIMENT_TRACKER.md...")

    tracker = (
        TRACKER_FILE if TRACKER_FILE.exists() else REPO_ROOT / "docs" / "EXPERIMENT_TRACKER.md"
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = f"""
### {exp["version"]}: {exp["name"]}
- **Date:** {timestamp}
- **Hypothesis:** {exp["hypothesis"]}
- **Change:** `{exp["script"]}` with flags: `{" ".join(exp.get("flags", []))}`
- **Status:** {exp.get("status", "pending")}
"""

    if results and analysis:
        entry += f"""- **IoU:** {analysis["iou"]:.4f}
- **Recall:** {analysis["recall"]:.4f}
- **Precision:** {analysis["precision"]:.4f}
- **Dice/F1:** {analysis["dice"]:.4f}
- **best_epoch:** {analysis["best_epoch"]}
- **val_loss:** {analysis["val_loss"]:.4f}
- **Acceptance:** {"ALL MET ✅" if analysis["passes_acceptance"] else "NOT YET ❌"}
- **Verdict:** {analysis["verdict"]}
"""
    else:
        entry += "- **Results:** (pending or failed)\n"

    entry += "- **Next:** See experiment queue for next step\n\n"

    with open(tracker, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"  [OK] Appended to {tracker}")


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #


def run_one_experiment(exp: dict, do_kaggle: bool = True) -> dict | None:
    """Run a single experiment end-to-end."""
    print(f"\n{'#' * 80}")
    print(f"# EXPERIMENT: {exp['version']} — {exp['name']}")
    print(f"{'#' * 80}")
    print(f"Hypothesis: {exp['hypothesis']}")
    print(f"Script: {exp['script']}")
    print(f"Flags: {' '.join(exp.get('flags', []))}")

    # Step 1: Smoke test
    if not run_smoke_test():
        exp["status"] = "smoke_failed"
        return None

    # Step 2: Git commit + push
    git_commit_push(exp["version"], exp["name"])

    if not do_kaggle:
        print("\n[info] Skipping Kaggle (--no-kaggle flag). Experiment staged.")
        exp["status"] = "staged"
        return None

    # Step 3: Push to Kaggle
    slug = kernel_slug_for(exp)
    if not kaggle_push_kernel(exp):
        exp["status"] = "push_failed"
        return None

    # Step 4: Monitor
    if not kaggle_monitor(slug):
        exp["status"] = "run_failed"
        return None

    # Step 5: Download results
    results = kaggle_pull_output(exp["version"], slug)
    if results is None:
        exp["status"] = "download_failed"
        return None

    # Step 6: Analyze
    analysis = analyze_results(exp["version"], results)

    # Step 7: Document
    document_experiment(exp, results, analysis)

    exp["status"] = "accepted" if analysis["passes_acceptance"] else "completed"
    exp["results"] = analysis
    return analysis


def main():
    parser = argparse.ArgumentParser(description="Wildfire experiment loop runner")
    parser.add_argument(
        "--auto", action="store_true", help="Run all pending experiments automatically"
    )
    parser.add_argument("--list", action="store_true", help="List experiment queue")
    parser.add_argument(
        "--run", type=str, default=None, help="Run specific experiment version (e.g. v14)"
    )
    parser.add_argument(
        "--no-kaggle", action="store_true", help="Run smoke test + git push only, skip Kaggle"
    )
    parser.add_argument("--reset-queue", action="store_true", help="Reset queue to defaults")
    args = parser.parse_args()

    if args.reset_queue:
        QUEUE_FILE.write_text(json.dumps(DEFAULT_QUEUE, indent=2))
        print(f"[info] Queue reset to defaults at {QUEUE_FILE}")

    queue = load_queue()

    if args.list or (not args.auto and not args.run):
        list_queue(queue)
        print("Use --auto to run all, or --run vX to run specific experiment.")
        return

    # Filter to target experiment
    if args.run:
        target = [e for e in queue if e["version"] == args.run]
        if not target:
            print(f"[error] Experiment {args.run} not found in queue.")
            return
        queue_to_run = target
    else:
        queue_to_run = [e for e in queue if e.get("status") == "pending"]

    if not queue_to_run:
        print("[info] No pending experiments to run.")
        return

    print(
        f"\n[info] Will run {len(queue_to_run)} experiment(s): "
        f"{[e['version'] for e in queue_to_run]}"
    )

    for exp in queue_to_run:
        analysis = run_one_experiment(exp, do_kaggle=not args.no_kaggle)
        if analysis and analysis["passes_acceptance"]:
            print(f"\n🎉 ACCEPTANCE CRITERIA MET at {exp['version']}! 🎉")
            print("Stopping experiment loop.")
            break
        save_queue(queue)

    print("\n[info] Experiment loop complete.")
    list_queue(queue)


if __name__ == "__main__":
    main()
