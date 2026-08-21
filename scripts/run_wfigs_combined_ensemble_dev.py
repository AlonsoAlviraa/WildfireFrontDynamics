#!/usr/bin/env python3
"""Replicate combined WFIGS features across all RCDA paper seeds on DEV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.run_wfigs_front_geometry_ensemble_dev import (  # noqa: E402
    SEEDS,
    _assert_dev_only,
    _local_source_summary,
)
from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)


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
            include_tile_standardized_features=True,
            source_seeds=SEEDS,
        ),
    )
    if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
        raise RuntimeError("combined-feature ensemble DEV-only invariant violated")
    if report["ensemble"] is None or report["ensemble"]["members"] != len(SEEDS):
        raise RuntimeError("combined-feature ensemble did not contain all seeds")
    print(json.dumps(report["ensemble"]["validation"]["selected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
