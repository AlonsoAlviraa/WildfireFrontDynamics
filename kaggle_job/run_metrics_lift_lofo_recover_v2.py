#!/usr/bin/env python3
"""Kaggle: E_recover_v2 — sealed lofo_v1 core-3 + multi_if init, longer/lower-LR.

Goal (E2 profile): core-3 mean >= 0.7681 (+0.010 vs sealed baseline 0.7581)
AND min (ACOM2) >= 0.700. No Hellín train-pool (E3a KILL). Residual small only.

vs E_recover (mean 0.7665 / min 0.7011, Δmean +0.0084, L1 fail / L2 pass):
  epochs 28 (was 16), lr 1e-4 (was 1.5e-4), patience 10 (was 8),
  ACOM2 change_loss_weight 10 / pos_weight 8 (was 9 / 7.5).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO_URL = "https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git"
REPO_DIR = Path("/tmp/WildfireFrontDynamics")
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
EPOCHS = int(os.environ.get("WF_EPOCHS", "28"))
LR = float(os.environ.get("WF_LR", "1e-4"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "10"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
BASELINE_MEAN = 0.7580534465179306
BASELINE_MIN = 0.6931861844919686
TARGET_MEAN = BASELINE_MEAN + 0.010  # E2 L1 KEEP bar


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _install_p100() -> None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0 or "P100" not in (r.stdout or ""):
            return
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "torch==2.1.2", "torchvision==0.16.2"],
            check=False,
            timeout=600,
        )
    except Exception as exc:
        print(f"[warn] p100: {exc}", flush=True)


def _root() -> Path:
    for c in (
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3"),
    ):
        if not c.is_dir():
            continue
        if any((c / f / "train").is_dir() for f in CORE3):
            return c
        z = c / "lofo_v1_core3.zip"
        if z.is_file():
            dest = Path("/tmp/lofo_v1")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            for cand in (dest, dest / "lofo_v1"):
                if any((cand / f / "train").is_dir() for f in CORE3):
                    return cand
    raise FileNotFoundError("lofo_v1 core3 missing (expect alonsoalviraaaa/wfd-lofo-v1-core3)")


def _find_init(data_root: Path) -> str:
    """Prefer multi_if; fall back to v21; optional recover fold weights if uploaded."""
    names = (
        "weights_multi_if.pt",
        "weights_v21_best.pt",
        "acom2_recover.pt",  # optional package for v2b-style init
    )
    search_roots = [
        data_root,
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/working"),
        Path("/tmp"),
    ]
    for name in names:
        for root in search_roots:
            if not root.exists():
                continue
            direct = root / name
            if direct.is_file():
                return str(direct)
            try:
                for p in root.rglob(name):
                    if p.is_file():
                        return str(p)
            except OSError:
                continue
    return ""


def _fold_hparams(held: str) -> tuple[float, float]:
    """Return (change_loss_weight, pos_weight) per held-out fold."""
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held == "LA_ESTRELLA_ACOM1":
        return 7.0, 6.5
    return 6.5, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("METRICS LIFT E_recover_v2 — sealed LOFO + multi_if, longer/lower-LR", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} batch={BATCH}", flush=True)
    print(f"target mean>={TARGET_MEAN:.4f}  min>=0.700  (no Hellin)", flush=True)
    print("=" * 70, flush=True)
    _install_p100()

    data_root = _root()
    init = _find_init(data_root)
    print("init", init or "(none)", "data", data_root, flush=True)

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    results = []
    for held in CORE3:
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        change_w, pos_w = _fold_hparams(held)
        cfg = UNetTrainConfig(
            epochs=EPOCHS,
            batch_size=BATCH,
            lr=LR,
            loss="composite",
            pos_weight=pos_w,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=change_w,
            weighted_sampler=True,
            patience=PATIENCE,
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"metrics_lift_recover_v2_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init or None,
        )
        print(
            f"=== recover_v2 held={held} change_w={change_w} pos_w={pos_w} ===",
            flush=True,
        )
        run_training(cfg)
        ts = out / "training_summary.json"
        row = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_recover_v2_sealed_multi_if",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(
                    {
                        "schema_path_id": "E_recover_v2",
                        "feature_schema": "legacy17",
                        "held_out": held,
                        "no_hellin": True,
                        "init_weights_path": init,
                        "experiment_id": "E_recover_v2_sealed_multi_if",
                        "change_loss_weight": change_w,
                        "pos_weight": pos_w,
                    }
                )
                ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                em = out / "evaluation_metrics.json"
                if not em.is_file():
                    em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    mean_iou = (sum(ious) / len(ious)) if ious else None
    min_iou = min(ious) if ious else None
    delta_mean = (mean_iou - BASELINE_MEAN) if mean_iou is not None else None
    board = {
        "schema": "wfd_kaggle_metrics_lift_recover_v2",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_recover_v2_sealed_multi_if",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "init_weights_path": init,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "delta_mean_vs_baseline": delta_mean,
        "delta_min_vs_baseline": (min_iou - BASELINE_MIN) if min_iou is not None else None,
        "baselines": {
            "lofo_mean_iou": BASELINE_MEAN,
            "lofo_min_iou": BASELINE_MIN,
        },
        "e2_target": {
            "mean_ge": TARGET_MEAN,
            "min_ge": 0.700,
            "l1_pass": bool(mean_iou is not None and mean_iou >= TARGET_MEAN),
            "l2_pass": bool(min_iou is not None and min_iou >= 0.700),
        },
        "note": "no Hellin; multi_if init; residual small; longer/lower-LR recover_v2",
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
        },
    }
    (out_root / "metrics_lift_recover_v2_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
