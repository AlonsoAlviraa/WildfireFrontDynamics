#!/usr/bin/env python3
"""Push the preregistered validation-only RCDA stage-2 physics/context sweep."""

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

from scripts.push_rcda_paper_kaggle import _helpers_source  # noqa: E402
from scripts.push_rcda_sealed_kaggle import _protocol_blobs  # noqa: E402

STAGE = ROOT / "kaggle_job/_push_rcda_paper_stage2"
KERNEL_ID = "alonsoalvira/wfd-rcda-paper-stage2-v1"

STAGE2_RECIPES: tuple[dict[str, object], ...] = (
    {
        "run_name": "film_hybrid_v1",
        "model_name": "film_unet",
        "target_mode": "hybrid",
        "lr": 4e-4,
    },
    {
        "run_name": "film_growth_v1",
        "model_name": "film_unet",
        "target_mode": "growth",
        "lr": 4e-4,
    },
    {
        "run_name": "resunet_growth_v1",
        "model_name": "resunet",
        "target_mode": "growth",
        "lr": 4e-4,
    },
    {
        "run_name": "resunet_growth_low_lr_v1",
        "model_name": "resunet",
        "target_mode": "growth",
        "lr": 2e-4,
        "epochs": 32,
        "patience": 8,
    },
    {
        "run_name": "resunet_hybrid_long_v2",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 4e-4,
        "epochs": 40,
        "patience": 10,
    },
    {
        "run_name": "resunet_hybrid_low_lr_v2",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 2e-4,
        "epochs": 32,
        "patience": 8,
    },
    {
        "run_name": "resunet_hybrid_precision_v3",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 4e-4,
        "epochs": 32,
        "patience": 8,
        "tversky_alpha": 0.5,
        "tversky_beta": 0.5,
    },
    {
        "run_name": "resunet_hybrid_event_balanced_v1",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 2e-4,
        "epochs": 32,
        "patience": 8,
        "event_balance_power": 1.0,
    },
    {
        "run_name": "resunet_hybrid_uniform_events_v1",
        "model_name": "resunet",
        "target_mode": "hybrid",
        "lr": 2e-4,
        "epochs": 32,
        "patience": 8,
        "sampling_strategy": "uniform_events",
    },
    {
        "run_name": "aspp_extent_v1",
        "model_name": "aspp_unet",
        "target_mode": "extent",
        "lr": 6e-4,
    },
    {
        "run_name": "aspp_growth_precision_v1",
        "model_name": "aspp_unet",
        "target_mode": "growth",
        "lr": 6e-4,
        "tversky_alpha": 0.4,
        "tversky_beta": 0.6,
    },
    {
        "run_name": "aspp_growth_recall_v1",
        "model_name": "aspp_unet",
        "target_mode": "growth",
        "lr": 6e-4,
        "tversky_alpha": 0.2,
        "tversky_beta": 0.8,
    },
    {
        "run_name": "aspp_hybrid_uniform_v1",
        "model_name": "aspp_unet",
        "target_mode": "hybrid",
        "lr": 6e-4,
        "weighted_sampling": False,
    },
    {
        "run_name": "wide_unet_hybrid_v1",
        "model_name": "unet",
        "target_mode": "hybrid",
        "lr": 4e-4,
        "base_channels": 48,
    },
)


def self_contained_stage2_kernel() -> str:
    library = (ROOT / "wildfire_front/ml/rcda_sealed.py").read_text(encoding="utf-8")
    blobs = json.dumps(_protocol_blobs(), indent=2)
    recipes = json.dumps(STAGE2_RECIPES, indent=2)
    return f'''{library.rstrip()}

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

{_helpers_source()}
PROTOCOL_BLOBS = {blobs}
STAGE2_RECIPES = json.loads(r\'''{recipes}\''')

def main() -> int:
    output = Path(os.environ.get("RCDA_STAGE2_OUTPUT", "/kaggle/working/rcda_paper_stage2"))
    output.mkdir(parents=True, exist_ok=True)
    dataset = locate_dataset()
    protocol = locate_protocol(Path("/kaggle/input/wfd-rcda-sealed"))
    requested_runs = {{
        item.strip()
        for item in os.environ.get("RCDA_STAGE2_RUNS", "").split(",")
        if item.strip()
    }}
    active_recipes = [
        recipe
        for recipe in STAGE2_RECIPES
        if not requested_runs or str(recipe["run_name"]) in requested_runs
    ]
    if requested_runs and len(active_recipes) != len(requested_runs):
        known = {{str(recipe["run_name"]) for recipe in STAGE2_RECIPES}}
        raise ValueError(f"unknown RCDA_STAGE2_RUNS: {{sorted(requested_runs - known)}}")
    reports = []
    for recipe in active_recipes:
        options = dict(recipe)
        config = SealedTrainConfig(
            dataset_root=str(dataset),
            protocol_dir=str(protocol),
            output_dir=str(output),
            seed=0,
            epochs=int(options.pop("epochs", 20)),
            batch_size=8,
            patience=int(options.pop("patience", 6)),
            num_workers=2,
            amp=True,
            scheduler_name="cosine",
            selection_metric="event_macro_iou",
            evaluate_test=False,
            compute_paper_metrics=False,
            **options,
        )
        reports.append(train_sealed(config))
    ranked = sorted(
        reports,
        key=lambda row: float(row["val"]["selected"]["event_macro_iou"]),
        reverse=True,
    )
    summary = {{
        "schema": "wfd_rcda_paper_tune_v1",
        "stage": 2,
        "selection_split": "val",
        "selection_metric": "event_macro_iou",
        "test_evaluated": False,
        "protocol_seed": PROTOCOL_SEED,
        "stage2_design_basis": (
            "Eight original preregistered recipes plus long and low-LR "
            "ResUNet-hybrid continuations added after the phase-1 VAL winner "
            "peaked at its maximum epoch; a precision-balanced continuation "
            "was added after its sealed VAL report showed precision 0.183 "
            "versus recall 0.377. An event-duration-balanced continuation was "
            "registered after the TRAIN event-count audit found 1-61 samples "
            "per fire. A uniform-event sampler was then registered because a "
            "TRAIN-only sampler audit measured event-mass CV 0.647 for the "
            "default strategy versus approximately zero for uniform events. "
            "TEST remained unevaluated."
        ),
        "recipes": active_recipes,
        "ranking": [
            {{
                "rank": index + 1,
                "run_name": row["config"]["run_name"],
                "val_event_macro_iou": row["val"]["selected"]["event_macro_iou"],
                "val_pooled_iou": row["val"]["selected"]["iou"],
                "threshold": row["selected_threshold"],
                "best_epoch": row["best_epoch"],
                "training_status": row.get("training_termination", {{}}).get(
                    "status", "completed"
                ),
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
    source = self_contained_stage2_kernel()
    compile(source, "run_rcda_paper_stage2.py", "exec")
    (STAGE / "run_rcda_paper_stage2.py").write_text(source, encoding="utf-8")
    metadata = {
        "id": KERNEL_ID,
        "title": "wfd-rcda-paper-stage2-v1",
        "code_file": "run_rcda_paper_stage2.py",
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
    if not args.stage_only:
        subprocess.run(["kaggle", "kernels", "push", "-p", str(stage)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
