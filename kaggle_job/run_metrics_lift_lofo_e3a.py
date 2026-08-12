#!/usr/bin/env python3
"""Kaggle GPU: metrics-lift E3a LOFO (Hellín train-pool) residual small.

Deep research (2023-2026): larger U-Net/ViT does not consistently beat residual
~1M on LOYO; multi-fire data is the primary EV. This job:

* residual small + composite + delta (same as sealed LOFO v1 recipe)
* core-3 folds: CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2
* data: lofo_v2 packs with hellin_2024 in train when not held out
* never Tobarra KEEP reopen; never field fusion; IoU ≠ ROS

Outputs under /kaggle/working/{FOLD}/evaluation_metrics.json + board summary.
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
EPOCHS = int(os.environ.get("WF_EPOCHS", "12"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
SMOKE = os.environ.get("WF_SMOKE", "").strip() in {"1", "true", "yes"}


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
        print("P100 → torch 2.1.2")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "torch==2.1.2", "torchvision==0.16.2"],
            check=False,
            timeout=600,
        )
    except Exception as exc:
        print(f"[warn] p100 fix: {exc}")


def _find_lofo_root() -> Path:
    candidates = [
        Path("/kaggle/input/wfd-lofo-v2-e3a"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v2-e3a"),
        Path("/kaggle/input/clm-wildfire-patches/lofo_v2"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/clm-wildfire-patches/lofo_v2"),
    ]
    for c in candidates:
        if not c.is_dir():
            continue
        # flat dataset: folds directly under root
        if any((c / f / "train").is_dir() for f in CORE3):
            print(f"[data] lofo root {c}")
            return c
        nested = c / "lofo_v2"
        if nested.is_dir() and any((nested / f / "train").is_dir() for f in CORE3):
            print(f"[data] lofo root {nested}")
            return nested
        # single pack zip (dataset create from flat zip)
        for zname in ("lofo_v2_core3.zip", "lofo_v2.zip"):
            z = c / zname
            if not z.is_file():
                continue
            dest = Path("/tmp/lofo_v2")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            print(f"[data] extract {z} → {dest}")
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(dest)
            for cand in (dest, dest / "lofo_v2", Path("/tmp")):
                if any((cand / f / "train").is_dir() for f in CORE3):
                    print(f"[data] lofo root {cand}")
                    return cand
    local = Path("artifacts/clm_ndws_patches/lofo_v2")
    if local.is_dir() and any((local / f / "train").is_dir() for f in CORE3):
        return local.resolve()
    raise FileNotFoundError("lofo_v2 packs not found under /kaggle/input")


def _find_init_weights(lofo_root: Path) -> str:
    for p in (
        lofo_root / "weights_v21_best.pt",
        lofo_root.parent / "weights_v21_best.pt",
        Path("/kaggle/input/wfd-lofo-v2-e3a/weights_v21_best.pt"),
        Path("/kaggle/input/wildfire-checkpoint-weights/weights_v21_best.pt"),
        Path("models/production/weights_v21_best.pt"),
    ):
        if p.is_file():
            print(f"[init] {p}")
            return str(p)
    print("[init] none — train from residual random/schema default")
    return ""


def _clone_repo() -> None:
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    print("Cloning repo...")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    rev = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"  commit {rev.stdout.strip()}")


def main() -> int:
    print("=" * 70)
    print("METRICS LIFT E3a — LOFO residual small (Hellín train-pool)")
    print("Rails: lab_ml only · fusion OFF · IoU≠ROS · no Tobarra KEEP · no larger U-Net")
    print("=" * 70)
    _install_p100()
    lofo_root = _find_lofo_root()
    init_w = _find_init_weights(lofo_root)
    out_root = _working()
    epochs = 1 if SMOKE else EPOCHS

    _clone_repo()
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))

    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    results: list[dict] = []
    for held in CORE3:
        data = lofo_root / held
        if not (data / "train").is_dir():
            results.append({"held": held, "status": "missing_split"})
            continue
        out = out_root / held
        out.mkdir(parents=True, exist_ok=True)
        cfg = UNetTrainConfig(
            epochs=epochs,
            batch_size=BATCH,
            lr=3e-4,
            loss="composite",
            pos_weight=5.0,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=5.0,
            weighted_sampler=True,
            patience=6 if epochs > 2 else max(1, epochs),
            data_dir=str(data),
            output_dir=str(out),
            version_tag=f"metrics_lift_e3a_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init_w,
        )
        print(f"\n=== LOFO held={held} epochs={epochs} ===", flush=True)
        summary = run_training(cfg)
        row = {
            "held": held,
            "status": "ok",
            "feature_schema": "legacy17",
            "schema_path_id": "E3a",
            "experiment_id": "E3a_hellin_train_pool",
            "smoke": SMOKE,
        }
        if isinstance(summary, dict):
            row.update(
                {
                    "model_iou": summary.get("model_iou") or summary.get("test_iou"),
                    "copy_baseline_iou": summary.get("copy_baseline_iou"),
                    "improvement_vs_copy_iou": summary.get("improvement_vs_copy_iou"),
                    "test_iou": summary.get("test_iou") or summary.get("model_iou"),
                }
            )
        # enrich training_summary
        ts = out / "training_summary.json"
        if ts.is_file():
            try:
                prev = json.loads(ts.read_text(encoding="utf-8"))
                if isinstance(prev, dict):
                    prev.update(
                        {
                            "feature_schema": "legacy17",
                            "schema_path_id": "E3a",
                            "held_out": held,
                            "experiment_id": "E3a_hellin_train_pool",
                            "rails": {
                                "field_ops_allow_ml_live_in_fusion": False,
                                "iou_is_not_ros": True,
                                "tobarra_keep_reopen": False,
                                "larger_unet_default": False,
                            },
                        }
                    )
                    ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                    row["model_iou"] = (
                        row.get("model_iou") or prev.get("model_iou") or prev.get("test_iou")
                    )
                    row["copy_baseline_iou"] = row.get("copy_baseline_iou") or prev.get(
                        "copy_baseline_iou"
                    )
                    row["improvement_vs_copy_iou"] = row.get("improvement_vs_copy_iou") or prev.get(
                        "improvement_vs_copy_iou"
                    )
            except Exception as exc:
                row["summary_enrich_error"] = str(exc)
        # evaluation_metrics symlink-ish copy for scorer
        em = out / "evaluation_metrics.json"
        if not em.is_file() and ts.is_file():
            try:
                prev = json.loads(ts.read_text(encoding="utf-8"))
                em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
            except Exception:
                pass
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    board = {
        "schema": "wfd_kaggle_metrics_lift_e3a_board_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E3a_hellin_train_pool",
        "product_rail": "lab_ml",
        "feature_schema": "legacy17",
        "architecture": "residual_small",
        "epochs": epochs,
        "smoke": SMOKE,
        "folds": results,
        "core3_mean_iou": (sum(ious) / len(ious)) if ious else None,
        "core3_min_iou": min(ious) if ious else None,
        "n_folds_ok": len(ious),
        "baselines": {
            "lofo_mean_iou": 0.7580534465179306,
            "lofo_min_iou": 0.6931861844919686,
            "note": "compare after download; scorer is source of KEEP",
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "deep_research": "capacity≠LOYO win; multi-fire data primary EV",
        },
        "honesty": [
            "Not field fusion",
            "Not Tobarra KEEP reopen",
            "Not ML IoU as ROS",
            "Hellín train-pool only may leave D3 SKIPPED",
        ],
    }
    out_path = out_root / "metrics_lift_e3a_kaggle_board.json"
    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    print("\n=== BOARD ===")
    print(json.dumps(board, indent=2))
    print(f"wrote {out_path}")
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
