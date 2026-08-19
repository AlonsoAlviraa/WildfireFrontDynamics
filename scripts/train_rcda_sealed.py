"""Local entry for sealed RCDA/U-Net training."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.rcda_sealed import SealedTrainConfig, train_sealed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/dataset",
    )
    parser.add_argument(
        "--protocol-dir",
        type=Path,
        default=ROOT / "data/external/rcda_net_full/protocol",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/ml_eval/rcda_sealed",
    )
    parser.add_argument("--model-name", default="unet", choices=("unet", "rcda"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    report = train_sealed(
        SealedTrainConfig(
            dataset_root=str(args.dataset_root),
            protocol_dir=str(args.protocol_dir),
            output_dir=str(args.output_dir),
            model_name=args.model_name,
            seed=args.seed,
            epochs=2 if args.smoke else args.epochs,
            batch_size=2 if args.smoke else args.batch_size,
            smoke=args.smoke,
            max_train_samples=8 if args.smoke else None,
            max_eval_samples=8 if args.smoke else None,
            num_workers=0 if args.smoke else 2,
            amp=not args.smoke,
        )
    )
    print(report["selected_threshold"], report["test_once"]["iou"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
