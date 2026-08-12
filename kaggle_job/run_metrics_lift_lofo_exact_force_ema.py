#!/usr/bin/env python3
"""Kaggle: exact force_train_multi_if hparams + EMA (recipe_t1_fix track).

Historic champion (grid rank-1)::

    force_train_multi_if  mean=0.785709  min=0.707073
    epochs=36 lr=3e-5 patience=20 batch=8
    change_w=6 pos_w=6  acom2_change_w=10 acom2_pos_w=8

This kernel runs three sealed configs (no feature thrash, residual-small)::

1. exact_force_train — bit-for-bit hparam clone (repro check)
2. exact_force_ema   — same + EMA 0.999 (stabilize epoch-1 peak)
3. exact_force_ema_long — EMA + patience 28 / epochs 48 / lr 2.5e-5

Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra · residual small.
work_class: recipe_t1_fix
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
HIST_MEAN = 0.7857091284390876
HIST_MIN = 0.7070728142438604
BASELINE_MEAN = 0.7580534465179306

CONFIGS: list[dict] = [
    {
        "id": "exact_force_train",
        "epochs": 36,
        "lr": 3e-5,
        "patience": 20,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "ema_decay": 0.0,
        "note": "exact historic force_train_multi_if clone",
    },
    {
        "id": "exact_force_ema",
        "epochs": 36,
        "lr": 3e-5,
        "patience": 20,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "ema_decay": 0.999,
        "note": "historic hparams + EMA 0.999",
    },
    {
        "id": "exact_force_ema_long",
        "epochs": 48,
        "lr": 2.5e-5,
        "patience": 28,
        "batch": 8,
        "change_w": 6.0,
        "pos_w": 6.0,
        "acom2_change_w": 10.0,
        "acom2_pos_w": 8.0,
        "ema_decay": 0.999,
        "note": "EMA + longer low-LR continuation",
    },
]


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
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] p100: {exc}", flush=True)


def _root() -> Path:
    input_root = Path("/kaggle/input")
    candidates = [
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3"),
        Path("/kaggle/input/wfd-lofo-grid-inits"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-grid-inits"),
    ]
    if input_root.is_dir():
        for d in input_root.rglob("*"):
            if d.is_dir() and all((d / f / "train").is_dir() for f in CORE3):
                return d
    for c in candidates:
        if c.is_dir() and all((c / f / "train").is_dir() for f in CORE3):
            return c
        if c.is_dir():
            for z in c.glob("*.zip"):
                dest = Path("/tmp/lofo_core3")
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir(parents=True)
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(dest)
                for cand in (dest, *list(dest.iterdir())):
                    if cand.is_dir() and all((cand / f / "train").is_dir() for f in CORE3):
                        return cand
    raise FileNotFoundError("sealed LOFO core-3 pack missing under /kaggle/input")


def _find_init(data_root: Path) -> str:
    names = ("weights_multi_if.pt", "weights_multi_if_r8.pt", "weights_v21_best.pt")
    roots = [data_root, Path("/kaggle/input"), Path("/kaggle/working")]
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


def _fold_hparams(cfg: dict, held: str) -> tuple[float, float]:
    if held == "LA_ESTRELLA_ACOM2":
        return float(cfg["acom2_change_w"]), float(cfg["acom2_pos_w"])
    return float(cfg["change_w"]), float(cfg["pos_w"])


def main() -> int:
    print("=" * 70, flush=True)
    print("EXACT FORCE+EMA — beat historic force_train_multi_if", flush=True)
    print(f"historic mean={HIST_MEAN:.6f} min={HIST_MIN:.6f}", flush=True)
    print(f"n_configs={len(CONFIGS)} residual_small multi_if", flush=True)
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
    leaderboard: list[dict] = []

    for cfg in CONFIGS:
        cid = cfg["id"]
        fold_rows: list[dict] = []
        for held in CORE3:
            out = out_root / cid / held
            out.mkdir(parents=True, exist_ok=True)
            change_w, pos_w = _fold_hparams(cfg, held)
            train_cfg = UNetTrainConfig(
                epochs=int(cfg["epochs"]),
                batch_size=int(cfg["batch"]),
                lr=float(cfg["lr"]),
                loss="composite",
                pos_weight=pos_w,
                model="small",
                architecture="residual",
                target_mode="delta",
                change_loss_weight=change_w,
                weighted_sampler=True,
                patience=int(cfg["patience"]),
                ema_decay=float(cfg.get("ema_decay") or 0.0),
                data_dir=str(data_root / held),
                output_dir=str(out),
                version_tag=f"exact_{cid}_{held}",
                early_stop_metric="improvement_vs_copy_iou",
                init_weights_path=init or None,
            )
            print(
                f"=== {cid} held={held} ch={change_w} pos={pos_w} "
                f"lr={cfg['lr']} ema={cfg.get('ema_decay')} ===",
                flush=True,
            )
            run_training(train_cfg)
            ts = out / "training_summary.json"
            row: dict = {
                "held": held,
                "status": "ok",
                "config_id": cid,
                "work_class": "recipe_t1_fix",
                "feature_schema": "legacy17",
                "change_loss_weight": change_w,
                "pos_weight": pos_w,
                "lr": cfg["lr"],
                "epochs": cfg["epochs"],
                "ema_decay": cfg.get("ema_decay"),
            }
            if ts.is_file():
                prev = json.loads(ts.read_text(encoding="utf-8"))
                if isinstance(prev, dict):
                    prev.update(
                        {
                            "work_class": "recipe_t1_fix",
                            "feature_schema": "legacy17",
                            "experiment_id": f"exact_{cid}",
                            "held_out": held,
                            "init_weights_path": init,
                        }
                    )
                    ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                    row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                    row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                    row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                    row["best_epoch"] = prev.get("best_epoch")
                    em = out / "evaluation_metrics.json"
                    if not em.is_file():
                        em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
            fold_rows.append(row)
            print(json.dumps(row, indent=2), flush=True)

        ious = [float(r["model_iou"]) for r in fold_rows if r.get("model_iou") is not None]
        mean_iou = (sum(ious) / len(ious)) if ious else None
        min_iou = min(ious) if ious else None
        beats = bool(
            mean_iou is not None
            and min_iou is not None
            and mean_iou > HIST_MEAN
            and min_iou > HIST_MIN
        )
        entry = {
            "config_id": cid,
            "mean": mean_iou,
            "min": min_iou,
            "delta_mean_vs_historic": (mean_iou - HIST_MEAN) if mean_iou is not None else None,
            "delta_min_vs_historic": (min_iou - HIST_MIN) if min_iou is not None else None,
            "beats_historic_force_train": beats,
            "note": cfg.get("note"),
            "folds": fold_rows,
            "work_class": "recipe_t1_fix",
            "hparams": {
                k: cfg[k]
                for k in ("epochs", "lr", "patience", "batch", "ema_decay", "acom2_change_w")
                if k in cfg
            },
        }
        leaderboard.append(entry)
        print(f"[board] {cid} mean={mean_iou} min={min_iou} beats={beats}", flush=True)

    leaderboard.sort(
        key=lambda e: (
            0 if e.get("beats_historic_force_train") else 1,
            -(e.get("mean") or 0.0),
            -(e.get("min") or 0.0),
        )
    )
    for i, e in enumerate(leaderboard, 1):
        e["rank"] = i

    any_beat = any(e.get("beats_historic_force_train") for e in leaderboard)
    board = {
        "schema": "wfd_kaggle_exact_force_ema_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_exact_force_ema",
        "work_class": "recipe_t1_fix",
        "feature_schema": "legacy17",
        "architecture": "residual_small",
        "init_weights_path": init,
        "historic_force_train_multi_if": {"mean": HIST_MEAN, "min": HIST_MIN},
        "baselines": {"lofo_mean_iou": BASELINE_MEAN},
        "n_configs": len(CONFIGS),
        "leaderboard": leaderboard,
        "any_beats_historic": any_beat,
        "best": leaderboard[0] if leaderboard else None,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
        "note": "Exact force_train clone + EMA variants. Beat = mean>0.785709 AND min>0.707073.",
    }
    (out_root / "exact_force_ema_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if leaderboard and all(len(e.get("folds") or []) == 3 for e in leaderboard) else 1


if __name__ == "__main__":
    raise SystemExit(main())
