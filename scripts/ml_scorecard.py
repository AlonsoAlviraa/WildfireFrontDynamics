#!/usr/bin/env python3
"""Build ml_scorecard_v1 JSON with U1 selective@80% gate.

Modes:
  * default / catalog: primary metrics from clm_ensemble_v34 manifest; U1 unknown
  * --offline-fixture: synthetic patch IoUs/confidences for CI (U1 pass or fail)
  * (future) full holdout run — not required for offline CI

Outputs:
  outputs/ml_eval/scorecards/ml_scorecard_latest.json

Production fusion remains OFF until a human promotes a U1-pass scorecard.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_scorecard_latest.json"
DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_PROTOCOL = "clm_holdout_test_seed42_v1"
U1_COVERAGE = 0.8
U1_MARGIN = 0.01
U1A_EPS = 0.01


def _catalog_primary(product_id: str = DEFAULT_PRODUCT) -> dict[str, Any]:
    """Primary metrics placeholders from catalog/manifest (no holdout run)."""
    man = ROOT / "models" / "clm_ensemble" / "manifest.json"
    metrics: dict[str, Any] = {}
    if man.is_file():
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
            metrics = dict(data.get("metrics") or {})
            product_id = str(data.get("id") or data.get("version") or product_id)
        except (OSError, json.JSONDecodeError):
            pass
    primary: dict[str, Any] = {}
    if "test_iou" in metrics or "model_iou" in metrics:
        primary["model_iou"] = float(metrics.get("model_iou") or metrics.get("test_iou") or 0.0)
    if "copy_baseline_iou" in metrics:
        primary["copy_baseline_iou"] = float(metrics["copy_baseline_iou"])
    if "improvement_vs_copy_iou" in metrics:
        primary["improvement_vs_copy_iou"] = float(metrics["improvement_vs_copy_iou"])
    if "model_iou_growth" in metrics:
        primary["model_iou_growth"] = float(metrics["model_iou_growth"])
    if not primary:
        # Hardcoded published v34 floors (docs/design) when manifest absent offline
        primary = {
            "model_iou": 0.8963,
            "copy_baseline_iou": 0.6418,
            "improvement_vs_copy_iou": 0.2545,
            "model_iou_growth": 0.9071,
        }
    return {"product_id": product_id, "primary": primary, "metrics_raw": metrics}


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
) -> dict[str, Any]:
    from wildfire_front.ml.reliability_metrics import ece_patch_conf, overconfidence_gap
    from wildfire_front.ml.scorecard_schema import validate_ml_scorecard

    cat = _catalog_primary(product_id)
    product_id = cat["product_id"]
    primary = cat["primary"]

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
        # U1c: ECE reported (not a kill gate alone)
        ece_val = float(ece_patch_conf(conf_l, y_l, n_bins=10))
        # Combined U1 for fusion recommendation: U1a ∧ U1b
        u1_pass = bool(u1a_pass and u1b_pass)
        unc = {
            "ece_patch_conf": ece_val,
            "selective_iou_at_80pct_coverage": float(u1_detail.get("selective_iou") or float("nan")),
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
        if "model_iou" not in primary or offline:
            primary = dict(primary)
            primary["model_iou"] = float(np.mean(ious_l)) if ious_l else primary.get("model_iou", 0.0)
            primary["n_patches"] = len(ious_l)

    # Default: no patch run → U1 not passed; fusion stays recommended OFF
    if ious is None and synthetic_mode is None:
        u1_pass = False
        u1a_pass = False
        u1b_pass = False
        u1_detail = {"beats_random": False, "reason": "no_patch_data"}
        u1a_detail = {"u1a_pass": False, "reason": "no_patch_data"}

    allow_fusion_rec = bool(u1_pass)
    reasons: list[str] = []
    if not u1a_pass:
        reasons.append("U1a_fail_or_missing")
    if not u1b_pass:
        reasons.append("U1b_fail_or_missing")
    if ious is None and synthetic_mode is None:
        reasons = ["U1_fail_or_missing_patch_data"]
    gates = {
        "U1a_selective_ge_full_minus_eps": u1a_pass,
        "U1_selective_beats_random": u1b_pass,  # U1b
        "U1b_selective_beats_random": u1b_pass,
        "u1_val_passed": u1_pass,  # U1a ∧ U1b
        "ml_product_go": False,  # never auto-GO; human promote
        "allow_ml_live_in_fusion_recommended": allow_fusion_rec,
        "reasons": reasons,
    }

    doc: dict[str, Any] = {
        "schema": "ml_scorecard_v1",
        "product_id": product_id,
        "protocol": DEFAULT_PROTOCOL,
        "split": split,
        "action": action,
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
            "note": (
                "Production fusion weight OFF until human promotes U1 pass. "
                "CLI u1_verdict is not ml_product_go (always false until human promote). "
                "Holdout IoU is research quality, not live fire certainty. "
                "No ROS fields in this scorecard (dual-product honesty)."
            ),
        },
    }

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
    p = argparse.ArgumentParser(description="Build ml_scorecard_v1 + U1 gate")
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
    args = p.parse_args(argv)

    # VAL scorecard is allowed; test only report/scorecard/gate (rails)
    if args.split == "test" and args.action not in ("report", "scorecard", "gate"):
        print("test split only allows report/scorecard/gate", file=sys.stderr)
        return 2

    if args.offline_fixture:
        doc = build_scorecard(
            product_id=args.product,
            split=args.split,
            action=args.action,
            offline=True,
            synthetic_mode=args.synthetic_mode,
        )
    else:
        doc = build_scorecard(
            product_id=args.product,
            split=args.split,
            action=args.action,
            offline=False,
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8")

    u1_combined = bool(doc.get("gates", {}).get("u1_val_passed"))
    u1a = bool(doc.get("gates", {}).get("U1a_selective_ge_full_minus_eps"))
    u1b = bool(doc.get("gates", {}).get("U1_selective_beats_random"))
    fusion_rec = bool(doc.get("allow_ml_live_in_fusion_recommended"))
    schema_ok = bool((doc.get("schema_validation") or {}).get("pass"))
    # Not product/fusion GO — only U1 gate status (ml_product_go stays false).
    u1_verdict = "U1_PASS" if (u1_combined and schema_ok) else "U1_FAIL"
    print(
        json.dumps(
            {
                "wrote": str(out),
                "u1_verdict": u1_verdict,
                "U1a_selective_ge_full_minus_eps": u1a,
                "U1_selective_beats_random": u1b,
                "u1_val_passed": u1_combined,
                "ml_product_go": False,
                "allow_ml_live_in_fusion_recommended": fusion_rec,
                "schema_ok": schema_ok,
                "note": (
                    "u1_verdict is not product GO. "
                    "Fusion live weight remains OFF until human promotes U1 pass "
                    "(ml_product_go always false from this CLI)."
                ),
            },
            indent=2,
        )
    )
    return 0 if schema_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
