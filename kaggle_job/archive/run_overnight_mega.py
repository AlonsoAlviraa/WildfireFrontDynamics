#!/usr/bin/env python3
"""Overnight mega-training — sequential experiments, one Kaggle session.

Runs 8 experiments (~2-4h T4) reusing preprocess per filter_mode.
Outputs: /kaggle/working/overnight_report.json + per-version summaries.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")
WORKING = Path(os.environ.get("KAGGLE_WORKING", "/kaggle/working"))

EXPERIMENTS: list[dict] = [
    {
        "version_tag": "v23",
        "hypothesis": "v21 + EMA decay 0.999",
        "data_key": "any_fire",
        "architecture": "residual",
        "target_mode": "delta",
        "ema_decay": 0.999,
        "epochs": 50,
        "patience": 12,
    },
    {
        "version_tag": "v25",
        "hypothesis": "v21 long schedule 100 epochs",
        "data_key": "any_fire",
        "architecture": "residual",
        "target_mode": "delta",
        "epochs": 100,
        "patience": 20,
    },
    {
        "version_tag": "v27",
        "hypothesis": "v21 + focal loss (hard examples)",
        "data_key": "any_fire",
        "architecture": "residual",
        "target_mode": "delta",
        "loss": "focal",
        "epochs": 50,
    },
    {
        "version_tag": "v28",
        "hypothesis": "v21 lower LR fine-grain",
        "data_key": "any_fire",
        "architecture": "residual",
        "target_mode": "delta",
        "lr": 5e-4,
        "epochs": 80,
        "patience": 15,
    },
    {
        "version_tag": "v24",
        "hypothesis": "v22 changed-filter + EMA",
        "data_key": "changed",
        "architecture": "residual",
        "target_mode": "delta",
        "ema_decay": 0.999,
        "epochs": 50,
        "patience": 12,
    },
    {
        "version_tag": "v26",
        "hypothesis": "v22 changed-filter long 100 epochs",
        "data_key": "changed",
        "architecture": "residual",
        "target_mode": "delta",
        "epochs": 100,
        "patience": 20,
    },
    {
        "version_tag": "v29",
        "hypothesis": "v22 changed + focal loss",
        "data_key": "changed",
        "architecture": "residual",
        "target_mode": "delta",
        "loss": "focal",
        "epochs": 50,
    },
    {
        "version_tag": "v30",
        "hypothesis": "CLM fine-tune warm-start from v21 weights",
        "data_key": "any_fire",
        "architecture": "residual",
        "target_mode": "delta",
        "epochs": 35,
        "lr": 3e-4,
        "patience": 8,
        "warm_start_from": "v21",
    },
]

FILTER_MAP = {"any_fire": "any_fire", "changed": "changed"}


def _install_pytorch_p100_compat() -> None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and "P100" in r.stdout:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q",
                 "torch==2.1.2", "torchvision==0.16.2"],
                check=False,
            )
    except Exception:
        pass


def _clone_and_enter() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR))


def _detect_clm() -> str | None:
    import zipfile

    for candidate in (
        "/kaggle/input/clm-wildfire-patches",
        "/kaggle/input/datasets/alonsoalviraaaa/clm-wildfire-patches",
    ):
        root = Path(candidate)
        if not root.is_dir():
            continue
        z = root / "train.zip"
        if z.exists() and not (root / "train").is_dir():
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(root)
        if (root / "train").is_dir():
            return candidate
    return None


def _resolve_warm_start(tag: str, working: Path) -> str | None:
    candidates = [
        working / "experiments" / tag / "weights_pretrained_best.pt",
        Path(f"/kaggle/input/wildfire-checkpoint-weights/{tag}/weights_pretrained_best.pt"),
        Path(f"/kaggle/input/wildfire-checkpoint-weights/v21/weights_pretrained_best.pt"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


print("=" * 70)
print("OVERNIGHT MEGA TRAINING — WildfireFrontDynamics")
print(f"Experiments queued: {len(EXPERIMENTS)}")
print("=" * 70)

_install_pytorch_p100_compat()
_clone_and_enter()

from kaggle_job.kaggle_common import run_preprocess_ndws, verify_residual_imports  # noqa: E402
from wildfire_front.ml.unet_train import UNetTrainConfig, merge_clm_patches, run_training  # noqa: E402

verify_residual_imports(REPO_DIR)
clm_dir = _detect_clm()

data_roots: dict[str, Path] = {}
report: dict = {
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "experiments": [],
    "best": {"version": "v21", "test_iou": 0.2256, "improvement_vs_copy_iou": 0.0756},
}

for exp in EXPERIMENTS:
    tag = exp["version_tag"]
    data_key = exp["data_key"]
    filter_mode = FILTER_MAP[data_key]

    if data_key not in data_roots:
        root = Path(f"/tmp/ndws_npz_{data_key}")
        data_roots[data_key] = root
        print(f"\n=== PREPROCESS {data_key} -> {root} ===")
        run_preprocess_ndws(root, filter_mode=filter_mode, min_total=50)
        if clm_dir:
            merge_clm_patches(root, Path(clm_dir))

    out_dir = WORKING / "experiments" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    warm_start = None
    if exp.get("warm_start_from"):
        warm_start = _resolve_warm_start(str(exp["warm_start_from"]), WORKING)

    cfg = UNetTrainConfig(
        version_tag=tag,
        data_dir=str(data_roots[data_key]),
        output_dir=str(out_dir),
        architecture=exp.get("architecture", "residual"),
        target_mode=exp.get("target_mode", "delta"),
        loss=exp.get("loss", "composite"),
        lr=exp.get("lr", 1e-3),
        epochs=exp.get("epochs", 50),
        patience=exp.get("patience", 10),
        ema_decay=exp.get("ema_decay", 0.0),
        weighted_sampler=True,
        clm_data_dir=clm_dir,
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=warm_start,
    )

    print(f"\n{'=' * 70}\nSTART {tag}: {exp['hypothesis']}\n{'=' * 70}")
    t0 = time.time()
    try:
        summary = run_training(cfg)
        row = {
            "version": tag,
            "hypothesis": exp["hypothesis"],
            "status": "complete",
            "elapsed_s": round(time.time() - t0, 1),
            "test_iou": summary.get("test_iou"),
            "improvement_vs_copy_iou": summary.get("improvement_vs_copy_iou"),
            "improvement_vs_copy_iou_changed": summary.get("improvement_vs_copy_iou_changed"),
            "best_epoch": summary.get("best_epoch"),
        }
        iou = float(summary.get("test_iou", 0))
        delta = float(summary.get("improvement_vs_copy_iou", 0))
        if iou > report["best"]["test_iou"] or (
            abs(iou - report["best"]["test_iou"]) < 0.002 and delta > report["best"]["improvement_vs_copy_iou"]
        ):
            report["best"] = {
                "version": tag,
                "test_iou": iou,
                "improvement_vs_copy_iou": delta,
            }
            print(f"*** NEW BEST: {tag} IoU={iou:.4f} delta={delta:+.4f} ***")
    except Exception as exc:
        row = {
            "version": tag,
            "hypothesis": exp["hypothesis"],
            "status": "failed",
            "error": str(exc)[-500:],
            "elapsed_s": round(time.time() - t0, 1),
        }
        print(f"FAILED {tag}: {exc}")

    report["experiments"].append(row)
    (WORKING / "overnight_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Checkpoint report -> {WORKING / 'overnight_report.json'}")

report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
(WORKING / "overnight_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\n=== OVERNIGHT MEGA COMPLETE ===")
print(json.dumps(report["best"], indent=2))