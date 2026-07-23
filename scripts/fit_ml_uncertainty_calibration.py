#!/usr/bin/env python3
"""Fit Head A logistic uncertainty calibrator on VAL (operator tool).

Requires local ensemble weights + holdout VAL NPZ. Without them, exits 0 with
SKIP (operator tool — must not fail CI).

Protocol: fit is VAL-only. Paths under test/ or lofo/ are refused. The data
directory must contain a path component named ``val`` (case-insensitive).

Usage (when weights + VAL available)::

  $env:PYTHONPATH = "."
  python scripts/fit_ml_uncertainty_calibration.py
  python scripts/fit_ml_uncertainty_calibration.py --max-patches 50

Artifact default: models/clm_ensemble/uncertainty_calibration_v1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_VAL = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "val"
DEFAULT_OUT = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
DEFAULT_PROTOCOL = "clm_holdout_test_seed42_v1"

# Path components that must never be used as fit data (protocol integrity).
_FORBIDDEN_DIR_NAMES = frozenset({"test", "lofo", "train"})


def assert_val_fit_data_dir(data_dir: Path, *, split: str = "val") -> None:
    """Refuse non-VAL data sources for Head A fit.

    Rules:
    - ``split`` must be ``val`` (only fit_uncertainty-allowed split for holdout).
    - Path must not include components named test / lofo / train.
    - Path must include a component named ``val`` (e.g. holdout_v1/val).
    """
    if str(split) != "val":
        raise ValueError(
            f"fit_ml_uncertainty_calibration only allows --split val, got {split!r} "
            "(VAL-only protocol; never fit on test/lofo)"
        )
    try:
        resolved = data_dir.resolve()
    except OSError:
        resolved = data_dir
    parts = [p.lower() for p in Path(resolved).parts]
    # Forbid test/lofo/train components (and lofo_* folder names)
    for part in parts:
        base = part.split(".")[0]
        if base in _FORBIDDEN_DIR_NAMES or base.startswith("lofo"):
            raise ValueError(
                f"refusing fit data dir {data_dir}: path component {part!r} is not VAL "
                f"(fit never sees holdout test or LOFO)"
            )
    if "val" not in parts:
        raise ValueError(
            f"refusing fit data dir {data_dir}: path must contain a 'val' component "
            f"(e.g. artifacts/clm_ndws_patches/holdout_v1/val). "
            f"Do not point --val-dir at test/lofo."
        )


def _weights_and_val_ready(product_id: str, val_dir: Path) -> tuple[bool, str]:
    from wildfire_front.ml.product_catalog import get_product

    try:
        spec = get_product(product_id)
    except KeyError as exc:
        return False, str(exc)
    ok, msg = spec.resolve_existing()
    if not ok:
        return False, msg
    if not val_dir.is_dir():
        return False, f"missing VAL NPZ dir: {val_dir}"
    npzs = list(val_dir.glob("*.npz"))
    if not npzs:
        return False, f"no *.npz under {val_dir}"
    return True, f"ok product={product_id} n_val={len(npzs)}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fit ML Head A calibrator on VAL only")
    p.add_argument("--product", default=DEFAULT_PRODUCT)
    p.add_argument("--val-dir", type=Path, default=DEFAULT_VAL)
    p.add_argument(
        "--split",
        default="val",
        choices=["val"],
        help="Fit split (VAL only; test/lofo refused)",
    )
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--max-patches", type=int, default=0, help="0 = all VAL patches")
    p.add_argument("--tau-iou", type=float, default=0.5)
    p.add_argument("--mask-threshold", type=float, default=0.5)
    p.add_argument("--abstain-threshold", type=float, default=0.35)
    p.add_argument("--device", type=str, default=None)
    args = p.parse_args(argv)

    # Protocol path check first (hard fail — not SKIP)
    try:
        assert_val_fit_data_dir(args.val_dir, split=str(args.split))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2

    ready, reason = _weights_and_val_ready(args.product, args.val_dir)
    if not ready:
        print(
            f"SKIP: fit_ml_uncertainty_calibration requires weights + VAL NPZ "
            f"({reason}). Operator tool — not a CI failure.",
            flush=True,
        )
        return 0

    from wildfire_front.ml.ndws_metrics import evaluate_sample
    from wildfire_front.ml.product_catalog import load_predictor_for_product
    from wildfire_front.ml.protocol_rails import SplitContext
    from wildfire_front.ml.reliability_metrics import (
        ece_patch_conf,
        selective_beats_random,
        selective_iou_at_coverage,
    )
    from wildfire_front.ml.spread_predictor import EnsembleSpreadPredictor
    from wildfire_front.ml.uncertainty import (
        features_from_diagnostics,
        fit_logistic_calibrator,
        save_calibrator,
    )

    print(f"Loading product {args.product} …", flush=True)
    predictor = load_predictor_for_product(args.product, device=args.device)
    paths = sorted(args.val_dir.glob("*.npz"))
    if args.max_patches and args.max_patches > 0:
        paths = paths[: args.max_patches]

    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    ious: list[float] = []

    thr = float(args.mask_threshold)
    tau = float(args.tau_iou)
    for i, path in enumerate(paths):
        with np.load(path) as data:
            seq = data["sequence"]
            current_fire = data["current_fire"]
            target_fire = data.get("target_fire")
        if target_fire is None:
            continue
        pred = predictor.predict_with_uncertainty(
            seq,
            current_fire,
            threshold=thr,
            product_id=args.product,
            protocol=DEFAULT_PROTOCOL,
        )
        diag = pred.diagnostics
        prob = pred.prob
        sample = evaluate_sample(prob, current_fire, target_fire, threshold=thr)
        iou = float(sample["model_full"].iou)
        y = 1 if iou >= tau else 0
        feature_rows.append(features_from_diagnostics(diag))
        labels.append(y)
        ious.append(iou)
        if (i + 1) % 50 == 0:
            print(f"  patches {i + 1}/{len(paths)}", flush=True)

    if not feature_rows:
        print("SKIP: no VAL patches with target_fire", flush=True)
        return 0

    # SplitContext label matches asserted data dir (VAL only).
    ctx = SplitContext(
        split="val",
        action="fit_uncertainty",
        protocol=DEFAULT_PROTOCOL,
    )
    cal = fit_logistic_calibrator(
        feature_rows,
        labels,
        split_context=ctx,
        tau_iou=tau,
        n_iter=250,
    )
    cal.calibrator_id = "uncertainty_calibration_v1"
    cal.abstain_threshold = float(args.abstain_threshold)

    confs = []
    for row in feature_rows:
        diag = {
            "mean_entropy": float(row[0]),
            "member_disagreement": float(row[1]),
            "mean_margin": float(row[2]),
        }
        confs.append(cal.predict_proba(diag))
    ece = ece_patch_conf(confs, labels, n_bins=10)
    sel = selective_iou_at_coverage(ious, confs, coverage=0.8)
    u1 = selective_beats_random(ious, confs, coverage=0.8, n_trials=50, seed=42, margin=0.01)
    full_mean = float(np.mean(ious))
    sel_iou = float(sel.get("selective_iou") or float("nan"))
    u1a = bool(np.isfinite(sel_iou) and sel_iou >= full_mean - 0.01)

    metrics_on_val = {
        "ece_patch_conf": ece,
        "selective_iou_at_80pct_coverage": sel.get("selective_iou"),
        "full_coverage_mean_iou": full_mean,
        "u1a_selective_ge_full_minus_eps": u1a,
        "beats_random_selective": bool(u1.get("beats_random")),
        "delta_vs_random": u1.get("delta_vs_random"),
        "n_patches": len(labels),
        "positive_rate": float(np.mean(labels)),
        "fit_data_dir": str(args.val_dir.resolve()),
        "fit_split": "val",
    }

    out = save_calibrator(
        cal,
        args.output,
        extra={
            "protocol": DEFAULT_PROTOCOL,
            "product_id": args.product,
            "metrics_on_val": metrics_on_val,
            "n_patches_fit": len(labels),
            "predictor_type": (
                "ensemble"
                if isinstance(predictor, EnsembleSpreadPredictor)
                else "single"
            ),
        },
    )
    print(json.dumps({"wrote": str(out), "metrics_on_val": metrics_on_val}, indent=2))
    print(
        "NOTE: fusion allow_ml_live_in_fusion stays false until human promotes U1 pass.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
