"""Smoke test: fine-tune the A3C-LSTM model on real Tobarra LWIR data.

Runs 1-2 epochs of behavior-cloning fine-tuning to verify end-to-end that the
real data pipeline (materialized masks + thermal-injected channels) feeds the
model correctly. This is intentionally lightweight — a production run would use
more epochs, data augmentation, and a hold-out split.

Usage::

    set PYTHONPATH=. && python scripts/smoke_test_finetune.py --epochs 1
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the package and models/ are importable when running as a standalone script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.train import fine_tune_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", type=Path,
                        default=ROOT / "artifacts" / "tobarra_reprojected_lwir")
    parser.add_argument("--masks-dir", type=Path,
                        default=ROOT / "artifacts" / "tobarra_lwir_masks")
    parser.add_argument("--weights", type=Path,
                        default=ROOT / "models" / "v3.pt",
                        help="Pre-trained base weights")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "models" / "tobarra_finetuned.pt",
                        help="Where to save fine-tuned weights")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--max-patches", type=int, default=50,
                        help="Cap number of patches for fast CPU smoke tests (default: 50)")
    args = parser.parse_args()

    print("=" * 60)
    print("SMOKE TEST: Fine-tuning A3C-LSTM on real Tobarra LWIR data")
    print("=" * 60)
    print(f"  images_dir  : {args.images_dir}")
    print(f"  masks_dir   : {args.masks_dir}")
    print(f"  base weights: {args.weights}")
    print(f"  output      : {args.output}")
    print(f"  epochs      : {args.epochs}")
    print(f"  lr          : {args.lr}")
    print(f"  max_patches : {args.max_patches}")
    print()

    if not args.images_dir.is_dir():
        print(f"ERROR: images dir not found: {args.images_dir}")
        return 1
    if not args.masks_dir.is_dir():
        print(f"ERROR: masks dir not found: {args.masks_dir}")
        return 1
    if not args.weights.exists():
        print(f"ERROR: base weights not found: {args.weights}")
        return 1

    t0 = time.time()
    result = fine_tune_model(
        images_dir=args.images_dir,
        masks_dir=args.masks_dir,
        weights_path=args.weights,
        output_weights_path=args.output,
        epochs=args.epochs,
        lr=args.lr,
        max_patches=args.max_patches,
    )
    elapsed = time.time() - t0

    print()
    print("=" * 60)
    print(f"SMOKE TEST COMPLETE in {elapsed:.1f}s")
    print(f"  status       : {result['status']}")
    print(f"  loss_history : {result['loss_history']}")
    print(f"  output       : {args.output}")
    print("=" * 60)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())