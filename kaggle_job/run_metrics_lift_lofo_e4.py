#!/usr/bin/env python3
"""Kaggle GPU: metrics-lift E4 curriculum LOFO residual (raise ACOM2 floor).

After E3a KILL (Hellín pool hurt min floor), E4 uses sealed-style LOFO data
with stronger growth curriculum (change_loss_weight, pos_weight, longer train).

Deep research: residual ~1M stays default; no larger U-Net.
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
EPOCHS = int(os.environ.get("WF_EPOCHS", "20"))
BATCH = int(os.environ.get("WF_BATCH", "8"))


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
        print(f"[warn] p100: {exc}")


def _find_lofo_root() -> Path:
    for c in (
        Path("/kaggle/input/wfd-lofo-v2-e3a"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v2-e3a"),
    ):
        if not c.is_dir():
            continue
        if any((c / f / "train").is_dir() for f in CORE3):
            return c
        for zname in ("lofo_v2_core3.zip", "lofo_v2.zip"):
            z = c / zname
            if not z.is_file():
                continue
            dest = Path("/tmp/lofo_v2")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(dest)
            for cand in (dest, dest / "lofo_v2"):
                if any((cand / f / "train").is_dir() for f in CORE3):
                    return cand
    raise FileNotFoundError("lofo packs missing")


def _find_init(lofo_root: Path) -> str:
    for p in (
        lofo_root / "weights_v21_best.pt",
        Path("/kaggle/input/wfd-lofo-v2-e3a/weights_v21_best.pt"),
    ):
        if p.is_file():
            return str(p)
    # after extract
    for p in Path("/tmp").rglob("weights_v21_best.pt"):
        return str(p)
    return ""


def main() -> int:
    print("=" * 70)
    print("METRICS LIFT E4 — curriculum residual LOFO (floor-first)")
    print("=" * 70)
    _install_p100()
    lofo_root = _find_lofo_root()
    init_w = _find_init(lofo_root)
    out_root = _working()

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))

    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    results = []
    for held in CORE3:
        data = lofo_root / held
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        # E4 curriculum: stronger growth focus when generalizing to weak fold
        # (held-out never in train; curriculum on train growth pixels)
        change_w = 10.0 if held == "LA_ESTRELLA_ACOM2" else 7.0
        pos_w = 8.0 if held == "LA_ESTRELLA_ACOM2" else 6.0
        cfg = UNetTrainConfig(
            epochs=EPOCHS,
            batch_size=BATCH,
            lr=2e-4,
            loss="composite",
            pos_weight=pos_w,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=change_w,
            weighted_sampler=True,
            patience=8,
            data_dir=str(data),
            output_dir=str(out),
            version_tag=f"metrics_lift_e4_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init_w,
        )
        print(f"\n=== E4 held={held} change_w={change_w} pos_w={pos_w} ===", flush=True)
        summary = run_training(cfg)
        row = {
            "held": held,
            "status": "ok",
            "schema_path_id": "E4",
            "experiment_id": "E4_curriculum_growth",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
        }
        ts = out / "training_summary.json"
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(
                    {
                        "feature_schema": "legacy17",
                        "schema_path_id": "E4",
                        "experiment_id": "E4_curriculum_growth",
                        "held_out": held,
                    }
                )
                ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                em = out / "evaluation_metrics.json"
                if not em.is_file():
                    em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        elif isinstance(summary, dict):
            row["model_iou"] = summary.get("model_iou") or summary.get("test_iou")
            row["copy_baseline_iou"] = summary.get("copy_baseline_iou")
            row["improvement_vs_copy_iou"] = summary.get("improvement_vs_copy_iou")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    board = {
        "schema": "wfd_kaggle_metrics_lift_e4_board_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E4_curriculum_growth",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "folds": results,
        "core3_mean_iou": (sum(ious) / len(ious)) if ious else None,
        "core3_min_iou": min(ious) if ious else None,
        "baselines": {"lofo_mean_iou": 0.7580534465179306, "lofo_min_iou": 0.6931861844919686},
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
        },
        "prior": "E3a_hellin_train_pool CLOSED_KILL",
    }
    (out_root / "metrics_lift_e4_kaggle_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2))
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
