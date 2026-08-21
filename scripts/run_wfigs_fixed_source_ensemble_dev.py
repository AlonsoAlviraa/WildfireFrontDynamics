#!/usr/bin/env python3
"""Adapt one fixed RCDA source with three WFIGS RNG seeds on DEV only."""

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

ADAPTATION_SEEDS = (11, 29, 47)


def _assert_dev_only(dataset_root: Path) -> None:
    if any(token in dataset_root.name.lower() for token in ("confirm", "test", "prospective")):
        raise ValueError(f"fixed-source runner accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def _source_summary(checkpoint: Path) -> Path:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if payload.get("selection_split") != "val":
        raise ValueError("fixed source checkpoint was not selected on RCDA VAL")
    if payload.get("model_name") != "resunet" or payload.get("target_mode") != "hybrid":
        raise ValueError("fixed source must be RCDA resunet hybrid")
    config = {
        "model_name": payload["model_name"],
        "base_channels": int(payload.get("base_channels", 32)),
        "target_mode": "hybrid",
        "extent_loss_weight": 0.35,
        "growth_loss_weight": 0.65,
        "tversky_alpha": 0.3,
        "tversky_beta": 0.7,
        "tversky_gamma": 0.75,
    }
    reports = [
        {
            "local_checkpoint": str(checkpoint),
            "config": {"seed": seed, **config},
        }
        for seed in ADAPTATION_SEEDS
    ]
    temporary = Path(tempfile.mkdtemp(prefix="wfd_fixed_source_ensemble_"))
    path = temporary / "source_summary.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_fixed_source_ensemble_wrapper_v1",
                "test_used_for_selection": False,
                "fixed_source_seed": int(payload.get("seed", 47)),
                "reports": reports,
            }
        ),
        encoding="utf-8",
    )
    return path


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
    source_summary = _source_summary(args.source_checkpoint)
    report = adapt_frozen_rcda_on_wfigs(
        final_summary_path=source_summary,
        wfigs_dataset_root=args.wfigs_dev_root,
        rcda_normalization_path=args.rcda_normalization,
        output_root=args.output,
        adaptation=WFIGSAdaptConfig(
            epochs=args.epochs,
            batch_size=4,
            lr=1e-4,
            patience=args.patience,
            trainable_scope="decoder_plus_input",
            front_ring_bce_weight=0.05,
            target_mode="hybrid",
            augment=True,
            include_geometry_features=True,
            include_tile_standardized_features=True,
            source_seeds=ADAPTATION_SEEDS,
        ),
    )
    if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
        raise RuntimeError("fixed-source DEV-only invariant violated")
    if report["ensemble"] is None or report["ensemble"]["members"] != len(ADAPTATION_SEEDS):
        raise RuntimeError("fixed-source ensemble did not contain all adaptation seeds")
    print(json.dumps(report["ensemble"]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
