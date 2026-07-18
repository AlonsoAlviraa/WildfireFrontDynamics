#!/usr/bin/env python3
"""Cross-protocol re-evaluation: v14/v19/v20 on the same test NPZ split.

Usage (local smoke — synthetic data, tagged in JSON)::

    python scripts/reeval_cross_protocol.py --smoke

Usage (real test NPZ, e.g. from Kaggle preprocess)::

    python scripts/reeval_cross_protocol.py \\
        --data-dir /tmp/ndws_npz \\
        --v14-weights kaggle_outputs_v14/weights_pretrained_best.pt \\
        --v19-weights kaggle_outputs_v19/weights_pretrained_best.pt \\
        --v20-weights kaggle_outputs_v20/_top/weights_pretrained_best.pt \\
        --output cross_protocol_report.json

Without real data and without --smoke the script exits non-zero and does
**not** silently invent synthetic metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.cross_protocol_eval import run_cross_protocol_eval  # noqa: E402

# Paths that must never receive synthetic / smoke product metrics.
_PROTECTED_ROOT_PARTS = frozenset({"docs", "models", "data"})
_DEFAULT_SMOKE_SEED = 42


def _is_protected_output(path: Path, project_root: Path = PROJECT_ROOT) -> bool:
    """True if writing here would overwrite product/docs/production scorecards."""
    resolved = path.resolve()
    root = project_root.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return False
    if not rel.parts:
        return False
    if rel.parts[0] in _PROTECTED_ROOT_PARTS:
        return True
    name = resolved.name.lower()
    if "scorecard" in name or name.endswith("_verdict.json"):
        return True
    return False


def _has_test_npz(data_dir: Path) -> bool:
    test_dir = data_dir / "test"
    if not test_dir.is_dir():
        return False
    return any(test_dir.glob("*.npz"))


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
    parser.add_argument(
        "--smoke",
        "--smoke-test",
        action="store_true",
        dest="smoke",
        help="Allow synthetic NPZ when real test data is missing; tag output synthetic:true",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_DEFAULT_SMOKE_SEED,
        help=f"RNG seed used when generating synthetic smoke data (default {_DEFAULT_SMOKE_SEED})",
    )
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
    output_path = Path(args.output)
    used_synthetic = False
    need_synthetic = not _has_test_npz(data_dir)

    if need_synthetic and not args.smoke:
        print(
            "ERROR: Real test NPZ data not found "
            f"(expected *.npz under {data_dir / 'test'}).\n"
            "  Refusing silent synthetic analysis — product metrics would be fake.\n"
            "  Fix: pass --data-dir pointing at a real NDWS NPZ layout, or use --smoke "
            "for an explicitly tagged synthetic demo.",
            file=sys.stderr,
        )
        return 1

    if need_synthetic and _is_protected_output(output_path):
        print(
            "ERROR: Refusing to write synthetic/smoke results to product or docs path:\n"
            f"  {output_path.resolve()}\n"
            "  Use a non-product output path (e.g. ./cross_protocol_report_smoke.json).",
            file=sys.stderr,
        )
        return 1

    if need_synthetic:
        print(f"[smoke] building synthetic NPZ under {data_dir} (seed={args.seed})")
        np.random.seed(args.seed)
        _make_smoke_test_dir(data_dir)
        used_synthetic = True

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

    report = run_cross_protocol_eval(checkpoints, data_dir, output_path)
    report["synthetic"] = used_synthetic
    report["smoke"] = bool(args.smoke)
    if used_synthetic:
        report["synthetic_seed"] = int(args.seed)
    # Re-write so synthetic tag is always present in the on-disk JSON.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("\n=== Cross-protocol report ===")
    if used_synthetic:
        print("[synthetic=true] metrics are from smoke NPZ — not production scorecards")
    for name, row in report["results"].items():
        print(
            f"{name}: IoU={row['test_iou']:.4f}  "
            f"copy={row['copy_baseline_iou']:.4f}  "
            f"dilated={row['dilated_copy_baseline_iou']:.4f}  "
            f"delta_full={row['improvement_vs_copy_iou']:+.4f}  "
            f"delta_changed={row['improvement_vs_copy_iou_changed']:+.4f}  "
            f"legacy_delta={row['legacy_improvement_vs_naive_copy_iou_changed']:+.4f}"
        )
    print(f"\nWrote {output_path} (synthetic={used_synthetic})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
