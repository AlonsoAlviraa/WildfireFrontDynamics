#!/usr/bin/env python3
"""Evaluate frozen Head A calibrator U1 on holdout VAL or TEST (never fit).

Protocol:
  * Calibrator is **loaded frozen** from JSON (default product artifact).
  * Never fits / refits on the eval split.
  * ``--split test`` path must contain ``test`` and must not be a VAL-only path.
  * Honest fusion recommendation requires TEST + frozen VAL-fit cal + U1 pass.

Usage::

  $env:PYTHONPATH = "."
  python scripts/eval_ml_uncertainty_u1.py --split test \\
    --calibrator models/clm_ensemble/uncertainty_calibration_v1.json

Without weights or NPZ: exits 0 with SKIP (operator tool; not a CI failure).
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
DEFAULT_PROTOCOL = "clm_holdout_test_seed42_v1"
DEFAULT_CAL = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
DEFAULT_TEST = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
DEFAULT_VAL = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "val"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_scorecard_u1_latest.json"


def _weights_and_data_ready(product_id: str, data_dir: Path) -> tuple[bool, str]:
    from wildfire_front.ml.product_catalog import get_product

    try:
        spec = get_product(product_id)
    except KeyError as exc:
        return False, str(exc)
    ok, msg = spec.resolve_existing()
    if not ok:
        return False, msg
    if not data_dir.is_dir():
        return False, f"missing eval NPZ dir: {data_dir}"
    npzs = list(data_dir.glob("*.npz"))
    if not npzs:
        return False, f"no *.npz under {data_dir}"
    return True, f"ok product={product_id} n={len(npzs)}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="U1 eval with frozen calibrator (never fit on eval split)"
    )
    p.add_argument("--product", default=DEFAULT_PRODUCT)
    p.add_argument(
        "--split",
        default="test",
        choices=["val", "test"],
        help="Eval split (default test = honest U1; val = lab only)",
    )
    p.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="NPZ directory (default: holdout_v1/{split})",
    )
    p.add_argument(
        "--calibrator",
        type=Path,
        default=DEFAULT_CAL,
        help="Frozen Head A calibrator JSON (required for promote path)",
    )
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--max-patches", type=int, default=0, help="0 = all patches")
    p.add_argument("--tau-iou", type=float, default=0.5)
    p.add_argument("--mask-threshold", type=float, default=0.5)
    p.add_argument("--device", type=str, default=None)
    p.add_argument(
        "--allow-identity",
        action="store_true",
        help=(
            "Allow identity calibrator (research only; never promote). "
            "Default refuses identity — frozen product calibrator required."
        ),
    )
    args = p.parse_args(argv)

    from wildfire_front.ml.protocol_rails import assert_split_role
    from wildfire_front.ml.u1_eval import assert_eval_split_path, assert_never_fit_on_test
    from wildfire_front.ml.uncertainty import load_calibrator

    split = str(args.split)
    # U1 eval is report/scorecard only — never fit.
    assert_never_fit_on_test("report", split)
    try:
        assert_split_role(split, "scorecard")
    except Exception as exc:  # ProtocolRailError
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2

    eval_dir = args.eval_dir
    if eval_dir is None:
        eval_dir = DEFAULT_TEST if split == "test" else DEFAULT_VAL
    eval_dir = Path(eval_dir)

    try:
        assert_eval_split_path(eval_dir, split)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2

    cal_path = Path(args.calibrator)
    if not cal_path.is_file():
        if args.allow_identity:
            print(
                f"SKIP: calibrator missing at {cal_path} and no weights path for full run.",
                flush=True,
            )
            return 0
        print(
            f"ERROR: frozen calibrator required but not found: {cal_path}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    cal = load_calibrator(cal_path)
    if cal.is_identity and not args.allow_identity:
        print(
            "ERROR: calibrator is identity; refuse promote/honest path "
            "(pass --allow-identity for research only)",
            file=sys.stderr,
            flush=True,
        )
        return 2
    if str(getattr(cal, "fit_split", "val")).lower() == "test":
        print(
            "ERROR: calibrator claims fit_split=test — refuse (never fit on TEST)",
            file=sys.stderr,
            flush=True,
        )
        return 2

    ready, reason = _weights_and_data_ready(args.product, eval_dir)
    if not ready:
        print(
            f"SKIP: eval_ml_uncertainty_u1 requires weights + {split} NPZ ({reason}). "
            "Operator tool — not a CI failure.",
            flush=True,
        )
        return 0

    from wildfire_front.ml.ndws_metrics import evaluate_sample
    from wildfire_front.ml.product_catalog import load_predictor_for_product
    from wildfire_front.ml.spread_predictor import EnsembleSpreadPredictor
    from scripts.ml_scorecard import build_scorecard

    print(
        f"Loading product {args.product} + frozen calibrator {cal_path} …",
        flush=True,
    )
    predictor = load_predictor_for_product(args.product, device=args.device)
    paths = sorted(eval_dir.glob("*.npz"))
    if args.max_patches and args.max_patches > 0:
        paths = paths[: int(args.max_patches)]

    thr = float(args.mask_threshold)
    tau = float(args.tau_iou)
    ious: list[float] = []
    confs: list[float] = []
    labels: list[int] = []

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
            calibrator=cal,
            product_id=args.product,
            protocol=DEFAULT_PROTOCOL,
        )
        sample = evaluate_sample(
            pred.prob, current_fire, target_fire, threshold=thr
        )
        iou = float(sample["model_full"].iou)
        conf = float(pred.confidence)
        y = 1 if iou >= tau else 0
        ious.append(iou)
        confs.append(conf)
        labels.append(y)
        if (i + 1) % 50 == 0:
            print(f"  patches {i + 1}/{len(paths)}", flush=True)

    if not ious:
        print(f"SKIP: no {split} patches with target_fire", flush=True)
        return 0

    cal_fit_split = str(getattr(cal, "fit_split", "val") or "val")
    doc = build_scorecard(
        product_id=args.product,
        split=split,
        action="scorecard",
        ious=ious,
        confidences=confs,
        labels=labels,
        offline=False,
        calibrator_path=str(cal_path),
        calibrator_fit_split=cal_fit_split,
        frozen_calibrator=not cal.is_identity,
        identity_calibrator=bool(cal.is_identity),
        eval_dir=str(eval_dir.resolve()),
        require_frozen_calibrator=not bool(args.allow_identity),
        u1_eval_split=split,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8")

    # Also write a split-tagged copy for operators
    tag = out.with_name(f"ml_scorecard_u1_{split}.json")
    if tag != out:
        tag.write_text(json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8")

    gates = doc.get("gates") or {}
    summary: dict[str, Any] = {
        "wrote": str(out),
        "split": split,
        "calibrator": str(cal_path),
        "calibrator_fit_split": cal_fit_split,
        "n_patches": len(ious),
        "mean_iou_eval_split": float(np.mean(ious)),
        "ece_patch_conf": (doc.get("uncertainty") or {}).get("ece_patch_conf"),
        "U1a": gates.get("U1a_selective_ge_full_minus_eps"),
        "U1b": gates.get("U1b_selective_beats_random")
        or gates.get("U1_selective_beats_random"),
        "u1_val_lab_pass": gates.get("u1_val_lab_pass"),
        "u1_val_optimistic": gates.get("u1_val_optimistic"),
        "u1_test_honest": gates.get("u1_test_honest"),
        "allow_ml_live_in_fusion_recommended": doc.get(
            "allow_ml_live_in_fusion_recommended"
        ),
        "ml_product_go": False,
        "predictor_type": (
            "ensemble"
            if isinstance(predictor, EnsembleSpreadPredictor)
            else "single"
        ),
        "note": (
            "Never fit on TEST. Fusion recommended only if u1_test_honest. "
            "ml_product_go stays false until promote script + human checklist."
        ),
    }
    print(json.dumps(summary, indent=2), flush=True)
    schema_ok = bool((doc.get("schema_validation") or {}).get("pass"))
    return 0 if schema_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
