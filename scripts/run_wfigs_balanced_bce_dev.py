#!/usr/bin/env python3
"""Run a class-balanced growth BCE WFIGS DEV experiment."""

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

from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)


def _assert_dev_only(dataset_root: Path) -> None:
    if any(token in dataset_root.name.lower() for token in ("confirm", "test", "prospective")):
        raise ValueError(f"balanced-BCE runner accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_checkpoint", type=Path)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--patience", type=int, default=5)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)
    payload = torch.load(args.source_checkpoint, map_location="cpu", weights_only=False)
    if payload.get("selection_split") != "val":
        raise ValueError("RCDA source checkpoint was not selected on RCDA VAL")
    if payload.get("model_name") != "resunet" or payload.get("target_mode") != "hybrid":
        raise ValueError("source checkpoint must be RCDA resunet hybrid")
    seed = int(payload["seed"])
    source_summary = {
        "schema": "wfd_rcda_balanced_bce_source_wrapper_v1",
        "test_used_for_selection": False,
        "reports": [
            {
                "local_checkpoint": str(args.source_checkpoint),
                "config": {
                    "seed": seed,
                    "model_name": payload["model_name"],
                    "base_channels": int(payload.get("base_channels", 32)),
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
    with tempfile.TemporaryDirectory(prefix="wfd_balanced_bce_source_") as temporary:
        summary_path = Path(temporary) / "source_summary.json"
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
                patience=args.patience,
                trainable_scope="decoder",
                front_ring_bce_weight=0.05,
                balanced_growth_bce_weight=0.10,
                target_mode="hybrid",
                augment=True,
                source_seeds=(seed,),
            ),
        )
    if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
        raise RuntimeError("balanced-BCE DEV-only invariant violated")
    print(json.dumps(report["reports"][0]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
