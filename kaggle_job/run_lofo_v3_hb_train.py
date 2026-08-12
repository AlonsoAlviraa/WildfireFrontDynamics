#!/usr/bin/env python3
"""Kaggle: LOFO v3 Hellín + Brazatortas train — residual-small multi_if.

Pack: alonsoalviraaaa/wfd-lofo-v3-hellin-brazatortas (legacy17, T=1 uniform)
  held: CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2, hellin_2024
  train fill: tobarra + brazatortas (capped) + non-held core

Fix vs failed run: Brazatortas was T=3 vs sealed T=1 → collate stack error.
Dataset v2 collapses Brazatortas to T=1 (last frame).

Recipe: exact_force_ema_long champion hparams.
Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra KEEP.
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
# LOFO v2 Hellín board (no Brazatortas train)
V2_CORE3_MEAN = 0.775042
V2_CORE3_MIN = 0.699819
V2_HELLIN = 0.572131


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


def _looks_like_lofo(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in FOLDS)


def _maybe_extract_zip(zpath: Path) -> Path | None:
    dest = Path("/tmp/lofo_v3_hellin_brazatortas")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    if _looks_like_lofo(dest):
        return dest
    nested = dest / "lofo_v3_hellin_brazatortas"
    if nested.is_dir() and _looks_like_lofo(nested):
        return nested
    for child in dest.rglob("train"):
        parent = child.parent.parent
        if _looks_like_lofo(parent):
            return parent
    return None


def _root() -> Path:
    input_root = Path("/kaggle/input")
    hard = [
        Path("/kaggle/input/wfd-lofo-v3-hellin-brazatortas"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v3-hellin-brazatortas"),
        Path("/kaggle/input/wfd-lofo-v3-hellin-brazatortas/lofo_v3_hellin_brazatortas"),
        Path(
            "/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v3-hellin-brazatortas/"
            "lofo_v3_hellin_brazatortas"
        ),
        Path(
            "/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v3-hellin-brazatortas/"
            "lofo_v3_hellin_brazatortas/lofo_v3_hellin_brazatortas"
        ),
    ]
    for c in hard:
        if c.is_dir() and _looks_like_lofo(c):
            return c
    if input_root.is_dir():
        for d in input_root.rglob("*"):
            if d.is_dir() and _looks_like_lofo(d):
                return d
        for z in input_root.rglob("*.zip"):
            got = _maybe_extract_zip(z)
            if got is not None:
                return got
    raise FileNotFoundError("lofo_v3_hellin_brazatortas pack missing under /kaggle/input")


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


def _fold_hparams(held: str) -> tuple[float, float]:
    if held == "LA_ESTRELLA_ACOM2":
        return 10.0, 8.0
    if held in ("LA_ESTRELLA_ACOM1", "hellin_2024"):
        return 7.0, 6.5
    return 6.0, 6.0


def _assert_uniform_T1(data_root: Path, sample_n: int = 64) -> None:
    """Fail closed if any train npz is not T=1 (prevents collate crash)."""
    import numpy as np

    checked = 0
    for held in FOLDS:
        train = data_root / held / "train"
        if not train.is_dir():
            continue
        for p in sorted(train.glob("*.npz"))[: sample_n // len(FOLDS) + 1]:
            with np.load(p, allow_pickle=True) as z:
                seq = z["sequence"]
            if seq.ndim != 4 or seq.shape[0] != 1 or seq.shape[1] != 17:
                raise RuntimeError(
                    f"non-uniform sequence in {p}: shape={tuple(seq.shape)}; "
                    "expected (1,17,H,W). Re-package T1-fixed dataset."
                )
            checked += 1
    print(f"[gate] uniform T=1 checked n={checked}", flush=True)


def main() -> int:
    print("=" * 70, flush=True)
    print("LOFO v3 HELLÍN+BRAZATORTAS — residual-small multi_if (T1 uniform)", flush=True)
    print(f"epochs={EPOCHS} lr={LR} patience={PATIENCE} ema={EMA}", flush=True)
    print(f"folds={FOLDS}", flush=True)
    print(
        f"v2 ref core3 mean={V2_CORE3_MEAN:.6f} min={V2_CORE3_MIN:.6f} hellin={V2_HELLIN:.6f}",
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

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    os.chdir(REPO_DIR)
    sys.path.insert(0, str(REPO_DIR.resolve()))
    from wildfire_front.ml.unet_train import UNetTrainConfig, run_training

    out_root = _working()
    results = []
    for held in FOLDS:
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
            version_tag=f"lofo_v3_hb_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== held={held} ch={change_w} pos={pos_w} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "experiment_id": "E_lofo_v3_hellin_brazatortas",
            "feature_schema": "legacy17",
            "work_class": "data_lofo_v3_hellin_brazatortas",
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
                prev.update(row)
                ts.write_text(json.dumps(prev, indent=2), encoding="utf-8")
                row["model_iou"] = prev.get("model_iou") or prev.get("test_iou")
                row["copy_baseline_iou"] = prev.get("copy_baseline_iou")
                row["improvement_vs_copy_iou"] = prev.get("improvement_vs_copy_iou")
                row["best_epoch"] = prev.get("best_epoch")
                em = out / "evaluation_metrics.json"
                if not em.is_file():
                    em.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        results.append(row)
        print(json.dumps(row, indent=2), flush=True)

    def _ious(names: tuple[str, ...]) -> list[float]:
        out = []
        for r in results:
            if r.get("held") in names and r.get("model_iou") is not None:
                out.append(float(r["model_iou"]))
        return out

    core_ious = _ious(CORE3)
    all_ious = _ious(FOLDS)
    hellin_row = next((r for r in results if r["held"] == "hellin_2024"), None)
    core_mean = sum(core_ious) / len(core_ious) if core_ious else None
    core_min = min(core_ious) if core_ious else None
    all_mean = sum(all_ious) / len(all_ious) if all_ious else None
    all_min = min(all_ious) if all_ious else None

    board = {
        "schema": "wfd_kaggle_lofo_v3_hellin_brazatortas_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_lofo_v3_hellin_brazatortas",
        "work_class": "data_lofo_v3_hellin_brazatortas",
        "feature_schema": "legacy17",
        "architecture": "residual_small",
        "recipe": "exact_force_ema_long_hparams",
        "sequence_layout": "T1_uniform",
        "brazatortas_in_train": True,
        "epochs": EPOCHS,
        "lr": LR,
        "patience": PATIENCE,
        "ema_decay": EMA,
        "init_weights_path": init,
        "folds": results,
        "core3_mean_iou": core_mean,
        "core3_min_iou": core_min,
        "all4_mean_iou": all_mean,
        "all4_min_iou": all_min,
        "hellin_iou": (hellin_row or {}).get("model_iou"),
        "hellin_improvement_vs_copy": (hellin_row or {}).get("improvement_vs_copy_iou"),
        "vs_lofo_v2_hellin": {
            "core3_mean": V2_CORE3_MEAN,
            "core3_min": V2_CORE3_MIN,
            "hellin": V2_HELLIN,
            "delta_core3_mean": (core_mean - V2_CORE3_MEAN) if core_mean is not None else None,
            "delta_core3_min": (core_min - V2_CORE3_MIN) if core_min is not None else None,
            "delta_hellin": (
                (float(hellin_row["model_iou"]) - V2_HELLIN)
                if hellin_row and hellin_row.get("model_iou") is not None
                else None
            ),
        },
        "comparability": {
            "sealed_champion_exact_force_ema_long": {
                "mean": SEALED_CHAMP_MEAN,
                "min": SEALED_CHAMP_MIN,
            },
            "same_geography_as_sealed_lofo_v1": False,
            "note": ("Hellín held + Brazatortas train fill. Score as data_lofo_v3 not recipe_t1."),
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "ml_product_go": True,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
        },
    }
    (out_root / "lofo_v3_hb_board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
    # alias for poll scripts
    (out_root / "lofo_v2_hellin_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2), flush=True)
    return 0 if len(results) == len(FOLDS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
