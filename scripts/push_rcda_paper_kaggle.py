#!/usr/bin/env python3
"""Stage and push the validation-only RCDA paper ablation sweep to Kaggle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.push_rcda_sealed_kaggle import _protocol_blobs  # noqa: E402

STAGE = ROOT / "kaggle_job/_push_rcda_paper_tune"
KERNEL_ID = "alonsoalvira/wfd-rcda-paper-tune-v1"

TUNING_RECIPES: tuple[dict[str, object], ...] = (
    {
        "run_name": "unet_growth_v2",
        "model_name": "unet",
        "target_mode": "growth",
        "lr": 6e-4,
    },
    {
        "run_name": "unet_extent_v1",
        "model_name": "unet",
        "target_mode": "extent",
        "lr": 6e-4,
    },
    {
        "run_name": "unet_hybrid_v1",
        "model_name": "unet",
        "target_mode": "hybrid",
        "lr": 6e-4,
    },
    {
        "run_name": "aspp_growth_v1",
        "model_name": "aspp_unet",
        "target_mode": "growth",
        "lr": 6e-4,
    },
    {
        "run_name": "aspp_hybrid_v1",
        "model_name": "aspp_unet",
        "target_mode": "hybrid",
        "lr": 6e-4,
    },
    {
        "run_name": "resunet_hybrid_v1",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 4e-4,
    },
)


def _helpers_source() -> str:
    source = (ROOT / "kaggle_job/run_rcda_sealed_train.py").read_text(encoding="utf-8")
    start = source.index("ZENODO_URL")
    end = source.index("def main() -> int:")
    return source[start:end]


def self_contained_tune_kernel() -> str:
    library = (ROOT / "wildfire_front/ml/rcda_sealed.py").read_text(encoding="utf-8")
    recipes = json.dumps(TUNING_RECIPES, indent=2)
    blobs = json.dumps(_protocol_blobs(), indent=2)
    return f'''{library.rstrip()}

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

{_helpers_source()}
PROTOCOL_BLOBS = {blobs}
TUNING_RECIPES = {recipes}

def main() -> int:
    output = Path("/kaggle/working/rcda_paper_tune")
    output.mkdir(parents=True, exist_ok=True)
    dataset = locate_dataset()
    protocol = locate_protocol(Path("/kaggle/input/wfd-rcda-sealed"))
    reports = []
    for recipe in TUNING_RECIPES:
        config = SealedTrainConfig(
            dataset_root=str(dataset),
            protocol_dir=str(protocol),
            output_dir=str(output),
            run_name=str(recipe["run_name"]),
            model_name=str(recipe["model_name"]),
            target_mode=str(recipe["target_mode"]),
            seed=0,
            epochs=24,
            batch_size=8,
            lr=float(recipe["lr"]),
            patience=7,
            num_workers=2,
            amp=True,
            scheduler_name="cosine",
            selection_metric="event_macro_iou",
            evaluate_test=False,
            compute_paper_metrics=False,
        )
        reports.append(train_sealed(config))
    ranked = sorted(
        reports,
        key=lambda row: float(row["val"]["selected"]["event_macro_iou"]),
        reverse=True,
    )
    summary = {{
        "schema": "wfd_rcda_paper_tune_v1",
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_evaluated": False,
        "protocol_seed": PROTOCOL_SEED,
        "recipes": TUNING_RECIPES,
        "ranking": [
            {{
                "rank": index + 1,
                "run_name": row["config"]["run_name"],
                "val_event_macro_iou": row["val"]["selected"]["event_macro_iou"],
                "val_pooled_iou": row["val"]["selected"]["iou"],
                "threshold": row["selected_threshold"],
                "best_epoch": row["best_epoch"],
            }}
            for index, row in enumerate(ranked)
        ],
        "reports": reports,
    }}
    (output / "TUNING_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\\n", encoding="utf-8"
    )
    print(json.dumps(summary["ranking"], indent=2), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def stage_kernel() -> Path:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    (STAGE / "run_rcda_paper_tune.py").write_text(
        self_contained_tune_kernel(), encoding="utf-8"
    )
    metadata = {
        "id": KERNEL_ID,
        "title": "wfd-rcda-paper-tune-v1",
        "code_file": "run_rcda_paper_tune.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [
            "alonsoalvira/wfd-rcda-sealed",
            "alonsoalvira/wfd-rcda-archive",
        ],
        "competition_sources": [],
        "kernel_sources": [],
    }
    (STAGE / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return STAGE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    stage = stage_kernel()
    compile(
        (stage / "run_rcda_paper_tune.py").read_text(encoding="utf-8"),
        "run_rcda_paper_tune.py",
        "exec",
    )
    if not args.stage_only:
        subprocess.run(["kaggle", "kernels", "push", "-p", str(stage)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
