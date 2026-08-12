"""Honest U1 evaluation helpers (fit VAL → report TEST; never mix catalog IoU).

Dual-product rails (lab ML vs field_ops) — aligned with product facade
------------------------------------------------------------------
* **lab ML** (``clm_ensemble_v34``): mask IoU / selective / ECE only — **not** ROS.
* **field_ops** (``front_dynamics_v1``): ops ROS; fusion stays **OFF** here.
* ``ml_product_go`` is **promoted true** for lab ``clm_ensemble_v34`` (human
  promote authorized 2026-08-05); U1 never *auto*-flips it (no silent thrash).
* Scorecard path (shared): features → calibrator → rank/reject → scorecard
  (``product_facade`` / ``lab_reject_calibration``); this module is the U1 honesty
  + fusion-**recommend** gate, not a second conf/rank implementation.
* Rank/reject thr is VAL-only; default lab surface freezes **iter1 reject**.
* Multi-fire honesty is first-class elsewhere (Tobarra hard KILL, W3 external
  report-only); U1 holdout is **not** multi-fire generalization.
* Dead thrash paths closed: same-holdout ECE retune, Tobarra KEEP reopen.

Product rule: ``allow_ml_live_in_fusion_recommended`` is true **only** when U1
passes on the **TEST** holdout with a **frozen** (non-identity) calibrator
that was fit on VAL. VAL-only U1 is a lab diagnostic (optimistic if same-split
as fit) and must never promote fusion **or** flip field_ops policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from wildfire_front.ml.protocol_rails import (
    CATALOG_HOLDOUT_IOU_PROVENANCE_ONLY,
    DEFAULT_PRODUCT_ID,
    DEFAULT_PROTOCOL,
    LAB_ML_BANNER,
    LOCKED_REJECT_THR_DEFAULT,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    reject_ros_keys_in_primary,
)

# Published catalog TEST reference (research quality only — not primary.model_iou
# for U1 eval runs). Source: models/clm_ensemble/manifest.json / design doc.
# Align constant with protocol_rails provenance rail.
CATALOG_HOLDOUT_TEST_IOU: Final = float(CATALOG_HOLDOUT_IOU_PROVENANCE_ONLY)
CATALOG_COPY_BASELINE_IOU: Final = 0.6418
CATALOG_IMPROVEMENT_VS_COPY: Final = 0.2545
CATALOG_GROWTH_IOU: Final = 0.9071

# Dual-product honesty notes for scorecard provenance / facade (shared surface).
FIXED_HONESTY_NOTES: tuple[str, ...] = (
    "Dual product: lab ML (mask/confidence IoU) ≠ field_ops ROS (front_dynamics_v1).",
    "IoU ≠ ROS; never invent tactical Vp / ops ROS from ML IoU.",
    "Not Tobarra ops ROS; not REDIAM O2 perimeter truth for next-day IoU.",
    "Catalog TEST IoU 0.8963 is holdout research quality under provenance only.",
    "Calibrator fit is VAL-only; honest fusion gate is U1 on TEST with frozen cal.",
    "Rank/reject thr is VAL-only; default lab surface freezes iter1 reject.",
    "ml_product_go is promoted true for lab clm_ensemble_v34 (human promote 2026-08-05); no silent auto_ml_product_go thrash.",
    "field_ops.allow_ml_live_in_fusion stays OFF (lab GO ≠ field fusion).",
    "allow_ml_live_in_fusion_recommended requires u1_test_honest, not VAL-only lab pass.",
    "Multi-fire honesty: Tobarra = hard (KILL, no KEEP reopen); W3 external = report-only.",
    "No same-holdout ECE retune thrash; U1 is not an ECE re-fit path.",
    LAB_ML_BANNER,
)


def catalog_holdout_test_reference() -> dict[str, Any]:
    """Published champion metrics — provenance only, never unlabeled primary."""
    return {
        "test_iou": CATALOG_HOLDOUT_TEST_IOU,
        "copy_baseline_iou": CATALOG_COPY_BASELINE_IOU,
        "improvement_vs_copy_iou": CATALOG_IMPROVEMENT_VS_COPY,
        "model_iou_growth": CATALOG_GROWTH_IOU,
        "product_id": DEFAULT_PRODUCT_ID,
        "protocol": DEFAULT_PROTOCOL,
        "product_rail": "lab_ml",
        "note": (
            "Published CLM holdout TEST metrics from manifest. "
            "Do not treat as U1 eval mean IoU or live fire certainty. "
            "Provenance only — never primary.model_iou."
        ),
    }


def dual_product_honesty_rails() -> dict[str, Any]:
    """Canonical dual-product rails for U1 / scorecard gates (lab GO true, fusion OFF)."""
    rails = dual_product_rails_dict()
    rails["product_rail"] = "lab_ml"
    # Lab product promoted (human authorize 2026-08-05); do not clamp to false.
    rails["ml_product_go"] = True
    rails["field_ops_allow_ml_live_in_fusion"] = False
    rails["field_ops_ml_live_fusion"] = "OFF"
    rails["field_fusion_off"] = True
    rails["iou_is_not_ros"] = True
    rails["banner"] = LAB_ML_BANNER
    return rails


def multi_fire_honesty_for_u1() -> dict[str, Any]:
    """Multi-fire honesty tags (first-class): U1 holdout ≠ Tobarra/W3 generalization."""
    mf = multi_fire_honesty_dict()
    return {
        "tobarra": dict(mf.get("tobarra") or {}),
        "w3_external": dict(mf.get("w3_external") or {}),
        "cardoso_lofo": dict(mf.get("cardoso_lofo") or {}),
        "u1_holdout_note": (
            "U1 holdout TEST honesty is not multi-fire generalization; "
            "Tobarra hard + W3 external are separate boards (report-only, frozen thr)."
        ),
        "no_tobarra_keep_reopen": True,
        "no_ece_retune_same_holdout": True,
        "iou_is_not_ros": True,
    }


def assert_eval_split_path(data_dir: Path, split: str) -> None:
    """Refuse path component mismatch with declared eval split.

    ``--split test`` must not point at a ``val`` path component, and vice versa.
    Also refuse LOFO / train for U1 report paths that claim holdout val/test.
    """
    split_l = str(split).lower().strip()
    if split_l not in ("val", "test"):
        raise ValueError(f"U1 eval only supports split val|test, got {split!r}")
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
    """Hard refuse fit/calibrate/tune actions on test (VAL-only thr/cal protocol)."""
    tune = {
        "fit",
        "fit_uncertainty",
        "calibrate",
        "tune_mix",
        "tune_temperature",
        "tune_threshold",
        "tune_reject",
        "select",
        "train",
        "optimize",
    }
    if str(split).lower() == "test" and str(action).lower() in tune:
        raise ValueError(
            f"refusing action {action!r} on split test (never fit / calibrate / tune on TEST)"
        )


def compute_fusion_recommendation(
    *,
    eval_split: str,
    calibrator_fit_split: str,
    u1_pass: bool,
    frozen_calibrator: bool,
    identity_calibrator: bool = False,
) -> dict[str, Any]:
    """Decide fusion **recommendation** and honesty gate flags (lab rail only).

    ``allow_ml_live_in_fusion_recommended`` is true **only** when:
    - eval_split == \"test\"
    - U1 (U1a ∧ U1b) passed on that TEST eval
    - calibrator is frozen (loaded product JSON, not identity)
    - calibrator was fit on VAL (not test)

    VAL-only lab pass never recommends fusion (reason ``u1_not_eval_on_test``).

    **Rails (immutable on this path):**
    - ``ml_product_go`` is **true** (lab product promoted; no silent auto-flip thrash).
    - ``field_ops_allow_ml_live_in_fusion`` is always **false** (field fusion OFF).
    - Recommendation is advisory for field fusion — never flips field_ops policy.
    """
    eval_s = str(eval_split).lower()
    fit_s = str(calibrator_fit_split).lower() if calibrator_fit_split else "unknown"
    same_split_as_fit = bool(eval_s and fit_s and eval_s == fit_s)
    # Optimistic when reporting U1 on the same split used to fit (classic VAL-on-VAL).
    u1_val_optimistic = bool(u1_pass and same_split_as_fit and eval_s == "val")
    u1_val_lab_pass = bool(u1_pass and eval_s == "val")
    frozen_ok = bool(frozen_calibrator) and not bool(identity_calibrator)
    fit_ok = fit_s == "val"
    u1_test_honest = bool(u1_pass and eval_s == "test" and frozen_ok and fit_ok)

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

    # Dual-product rails: lab GO true (promoted); field fusion never auto-ON here.
    rails = dual_product_honesty_rails()

    return {
        "allow_ml_live_in_fusion_recommended": allow,
        # Lab product GO promoted; field fusion stays OFF (lab GO ≠ field fusion).
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "product_rail": "lab_ml",
        "iou_is_not_ros": True,
        "u1_val_optimistic": u1_val_optimistic,
        "u1_val_lab_pass": u1_val_lab_pass,
        "u1_test_honest": u1_test_honest,
        "same_split_as_fit": same_split_as_fit,
        "frozen_calibrator": frozen_ok,
        "reasons": reasons,
        "rails": rails,
        "multi_fire_honesty": multi_fire_honesty_for_u1(),
        "recommendation_rule": (
            "recommended true only if U1 pass on TEST with frozen VAL-fit calibrator; "
            "ml_product_go is promoted true for lab; never auto-flips "
            "field_ops.allow_ml_live_in_fusion (field fusion OFF; lab GO ≠ field fusion)"
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
    reject_thr: float | None = None,
) -> dict[str, Any]:
    """Build scorecard ``uncertainty`` object from patch arrays (no ROS keys).

    ``abstain_rate`` uses frozen iter1 reject thr (VAL-selected product surface
    ``iter1_reject_only`` / ``LOCKED_REJECT_THR_DEFAULT`` ≈ 0.795 from
    protocol_rails / product_facade), **not** legacy thr=0.35 (abstain≈0 band).
    Pass ``reject_thr`` only to override the frozen default (report-only).
    """
    import numpy as np

    ious_l = [float(x) for x in ious]
    conf_l = [float(x) for x in confidences]
    y_l = [1 if x >= tau_iou else 0 for x in ious_l] if labels is None else [int(x) for x in labels]
    # Rank/reject protocol: keep when conf >= thr; thr is VAL-frozen iter1 default.
    thr = float(LOCKED_REJECT_THR_DEFAULT) if reject_thr is None else float(reject_thr)
    unc: dict[str, Any] = {
        "n_patches": len(ious_l),
        "tau_iou": float(tau_iou),
        "coverage": float(coverage),
        "mean_confidence": float(np.mean(conf_l)) if conf_l else float("nan"),
        "abstain_rate": float(np.mean([c < thr for c in conf_l])) if conf_l else 0.0,
    }
    if ece is not None:
        unc["ece_patch_conf"] = float(ece)
    if overconf is not None:
        unc["overconfidence_gap"] = float(overconf)
    if u1b is not None:
        unc["selective_iou_at_80pct_coverage"] = u1b.get("selective_iou")
        unc["selective_iou_random_baseline_80"] = u1b.get("shuffle_selective_iou_mean") or u1b.get(
            "random_selective_iou_mean"
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
    No ROS / ops keys (dual-product honesty).
    """
    import numpy as np

    ious_l = [float(x) for x in ious]
    primary = {
        "model_iou": float(np.mean(ious_l)) if ious_l else 0.0,
        "n_patches": len(ious_l),
        "model_iou_split": str(eval_split),
        "model_iou_source": "eval_split_mean",
    }
    reject_ros_keys_in_primary(primary)
    return primary
