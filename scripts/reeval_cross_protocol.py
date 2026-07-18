#!/usr/bin/env python3
"""Cross-protocol re-evaluation: v14/v19/v20 on the same test NPZ split.

Usage (local smoke)::

    python scripts/reeval_cross_protocol.py --smoke-test

Usage (real test NPZ, e.g. from Kaggle preprocess)::

    python scripts/reeval_cross_protocol.py \\
        --data-dir /tmp/ndws_npz \\
        --v14-weights kaggle_outputs_v14/weights_pretrained_best.pt \\
        --v19-weights kaggle_outputs_v19/weights_pretrained_best.pt \\
        --v20-weights kaggle_outputs_v20/_top/weights_pretrained_best.pt \\
        --output cross_protocol_report.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.cross_protocol_eval import run_cross_protocol_eval  # noqa: E402


def _make_smoke_test_dir(root: Path, n_test: int = 24) -> None:
    for split_name, n in [("train", 8), ("val", 8), ("test", n_test)]:
        d = root / split_name
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.3
            cf = np.zeros((64, 64), dtype=np.float32)
            tf = np.zeros((64, 64), dtype=np.float32)
            cf[22:38, 22:38] = 1.0
            tf[20:40, 20:40] = 1.0
            if i % 3 == 0:
                tf[40, 40] = 1.0
            if i % 5 == 0:
                tf[22, 22] = 0.0
            change_fraction = float(np.mean((cf >= 0.5) != (tf >= 0.5)))
            np.savez_compressed(
                d / f"patch_{i:06d}.npz",
                sequence=seq,
                current_fire=cf,
                target_fire=tf,
                change_fraction=change_fraction,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-protocol NDWS checkpoint evaluation")
    parser.add_argument("--data-dir", type=str, default=str(PROJECT_ROOT / "_cross_eval_npz"))
    parser.add_argument("--output", type=str, default=str(PROJECT_ROOT / "cross_protocol_report.json"))
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument(
        "--v14-weights",
        type=str,
        default=str(PROJECT_ROOT / "kaggle_outputs_v14" / "weights_pretrained_best.pt"),
    )
    parser.add_argument(
        "--v19-weights",
        type=str,
        default=str(PROJECT_ROOT / "kaggle_outputs_v19" / "weights_pretrained_best.pt"),
    )
    parser.add_argument(
        "--v20-weights",
        type=str,
        default=str(PROJECT_ROOT / "kaggle_outputs_v20" / "_top" / "weights_pretrained_best.pt"),
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if args.smoke_test or not (data_dir / "test").exists():
        print(f"[smoke] building synthetic NPZ under {data_dir}")
        _make_smoke_test_dir(data_dir)

    checkpoints: dict[str, dict] = {}
    for name, path, arch, mode in [
        ("v14", args.v14_weights, "standard", "absolute"),
        ("v19", args.v19_weights, "standard", "changed_weighted"),
        ("v20", args.v20_weights, "residual", "changed_weighted"),
    ]:
        p = Path(path)
        if p.is_file():
            checkpoints[name] = {
                "weights": p,
                "architecture": arch,
                "target_mode": mode,
            }
        else:
            print(f"[skip] {name}: weights not found at {p}")

    if not checkpoints:
        print("No checkpoint weights found.", file=sys.stderr)
        return 1

    report = run_cross_protocol_eval(checkpoints, data_dir, Path(args.output))

    print("\n=== Cross-protocol report ===")
    for name, row in report["results"].items():
        print(
            f"{name}: IoU={row['test_iou']:.4f}  "
            f"copy={row['copy_baseline_iou']:.4f}  "
            f"dilated={row['dilated_copy_baseline_iou']:.4f}  "
            f"delta_full={row['improvement_vs_copy_iou']:+.4f}  "
            f"delta_changed={row['improvement_vs_copy_iou_changed']:+.4f}  "
            f"legacy_delta={row['legacy_improvement_vs_naive_copy_iou_changed']:+.4f}"
        )
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
