#!/usr/bin/env python3
"""Fine-tune frozen RCDA seeds on WFIGS TRAIN, selecting only on WFIGS VAL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument("--wfigs-dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=7)
    args = parser.parse_args()
    report = adapt_frozen_rcda_on_wfigs(
        final_summary_path=args.final_summary,
        wfigs_dataset_root=args.wfigs_dataset_root,
        rcda_normalization_path=(
            ROOT / "data/external/rcda_net_full/protocol/normalization_train_only.json"
        ),
        output_root=args.output,
        adaptation=WFIGSAdaptConfig(
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            patience=args.patience,
        ),
    )
    print(json.dumps(report["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
