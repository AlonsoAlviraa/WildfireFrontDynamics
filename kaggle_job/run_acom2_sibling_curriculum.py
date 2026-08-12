#!/usr/bin/env python3
"""Kaggle: ACOM2 regime attack — fixed exact_force_ema_long + sibling curriculum.

Single non-hparam lever: when held=LA_ESTRELLA_ACOM2, oversample sibling
LA_ESTRELLA_ACOM1 train patches (3×) before training. All other folds use
exact champion recipe with no oversample thrash.

Recipe frozen (exact_force_ema_long)::
  epochs=48 lr=2.5e-5 patience=28 batch=8 ema=0.999
  change_w=6 pos_w=6  acom2_change_w=10 acom2_pos_w=8
  residual-small · multi_if init · legacy17

Rails: lab only · fusion OFF · IoU≠ROS · no Tobarra KEEP · no larger U-Net.
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
# Fixed champion recipe — do not thrash
EPOCHS = 48
LR = 2.5e-5
PATIENCE = 28
BATCH = 8
EMA = 0.999
CHANGE_W = 6.0
POS_W = 6.0
ACOM2_CHANGE_W = 10.0
ACOM2_POS_W = 8.0
SIBLING_OVERSAMPLE = 3.0  # the one lever
SIBLING = {"LA_ESTRELLA_ACOM2": "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM1": "LA_ESTRELLA_ACOM2"}

V3_ACOM2_MIN = 0.6976247037297344
SEALED_ACOM2_MIN = 0.7071461821856562
SEALED_MEAN = 0.7877704721329809
SEALED_MIN = 0.7071461821856562


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


def _looks(root: Path) -> bool:
    return all((root / f / "train").is_dir() for f in CORE3)


def _maybe_zip(zpath: Path) -> Path | None:
    dest = Path("/tmp/lofo_core3_acom2")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    if _looks(dest):
        return dest
    for child in dest.rglob("train"):
        parent = child.parent.parent
        if _looks(parent):
            return parent
    return None


def _root() -> Path:
    hard = [
        Path("/kaggle/input/wfd-lofo-v1-core3"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3"),
        Path("/kaggle/input/wfd-lofo-v1-core3/lofo_v1"),
        Path("/kaggle/input/datasets/alonsoalviraaaa/wfd-lofo-v1-core3/lofo_v1"),
    ]
    for c in hard:
        if c.is_dir() and _looks(c):
            return c
    if Path("/kaggle/input").is_dir():
        for d in Path("/kaggle/input").rglob("*"):
            if d.is_dir() and _looks(d):
                return d
        for z in Path("/kaggle/input").rglob("*.zip"):
            got = _maybe_zip(z)
            if got is not None:
                return got
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


def _source_of(path: Path) -> str:
    import numpy as np

    try:
        with np.load(path, allow_pickle=True) as z:
            if "source" in z.files:
                s = z["source"]
                return str(s.item() if hasattr(s, "item") else s)
    except Exception:  # noqa: BLE001
        pass
    # filename fallback: SOURCE__name.npz or clm_SOURCE_####.npz
    name = path.name
    if "__" in name:
        return name.split("__", 1)[0]
    if name.startswith("clm_"):
        rest = name[4:]
        parts = rest.rsplit("_", 1)
        return parts[0] if parts else name
    return "unknown"


def materialize_sibling_curriculum(
    data_root: Path,
    held: str,
    *,
    oversample: float,
    out_root: Path,
) -> dict:
    """Copy fold; if held has sibling, duplicate sibling train patches."""
    src_fold = data_root / held
    dst_fold = out_root / held
    if dst_fold.exists():
        shutil.rmtree(dst_fold)
    for split in ("train", "val", "test"):
        s = src_fold / split
        d = dst_fold / split
        d.mkdir(parents=True, exist_ok=True)
        if not s.is_dir():
            continue
        for p in s.glob("*.npz"):
            shutil.copy2(p, d / p.name)

    sib = SIBLING.get(held)
    n_added = 0
    n_sib_base = 0
    if sib and oversample > 1.0 and held == "LA_ESTRELLA_ACOM2":
        train = dst_fold / "train"
        sib_paths = [p for p in train.glob("*.npz") if _source_of(p) == sib]
        n_sib_base = len(sib_paths)
        extra_copies = max(0, int(oversample) - 1)
        frac = oversample - int(oversample)
        for copy_i in range(extra_copies):
            for p in sib_paths:
                dest = train / f"sibx{copy_i + 2}__{p.name}"
                shutil.copy2(p, dest)
                n_added += 1
        if frac > 0 and sib_paths:
            k = max(1, int(round(frac * len(sib_paths))))
            for p in sib_paths[:k]:
                dest = train / f"sibxfrac__{p.name}"
                shutil.copy2(p, dest)
                n_added += 1
    return {
        "held": held,
        "sibling": sib,
        "sibling_base": n_sib_base,
        "sibling_extra_added": n_added,
        "oversample": oversample if held == "LA_ESTRELLA_ACOM2" else 1.0,
        "train_n": len(list((dst_fold / "train").glob("*.npz"))),
    }


def main() -> int:
    print("=" * 70, flush=True)
    print("ACOM2 sibling curriculum — exact_force_ema_long FIXED", flush=True)
    print(f"lever=sibling_oversample×{SIBLING_OVERSAMPLE} (ACOM2 fold only)", flush=True)
    print(f"vs v3 ACOM2 min={V3_ACOM2_MIN:.4f} sealed ACOM2 min={SEALED_ACOM2_MIN:.4f}", flush=True)
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
    pack_root = out_root / "lofo_sibling_curriculum"
    fold_rows: list[dict] = []
    curriculum_meta: list[dict] = []

    for held in CORE3:
        ov = SIBLING_OVERSAMPLE if held == "LA_ESTRELLA_ACOM2" else 1.0
        meta = materialize_sibling_curriculum(data_root, held, oversample=ov, out_root=pack_root)
        curriculum_meta.append(meta)
        print("curriculum", meta, flush=True)

        change_w = ACOM2_CHANGE_W if held == "LA_ESTRELLA_ACOM2" else CHANGE_W
        pos_w = ACOM2_POS_W if held == "LA_ESTRELLA_ACOM2" else POS_W
        out = out_root / "exact_force_ema_long_sibling" / held
        out.mkdir(parents=True, exist_ok=True)
        train_cfg = UNetTrainConfig(
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
            data_dir=str(pack_root / held),
            output_dir=str(out),
            version_tag=f"acom2_sib_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init or None,
        )
        print(
            f"=== exact_force_ema_long held={held} ch={change_w} pos={pos_w} "
            f"sib_ov={meta['oversample']} ===",
            flush=True,
        )
        run_training(train_cfg)
        ts = out / "training_summary.json"
        row: dict = {
            "held": held,
            "status": "ok",
            "config_id": "exact_force_ema_long_sibling_curriculum",
            "work_class": "recipe_t1_acom2_sibling",
            "feature_schema": "legacy17",
            "architecture": "residual_small",
            "change_loss_weight": change_w,
            "pos_weight": pos_w,
            "lr": LR,
            "epochs": EPOCHS,
            "ema_decay": EMA,
            "sibling_oversample": meta["oversample"],
            "lever": "sibling_data_curriculum",
        }
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(
                    {
                        "work_class": "recipe_t1_acom2_sibling",
                        "experiment_id": "E_acom2_sibling_curriculum",
                        "held_out": held,
                        "init_weights_path": init,
                        "sibling_oversample": meta["oversample"],
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

    ious = {r["held"]: float(r["model_iou"]) for r in fold_rows if r.get("model_iou") is not None}
    mean_iou = sum(ious.values()) / len(ious) if ious else None
    min_iou = min(ious.values()) if ious else None
    acom2 = ious.get("LA_ESTRELLA_ACOM2")
    board = {
        "schema": "wfd_kaggle_acom2_sibling_curriculum_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_acom2_sibling_curriculum",
        "work_class": "recipe_t1_acom2_sibling",
        "feature_schema": "legacy17",
        "architecture": "residual_small",
        "recipe": "exact_force_ema_long",
        "lever": "sibling_data_curriculum",
        "sibling_oversample_acom2": SIBLING_OVERSAMPLE,
        "hparams": {
            "epochs": EPOCHS,
            "lr": LR,
            "patience": PATIENCE,
            "batch": BATCH,
            "ema_decay": EMA,
            "change_w": CHANGE_W,
            "pos_w": POS_W,
            "acom2_change_w": ACOM2_CHANGE_W,
            "acom2_pos_w": ACOM2_POS_W,
            "init": "weights_multi_if.pt",
        },
        "init_weights_path": init,
        "curriculum_meta": curriculum_meta,
        "folds": fold_rows,
        "core3_mean": mean_iou,
        "core3_min": min_iou,
        "acom2_iou": acom2,
        "vs_v3_acom2_min": {
            "prior": V3_ACOM2_MIN,
            "delta": (acom2 - V3_ACOM2_MIN) if acom2 is not None else None,
            "beats": bool(acom2 is not None and acom2 > V3_ACOM2_MIN),
        },
        "vs_sealed_acom2_min": {
            "prior": SEALED_ACOM2_MIN,
            "delta": (acom2 - SEALED_ACOM2_MIN) if acom2 is not None else None,
            "beats": bool(acom2 is not None and acom2 > SEALED_ACOM2_MIN),
        },
        "vs_sealed_champion": {
            "mean": SEALED_MEAN,
            "min": SEALED_MIN,
            "delta_mean": (mean_iou - SEALED_MEAN) if mean_iou is not None else None,
            "delta_min": (min_iou - SEALED_MIN) if min_iou is not None else None,
        },
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
            "no_hparam_grid": True,
        },
        "note": (
            "One lever only: sibling ACOM1 oversample on ACOM2 held fold. "
            "Recipe bit-for-bit exact_force_ema_long."
        ),
    }
    board_path = out_root / "acom2_sibling_curriculum_board.json"
    board_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    print(json.dumps(board, indent=2), flush=True)
    print(f"BOARD -> {board_path}", flush=True)
    return (
        0 if len(fold_rows) == 3 and all(r.get("model_iou") is not None for r in fold_rows) else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
