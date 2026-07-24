#!/usr/bin/env python3
"""Multi-product CLI — NDWS v21 | CLM v28 | CLM ensemble v34.

Examples:
  python scripts/predict_spread.py --list-products
  python scripts/predict_spread.py --product clm_ensemble_v34 \\
      --npz artifacts/clm_ndws_patches/holdout_v1/test --eval --max-patches 50
  python scripts/predict_spread.py --product clm_v28 --npz path/patch.npz --output pred.npz
  python scripts/predict_spread.py --product clm_ensemble_v34 --npz path/patch.npz \\
      --with-uncertainty --ml-live-json outbox/ml_prediction.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ml.ndws_metrics import (  # noqa: E402
    aggregate_ndws_evaluation,
    evaluate_sample,
)
from wildfire_front.ml.product_catalog import (  # noqa: E402
    get_product,
    list_products,
    load_catalog,
    load_predictor_for_product,
)
from wildfire_front.ml.spread_predictor import (  # noqa: E402
    EnsembleSpreadPredictor,
    SpreadPredictor,
)


def _product_choices() -> list[str]:
    try:
        return sorted((load_catalog().get("products") or {}).keys())
    except OSError:
        return ["ndws_v21", "clm_v28", "clm_ensemble_v34", "clm_ensemble_v30"]


def _resolve_calibrator(path: str | None):
    """Load Head A calibrator for the live product path.

    - Explicit ``--calibrator``: required file (missing → FileNotFoundError).
    - Default: product artifact under ``models/clm_ensemble/`` only.
    - Never auto-load ``tests/fixtures/…`` (CI fixture is offline-only).
    - Missing product artifact → identity (force abstain on product path).
    """
    from wildfire_front.ml.uncertainty import LogisticCalibrator, load_calibrator

    if path:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(
                f"--calibrator path not found: {p} "
                "(refusing silent identity when path was explicitly set)"
            )
        return load_calibrator(p)
    # Product artifacts only — never tests/fixtures (BUG-1 / no silent fake calibration)
    candidates = [
        PROJECT_ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json",
        PROJECT_ROOT / "models" / "clm_ensemble" / "uncertainty_calibrator_v1.json",
    ]
    for c in candidates:
        if c.is_file():
            return load_calibrator(c)
    return LogisticCalibrator.identity()


def main() -> int:
    choices = _product_choices()
    default = (
        load_catalog().get("default_product")
        if Path(PROJECT_ROOT / "models" / "catalog.json").is_file()
        else "clm_v28"
    )
    if default not in choices:
        default = "clm_v28" if "clm_v28" in choices else choices[0]

    parser = argparse.ArgumentParser(
        description="Production spread prediction (NDWS | CLM single | CLM ensemble)"
    )
    parser.add_argument(
        "--product",
        choices=choices,
        default=default,
        help=f"Catalog product (default: {default})",
    )
    parser.add_argument("--list-products", action="store_true")
    parser.add_argument("--manifest", type=str, default=None, help="Override manifest path")
    parser.add_argument("--weights", type=str, default=None, help="Override single-model weights")
    parser.add_argument(
        "--members",
        type=str,
        nargs="*",
        default=None,
        help="Override ensemble member weight paths",
    )
    parser.add_argument("--npz", type=str, default=None, help="Input patch NPZ or directory")
    parser.add_argument(
        "--output", type=str, default=None, help="Write prediction NPZ (single file)"
    )
    parser.add_argument("--eval", action="store_true", help="Metrics if target_fire present")
    parser.add_argument("--max-patches", type=int, default=0, help="0 = all")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print eval report only as JSON (no prose)",
    )
    parser.add_argument(
        "--with-uncertainty",
        action="store_true",
        help="Emit ml_live_metrics_v1 (+ optional mask summary) via predict_with_uncertainty",
    )
    parser.add_argument(
        "--ml-live-json",
        type=str,
        default=None,
        help="Write ml_prediction_v1 JSON (outbox/ml_prediction.json shape) for Decision Card",
    )
    parser.add_argument(
        "--calibrator",
        type=str,
        default=None,
        help=(
            "Path to Head A calibrator JSON (must exist if set). "
            "Default: models/clm_ensemble/uncertainty_calibration_v1.json only; "
            "if missing, identity calibrator (force abstain). Never auto-loads CI fixtures."
        ),
    )
    parser.add_argument(
        "--abstain-below",
        type=float,
        default=None,
        help=(
            "Confidence threshold for abstain (default: calibrator.abstain_threshold "
            "from artifact, else 0.35)"
        ),
    )
    args = parser.parse_args()

    if args.list_products:
        print(json.dumps(list_products(), indent=2))
        return 0

    if not args.npz:
        print("--npz required unless --list-products", file=sys.stderr)
        return 2

    # Build predictor
    if args.manifest:
        manifest_path = Path(args.manifest)
        mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
        is_ens = bool(mdata.get("members") or mdata.get("product_type") == "ensemble")
        if is_ens:
            members = args.members
            if not members:
                members = mdata.get("members") or []
            member_paths = []
            for rel in members:
                p = Path(rel)
                member_paths.append(p if p.is_absolute() else (PROJECT_ROOT / p).resolve())
            predictor: SpreadPredictor | EnsembleSpreadPredictor = (
                EnsembleSpreadPredictor.from_manifest(manifest_path, member_weights=member_paths)
            )
            product_id = str(mdata.get("id") or mdata.get("version") or "ensemble")
            product_label = product_id
            domain = str(mdata.get("domain") or "ensemble")
        else:
            weights_path = args.weights
            predictor = SpreadPredictor.from_manifest(manifest_path, weights_path=weights_path)
            product_id = str(mdata.get("version") or "custom")
            product_label = product_id
            domain = "custom"
    else:
        spec = get_product(args.product)
        ok, msg = spec.resolve_existing()
        if not ok:
            print(f"Product {args.product} not ready: {msg}", file=sys.stderr)
            return 1
        if not args.json:
            print(f"Product: {spec.id} ({spec.domain}) type={spec.product_type}")
            print(f"  use_when: {spec.use_when}")
            print(f"  not_for:  {spec.not_for}")
            if spec.product_type == "ensemble":
                print(f"  members:  {len(spec.member_paths)}  mode={spec.ensemble_mode}")
                for m in spec.member_paths:
                    print(f"    - {m}")
        if args.members and spec.product_type == "ensemble":
            from wildfire_front.ml.spread_predictor import SpreadModelManifest

            manifest = SpreadModelManifest.from_json(spec.manifest_path)
            predictor = EnsembleSpreadPredictor(
                manifest,
                [Path(m) for m in args.members],
                ensemble_mode=spec.ensemble_mode,
            )
        else:
            predictor = load_predictor_for_product(args.product)
        product_id = spec.id
        product_label = spec.label
        domain = spec.domain

    npz_path = Path(args.npz)
    paths = sorted(npz_path.glob("*.npz")) if npz_path.is_dir() else [npz_path]
    if args.max_patches and args.max_patches > 0:
        paths = paths[: args.max_patches]
    if not paths:
        print(f"No NPZ under {npz_path}", file=sys.stderr)
        return 1

    use_unc = bool(args.with_uncertainty or args.ml_live_json)
    calibrator = None
    if use_unc:
        try:
            calibrator = _resolve_calibrator(args.calibrator)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if calibrator is not None and getattr(calibrator, "is_identity", False) and not args.json:
            print(
                "NOTE: no product calibrator under models/clm_ensemble/ — "
                "using identity (live confidence forces abstain). "
                "Fit with scripts/fit_ml_uncertainty_calibration.py or pass --calibrator.",
                flush=True,
            )

    sample_metrics: list[dict] = []
    metrics_rows: list[dict] = []
    last_live_doc: dict | None = None

    for path in paths:
        with np.load(path) as data:
            seq = data["sequence"]
            current_fire = data["current_fire"]
            target_fire = data.get("target_fire", None)

        thr = predictor.manifest.threshold
        if use_unc and hasattr(predictor, "predict_with_uncertainty"):
            from wildfire_front.ml.uncertainty import build_ml_prediction_document

            unc_kwargs: dict = {
                "threshold": thr,
                "calibrator": calibrator,
                "product_id": product_id,
            }
            # None → predictor uses calibrator.abstain_threshold (artifact default)
            if args.abstain_below is not None:
                unc_kwargs["abstain_below"] = float(args.abstain_below)
            unc = predictor.predict_with_uncertainty(seq, current_fire, **unc_kwargs)
            pred_prob = unc.prob
            pred_bin = unc.binary
            mask_summary = {
                "mean_prob": float(np.mean(pred_prob)),
                "fire_frac": float(np.mean(pred_bin)),
                "shape": list(pred_prob.shape),
            }
            last_live_doc = build_ml_prediction_document(unc, mask_summary=mask_summary)
            # Print live metrics for single-patch / json mode
            if (
                args.with_uncertainty
                and (args.json or len(paths) == 1)
                and (not args.ml_live_json or len(paths) == 1)
            ):
                print(json.dumps(last_live_doc, indent=2))
        else:
            pred_prob = predictor.predict(seq, current_fire)
            pred_bin = (pred_prob >= thr).astype(np.float32)

        if args.eval and target_fire is not None:
            sample = evaluate_sample(pred_prob, current_fire, target_fire)
            sample_metrics.append(sample)
            metrics_rows.append(
                {
                    "file": path.name,
                    "iou": float(sample["model_full"].iou),
                    "copy_iou": float(sample["copy_full"].iou),
                }
            )

        if args.output and len(paths) == 1:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            n_mem = getattr(predictor, "n_members", 1)
            np.savez_compressed(
                out,
                prediction=pred_prob,
                prediction_binary=pred_bin,
                current_fire=current_fire,
                target_fire=target_fire if target_fire is not None else np.array([]),
                product=product_id,
                model_version=predictor.manifest.version,
                n_members=np.int32(n_mem),
            )
            if not args.json:
                print(f"Wrote {out}")

    if args.ml_live_json and last_live_doc is not None:
        live_path = Path(args.ml_live_json)
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps(last_live_doc, indent=2), encoding="utf-8")
        if not args.json:
            print(f"Wrote {live_path}")

    if metrics_rows:
        ious = np.asarray([r["iou"] for r in metrics_rows], dtype=float)
        copy_ious = np.asarray([r["copy_iou"] for r in metrics_rows], dtype=float)
        agg = aggregate_ndws_evaluation(sample_metrics) if sample_metrics else {}
        report = {
            "product": product_id,
            "label": product_label,
            "domain": domain,
            "model_version": predictor.manifest.version,
            "product_type": getattr(predictor.manifest, "product_type", "single"),
            "n_members": getattr(predictor, "n_members", 1),
            "n_patches": len(metrics_rows),
            "mean_iou": float(ious.mean()),
            "mean_copy_iou": float(copy_ious.mean()),
            "mean_delta_vs_copy": float((ious - copy_ious).mean()),
            "micro_iou": float(agg.get("model_iou") or ious.mean()),
            "micro_delta": float(agg.get("improvement_vs_copy_iou") or (ious - copy_ious).mean()),
            "model_iou_growth": float(agg.get("model_iou_growth") or 0.0),
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
