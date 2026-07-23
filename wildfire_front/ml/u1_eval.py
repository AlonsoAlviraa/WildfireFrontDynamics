"""Honest U1 evaluation helpers (fit VAL → report TEST; never mix catalog IoU).

Product rule: ``allow_ml_live_in_fusion_recommended`` is true **only** when U1
passes on the **TEST** holdout with a **frozen** (non-identity) calibrator
that was fit on VAL. VAL-only U1 is a lab diagnostic (optimistic if same-split
as fit) and must never promote fusion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

# Published catalog TEST reference (research quality only — not primary.model_iou
# for U1 eval runs). Source: models/clm_ensemble/manifest.json / design doc.
CATALOG_HOLDOUT_TEST_IOU = 0.8963
CATALOG_COPY_BASELINE_IOU = 0.6418
CATALOG_IMPROVEMENT_VS_COPY = 0.2545
CATALOG_GROWTH_IOU = 0.9071

FIXED_HONESTY_NOTES: tuple[str, ...] = (
    "Dual product: ML mask/confidence ≠ ops ROS (front_dynamics_v1).",
    "Not a rate-of-spread (ROS) product; never invent tactical Vp from ML IoU.",
    "Not Tobarra ops ROS; not REDIAM O2 perimeter truth for next-day IoU.",
    "Catalog TEST IoU 0.8963 is holdout research quality under provenance only.",
    "Calibrator fit is VAL-only; honest fusion gate is U1 on TEST with frozen cal.",
    "ml_product_go never auto-flips; promote is a separate human-gated script.",
    "allow_ml_live_in_fusion_recommended requires u1_test_honest, not VAL-only lab pass.",
)


def catalog_holdout_test_reference() -> dict[str, Any]:
    """Published champion metrics — provenance only, never unlabeled primary."""
    return {
        "test_iou": CATALOG_HOLDOUT_TEST_IOU,
        "copy_baseline_iou": CATALOG_COPY_BASELINE_IOU,
        "improvement_vs_copy_iou": CATALOG_IMPROVEMENT_VS_COPY,
        "model_iou_growth": CATALOG_GROWTH_IOU,
        "product_id": "clm_ensemble_v34",
        "protocol": "clm_holdout_test_seed42_v1",
        "note": (
            "Published CLM holdout TEST metrics from manifest. "
            "Do not treat as U1 eval mean IoU or live fire certainty."
        ),
    }


def assert_eval_split_path(data_dir: Path, split: str) -> None:
    """Refuse path component mismatch with declared eval split.

    ``--split test`` must not point at a ``val`` path component, and vice versa.
    Also refuse LOFO / train for U1 report paths that claim holdout val/test.
    """
    split_l = str(split).lower().strip()
    if split_l not in ("val", "test"):
        raise ValueError(
            f"U1 eval only supports split val|test, got {split!r}"
        )
    try:
        resolved = data_dir.resolve()
    except OSError:
        resolved = data_dir
    parts = [p.lower() for p in Path(resolved).parts]
    # LOFO / train never for holdout U1 honesty path
    for part in parts:
        base = part.split(".")[0]
        if base == "lofo" or base.startswith("lofo"):
            raise ValueError(
                f"refusing eval dir {data_dir}: LOFO path is stress-only, not U1 promote"
            )
        if base == "train":
            raise ValueError(
                f"refusing eval dir {data_dir}: train split is not allowed for U1 eval"
            )
    if split_l == "test":
        if "val" in parts and "test" not in parts:
            raise ValueError(
                f"refusing eval dir {data_dir}: path has 'val' but --split test "
                "(protocol rails: do not evaluate TEST claim on VAL path)"
            )
        if "test" not in parts:
            raise ValueError(
                f"refusing eval dir {data_dir}: path must contain a 'test' component "
                "when --split test (e.g. holdout_v1/test)"
            )
    if split_l == "val":
        if "test" in parts and "val" not in parts:
            raise ValueError(
                f"refusing eval dir {data_dir}: path has 'test' but --split val "
                "(protocol rails: do not claim VAL on TEST path)"
            )
        if "val" not in parts:
            raise ValueError(
                f"refusing eval dir {data_dir}: path must contain a 'val' component "
                "when --split val"
            )


def assert_never_fit_on_test(action: str, split: str) -> None:
    """Hard refuse fit/calibrate/tune actions on test."""
    tune = {
        "fit",
        "fit_uncertainty",
        "calibrate",
        "tune_mix",
        "tune_temperature",
        "select",
        "train",
        "optimize",
    }
    if str(split).lower() == "test" and str(action).lower() in tune:
        raise ValueError(
            f"refusing action {action!r} on split test "
            "(never fit / calibrate / tune on TEST)"
        )


def compute_fusion_recommendation(
    *,
    eval_split: str,
    calibrator_fit_split: str,
    u1_pass: bool,
    frozen_calibrator: bool,
    identity_calibrator: bool = False,
) -> dict[str, Any]:
    """Decide fusion recommendation and honesty gate flags.

    ``allow_ml_live_in_fusion_recommended`` is true **only** when:
    - eval_split == \"test\"
    - U1 (U1a ∧ U1b) passed on that TEST eval
    - calibrator is frozen (loaded product JSON, not identity)
    - calibrator was fit on VAL (not test)

    VAL-only lab pass never recommends fusion (reason ``u1_not_eval_on_test``).
    """
    eval_s = str(eval_split).lower()
    fit_s = str(calibrator_fit_split).lower() if calibrator_fit_split else "unknown"
    same_split_as_fit = bool(eval_s and fit_s and eval_s == fit_s)
    # Optimistic when reporting U1 on the same split used to fit (classic VAL-on-VAL).
    u1_val_optimistic = bool(u1_pass and same_split_as_fit and eval_s == "val")
    u1_val_lab_pass = bool(u1_pass and eval_s == "val")
    frozen_ok = bool(frozen_calibrator) and not bool(identity_calibrator)
    fit_ok = fit_s == "val"
    u1_test_honest = bool(
        u1_pass and eval_s == "test" and frozen_ok and fit_ok
    )

    reasons: list[str] = []
    if not u1_pass:
        reasons.append("u1_fail")
    if eval_s != "test":
        reasons.append("u1_not_eval_on_test")
    if identity_calibrator or not frozen_calibrator:
        reasons.append("calibrator_not_frozen")
    if fit_s != "val":
        reasons.append("calibrator_fit_split_not_val")
    if same_split_as_fit and eval_s == "val":
        reasons.append("u1_val_optimistic_same_split_as_fit")

    allow = bool(u1_test_honest)
    if allow:
        reasons = []

    return {
        "allow_ml_live_in_fusion_recommended": allow,
        "u1_val_optimistic": u1_val_optimistic,
        "u1_val_lab_pass": u1_val_lab_pass,
        "u1_test_honest": u1_test_honest,
        "same_split_as_fit": same_split_as_fit,
        "frozen_calibrator": frozen_ok,
        "reasons": reasons,
        "recommendation_rule": (
            "recommended true only if U1 pass on TEST with frozen VAL-fit calibrator"
        ),
    }


def patch_metrics_to_uncertainty_block(
    ious: Sequence[float],
    confidences: Sequence[float],
    labels: Sequence[int] | None,
    *,
    coverage: float = 0.8,
    tau_iou: float = 0.5,
    u1a: dict[str, Any] | None = None,
    u1b: dict[str, Any] | None = None,
    ece: float | None = None,
    overconf: float | None = None,
) -> dict[str, Any]:
    """Build scorecard ``uncertainty`` object from patch arrays (no ROS keys)."""
    import numpy as np

    ious_l = [float(x) for x in ious]
    conf_l = [float(x) for x in confidences]
    if labels is None:
        y_l = [1 if x >= tau_iou else 0 for x in ious_l]
    else:
        y_l = [int(x) for x in labels]
    unc: dict[str, Any] = {
        "n_patches": len(ious_l),
        "tau_iou": float(tau_iou),
        "coverage": float(coverage),
        "mean_confidence": float(np.mean(conf_l)) if conf_l else float("nan"),
        "abstain_rate": float(np.mean([c < 0.35 for c in conf_l])) if conf_l else 0.0,
    }
    if ece is not None:
        unc["ece_patch_conf"] = float(ece)
    if overconf is not None:
        unc["overconfidence_gap"] = float(overconf)
    if u1b is not None:
        unc["selective_iou_at_80pct_coverage"] = u1b.get("selective_iou")
        unc["selective_iou_random_baseline_80"] = (
            u1b.get("shuffle_selective_iou_mean")
            or u1b.get("random_selective_iou_mean")
        )
        unc["beats_random_selective"] = bool(u1b.get("beats_random"))
        unc["delta_vs_random"] = u1b.get("delta_vs_random")
    if u1a is not None and "selective_iou" in u1a and "selective_iou_at_80pct_coverage" not in unc:
        unc["selective_iou_at_80pct_coverage"] = u1a.get("selective_iou")
    # silence unused y_l for callers that only need structure — keep for future ECE
    _ = y_l
    return unc


def primary_from_eval_ious(
    ious: Sequence[float],
    *,
    eval_split: str,
) -> dict[str, Any]:
    """Primary block: model_iou is **only** mean IoU of the eval split.

    Catalog TEST 0.8963 must never appear here — use
    ``catalog_holdout_test_reference()`` under provenance instead.
    """
    import numpy as np

    ious_l = [float(x) for x in ious]
    return {
        "model_iou": float(np.mean(ious_l)) if ious_l else 0.0,
        "n_patches": len(ious_l),
        "model_iou_split": str(eval_split),
        "model_iou_source": "eval_split_mean",
    }
