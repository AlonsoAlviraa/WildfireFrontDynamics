#!/usr/bin/env python3
"""Adapt all frozen RCDA seeds with front geometry on WFIGS DEV only."""

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

SEEDS = (11, 29, 47)


def _assert_dev_only(dataset_root: Path) -> None:
    if any(token in dataset_root.name.lower() for token in ("confirm", "test", "prospective")):
        raise ValueError(f"front-geometry ensemble runner accepts DEV only; refusing {dataset_root}")
    for name in ("train.json", "validation.json"):
        if not (dataset_root / name).is_file():
            raise FileNotFoundError(dataset_root / name)


def _local_source_summary(final_summary_path: Path, source_dir: Path) -> Path:
    final = json.loads(final_summary_path.read_text(encoding="utf-8"))
    if final.get("test_used_for_selection") is not False:
        raise ValueError("RCDA final summary does not prove selection isolation")
    by_seed = {int(row["config"]["seed"]): row for row in final.get("reports") or []}
    if set(by_seed) != set(SEEDS):
        raise ValueError(f"RCDA final summary must contain exactly seeds {SEEDS}")
    reports = []
    for seed in SEEDS:
        source = by_seed[seed]
        config = source["config"]
        checkpoint = source_dir / f"resunet_hybrid_event_balanced_v1_final_seed{seed}_best.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        if payload.get("selection_split") != "val":
            raise ValueError(f"source checkpoint was not selected on RCDA VAL: {checkpoint}")
        reports.append(
            {
                "local_checkpoint": str(checkpoint),
                "config": {
                    "seed": seed,
                    "model_name": config["model_name"],
                    "base_channels": int(config["base_channels"]),
                    "target_mode": config["target_mode"],
                    "extent_loss_weight": float(config.get("extent_loss_weight", 0.35)),
                    "growth_loss_weight": float(config.get("growth_loss_weight", 0.65)),
                    "tversky_alpha": float(config.get("tversky_alpha", 0.3)),
                    "tversky_beta": float(config.get("tversky_beta", 0.7)),
                    "tversky_gamma": float(config.get("tversky_gamma", 0.75)),
                },
            }
        )
    temporary = Path(tempfile.mkdtemp(prefix="wfd_front_geometry_ensemble_source_"))
    summary_path = temporary / "source_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_front_geometry_ensemble_source_wrapper_v1",
                "test_used_for_selection": False,
                "reports": reports,
            }
        ),
        encoding="utf-8",
    )
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rcda_final_summary", type=Path)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--patience", type=int, default=5)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)
    source_summary = _local_source_summary(args.rcda_final_summary, args.source_dir)
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
            source_seeds=SEEDS,
        ),
    )
    if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
        raise RuntimeError("front-geometry ensemble DEV-only invariant violated")
    if report["ensemble"] is None or report["ensemble"]["members"] != len(SEEDS):
        raise RuntimeError("front-geometry ensemble did not contain all preregistered seeds")
    print(json.dumps(report["ensemble"]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
