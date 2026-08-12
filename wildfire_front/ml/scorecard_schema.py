"""ML scorecard schema validation (ml_scorecard_v1).

Dual-product / product-ROI rails encoded here (architecture, not retrain):

* **lab_ml vs field_ops** -- this schema is the lab ML claim surface; IoU != ROS.
* **Unified reject/rank surface** -- thr-based abstain and ranking share one protocol;
  thr is VAL-only; default freeze surface is ``iter1_reject_only``.
* **Facade-built scorecards** -- when a doc carries product_facade / rank_reject /
  lab_surface_iter1_reject markers, enforce facade gates: iter1 surface, VAL thr
  source, refuse ROS; allow human-promoted ``ml_product_go=true`` (lab GO != field fusion).
* **Multi-fire honesty** -- Tobarra hard + W3 external are first-class when present
  (not ad-hoc script-only).
* **No auto-promote thrash** -- forbid ``auto_ml_product_go`` / auto-flip keys; explicit
  promoted ``ml_product_go=true`` is allowed (owner 2026-08-05). Field_ops fusion stays OFF.
* **No thrash paths** -- same-holdout ECE retune / Tobarra KEEP reopen hooks forbidden
  as promote fields on the scorecard.
"""

from __future__ import annotations

from typing import Any, Final

from wildfire_front.ml.protocol_rails import (
    ROS_FORBIDDEN_KEYS,
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
        # ECE protocol tags (optional; never imply TEST thrash)
        "n_bins",
        "binning",
        "empty_bin_policy",
        "insufficient_n",
    }
)

# Unified reject/rank surface -- ranking path and thr-abstain share one protocol.
# Default freeze: recommended_lab_surface = iter1_reject_only; thr from VAL only.
SURFACE_ALLOWED_KEYS = frozenset(
    {
        "kind",  # reject | rank | reject_and_rank
        "protocol",
        "recommended_lab_surface",  # default freeze: iter1_reject_only
        "thr",
        "threshold",
        "thr_source",  # val | frozen | locked (never test/lofo tune)
        "thr_split",  # must be val when set
        "temperature",
        "temperature_split",  # must be val when set
        "abstain_rate",
        "keep_rate",
        "iou_accepted",
        "mean_iou_accepted",
        "test_abstain_rate",
        "test_iou_accepted",
        "selective_iou_at_coverage",
        "selective_iou_at_80pct_coverage",
        "coverage",
        "ranking_score",
        "rank_mode",
        "frozen",
        "val_only",
        "lab_reject_surface_improved",
        "lab_only",
        "iou_is_not_ros",
        "note",
    }
)

DEFAULT_RECOMMENDED_LAB_SURFACE: Final = "iter1_reject_only"
ALLOWED_RECOMMENDED_LAB_SURFACES: Final = frozenset(
    {
        "iter1_reject_only",
        "soft_dice_proxy_ranking",
        "rank_only",
        "reject_and_rank",
    }
)
ALLOWED_SURFACE_KINDS: Final = frozenset({"reject", "rank", "reject_and_rank", "iter1_reject"})
# thr may be reported from frozen VAL lock; never tuned on test/lofo
ALLOWED_THR_SOURCES: Final = frozenset(
    {
        "val",
        "frozen",
        "locked",
        "iter1_freeze",
        "val_frozen",
        "val_iter1_reject_frozen",
        "iter1_locked",
        "locked_iter1",
    }
)

# product_facade.build_scorecard rank_reject block (shared protocol surface).
RANK_REJECT_ALLOWED_KEYS: Final = frozenset(
    {
        "thr",
        "threshold",
        "surface",
        "recommended_lab_surface",
        "protocol_module",
        "mode_note",
        "note",
        "thr_source",
        "thr_split",
        "val_only",
        "frozen",
        "mode",
        "rank_score_name",
        "selective_coverage",
        "iou_is_not_ros",
        "lab_only",
    }
)

# Multi-fire honesty (Tobarra hard, W3 external) -- first-class when present.
MULTI_FIRE_ALLOWED_KEYS = frozenset(
    {
        "tobarra_hard",
        "tobarra_status",
        "tobarra_verdict",  # KILL / hard / inconclusive -- not silent KEEP promote
        "tobarra_mean_iou",
        "w3_external",
        "w3_status",
        "w3_fires",
        "lofo_mean_iou",
        "lofo_n_folds",
        "holdout_u1_mean_iou",
        "generalization_note",
        "fires",
        "folds",
        "n_fires",
        "no_ece_retune_same_holdout",
        "no_tobarra_keep_reopen",
        "iou_is_not_ros",
        "lab_only",
        "note",
    }
)

# Dual-product gates on lab ML scorecard.
GATES_ALLOWED_KEYS = frozenset(
    {
        "U1a_selective_ge_full_minus_eps",
        "U1_selective_beats_random",
        "U1b_selective_beats_random",
        "u1_val_passed",
        "u1_val_lab_pass",
        "u1_val_optimistic",
        "u1_test_honest",
        "ml_product_go",  # human-promoted true allowed; auto-flip keys still forbidden
        "allow_ml_live_in_fusion_recommended",  # recommendation only; not policy flip
        "field_ops_allow_ml_live_in_fusion",  # must be false / absent if set
        "reasons",
        "promote_draft",  # draft annotation only
        "promote_eligible",
        "iou_is_not_ros",
        "product_rail",  # lab_ml (not field_ops)
        "lab_ml_only",
        "lab_usable_freeze",
        # product_facade.build_scorecard freeze marker (iter1 reject surface)
        "lab_surface_iter1_reject",
    }
)

CLAIM_SURFACE_ALLOWED_KEYS = frozenset(
    {
        "kind",
        "not_tactical",
        "not_field_ops",
        "not_ros",
        "research_open_live_fusion",
        "primary_is_test_eval_mean",
        "catalog_reference_separate",
        "product_rail",
        "lab_ml_only",
        "iou_is_not_ros",
    }
)

# Keys that must never appear as truthy auto-promote / thrash hooks on a scorecard.
AUTO_PROMOTE_FORBIDDEN_KEYS: Final = frozenset(
    {
        "auto_promote",
        "auto_flip_ml_product_go",
        "ml_product_go_auto",
        "auto_enable_field_ops_fusion",
        "flip_field_ops_fusion",
        "field_ops_fusion_on",
        "ece_retune_same_holdout",
        "same_holdout_ece_retune",
        "retune_ece_on_test",
        "tobarra_keep_reopen",
        "tobarra_keep_auto_promote",
        "reopen_tobarra_keep",
        "re_promote_tobarra_kill_weights",
    }
)

# Dual-product: field_ops is not this scorecard's product rail.
ALLOWED_PRODUCT_RAILS: Final = frozenset({"lab_ml", "lab", "research_open_lab"})

# Marker module string used by product_facade.build_scorecard provenance/rails.
PRODUCT_FACADE_MODULE: Final = "wildfire_front.ml.product_facade"


def _ros_leak_fails(block: dict[str, Any], *, where: str) -> list[str]:
    fails: list[str] = []
    for k in block:
        if (
            k in ROS_FORBIDDEN_KEYS
            or str(k).startswith("ros_")
            or k in ("vp_tactical", "primary_ros_m_min", "speed_median_m_min")
        ):
            fails.append(f"forbidden_{where}_key:{k}")
    return fails


def _validate_thr_val_only(block: dict[str, Any], *, where: str) -> list[str]:
    """Reject thr tune markers that are not VAL / freeze-lock."""
    fails: list[str] = []
    for split_key in ("thr_split", "temperature_split"):
        if split_key in block and str(block[split_key]) != "val":
            fails.append(f"{where}_{split_key}_not_val:{block[split_key]}")
    if "thr_source" in block:
        src = str(block["thr_source"])
        if src not in ALLOWED_THR_SOURCES:
            fails.append(f"{where}_thr_source_not_val_or_freeze:{src}")
    if block.get("val_only") is False:
        fails.append(f"{where}_val_only_false")
    return fails


def _validate_surface(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    fails.extend(_ros_leak_fails(surface, where="surface"))
    for k in surface:
        # unknown surface keys (auto-promote handled elsewhere)
        if (
            k not in SURFACE_ALLOWED_KEYS
            and k not in AUTO_PROMOTE_FORBIDDEN_KEYS
            and k not in ROS_FORBIDDEN_KEYS
            and not str(k).startswith("ros_")
        ):
            fails.append(f"unknown_surface_key:{k}")
    if "kind" in surface and str(surface["kind"]) not in ALLOWED_SURFACE_KINDS:
        fails.append(f"bad_surface_kind:{surface['kind']}")
    rec = surface.get("recommended_lab_surface")
    if rec is not None and str(rec) not in ALLOWED_RECOMMENDED_LAB_SURFACES:
        fails.append(f"bad_recommended_lab_surface:{rec}")
    fails.extend(_validate_thr_val_only(surface, where="surface"))
    return fails


def _validate_rank_reject(block: dict[str, Any]) -> list[str]:
    """Validate product_facade rank_reject payload (shared thr + ranking)."""
    fails: list[str] = []
    fails.extend(_ros_leak_fails(block, where="rank_reject"))
    for k in block:
        if (
            k not in RANK_REJECT_ALLOWED_KEYS
            and k not in AUTO_PROMOTE_FORBIDDEN_KEYS
            and k not in ROS_FORBIDDEN_KEYS
            and not str(k).startswith("ros_")
        ):
            fails.append(f"unknown_rank_reject_key:{k}")
    surf = block.get("surface") or block.get("recommended_lab_surface")
    if surf is not None and str(surf) not in ALLOWED_RECOMMENDED_LAB_SURFACES:
        fails.append(f"bad_rank_reject_surface:{surf}")
    fails.extend(_validate_thr_val_only(block, where="rank_reject"))
    return fails


def is_facade_built_scorecard(doc: dict[str, Any]) -> bool:
    """True when the doc was assembled on the product_facade path.

    Detection markers (any one is enough):
    * top-level / provenance / rails ``product_facade`` string
    * ``rank_reject`` block (facade thr+surface payload)
    * gates ``lab_surface_iter1_reject``
    """
    if not isinstance(doc, dict):
        return False
    if doc.get("product_facade"):
        return True
    for name in ("provenance", "rails", "gates"):
        b = doc.get(name)
        if isinstance(b, dict) and b.get("product_facade"):
            return True
    if isinstance(doc.get("rank_reject"), dict):
        return True
    gates = doc.get("gates")
    if isinstance(gates, dict) and "lab_surface_iter1_reject" in gates:
        return True
    prov = doc.get("provenance")
    return bool(isinstance(prov, dict) and str(prov.get("pipeline") or "").find("rank/reject") >= 0)


def _validate_facade_gates(doc: dict[str, Any]) -> list[str]:
    """Enforce facade gates on facade-built scorecards.

    Required rails (architecture, not retrain):
    * default freeze surface ``iter1_reject_only``
    * thr source VAL / freeze-lock only
    * refuse ROS leakage
    * allow human-promoted ``ml_product_go=true`` (lab GO != field fusion)
    * field_ops fusion stays OFF
    """
    fails: list[str] = []
    fails.extend(_ros_leak_fails(doc, where="facade_doc"))

    gates = doc.get("gates") if isinstance(doc.get("gates"), dict) else {}
    rails = doc.get("rails") if isinstance(doc.get("rails"), dict) else {}
    rr = doc.get("rank_reject") if isinstance(doc.get("rank_reject"), dict) else {}
    surface = (
        doc.get("surface")
        if isinstance(doc.get("surface"), dict)
        else doc.get("reject_rank_surface")
        if isinstance(doc.get("reject_rank_surface"), dict)
        else {}
    )
    if not isinstance(surface, dict):
        surface = {}
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}

    # Explicit promoted ml_product_go=true is allowed (owner 2026-08-05).
    # Field fusion ON remains forbidden (lab GO != field fusion).
    if (
        gates.get("field_ops_allow_ml_live_in_fusion") is True
        or rails.get("field_ops_allow_ml_live_in_fusion") is True
    ):
        fails.append("facade_field_ops_fusion_on_forbidden")

    # iter1 surface freeze
    rec_candidates = [
        rr.get("surface"),
        rr.get("recommended_lab_surface"),
        surface.get("recommended_lab_surface"),
        surface.get("kind") if surface.get("kind") in ALLOWED_RECOMMENDED_LAB_SURFACES else None,
        rails.get("recommended_lab_surface"),
        prov.get("recommended_lab_surface"),
        doc.get("recommended_lab_surface"),
    ]
    rec = next((str(c) for c in rec_candidates if c is not None), None)
    if rec is not None and rec != DEFAULT_RECOMMENDED_LAB_SURFACE:
        fails.append(f"facade_surface_not_iter1_reject_only:{rec}")
    if "lab_surface_iter1_reject" in gates and gates.get("lab_surface_iter1_reject") is not True:
        fails.append("facade_lab_surface_iter1_reject_not_true")
    # If facade markers present but no surface claim at all, still require iter1 flag
    # when gates block exists without lab_surface_iter1_reject — soft: only if gates empty
    # of surface markers AND rank_reject lacks surface, default is ok (facade emits both).

    # VAL thr source on any thr-bearing block
    thr_blocks: list[tuple[str, dict[str, Any]]] = []
    if rr:
        thr_blocks.append(("rank_reject", rr))
    if surface:
        thr_blocks.append(("surface", surface))
    if isinstance(doc.get("tuning"), dict):
        thr_blocks.append(("tuning", doc["tuning"]))
    for where, block in thr_blocks:
        fails.extend(_validate_thr_val_only(block, where=f"facade_{where}"))
        # Explicit non-VAL thr_source aliases already covered by ALLOWED_THR_SOURCES

    # Dual-product: product_rail must stay lab when set
    for where, block in (
        ("gates", gates),
        ("rails", rails),
        (
            "claim_surface",
            doc.get("claim_surface") if isinstance(doc.get("claim_surface"), dict) else {},
        ),
        ("doc", doc),
    ):
        rail = block.get("product_rail") if isinstance(block, dict) else None
        if where == "doc":
            rail = doc.get("product_rail") or doc.get("product_surface")
        if rail is not None and str(rail) not in ALLOWED_PRODUCT_RAILS:
            fails.append(f"facade_product_rail_not_lab:{rail}")

    if gates.get("iou_is_not_ros") is False or rails.get("iou_is_not_ros") is False:
        fails.append("facade_iou_is_not_ros_false")

    return fails


def _validate_multi_fire(block: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    fails.extend(_ros_leak_fails(block, where="multi_fire"))
    for k in block:
        if (
            k not in MULTI_FIRE_ALLOWED_KEYS
            and k not in AUTO_PROMOTE_FORBIDDEN_KEYS
            and k not in ROS_FORBIDDEN_KEYS
            and not str(k).startswith("ros_")
        ):
            fails.append(f"unknown_multi_fire_key:{k}")
    # Tobarra KEEP reopen as promote is forbidden thrash
    verdict = str(block.get("tobarra_verdict") or "").upper()
    # Explicit KEEP on multi_fire without freeze rail is a thrash reopen signal
    if (
        verdict in ("KEEP", "KEEP_REOPEN", "KEEP_PROMOTE")
        and block.get("no_tobarra_keep_reopen") is not True
        and (block.get("tobarra_keep_reopen") or block.get("reopen_tobarra_keep"))
    ):
        fails.append("multi_fire_tobarra_keep_reopen_forbidden")
    if block.get("no_ece_retune_same_holdout") is False:
        fails.append("multi_fire_ece_retune_same_holdout_forbidden")
    if block.get("iou_is_not_ros") is False:
        fails.append("multi_fire_iou_is_not_ros_false")
    return fails


def _validate_gates(gates: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    fails.extend(_ros_leak_fails(gates, where="gates"))
    for k in gates:
        if (
            k not in GATES_ALLOWED_KEYS
            and k not in AUTO_PROMOTE_FORBIDDEN_KEYS
            and k not in ROS_FORBIDDEN_KEYS
            and not str(k).startswith("ros_")
        ):
            fails.append(f"unknown_gates_key:{k}")
    # Dual-product: human-promoted ml_product_go=true is allowed; field fusion stays OFF.
    # Auto-flip thrash keys are refused via AUTO_PROMOTE_FORBIDDEN_KEYS / _forbid_auto_promote.
    if gates.get("field_ops_allow_ml_live_in_fusion") is True:
        fails.append("gates_field_ops_fusion_on_forbidden")
    rail = gates.get("product_rail")
    if rail is not None and str(rail) not in ALLOWED_PRODUCT_RAILS:
        fails.append(f"gates_product_rail_not_lab:{rail}")
    if gates.get("iou_is_not_ros") is False:
        fails.append("gates_iou_is_not_ros_false")
    return fails


def _validate_claim_surface(cs: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    fails.extend(_ros_leak_fails(cs, where="claim_surface"))
    for k in cs:
        if (
            k not in CLAIM_SURFACE_ALLOWED_KEYS
            and k not in AUTO_PROMOTE_FORBIDDEN_KEYS
            and k not in ROS_FORBIDDEN_KEYS
            and not str(k).startswith("ros_")
        ):
            fails.append(f"unknown_claim_surface_key:{k}")
    if cs.get("not_ros") is False or cs.get("iou_is_not_ros") is False:
        fails.append("claim_surface_ros_claim_forbidden")
    if cs.get("not_field_ops") is False:
        fails.append("claim_surface_field_ops_claim_forbidden")
    rail = cs.get("product_rail")
    if rail is not None and str(rail) not in ALLOWED_PRODUCT_RAILS:
        fails.append(f"claim_surface_product_rail_not_lab:{rail}")
    return fails


def _forbid_auto_promote(doc: dict[str, Any]) -> list[str]:
    """Scan top-level and known nested blocks for thrash / auto-promote hooks."""
    fails: list[str] = []
    blocks: list[tuple[str, Any]] = [("", doc)]
    for name in ("gates", "surface", "multi_fire", "claim_surface", "provenance", "rails"):
        b = doc.get(name)
        if isinstance(b, dict):
            blocks.append((f"{name}.", b))
    for prefix, block in blocks:
        if not isinstance(block, dict):
            continue
        for k in AUTO_PROMOTE_FORBIDDEN_KEYS:
            if k not in block:
                continue
            val = block[k]
            # Presence of thrash key as True (or non-false) is forbidden
            if val is True or (val not in (False, None, 0, "false", "False")):
                fails.append(f"forbidden_auto_promote:{prefix}{k}")
        # Explicit ml_product_go=true is human-promoted lab GO (allowed).
        # Field fusion ON is never allowed on this schema path.
        if prefix == "" and block.get("field_ops_allow_ml_live_in_fusion") is True:
            fails.append("forbidden_auto_promote:field_ops_allow_ml_live_in_fusion")
    return fails


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

    # Dual-product product rail (optional top-level)
    rail = doc.get("product_rail") or doc.get("product_surface")
    if rail is not None and str(rail) not in ALLOWED_PRODUCT_RAILS:
        fails.append(f"product_rail_not_lab:{rail}")

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
            fails.extend(_ros_leak_fails(unc, where="uncertainty"))
            for k in unc:
                if k not in UNCERTAINTY_ALLOWED_KEYS:
                    if k in ROS_FORBIDDEN_KEYS or str(k).startswith("ros_"):
                        continue  # already reported
                    fails.append(f"unknown_uncertainty_key:{k}")

    # Unified reject/rank surface (optional; when present must be VAL-thr / freeze-safe)
    surface = doc.get("surface") or doc.get("reject_rank_surface")
    if surface is not None:
        if not isinstance(surface, dict):
            fails.append("surface_not_object")
        else:
            fails.extend(_validate_surface(surface))

    # product_facade rank_reject block (shared thr + ranking protocol)
    rank_reject = doc.get("rank_reject")
    if rank_reject is not None:
        if not isinstance(rank_reject, dict):
            fails.append("rank_reject_not_object")
        else:
            fails.extend(_validate_rank_reject(rank_reject))

    multi_fire = doc.get("multi_fire") or doc.get("multi_fire_honesty")
    if multi_fire is not None:
        if not isinstance(multi_fire, dict):
            fails.append("multi_fire_not_object")
        else:
            fails.extend(_validate_multi_fire(multi_fire))

    gates = doc.get("gates")
    if gates is not None:
        if not isinstance(gates, dict):
            fails.append("gates_not_object")
        else:
            fails.extend(_validate_gates(gates))

    claim = doc.get("claim_surface")
    if claim is not None:
        if not isinstance(claim, dict):
            fails.append("claim_surface_not_object")
        else:
            fails.extend(_validate_claim_surface(claim))

    fails.extend(
        validate_scorecard_tuning(
            doc.get("tuning") if isinstance(doc.get("tuning"), dict) else None
        )
    )
    fails.extend(_forbid_auto_promote(doc))

    # Facade-built scorecards: enforce iter1 surface, VAL thr, refuse ROS/fusion ON
    if is_facade_built_scorecard(doc):
        fails.extend(_validate_facade_gates(doc))
    return fails


def scorecard_gates_pass(doc: dict[str, Any]) -> dict[str, Any]:
    fails = validate_ml_scorecard(doc)
    return {
        "pass": len(fails) == 0,
        "fails": fails,
        "product_id": doc.get("product_id") if isinstance(doc, dict) else None,
    }
