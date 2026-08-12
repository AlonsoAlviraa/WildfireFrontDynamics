#!/usr/bin/env python3
"""Kaggle: LOFO v4 Cardoso-extra train — residual-small multi_if exact_force_ema_long.

Pack: alonsoalviraaaa/wfd-lofo-v4-cardoso-extra (legacy17, T=1)
  held: CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2, hellin_2024
  train fill includes Cardoso FOV-reproject extra patches (70) + honesty fires

Goal: honest Δmean vs sealed champion (0.7878) — target track +0.05 if data lifts.

Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra KEEP · residual-small.
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
FOLDS = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2", "hellin_2024")
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
EPOCHS = int(os.environ.get("WF_EPOCHS", "48"))
LR = float(os.environ.get("WF_LR", "2.5e-5"))
PATIENCE = int(os.environ.get("WF_PATIENCE", "28"))
BATCH = int(os.environ.get("WF_BATCH", "8"))
EMA = float(os.environ.get("WF_EMA_DECAY", "0.999"))
SEALED_CHAMP_MEAN = 0.7877704721329809
SEALED_CHAMP_MIN = 0.7071461821856562
V3_CORE3_MEAN = 0.7756272444439091
V3_CORE3_MIN = 0.6976247037297344
GOAL_DELTA = 0.05


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


def _install_p100() -> None:
    """No-op on modern Kaggle images (torch preinstalled). Keep for older P100 notes."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"[gpu] {(r.stdout or '').strip() or 'unknown'}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] gpu probe: {exc}", flush=True)


def _looks_like_lofo(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _maybe_extract_zip(zpath: Path) -> Path | None:
    dest = Path("/tmp/lofo_v4_cardoso_extra")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    if _looks_like_lofo(dest):
        return dest
    for child in dest.rglob("train"):
        parent = child.parent.parent
        if _looks_like_lofo(parent):
            return parent
    return None


def _root() -> Path:
    input_root = Path("/kaggle/input")
    hard = [
        Path("/kaggle/input/wfd-lofo-v4-cardoso-extra"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v4-cardoso-extra"),
        Path("/kaggle/input/wfd-lofo-v4-cardoso-extra/lofo_v4_cardoso_extra"),
        Path(
            "/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v4-cardoso-extra/lofo_v4_cardoso_extra"
        ),
    ]
    for c in hard:
        if c.is_dir() and _looks_like_lofo(c):
            return c
    if input_root.is_dir():
        # Prefer zip extract first (dataset often ships as single zip)
        for z in sorted(input_root.rglob("*.zip")):
            print(f"[data] try zip {z}", flush=True)
            got = _maybe_extract_zip(z)
            if got is not None:
                return got
        for d in input_root.rglob("*"):
            if d.is_dir() and _looks_like_lofo(d):
                return d
        print("[data] /kaggle/input tree:", flush=True)
        for p in sorted(input_root.rglob("*"))[:80]:
            print(" ", p, flush=True)
    raise FileNotFoundError("lofo_v4_cardoso_extra pack missing")


def _find_init(data_root: Path) -> str:
    names = (
        "weights_multi_if.pt",
        "weights_multi_if_r8.pt",
        "weights_champion_acom2_exact_force_ema_long.pt",
        "weights_v21_best.pt",
    )
    for name in names:
        for root in (data_root, Path("/kaggle/input"), Path("/kaggle/working")):
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
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held in ("LA_ESTRELLA_ACOM1", "hellin_2024"):
        return 7.0, 6.5
    return 6.0, 6.0


def _assert_uniform_T1(data_root: Path, sample_n: int = 64) -> None:
    import numpy as np

    checked = 0
    folds = [f for f in FOLDS if (data_root / f / "train").is_dir()]
    for held in folds:
        train = data_root / held / "train"
        for p in sorted(train.glob("*.npz"))[: max(1, sample_n // max(len(folds), 1))]:
            with np.load(p, allow_pickle=True) as z:
                seq = z["sequence"]
            if seq.ndim != 4 or seq.shape[0] != 1 or seq.shape[1] != 17:
                raise RuntimeError(
                    f"non-uniform sequence in {p}: shape={tuple(seq.shape)}; expected (1,17,H,W)"
                )
            checked += 1
    print(f"[gate] uniform T=1 checked n={checked}", flush=True)


def main() -> int:
    print("=" * 70, flush=True)
    print("LOFO v4 CARDOSO-EXTRA — residual-small multi_if (exact_force_ema_long)", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(f"folds={FOLDS}", flush=True)
    print(
        f"sealed mean={SEALED_CHAMP_MEAN:.6f} min={SEALED_CHAMP_MIN:.6f} goal_delta={GOAL_DELTA}",
        flush=True,
    )
    print("=" * 70, flush=True)
    _install_p100()

    data_root = _root()
    init = _find_init(data_root)
    print("data", data_root, "init", init or "(NONE)", flush=True)
    if not init:
        print("[error] multi_if init required", flush=True)
        return 2
    _assert_uniform_T1(data_root)

    run_folds = [f for f in FOLDS if (data_root / f / "train").is_dir()]
    if len(run_folds) < 3:
        print(f"[error] need >=3 folds, got {run_folds}", flush=True)
        return 2

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    results = []
    for held in run_folds:
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
            ema_decay=EMA,
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"lofo_v4_cx_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} ch={change_w} pos={pos_w} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_lofo_v4_cardoso_extra",
            "feature_schema": "legacy17",
            "work_class": "data_lofo_v4_cardoso_extra",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
            "lr": LR,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "ema_decay": EMA,
            "init_weights_path": init,
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                row["best_epoch"] = prev.get("best_epoch")
                em = out / "evaluation_metrics.json"
                if not em.is_file():
                    em.write_text(json.dumps({**prev, **row}, indent=2), encoding="utf-8")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    def _ious(names: tuple[str, ...]) -> list[float]:
        out = []
        for r in results:
            if r.get("held") in names and r.get("model_iou") is not None:
                out.append(float(r["model_iou"]))
        return out

    core_ious = _ious(CORE3)
    all_ious = [float(r["model_iou"]) for r in results if r.get("model_iou") is not None]
    hellin_row = next((r for r in results if r["held"] == "hellin_2024"), None)
    core_mean = sum(core_ious) / len(core_ious) if core_ious else None
    core_min = min(core_ious) if core_ious else None
    delta_sealed = (core_mean - SEALED_CHAMP_MEAN) if core_mean is not None else None
    goal_met = bool(delta_sealed is not None and delta_sealed >= GOAL_DELTA)

    board = {
        "schema": "wfd_kaggle_lofo_v4_cardoso_extra_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_lofo_v4_cardoso_extra",
        "work_class": "data_lofo_v4_cardoso_extra",
        "feature_schema": "legacy17",
        "architecture": "residual_small",
        "recipe": "exact_force_ema_long_hparams",
        "sequence_layout": "T1_uniform",
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA,
        "init_weights_path": init,
        "folds": results,
        "core3_mean_iou": core_mean,
        "core3_min_iou": core_min,
        "all_mean_iou": (sum(all_ious) / len(all_ious)) if all_ious else None,
        "hellin_iou": (hellin_row or {}).get("model_iou"),
        "vs_sealed_champion": {
            "mean": SEALED_CHAMP_MEAN,
            "min": SEALED_CHAMP_MIN,
            "delta_mean": delta_sealed,
            "delta_min": (core_min - SEALED_CHAMP_MIN) if core_min is not None else None,
        },
        "vs_lofo_v3": {
            "core3_mean": V3_CORE3_MEAN,
            "core3_min": V3_CORE3_MIN,
            "delta_core3_mean": (core_mean - V3_CORE3_MEAN) if core_mean is not None else None,
            "delta_core3_min": (core_min - V3_CORE3_MIN) if core_min is not None else None,
        },
        "GOAL_DELTA_MEAN": GOAL_DELTA,
        "GOAL_MET_PLUS_0_05": goal_met,
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
        "note": (
            "Data lever: Cardoso FOV-reproject extra + honesty fires. "
            "Same residual-small exact_force_ema_long hparams. Not recipe thrash."
        ),
    }
    (out_root / "lofo_v4_cardoso_extra_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
