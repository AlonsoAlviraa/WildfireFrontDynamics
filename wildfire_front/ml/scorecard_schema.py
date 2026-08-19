"""ML scorecard schema validation (ml_scorecard_v1)."""

from __future__ import annotations

from typing import Any

from wildfire_front.ml.protocol_rails import (
    ProtocolRailError,
    assert_split_role,
    reject_ros_keys_in_primary,
    validate_scorecard_tuning,
)

# Approximate additionalProperties:false allowlists (design scorecard schema).
PRIMARY_ALLOWED_KEYS = frozenset(
    {
        "model_iou",
        "copy_baseline_iou",
        "improvement_vs_copy_iou",
        "model_iou_growth",
        "improvement_vs_dilated_copy_iou_growth",
        "improvement_vs_copy_iou_changed",
        "model_iou_changed",
        "model_growth_transition_iou",
        "model_change_transition_iou",
        "improvement_vs_dilated_copy_growth_transition_iou",
        "improvement_vs_dilated_copy_change_transition_iou",
        "model_growth_average_precision_macro",
        "model_growth_fcer_iou",
        "model_growth_fcer_average_precision_macro",
        "observed_growth_fcer_capture_macro",
        "model_front_boundary_f1_macro",
        "improvement_vs_dilated_copy_front_boundary_f1",
        "model_growth_fcer_ece_macro",
        "model_growth_fcer_selective_error_80_macro",
        "model_growth_fcer_aurc_macro",
        "observed_growth_fcer_prevalence_macro",
        "fcer_semantics",
        "fcer_calibration_semantics",
        "boundary_metric_semantics",
        "transition_metric_semantics",
        "n_patches",
        "threshold",
        # Honesty tags: which split/source produced model_iou (never mix catalog silently)
        "model_iou_split",
        "model_iou_source",
    }
)
UNCERTAINTY_ALLOWED_KEYS = frozenset(
    {
        "ece_patch_conf",
        "ece_pixel_prob",
        "selective_iou_at_80pct_coverage",
        "selective_iou_at_coverage",
        "selective_iou_random_baseline_80",
        "spearman_conf_vs_iou",
        "beats_random_selective",
        "overconfidence_gap",
        "n_patches",
        "tau_iou",
        "abstain_rate",
        "coverage",
        "mean_confidence",
        "delta_vs_random",
    }
)


def validate_ml_scorecard(doc: dict[str, Any]) -> list[str]:
    """Return list of failure reasons; empty = valid enough to gate."""
    fails: list[str] = []
    if not isinstance(doc, dict):
        return ["not_a_dict"]
    if doc.get("schema") != "ml_scorecard_v1":
        fails.append(f"bad_schema:{doc.get('schema')}")
    for key in ("product_id", "protocol", "split", "action"):
        if key not in doc:
            fails.append(f"missing_{key}")
    if "split" in doc and "action" in doc:
        try:
            assert_split_role(str(doc["split"]), str(doc["action"]))
        except ProtocolRailError as e:
            fails.append(f"split_role:{e}")
        except (TypeError, ValueError) as e:
            fails.append(f"split_role:{e}")
    primary = doc.get("primary")
    if not isinstance(primary, dict):
        fails.append("missing_primary")
    else:
        try:
            reject_ros_keys_in_primary(primary)
        except Exception as e:
            fails.append(str(e))
        # additionalProperties:false for known forbidden ops leakage already handled
        for k in primary:
            if k.startswith("ros_") or k in ("vp_tactical", "primary_ros_m_min"):
                fails.append(f"forbidden_primary_key:{k}")
            elif k not in PRIMARY_ALLOWED_KEYS:
                fails.append(f"unknown_primary_key:{k}")
    unc = doc.get("uncertainty")
    if unc is not None:
        if not isinstance(unc, dict):
            fails.append("uncertainty_not_object")
        else:
            for k in unc:
                if k not in UNCERTAINTY_ALLOWED_KEYS:
                    fails.append(f"unknown_uncertainty_key:{k}")
    fails.extend(
        validate_scorecard_tuning(
            doc.get("tuning") if isinstance(doc.get("tuning"), dict) else None
        )
    )
    return fails


def scorecard_gates_pass(doc: dict[str, Any]) -> dict[str, Any]:
    fails = validate_ml_scorecard(doc)
    return {
        "pass": len(fails) == 0,
        "fails": fails,
        "product_id": doc.get("product_id") if isinstance(doc, dict) else None,
    }
