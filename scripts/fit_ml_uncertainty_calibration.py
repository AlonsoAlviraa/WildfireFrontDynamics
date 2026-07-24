#!/usr/bin/env python3
"""Fit Head A logistic uncertainty calibrator on VAL (operator tool).

Requires local ensemble weights + holdout VAL NPZ. Without them, exits 0 with
SKIP (operator tool — must not fail CI).

Protocol: fit is VAL-only. Paths under test/ or lofo/ are refused. The data
directory must contain a path component named ``val`` (case-insensitive).

Two-stage nested protocol (honesty protocol **b**)::

  1. Nested CV on VAL → nested_val_ece_mean = **logistic-only** ECE on outer folds
     (outer never used for that fold's logistic fit; Platt/temp **not** fit on outer)
  2. Final calibrator: logistic on VAL-inner + optional temperature/Platt on a
     **post-nested** VAL outer holdout (or full-VAL logistic if second_stage=none)
  3. Evaluate on TEST frozen via scripts/eval_ml_uncertainty_u1.py (never fit on TEST)

Usage (when weights + VAL available)::

  $env:PYTHONPATH = "."
  python scripts/fit_ml_uncertainty_calibration.py
  python scripts/fit_ml_uncertainty_calibration.py --nested-cv 5
  python scripts/fit_ml_uncertainty_calibration.py --nested-cv 5 --second-stage temperature
  python scripts/fit_ml_uncertainty_calibration.py --val-inner-frac 0.7 --second-stage platt

Artifact default: models/clm_ensemble/uncertainty_calibration_v1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_VAL = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "val"
DEFAULT_OUT = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
DEFAULT_PROTOCOL = "clm_holdout_test_seed42_v1"
DEFAULT_METRICS_OUT = (
    ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_uncertainty_fit_metrics.json"
)

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


def _parse_l2_grid(raw: str | None) -> list[float]:
    if not raw:
        return [1e-3, 1e-2, 5e-2, 1e-1, 5e-1, 1.0]
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return [float(p) for p in parts]


def _confs_from_rows(cal: Any, feature_rows: list[np.ndarray]) -> list[float]:
    from wildfire_front.ml.uncertainty import predict_proba_rows

    return predict_proba_rows(cal, feature_rows)


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
    p.add_argument(
        "--metrics-out",
        type=Path,
        default=DEFAULT_METRICS_OUT,
        help="JSON with nested_val_ece_mean + full-VAL fit metrics (and notes for TEST)",
    )
    p.add_argument("--max-patches", type=int, default=0, help="0 = all VAL patches")
    p.add_argument("--tau-iou", type=float, default=0.5)
    p.add_argument("--mask-threshold", type=float, default=0.5)
    p.add_argument("--abstain-threshold", type=float, default=0.35)
    p.add_argument("--device", type=str, default=None)
    p.add_argument(
        "--nested-cv",
        type=int,
        default=0,
        metavar="K",
        help="K-fold nested CV on VAL (0=off; recommended 5). Reports nested_val_ece_mean.",
    )
    p.add_argument(
        "--val-inner-frac",
        type=float,
        default=0.0,
        help=(
            "If >0 and --nested-cv is 0: single inner-fit/outer-calibrate split "
            "(e.g. 0.7). If both set, K-fold wins for nested metrics; inner-frac "
            "still used for full-VAL second-stage holdout when second-stage != none."
        ),
    )
    p.add_argument(
        "--second-stage",
        choices=["none", "temperature", "platt"],
        default="none",
        help="Optional temperature/Platt on outer VAL confidences (nested + final holdout)",
    )
    p.add_argument(
        "--l2-grid",
        type=str,
        default="",
        help="Comma-separated L2 grid for nested inner selection (default multi-point grid)",
    )
    p.add_argument("--l2", type=float, default=1e-2, help="L2 when nested-cv off / fallback")
    p.add_argument("--n-iter", type=int, default=800, help="Logistic GD iterations")
    p.add_argument(
        "--class-weight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Balanced class weights for imbalanced IoU>=tau labels (default on)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--features-cache",
        type=Path,
        default=None,
        help=(
            "Optional NPZ cache of VAL Head A features/labels/ious. "
            "If file exists, skip ensemble inference; if missing after run, write it."
        ),
    )
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
    from wildfire_front.ml.nested_cv import (
        nested_cv_provenance_block,
        val_inner_outer_fit_eval,
        val_nested_fit_eval,
    )
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
        fit_platt_on_logits,
        fit_temperature_on_logits,
        save_calibrator,
    )

    thr = float(args.mask_threshold)
    tau = float(args.tau_iou)
    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    ious: list[float] = []
    predictor = None
    cache_path = Path(args.features_cache) if args.features_cache else None

    if cache_path is not None and cache_path.is_file():
        print(f"Loading VAL features cache {cache_path} …", flush=True)
        try:

            def _cache_str(zobj: Any, key: str) -> str:
                if key not in zobj.files:
                    return ""
                raw = zobj[key]
                try:
                    return str(raw.item() if getattr(raw, "shape", None) == () else raw)
                except Exception:
                    return str(raw)

            with np.load(cache_path, allow_pickle=False) as z:
                # Provenance rails: refuse TEST/lofo-tagged or mismatched caches
                fit_split_c = _cache_str(z, "fit_split")
                product_c = _cache_str(z, "product_id")
                protocol_c = _cache_str(z, "protocol")
                val_dir_c = _cache_str(z, "val_dir")
                if fit_split_c and fit_split_c.lower() != "val":
                    raise ValueError(
                        f"features-cache fit_split={fit_split_c!r} is not val "
                        "(refuse TEST/lofo cache for Head A fit)"
                    )
                cache_parts = [p.lower() for p in Path(val_dir_c).parts] if val_dir_c else []
                for part in cache_parts:
                    base = part.split(".")[0]
                    if base in _FORBIDDEN_DIR_NAMES or base.startswith("lofo"):
                        raise ValueError(
                            f"features-cache val_dir contains forbidden component {part!r}"
                        )
                if product_c and product_c != str(args.product):
                    raise ValueError(
                        f"features-cache product_id={product_c!r} != --product {args.product!r}"
                    )
                if protocol_c and protocol_c != DEFAULT_PROTOCOL:
                    raise ValueError(
                        f"features-cache protocol={protocol_c!r} != {DEFAULT_PROTOCOL!r}"
                    )
                # Path-component check on cache file itself
                for part in [p.lower() for p in cache_path.parts]:
                    base = part.split(".")[0]
                    if base == "test" or base == "lofo" or base.startswith("lofo"):
                        raise ValueError(f"refusing features-cache path with component {part!r}")
                feats = np.asarray(z["features"], dtype=np.float64)
                labels = [int(v) for v in np.asarray(z["labels"]).ravel()]
                ious = [float(v) for v in np.asarray(z["ious"]).ravel()]
                feature_rows = [feats[i] for i in range(feats.shape[0])]
        except ValueError as exc:
            print(f"ERROR: features-cache integrity: {exc}", file=sys.stderr, flush=True)
            return 2
        print(f"  cached n={len(labels)}", flush=True)
    else:
        print(f"Loading product {args.product} …", flush=True)
        predictor = load_predictor_for_product(args.product, device=args.device)
        paths = sorted(args.val_dir.glob("*.npz"))
        if args.max_patches and args.max_patches > 0:
            paths = paths[: args.max_patches]

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

        if cache_path is not None and feature_rows:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                cache_path,
                features=np.stack(feature_rows, axis=0),
                labels=np.asarray(labels, dtype=np.int64),
                ious=np.asarray(ious, dtype=np.float64),
                fit_split=np.asarray("val"),
                product_id=np.asarray(str(args.product)),
                protocol=np.asarray(DEFAULT_PROTOCOL),
                val_dir=np.asarray(str(args.val_dir.resolve())),
                n_patches=np.asarray(len(labels), dtype=np.int64),
            )
            print(f"Wrote features cache {cache_path}", flush=True)

    if not feature_rows:
        print("SKIP: no VAL patches with target_fire", flush=True)
        return 0

    # SplitContext label matches asserted data dir (VAL only).
    ctx = SplitContext(
        split="val",
        action="fit_uncertainty",
        protocol=DEFAULT_PROTOCOL,
    )
    l2_grid = _parse_l2_grid(args.l2_grid if args.l2_grid else None)
    n_iter = int(args.n_iter)
    class_weight = bool(args.class_weight)
    second_stage = str(args.second_stage)
    seed = int(args.seed)

    nested_metrics: dict[str, Any] | None = None
    recommended_l2 = float(args.l2)

    if int(args.nested_cv) and int(args.nested_cv) >= 2:
        print(
            f"Nested CV K={int(args.nested_cv)} on VAL (n={len(labels)}) …",
            flush=True,
        )
        nested_metrics = val_nested_fit_eval(
            feature_rows,
            labels,
            split_context=ctx,
            ious=ious,
            n_folds=int(args.nested_cv),
            seed=seed,
            l2_grid=l2_grid,
            n_iter=n_iter,
            class_weight=class_weight,
            second_stage=second_stage,
        )
        recommended_l2 = float(nested_metrics.get("recommended_l2") or recommended_l2)
        print(
            json.dumps(
                {
                    "nested_val_ece_mean": nested_metrics.get("nested_val_ece_mean"),
                    "nested_val_ece_std": nested_metrics.get("nested_val_ece_std"),
                    "mean_u1b": nested_metrics.get("mean_u1b"),
                    "recommended_l2": recommended_l2,
                },
                indent=2,
            ),
            flush=True,
        )
    elif float(args.val_inner_frac) > 0:
        print(
            f"VAL inner/outer frac={float(args.val_inner_frac)} (n={len(labels)}) …",
            flush=True,
        )
        nested_metrics = val_inner_outer_fit_eval(
            feature_rows,
            labels,
            split_context=ctx,
            ious=ious,
            inner_frac=float(args.val_inner_frac),
            seed=seed,
            l2=float(args.l2),
            l2_grid=l2_grid if args.l2_grid else None,
            n_iter=n_iter,
            class_weight=class_weight,
            second_stage=second_stage,
        )
        # Drop non-JSON calibrator object before persistence
        nested_metrics = {k: v for k, v in nested_metrics.items() if k != "calibrator"}
        recommended_l2 = float(nested_metrics.get("recommended_l2") or recommended_l2)

    # Stage 2 (post-nested): final calibrator — second_stage only here, not in nested ECE.
    final_second_stage_note = "none"
    val_inner_ece: float | None = None
    val_outer_ece: float | None = None
    val_outer_ece_note = "n/a"
    inner_idx = None
    outer_idx = None
    if second_stage != "none":
        # Logistic on VAL-inner; Platt/temp on VAL-outer (post-nested only).
        from wildfire_front.ml.nested_cv import make_holdout_indices

        inner_frac = float(args.val_inner_frac) if float(args.val_inner_frac) > 0 else 0.75
        inner_idx, outer_idx = make_holdout_indices(
            len(feature_rows), inner_frac=inner_frac, seed=seed + 99
        )
        X_in = [feature_rows[i] for i in inner_idx]
        y_in = [labels[i] for i in inner_idx]
        X_out = [feature_rows[i] for i in outer_idx]
        y_out = [labels[i] for i in outer_idx]
        cal = fit_logistic_calibrator(
            X_in,
            y_in,
            split_context=ctx,
            tau_iou=tau,
            l2=recommended_l2,
            n_iter=n_iter,
            class_weight=class_weight,
        )
        confs_in = _confs_from_rows(cal, X_in)
        val_inner_ece = float(ece_patch_conf(confs_in, y_in, n_bins=10))
        logits = []
        for row in X_out:
            x = np.asarray(row, dtype=np.float64).ravel()
            logits.append(float(np.dot(cal.weights[:-1], x) + cal.weights[-1]))
        if second_stage == "temperature":
            t = fit_temperature_on_logits(logits, y_out)
            cal = cal.with_temperature(t)
            final_second_stage_note = (
                f"temperature={t:.4f} on post_nested_val_outer n={len(outer_idx)}"
            )
        else:
            a, b = fit_platt_on_logits(logits, y_out)
            cal = cal.with_platt(a, b)
            final_second_stage_note = (
                f"platt a={a:.4f} b={b:.4f} on post_nested_val_outer n={len(outer_idx)}"
            )
        confs_out = _confs_from_rows(cal, X_out)
        val_outer_ece = float(ece_patch_conf(confs_out, y_out, n_bins=10))
        val_outer_ece_note = (
            "val_outer_ece scores second_stage on the outer used to fit it "
            "(optimistic for post-hoc; not nested_val_ece_mean). Prefer TEST ECE."
        )
    else:
        cal = fit_logistic_calibrator(
            feature_rows,
            labels,
            split_context=ctx,
            tau_iou=tau,
            l2=recommended_l2,
            n_iter=n_iter,
            class_weight=class_weight,
        )
        final_second_stage_note = "none (full-VAL logistic only)"

    cal.calibrator_id = "uncertainty_calibration_v1"
    cal.abstain_threshold = float(args.abstain_threshold)

    confs = _confs_from_rows(cal, feature_rows)
    ece = ece_patch_conf(confs, labels, n_bins=10)  # full-VAL diagnostic (may include outer)
    sel = selective_iou_at_coverage(ious, confs, coverage=0.8)
    u1 = selective_beats_random(ious, confs, coverage=0.8, n_trials=50, seed=seed, margin=0.01)
    full_mean = float(np.mean(ious))
    sel_iou = float(sel.get("selective_iou") or float("nan"))
    u1a = bool(np.isfinite(sel_iou) and sel_iou >= full_mean - 0.01)

    nested_block = nested_cv_provenance_block(nested_metrics) if nested_metrics else None

    metrics_on_val: dict[str, Any] = {
        # Backward-compat key: full-VAL ECE with final cal (diagnostic; may be
        # partially same-split optimistic when second_stage used outer).
        "ece_patch_conf": ece,
        "val_full_mixture_ece": ece,
        "val_full_mixture_ece_note": (
            "Diagnostic only when second_stage!=none: includes outer used for Platt/temp. "
            "Use nested_val_ece_mean (logistic outer) and TEST ECE for honesty."
        ),
        "val_inner_ece": val_inner_ece,
        "val_outer_ece": val_outer_ece,
        "val_outer_ece_note": val_outer_ece_note,
        "selective_iou_at_80pct_coverage": sel.get("selective_iou"),
        "full_coverage_mean_iou": full_mean,
        "u1a_selective_ge_full_minus_eps": u1a,
        "beats_random_selective": bool(u1.get("beats_random")),
        "delta_vs_random": u1.get("delta_vs_random"),
        "n_patches": len(labels),
        "positive_rate": float(np.mean(labels)),
        "fit_data_dir": str(args.val_dir.resolve()),
        "fit_split": "val",
        "l2": recommended_l2,
        "n_iter": n_iter,
        "class_weight": class_weight,
        "second_stage": second_stage,
        "second_stage_detail": final_second_stage_note,
        "nested_val_ece_mean": (
            nested_metrics.get("nested_val_ece_mean") if nested_metrics else None
        ),
        "nested_val_ece_std": (
            nested_metrics.get("nested_val_ece_std") if nested_metrics else None
        ),
        "nested_logistic_ece_mean": (
            nested_metrics.get("nested_logistic_ece_mean") if nested_metrics else None
        ),
        "nested_cv": nested_block,
        "test_ece_note": (
            "TEST ECE is not computed here (never fit/report-mix on TEST in fit script). "
            "Run: python scripts/eval_ml_uncertainty_u1.py --split test "
            "--calibrator models/clm_ensemble/uncertainty_calibration_v1.json"
        ),
    }

    extra: dict[str, Any] = {
        "protocol": DEFAULT_PROTOCOL,
        "product_id": args.product,
        "metrics_on_val": metrics_on_val,
        "n_patches_fit": len(labels),
        "predictor_type": (
            "ensemble"
            if predictor is not None and isinstance(predictor, EnsembleSpreadPredictor)
            else ("cached_features" if predictor is None else "single")
        ),
        "nested_cv": nested_block,
        "fit_hyperparams": {
            "l2": recommended_l2,
            "n_iter": n_iter,
            "class_weight": class_weight,
            "second_stage": second_stage,
            "second_stage_detail": final_second_stage_note,
            "nested_cv_k": int(args.nested_cv) if int(args.nested_cv) >= 2 else 0,
            "val_inner_frac": float(args.val_inner_frac) or None,
            "seed": seed,
        },
    }

    out = save_calibrator(cal, args.output, extra=extra)

    metrics_doc = {
        "schema": "ml_uncertainty_fit_metrics_v1",
        "product_id": args.product,
        "protocol": DEFAULT_PROTOCOL,
        "calibrator_path": str(out).replace("\\", "/"),
        "fit_split": "val",
        "nested_val_ece_mean": metrics_on_val.get("nested_val_ece_mean"),
        "nested_val_ece_std": metrics_on_val.get("nested_val_ece_std"),
        "full_val_ece": ece,
        "full_val_u1a": u1a,
        "full_val_u1b": bool(u1.get("beats_random")),
        "nested_cv": nested_block,
        "metrics_on_val": metrics_on_val,
        "test_ece": None,  # filled by operator after eval_ml_uncertainty_u1
        "test_ece_after_freeze": None,
        "honesty": (
            "Fit VAL-only. Nested ECE is honest within VAL. "
            "TEST ECE requires frozen eval script; never used for fit."
        ),
    }
    metrics_path = Path(args.metrics_out)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics_doc, indent=2, allow_nan=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "wrote": str(out),
                "wrote_metrics": str(metrics_path),
                "metrics_on_val": {
                    "ece_patch_conf": ece,
                    "nested_val_ece_mean": metrics_on_val.get("nested_val_ece_mean"),
                    "u1a": u1a,
                    "u1b": bool(u1.get("beats_random")),
                    "n_patches": len(labels),
                    "l2": recommended_l2,
                    "second_stage": second_stage,
                },
            },
            indent=2,
        )
    )
    print(
        "NOTE: fusion allow_ml_live_in_fusion stays false until human promotes U1 pass. "
        "Next: eval_ml_uncertainty_u1.py --split test with this frozen calibrator.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
