#!/usr/bin/env python3
"""Train a residual U-Net from scratch on WFIGS TRAIN and select on DEV."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import SEALED_CHANNEL_NAMES, build_model, set_seed  # noqa: E402
from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)


def _assert_dev_only(dataset_root: Path) -> None:
    if any(token in dataset_root.name.lower() for token in ("confirm", "test", "prospective")):
        raise ValueError(f"scratch runner accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--seed", type=int, default=47)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)
    set_seed(args.seed)
    with tempfile.TemporaryDirectory(prefix="wfd_scratch_source_") as temporary:
        temporary_root = Path(temporary)
        checkpoint = temporary_root / "random_resunet_hybrid_seed.pt"
        model = build_model("resunet", in_channels=len(SEALED_CHANNEL_NAMES), base=32)
        torch.save(
            {
                "state_dict": model.state_dict(),
                "selection_split": "val",
                "model_name": "resunet",
                "target_mode": "hybrid",
                "base_channels": 32,
                "seed": args.seed,
            },
            checkpoint,
        )
        source_summary = {
            "schema": "wfd_wfigs_scratch_source_wrapper_v1",
            "test_used_for_selection": False,
            "reports": [
                {
                    "local_checkpoint": str(checkpoint),
                    "config": {
                        "seed": args.seed,
                        "model_name": "resunet",
                        "base_channels": 32,
                        "target_mode": "hybrid",
                        "extent_loss_weight": 0.35,
                        "growth_loss_weight": 0.65,
                        "tversky_alpha": 0.3,
                        "tversky_beta": 0.7,
                        "tversky_gamma": 0.75,
                    },
                }
            ],
        }
        summary_path = temporary_root / "source_summary.json"
        summary_path.write_text(json.dumps(source_summary), encoding="utf-8")
        report = adapt_frozen_rcda_on_wfigs(
            final_summary_path=summary_path,
            wfigs_dataset_root=args.wfigs_dev_root,
            rcda_normalization_path=args.rcda_normalization,
            output_root=args.output,
            adaptation=WFIGSAdaptConfig(
                epochs=args.epochs,
                batch_size=4,
                lr=1e-4,
                weight_decay=1e-4,
                patience=args.patience,
                trainable_scope="all",
                front_ring_bce_weight=0.05,
                target_mode="hybrid",
                augment=True,
                source_seeds=(args.seed,),
            ),
        )
    if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
        raise RuntimeError("scratch DEV-only invariant violated")
    print(json.dumps(report["reports"][0]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
