#!/usr/bin/env python3
"""Evaluate frozen RCDA seeds on untouched WFIGS TEST tensors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_external_eval import evaluate_frozen_rcda_on_wfigs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument("--wfigs-dataset-root", type=Path, required=True)
    parser.add_argument(
        "--rcda-normalization",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json",
    )
    parser.add_argument(
        "--geometry-baseline",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026/ml/GEOMETRY_BASELINE.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate_frozen_rcda_on_wfigs(
        final_summary_path=args.final_summary,
        wfigs_dataset_root=args.wfigs_dataset_root,
        rcda_normalization_path=args.rcda_normalization,
        geometry_baseline_path=args.geometry_baseline,
        output_path=args.output,
    )
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
