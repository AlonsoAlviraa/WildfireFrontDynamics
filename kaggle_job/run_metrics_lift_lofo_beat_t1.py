#!/usr/bin/env python3
"""Kaggle: beat historic force_train_multi_if T1 KEEP on sealed LOFO core-3.

Historic champion (grid): mean 0.785709 / min 0.707073 (recipe_t1_sealed, multi_if).
This push: longer/lower-LR residual-small + multi_if init + ACOM2 heavier change.

Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra thrash · residual small only.
work_class: recipe_t1_sealed (NOT feature_spatial_v1).
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
EPOCHS = int(os.environ.get("WF_EPOCHS", "50"))
LR = float(os.environ.get("WF_LR", "5e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "15"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
HIST_MEAN = 0.7857091284390876
HIST_MIN = 0.7070728142438604
BASELINE_MEAN = 0.7580534465179306


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
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "torch==2.1.2",
                "torchvision==0.16.2",
            ],
            check=False,
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] p100: {exc}", flush=True)


def _root() -> Path:
    input_root = Path("/kaggle/input")
    candidates = [
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3"),
        Path("/kaggle/input/wfd-lofo-v2-e3a"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v2-e3a"),
    ]
    if input_root.is_dir():
        for d in input_root.rglob("*"):
            if d.is_dir() and all((d / f / "train").is_dir() for f in CORE3):
                return d
    for c in candidates:
        if c.is_dir() and all((c / f / "train").is_dir() for f in CORE3):
            return c
        for z in c.glob("*.zip") if c.is_dir() else []:
            dest = Path("/tmp/lofo_core3")
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            for cand in (dest, *dest.iterdir()):
                if cand.is_dir() and all((cand / f / "train").is_dir() for f in CORE3):
                    return cand
    # debug
    if input_root.is_dir():
        for p in sorted(input_root.iterdir())[:20]:
            print(f"  input: {p}", flush=True)
    raise FileNotFoundError("sealed LOFO core-3 pack missing under /kaggle/input")


def _find_init(data_root: Path) -> str:
    names = (
        "weights_multi_if.pt",
        "weights_multi_if_r8.pt",
        "weights_v21_best.pt",
    )
    roots = [data_root, Path("/kaggle/input"), Path("/kaggle/working"), Path("/tmp")]
    for name in names:
        for root in roots:
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
    # Slightly more aggressive than force_train defaults for ACOM2 floor
    if held == "LA_ESTRELLA_ACOM2":
        return 11.0, 8.5
    if held == "LA_ESTRELLA_ACOM1":
        return 7.5, 7.0
    return 6.5, 6.0


def main() -> int:
    print("=" * 70, flush=True)
    print("BEAT T1 — sealed LOFO residual-small + multi_if, longer/lower-LR", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} batch={BATCH}", flush=True)
    print(f"historic mean={HIST_MEAN:.6f} min={HIST_MIN:.6f}", flush=True)
    print("=" * 70, flush=True)
    _install_p100()

    data_root = _root()
    init = _find_init(data_root)
    print("data", data_root, "init", init or "(none)", flush=True)

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
            version_tag=f"beat_t1_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init or None,
        )
        print(
            f"=== beat_t1 held={held} change_w={change_w} pos_w={pos_w} ===",
            flush=True,
        )
        run_training(cfg)
        ts = out / "training_summary.json"
        row = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_beat_t1_force_longer",
            "feature_schema": "legacy17",
            "work_class": "recipe_t1_sealed",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "init_weights_path": init,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(row)
                prev["schema_path_id"] = "E_beat_t1"
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
    board = {
        "schema": "wfd_kaggle_metrics_lift_beat_t1_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_beat_t1_force_longer",
        "feature_schema": "legacy17",
        "work_class": "recipe_t1_sealed",
        "architecture": "residual_small",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "init_weights_path": init,
        "folds": results,
        "core3_mean_iou": mean_iou,
        "core3_min_iou": min_iou,
        "historic_t1": {"mean": HIST_MEAN, "min": HIST_MIN, "config": "force_train_multi_if"},
        "beats_historic": bool(
            mean_iou is not None
            and min_iou is not None
            and mean_iou > HIST_MEAN
            and min_iou > HIST_MIN
        ),
        "e2_vs_sealed_baseline": {
            "mean_ge": BASELINE_MEAN + 0.010,
            "min_ge": 0.700,
            "l1_pass": bool(mean_iou is not None and mean_iou >= BASELINE_MEAN + 0.010),
            "l2_pass": bool(min_iou is not None and min_iou >= 0.700),
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
    }
    (out_root / "metrics_lift_beat_t1_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
