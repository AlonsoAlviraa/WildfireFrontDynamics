#!/usr/bin/env python3
"""Build ml_scorecard_v1 JSON with U1 selective@80% gate (honest promote rules).

Modes:
  * default / catalog: catalog TEST metrics under provenance only; U1 unknown
  * --offline-fixture: synthetic patch IoUs/confidences for CI
  * --calibrator + --eval-dir: operator path (prefer scripts/eval_ml_uncertainty_u1.py)

Honesty:
  * ``allow_ml_live_in_fusion_recommended`` is true **only** if U1 passes on
    **TEST** with a **frozen** VAL-fit calibrator (not VAL-only lab pass).
  * ``ml_product_go`` is **true** (human promote authorized 2026-08-05; lab GO ≠ field fusion).
  * primary.model_iou is mean IoU of the **eval split** when patches provided;
    catalog 0.8963 lives under ``provenance.catalog_holdout_test_reference``.

Outputs:
  outputs/ml_eval/scorecards/ml_scorecard_latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_scorecard_latest.json"
DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_PROTOCOL = "clm_holdout_test_seed42_v1"
U1_COVERAGE = 0.8
U1_MARGIN = 0.01
U1A_EPS = 0.01


def _catalog_reference(product_id: str = DEFAULT_PRODUCT) -> dict[str, Any]:
    """Load published catalog/manifest metrics for provenance only."""
    from wildfire_front.ml.u1_eval import catalog_holdout_test_reference

    ref = catalog_holdout_test_reference()
    man = ROOT / "models" / "clm_ensemble" / "manifest.json"
    if man.is_file():
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
            metrics = dict(data.get("metrics") or {})
            product_id = str(data.get("id") or data.get("version") or product_id)
            if "test_iou" in metrics or "model_iou" in metrics:
                ref["test_iou"] = float(
                    metrics.get("model_iou") or metrics.get("test_iou") or ref["test_iou"]
                )
            if "copy_baseline_iou" in metrics:
                ref["copy_baseline_iou"] = float(metrics["copy_baseline_iou"])
            if "improvement_vs_copy_iou" in metrics:
                ref["improvement_vs_copy_iou"] = float(metrics["improvement_vs_copy_iou"])
            if "model_iou_growth" in metrics:
                ref["model_iou_growth"] = float(metrics["model_iou_growth"])
            ref["product_id"] = product_id
        except (OSError, json.JSONDecodeError):
            pass
    ref["product_id"] = product_id
    return ref


def synthetic_patches(
    *,
    mode: str = "pass",
    n: int = 40,
    seed: int = 0,
) -> tuple[list[float], list[float], list[int]]:
    """Synthetic IoU / confidence / y=1{IoU>=0.5} for offline U1 tests.

    mode=pass: confidence ranks with IoU (selective beats shuffle).
    mode=fail: confidence anti-correlated / noise so U1 fails.
    """
    rng = np.random.default_rng(seed)
    if mode == "pass":
        ious = np.linspace(0.1, 0.95, n)
        confs = ious + rng.normal(0.0, 0.02, size=n)
        confs = np.clip(confs, 0.0, 1.0)
    else:
        ious = np.linspace(0.1, 0.95, n)
        confs = 1.0 - ious + rng.normal(0.0, 0.05, size=n)
        confs = np.clip(confs, 0.0, 1.0)
    y = (ious >= 0.5).astype(int).tolist()
    return ious.astype(float).tolist(), confs.astype(float).tolist(), y


def compute_u1a(
    ious: Sequence[float],
    confidences: Sequence[float],
    *,
    coverage: float = U1_COVERAGE,
    eps: float = U1A_EPS,
) -> dict[str, Any]:
    """U1a: selective@coverage IoU ≥ full-coverage mean IoU − ε."""
    from wildfire_front.ml.reliability_metrics import selective_iou_at_coverage

    iou = np.asarray(list(ious), dtype=np.float64).ravel()
    if iou.size == 0:
        return {
            "u1a_pass": False,
            "selective_iou": float("nan"),
            "full_coverage_mean_iou": float("nan"),
            "eps": eps,
        }
    full_mean = float(iou.mean())
    sel = selective_iou_at_coverage(ious, confidences, coverage=coverage)
    s = float(sel["selective_iou"])
    ok = bool(np.isfinite(s) and s >= full_mean - float(eps))
    return {
        "u1a_pass": ok,
        "selective_iou": s,
        "full_coverage_mean_iou": full_mean,
        "eps": float(eps),
        "delta_vs_full": float(s - full_mean) if np.isfinite(s) else float("nan"),
    }


def compute_u1(
    ious: Sequence[float],
    confidences: Sequence[float],
    *,
    coverage: float = U1_COVERAGE,
    margin: float = U1_MARGIN,
    n_trials: int = 50,
    seed: int = 42,
) -> dict[str, Any]:
    """U1b helper: selective@coverage beats shuffle-conf null + margin."""
    from wildfire_front.ml.reliability_metrics import selective_beats_random

    return selective_beats_random(
        ious,
        confidences,
        coverage=coverage,
        n_trials=n_trials,
        seed=seed,
        margin=margin,
        use_shuffle_conf=True,
    )


def build_scorecard(
    *,
    product_id: str = DEFAULT_PRODUCT,
    split: str = "val",
    action: str = "scorecard",
    ious: Sequence[float] | None = None,
    confidences: Sequence[float] | None = None,
    labels: Sequence[int] | None = None,
    offline: bool = False,
    synthetic_mode: str | None = None,
    calibrator_path: str | None = None,
    calibrator_fit_split: str = "val",
    frozen_calibrator: bool = False,
    identity_calibrator: bool = False,
    eval_dir: str | None = None,
    require_frozen_calibrator: bool = False,
    u1_eval_split: str | None = None,
    promote_draft: bool = False,
    nested_cv: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ml_scorecard_v1 with honest fusion recommendation gates.

    ``ml_product_go`` is True (human promote 2026-08-05). ``promote_draft`` only
    annotates provenance; field fusion stays OFF.
    """
    from wildfire_front.ml.reliability_metrics import ece_patch_conf, overconfidence_gap
    from wildfire_front.ml.scorecard_schema import validate_ml_scorecard
    from wildfire_front.ml.u1_eval import (
        FIXED_HONESTY_NOTES,
        catalog_holdout_test_reference,
        compute_fusion_recommendation,
        primary_from_eval_ious,
    )

    catalog_ref = _catalog_reference(product_id)
    product_id = str(catalog_ref.get("product_id") or product_id)
    eval_split = str(u1_eval_split or split)

    # Catalog numbers live ONLY under provenance.catalog_holdout_test_reference.
    # Catalog-only mode (no patch eval): do not put 0.8963 in primary.model_iou
    # even with tags — consumers that only read primary would still be misled.
    primary: dict[str, Any] = {
        "n_patches": 0,
    }

    unc: dict[str, Any] = {
        "n_patches": 0,
        "tau_iou": 0.5,
        "coverage": U1_COVERAGE,
    }
    u1_pass = False
    u1a_pass = False
    u1b_pass = False
    u1_detail: dict[str, Any] = {}
    u1a_detail: dict[str, Any] = {}

    if synthetic_mode is not None:
        ious, confidences, labels = synthetic_patches(mode=synthetic_mode)
        offline = True
        # Offline synthetic does not load a real calibrator unless caller set flags.
        if not frozen_calibrator and not identity_calibrator:
            # Lab synthetic: treat as non-frozen unless caller marks frozen.
            frozen_calibrator = False
            identity_calibrator = True

    if require_frozen_calibrator and (identity_calibrator or not frozen_calibrator):
        # Promote path hard rail — scorecard still builds but U1 honest stays false.
        pass

    if ious is not None and confidences is not None:
        ious_l = [float(x) for x in ious]
        conf_l = [float(x) for x in confidences]
        if labels is None:
            labels = [1 if x >= 0.5 else 0 for x in ious_l]
        y_l = [int(x) for x in labels]
        u1_detail = compute_u1(ious_l, conf_l)
        u1a_detail = compute_u1a(ious_l, conf_l)
        u1b_pass = bool(u1_detail.get("beats_random"))
        u1a_pass = bool(u1a_detail.get("u1a_pass"))
        ece_val = float(ece_patch_conf(conf_l, y_l, n_bins=10))
        u1_pass = bool(u1a_pass and u1b_pass)
        unc = {
            "ece_patch_conf": ece_val,
            "selective_iou_at_80pct_coverage": float(
                u1_detail.get("selective_iou") or float("nan")
            ),
            "selective_iou_random_baseline_80": float(
                u1_detail.get("shuffle_selective_iou_mean")
                or u1_detail.get("random_selective_iou_mean")
                or float("nan")
            ),
            "beats_random_selective": u1b_pass,
            "delta_vs_random": float(u1_detail.get("delta_vs_random") or float("nan")),
            "overconfidence_gap": float(overconfidence_gap(conf_l, y_l)),
            "mean_confidence": float(np.mean(conf_l)) if conf_l else float("nan"),
            "n_patches": len(ious_l),
            "tau_iou": 0.5,
            "coverage": U1_COVERAGE,
            "abstain_rate": float(np.mean([c < 0.35 for c in conf_l])) if conf_l else 0.0,
        }
        # primary.model_iou = mean of **this eval split only** (never catalog 0.8963)
        primary = primary_from_eval_ious(ious_l, eval_split=eval_split)

    if ious is None and synthetic_mode is None:
        u1_pass = False
        u1a_pass = False
        u1b_pass = False
        u1_detail = {"beats_random": False, "reason": "no_patch_data"}
        u1a_detail = {"u1a_pass": False, "reason": "no_patch_data"}

    # Offline synthetic with frozen flag: caller can pass frozen_calibrator=True
    # to simulate TEST honest path in CI.
    if require_frozen_calibrator and (identity_calibrator or not frozen_calibrator):
        # Force honest gate false via identity/frozen flags in recommendation.
        identity_calibrator = True
        frozen_calibrator = False

    rec = compute_fusion_recommendation(
        eval_split=eval_split,
        calibrator_fit_split=calibrator_fit_split or "val",
        u1_pass=u1_pass,
        frozen_calibrator=bool(frozen_calibrator),
        identity_calibrator=bool(identity_calibrator),
    )
    allow_fusion_rec = bool(rec["allow_ml_live_in_fusion_recommended"])

    reasons: list[str] = list(rec.get("reasons") or [])
    if not u1a_pass and "U1a_fail_or_missing" not in reasons:
        reasons.append("U1a_fail_or_missing")
    if not u1b_pass and "U1b_fail_or_missing" not in reasons:
        reasons.append("U1b_fail_or_missing")
    if ious is None and synthetic_mode is None:
        reasons = ["U1_fail_or_missing_patch_data"]
    if allow_fusion_rec:
        reasons = []

    # Lab product GO promoted (owner 2026-08-05); field fusion still OFF.
    ml_product_go = True
    if promote_draft:
        # Draft flag only annotates provenance — does not enable field fusion.
        pass

    gates = {
        "U1a_selective_ge_full_minus_eps": u1a_pass,
        "U1_selective_beats_random": u1b_pass,  # U1b alias
        "U1b_selective_beats_random": u1b_pass,
        "u1_val_passed": bool(u1_pass and eval_split == "val"),  # lab
        "u1_val_lab_pass": bool(rec.get("u1_val_lab_pass")),
        "u1_val_optimistic": bool(rec.get("u1_val_optimistic")),
        "u1_test_honest": bool(rec.get("u1_test_honest")),
        "ml_product_go": ml_product_go,
        "allow_ml_live_in_fusion_recommended": allow_fusion_rec,
        "reasons": reasons,
    }

    doc: dict[str, Any] = {
        "schema": "ml_scorecard_v1",
        "product_id": product_id,
        "protocol": DEFAULT_PROTOCOL,
        "split": split,
        "action": action,
        "calibrator_fit_split": str(calibrator_fit_split or "val"),
        "u1_eval_split": eval_split,
        "tuning": {
            "mix_split": "val",
            "temperature_split": "val",
            "uncertainty_calibration_split": "val",
        },
        "primary": primary,
        "uncertainty": unc,
        "gates": gates,
        "allow_ml_live_in_fusion_recommended": allow_fusion_rec,
        "provenance": {
            "offline": offline,
            "synthetic_mode": synthetic_mode,
            "calibrator_path": calibrator_path,
            "calibrator_fit_split": str(calibrator_fit_split or "val"),
            "u1_eval_split": eval_split,
            "eval_dir": eval_dir,
            "frozen_calibrator": bool(frozen_calibrator) and not bool(identity_calibrator),
            "identity_calibrator": bool(identity_calibrator),
            "require_frozen_calibrator": bool(require_frozen_calibrator),
            "promote_draft": bool(promote_draft),
            "catalog_holdout_test_reference": catalog_ref
            if catalog_ref
            else catalog_holdout_test_reference(),
            "u1_detail": {
                k: (float(v) if isinstance(v, (float, np.floating)) else v)
                for k, v in (u1_detail or {}).items()
                if k
                in (
                    "beats_random",
                    "delta_vs_random",
                    "selective_iou",
                    "margin",
                    "null_kind",
                    "reason",
                    "shuffle_selective_iou_mean",
                )
            },
            "u1a_detail": {
                k: (float(v) if isinstance(v, (float, np.floating)) else v)
                for k, v in (u1a_detail or {}).items()
                if k
                in (
                    "u1a_pass",
                    "selective_iou",
                    "full_coverage_mean_iou",
                    "eps",
                    "delta_vs_full",
                    "reason",
                )
            },
            "honesty_notes": list(FIXED_HONESTY_NOTES),
            "note": (
                "ml_product_go true (lab promote 2026-08-05). "
                "Field fusion OFF (lab GO ≠ field fusion). "
                "primary.model_iou is eval-split mean when patches provided; "
                "catalog 0.8963 is provenance.catalog_holdout_test_reference only. "
                "No ROS fields (dual-product honesty). Not Tobarra / not REDIAM O2."
            ),
            "recommendation_rule": rec.get("recommendation_rule"),
        },
    }
    # Nested CV provenance (VAL-only honest-within-VAL); never a TEST fit.
    nested_block = nested_cv
    if nested_block is None and calibrator_path and Path(calibrator_path).is_file():
        try:
            cal_doc = json.loads(Path(calibrator_path).read_text(encoding="utf-8"))
            if isinstance(cal_doc, dict):
                nested_block = cal_doc.get("nested_cv") or (
                    (cal_doc.get("metrics_on_val") or {}).get("nested_cv")
                )
        except (OSError, json.JSONDecodeError):
            nested_block = None
    if nested_block is not None:
        doc["provenance"]["nested_cv"] = nested_block
        doc["nested_cv"] = nested_block

    fails = validate_ml_scorecard(doc)
    doc["schema_validation"] = {"pass": len(fails) == 0, "fails": fails}
    return _json_safe(doc)


def _json_safe(obj: Any) -> Any:
    """Replace NaN/Inf with None for strict JSON serialization."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        if not np.isfinite(v):
            return None
        return v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build ml_scorecard_v1 + U1 gate (honest)")
    p.add_argument("--product", default=DEFAULT_PRODUCT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--offline-fixture",
        action="store_true",
        help="Synthetic patch IoUs/confidences (CI / no weights)",
    )
    p.add_argument(
        "--synthetic-mode",
        choices=["pass", "fail"],
        default="pass",
        help="With --offline-fixture: U1 pass or fail synthetic data",
    )
    p.add_argument("--split", default="val", choices=["val", "test"])
    p.add_argument(
        "--action",
        default="scorecard",
        choices=["scorecard", "report", "gate"],
    )
    p.add_argument(
        "--calibrator",
        type=Path,
        default=None,
        help="Path to frozen Head A calibrator JSON (metadata only in offline mode)",
    )
    p.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="Holdout NPZ dir (use scripts/eval_ml_uncertainty_u1.py for real run)",
    )
    p.add_argument(
        "--require-frozen-calibrator",
        action="store_true",
        help="Promote path: refuse identity; recommended only with frozen cal on TEST",
    )
    p.add_argument(
        "--frozen-calibrator",
        action="store_true",
        help="Mark scorecard as using a frozen (non-identity) calibrator",
    )
    p.add_argument(
        "--calibrator-fit-split",
        default="val",
        choices=["val", "test", "unknown"],
        help="Split the calibrator was fit on (must be val for honest gate)",
    )
    p.add_argument(
        "--promote-draft",
        action="store_true",
        help="Annotate provenance for draft field-fusion note (ml_product_go already true)",
    )
    args = p.parse_args(argv)

    if args.split == "test" and args.action not in ("report", "scorecard", "gate"):
        print("test split only allows report/scorecard/gate", file=sys.stderr)
        return 2

    # Path rails when eval-dir provided
    if args.eval_dir is not None:
        from wildfire_front.ml.u1_eval import assert_eval_split_path

        try:
            assert_eval_split_path(Path(args.eval_dir), str(args.split))
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    cal_path = str(args.calibrator) if args.calibrator else None
    frozen = bool(args.frozen_calibrator)
    identity = not frozen
    if args.calibrator and Path(args.calibrator).is_file():
        try:
            from wildfire_front.ml.uncertainty import load_calibrator

            cal = load_calibrator(args.calibrator)
            frozen = not cal.is_identity
            identity = bool(cal.is_identity)
            if args.calibrator_fit_split == "val":
                fit_split = str(getattr(cal, "fit_split", "val") or "val")
            else:
                fit_split = str(args.calibrator_fit_split)
        except Exception:
            fit_split = str(args.calibrator_fit_split)
    else:
        fit_split = str(args.calibrator_fit_split)

    if args.require_frozen_calibrator and (identity or not frozen) and not args.offline_fixture:
        print(
            "ERROR: --require-frozen-calibrator but no non-identity calibrator loaded",
            file=sys.stderr,
        )
        return 2

    if args.offline_fixture:
        doc = build_scorecard(
            product_id=args.product,
            split=args.split,
            action=args.action,
            offline=True,
            synthetic_mode=args.synthetic_mode,
            calibrator_path=cal_path,
            calibrator_fit_split=fit_split,
            frozen_calibrator=frozen and not identity,
            identity_calibrator=identity,
            eval_dir=str(args.eval_dir) if args.eval_dir else None,
            require_frozen_calibrator=bool(args.require_frozen_calibrator),
            u1_eval_split=str(args.split),
            promote_draft=bool(args.promote_draft),
        )
    elif args.eval_dir is not None:
        # Real eval is the dedicated script; ml_scorecard without patches is not enough.
        print(
            "NOTE: for real holdout U1 with weights, use "
            "scripts/eval_ml_uncertainty_u1.py (this CLI writes catalog/offline only "
            "unless --offline-fixture).",
            file=sys.stderr,
        )
        doc = build_scorecard(
            product_id=args.product,
            split=args.split,
            action=args.action,
            offline=False,
            calibrator_path=cal_path,
            calibrator_fit_split=fit_split,
            frozen_calibrator=frozen and not identity,
            identity_calibrator=identity,
            eval_dir=str(args.eval_dir),
            require_frozen_calibrator=bool(args.require_frozen_calibrator),
            u1_eval_split=str(args.split),
            promote_draft=bool(args.promote_draft),
        )
    else:
        doc = build_scorecard(
            product_id=args.product,
            split=args.split,
            action=args.action,
            offline=False,
            calibrator_path=cal_path,
            calibrator_fit_split=fit_split,
            frozen_calibrator=frozen and not identity,
            identity_calibrator=identity,
            require_frozen_calibrator=bool(args.require_frozen_calibrator),
            u1_eval_split=str(args.split),
            promote_draft=bool(args.promote_draft),
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8")

    gates = doc.get("gates") or {}
    u1_lab = bool(gates.get("u1_val_lab_pass") or gates.get("u1_val_passed"))
    u1_honest = bool(gates.get("u1_test_honest"))
    u1a = bool(gates.get("U1a_selective_ge_full_minus_eps"))
    u1b = bool(gates.get("U1_selective_beats_random"))
    fusion_rec = bool(doc.get("allow_ml_live_in_fusion_recommended"))
    schema_ok = bool((doc.get("schema_validation") or {}).get("pass"))
    # Verdict: honest TEST pass preferred; lab pass labeled separately.
    if u1_honest and schema_ok:
        u1_verdict = "U1_TEST_HONEST_PASS"
    elif u1_lab and schema_ok:
        u1_verdict = "U1_VAL_LAB_PASS"
    elif (u1a and u1b) and schema_ok:
        u1_verdict = "U1_PASS_NOT_PROMOTE"
    else:
        u1_verdict = "U1_FAIL"

    print(
        json.dumps(
            {
                "wrote": str(out),
                "u1_verdict": u1_verdict,
                "U1a_selective_ge_full_minus_eps": u1a,
                "U1_selective_beats_random": u1b,
                "u1_val_passed": bool(gates.get("u1_val_passed")),
                "u1_val_lab_pass": u1_lab,
                "u1_val_optimistic": bool(gates.get("u1_val_optimistic")),
                "u1_test_honest": u1_honest,
                "ml_product_go": True,
                "allow_ml_live_in_fusion_recommended": fusion_rec,
                "schema_ok": schema_ok,
                "split": args.split,
                "note": (
                    "u1_verdict is honesty gate; ml_product_go true (lab promote 2026-08-05). "
                    "allow_ml_live_in_fusion_recommended requires u1_test_honest. "
                    "Field fusion still OFF (lab GO ≠ field fusion)."
                ),
            },
            indent=2,
        )
    )
    return 0 if schema_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
