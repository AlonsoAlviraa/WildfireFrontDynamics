#!/usr/bin/env python3
"""Kaggle: sealed lofo_v1 core-3 + multi_if init + mild curriculum (no Hellín).

E3a Hellín pool KILL'd ACOM2 floor. This run recovers LOFO board with Spain
specialist init (weights_multi_if) on sealed packs — honest lift attempt
without multi-fire domain shift into ACOM2.
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
EPOCHS = int(os.environ.get("WF_EPOCHS", "16"))


def _working() -> Path:
    return Path("/kaggle/working") if Path("/kaggle/working").is_dir() else Path(".")


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
            for cand in (dest,):
                if any((cand / f / "train").is_dir() for f in CORE3):
                    return cand
    raise FileNotFoundError("lofo_v1 core3 missing")


def main() -> int:
    print("METRICS LIFT RECOVER — sealed LOFO + multi_if init (no Hellín)")
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and "P100" in (r.stdout or ""):
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
    except Exception:
        pass

    data_root = _root()
    init = ""
    for name in ("weights_multi_if.pt", "weights_v21_best.pt"):
        for p in [data_root / name, *_working().parent.glob(f"**/{name}")]:
            if Path(p).is_file():
                init = str(p)
                break
        if init:
            break
    # search extracted
    if not init:
        for p in Path("/tmp").rglob("weights_multi_if.pt"):
            init = str(p)
            break
    if not init:
        for p in Path("/tmp").rglob("weights_v21_best.pt"):
            init = str(p)
            break
    print("init", init, "data", data_root)

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
        cfg = UNetTrainConfig(
            epochs=EPOCHS,
            batch_size=8,
            lr=1.5e-4,
            loss="composite",
            pos_weight=6.0 if held != "LA_ESTRELLA_ACOM2" else 7.5,
            model="small",
            architecture="residual",
            target_mode="delta",
            change_loss_weight=6.0 if held != "LA_ESTRELLA_ACOM2" else 9.0,
            weighted_sampler=True,
            patience=8,
            data_dir=str(data_root / held),
            output_dir=str(out),
            version_tag=f"metrics_lift_recover_{held}",
            early_stop_metric="improvement_vs_copy_iou",
            init_weights_path=init,
        )
        print(f"=== recover held={held} ===", flush=True)
        run_training(cfg)
        ts = out / "training_summary.json"
        row = {"held": held, "status": "ok", "experiment_id": "E_recover_sealed_multi_if"}
        if ts.is_file():
            prev = json.loads(ts.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev.update(
                    {
                        "schema_path_id": "E_recover",
                        "feature_schema": "legacy17",
                        "held_out": held,
                        "no_hellin": True,
                        "init_weights_path": init,
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
    board = {
        "schema": "wfd_kaggle_metrics_lift_recover_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": "E_recover_sealed_multi_if",
        "folds": results,
        "core3_mean_iou": (sum(ious) / len(ious)) if ious else None,
        "core3_min_iou": min(ious) if ious else None,
        "baselines": {"lofo_mean_iou": 0.7580534465179306, "lofo_min_iou": 0.6931861844919686},
        "note": "no Hellín; multi_if init; residual small",
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
        },
    }
    (out_root / "metrics_lift_recover_board.json").write_text(
        json.dumps(board, indent=2), encoding="utf-8"
    )
    print(json.dumps(board, indent=2))
    return 0 if len(ious) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
