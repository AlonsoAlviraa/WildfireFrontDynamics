"""Protocol integrity rails for CLM holdout / VAL-only tuning (ML focus v1).

Hard rule: mix/temperature/uncertainty/reject-threshold fitting only on VAL
(or train for train). Test / LOFO / external may report and gate, never tune.

Dual-product rails (lab ML vs field_ops):
  · lab product · not field_ops fusion · IoU ≠ ROS
  · ml_product_go never auto-flips (human promote only)
  · field_ops.allow_ml_live_in_fusion stays OFF unless human promote
  · ranking + abstain share one VAL-only thr protocol; freeze iter1 reject default

Product path (single pipeline — no parallel thrash)
----------------------------------------------------
``product_facade`` + this module share one integrity surface:

    features → calibrator → rank/reject (VAL thr; freeze iter1) → scorecard

``DualProductRails`` / ``rank_abstain_protocol_dict`` are the integrity-layer
payloads; keys align with ``ProductRails`` / ``RankRejectConfig`` /
``ClmEnsembleV34Facade`` so scripts do not re-encode thr or dual-rail logic.
``DEAD_PATHS`` here is the unified dead thrash set (protocol + facade aliases).
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Final, Literal

SplitName = Literal["train", "val", "test", "lofo", "external"]
ActionName = Literal[
    "train",
    "fit",
    "optimize",
    "select",
    "calibrate",
    "tune_mix",
    "tune_temperature",
    "tune_threshold",
    "tune_reject",
    "fit_uncertainty",
    "report",
    "scorecard",
    "gate",
    "stress",
    "rank",
    "abstain",
]
ProductRailName = Literal["lab_ml", "field_ops"]

ALLOWED_ACTIONS: Final[dict[str, frozenset[str]]] = {
    "train": frozenset({"train", "fit", "optimize"}),
    "val": frozenset(
        {
            "select",
            "calibrate",
            "tune_mix",
            "tune_temperature",
            "tune_threshold",
            "tune_reject",
            "fit_uncertainty",
            "report",
            "scorecard",
            "gate",
            "rank",
            "abstain",
        }
    ),
    "test": frozenset({"report", "scorecard", "gate", "rank", "abstain"}),
    "lofo": frozenset({"report", "stress", "scorecard", "gate", "rank", "abstain"}),
    # W3 / multi-fire external fires: evaluate only, never fit thr/ECE
    "external": frozenset({"report", "stress", "scorecard", "gate", "rank", "abstain"}),
}

# Actions that must never run on test/lofo/external
TUNE_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "tune_mix",
        "tune_temperature",
        "tune_threshold",
        "tune_reject",
        "calibrate",
        "fit_uncertainty",
        "select",
        "train",
        "fit",
        "optimize",
    }
)

# Rank + abstain share one thr selection protocol: VAL only
THR_TUNE_ACTIONS: Final[frozenset[str]] = frozenset(
    {"tune_threshold", "tune_reject", "select", "calibrate"}
)

DEFAULT_PROTOCOL: Final = "clm_holdout_test_seed42_v1"
DEFAULT_PRODUCT_ID: Final = "clm_ensemble_v34"
OPS_PRODUCT_ID: Final = "front_dynamics_v1"
PRODUCT_RAIL: Final[ProductRailName] = "lab_ml"
OPS_RAIL: Final[ProductRailName] = "field_ops"
LAB_ML_BANNER: Final = "lab product · not field_ops fusion · IoU ≠ ROS"
PRODUCT_FACADE_MODULE: Final = "wildfire_front.ml.product_facade"
PIPELINE_FEATURES_TO_SCORECARD: Final = "features→calibrator→rank/reject→scorecard"

# ── Dual-product rails (canonical defaults; never auto-flip) ───────────────
# Human promote authorized 2026-08-05: lab ml_product_go True (≠ field fusion).
ML_PRODUCT_GO_DEFAULT: Final = True
FIELD_OPS_ALLOW_ML_LIVE_IN_FUSION_DEFAULT: Final = False
FIELD_OPS_ML_LIVE_FUSION_DEFAULT: Final = "OFF"
IOU_IS_NOT_ROS: Final = True
RECOMMENDED_LAB_SURFACE_DEFAULT: Final = "iter1_reject_only"
STOP_ECE_THRASH_ON_SAME_TEST: Final = True
# Freeze-iter1 reject thr (VAL-selected; apply frozen on test/lofo/external)
# Aligns with product_facade.ITER1_LOCKED_REJECT_THR / RankRejectConfig.reject_thr
LOCKED_REJECT_THR_DEFAULT: Final = 0.795
THR_TUNE_SPLIT: Final = "val"
CATALOG_HOLDOUT_IOU_PROVENANCE_ONLY: Final = 0.8963
# RankRejectConfig-aligned knobs (shared with ClmEnsembleV34Facade rank/reject)
DEFAULT_RANK_SCORE_NAME: Final = "logistic_conf"
DEFAULT_SELECTIVE_COVERAGE: Final = 0.8

# Unified dead thrash / reopen paths (protocol + product_facade aliases).
# Do not re-enable as promote paths. product_facade.DEAD_PATHS is a subset;
# scripts may union both — this set is the integrity-layer superset.
FORBIDDEN_THRASH_PATHS: Final[frozenset[str]] = frozenset(
    {
        # ECE / same-holdout thrash
        "same_holdout_ece_retune",
        "ece_posthoc_same_test",
        "logistic_refit_same_test",
        # Tobarra KEEP re-promote of KILL weights (all name aliases)
        "tobarra_keep_reopen_kill_weights",
        "tobarra_keep_same_recipe",
        "tobarra_keep_reopen_same_recipe",
        # Promote / fusion auto-flip (protocol + facade aliases)
        "ml_product_go_auto_flip",
        "auto_ml_product_go",
        "field_ops_fusion_auto_on",
        "field_ops_ml_live_fusion_on",
        # Surface honesty
        "sdc_auto_promote_over_iter1",
        "claim_iou_as_ros",
        "catalog_0_8963_as_live_certainty",
        # PR11: larger backbone as default field product / fusion unlock
        "larger_unet_as_field_product",
        "swin_segformer_default_field_bet",
        "lab_larger_unet_field_fusion",
    }
)
# Alias for product_facade consumers at the integrity layer (single dead set).
DEAD_PATHS: Final[frozenset[str]] = FORBIDDEN_THRASH_PATHS

# PR11 lab track — larger U-Net / ViT is never the default bet (docs/design/LAB_UNET_SCALE_KILL_CRITERIA.md).
# Zero field fusion path from this flag; optional research only under LOFO/NDWS kill criteria.
LAB_LARGER_UNET_DEFAULT_BET: Final = False
LAB_LARGER_UNET_FIELD_FUSION_PATH: Final = False
LAB_UNET_SCALE_KILL_DOC: Final = "docs/design/LAB_UNET_SCALE_KILL_CRITERIA.md"

# Multi-fire honesty first-class (LOFO / W3; not ad-hoc script knowledge).
# Nested keys include both protocol (verdict/class) and product_facade
# MultiFireHonesty (fire_id / keep_verdict / reopen_same_recipe) shapes.
TOBARRA_FIRE_ID: Final = "tobarra_20240802"
W3_EXTERNAL_FIRES: Final[tuple[str, ...]] = (
    "hellin_2024",
    "brazatortas_2025",
    "retuerta_2025",
)
MULTI_FIRE_HONESTY: Final[dict[str, Any]] = {
    "tobarra": {
        "fire_id": TOBARRA_FIRE_ID,
        "class": "hard",
        "role": "hard_transfer",
        "verdict": "KILL",
        "keep_verdict": "KILL",
        "reopen_same_recipe": False,
        "note": "fresh LOFO KEEP-or-KILL → KILL; do not reopen same recipe",
        "do_not": "tobarra_keep_reopen_kill_weights",
    },
    "w3_external": {
        "role": "external_stress",
        "facade_role": "external_probe",
        "fires": W3_EXTERNAL_FIRES,
        "split": "external",
        "frozen_thr_and_cal": True,
        "note": "report-only; thr/cal frozen from VAL; never fit on external",
    },
    "cardoso_lofo": {
        "note": "≈U1 holdout family — not independent multi-fire generalization",
    },
    "cardoso_lofo_note": (
        "CARDOSO LOFO ≈ U1 holdout family — not independent multi-fire generalization"
    ),
    "iou_is_not_ros": True,
    "protocol": {
        "thr_tune_split": THR_TUNE_SPLIT,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE_DEFAULT,
        "locked_reject_thr": LOCKED_REJECT_THR_DEFAULT,
        "stop_ece_thrash_on_same_test": STOP_ECE_THRASH_ON_SAME_TEST,
        "pipeline": PIPELINE_FEATURES_TO_SCORECARD,
        "product_facade": PRODUCT_FACADE_MODULE,
    },
}

# Forbidden keys in ML primary scorecard (ops ROS leakage)
ROS_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "primary_ros_m_min",
        "ros_area_m_min",
        "ros_equiv_radius_m_min",
        "vp_tactical",
        "ros_m_min",
    }
)


@dataclass(frozen=True)
class SplitContext:
    split: SplitName
    action: ActionName
    protocol: str = DEFAULT_PROTOCOL

    def __post_init__(self) -> None:
        if self.split not in ALLOWED_ACTIONS:
            raise ValueError(f"unknown split {self.split!r}")


@dataclass(frozen=True)
class DualProductRails:
    """Canonical dual-product honesty rails for lab ML vs field_ops.

    Integrity-layer twin of ``product_facade.ProductRails``. Defaults freeze
    lab surface at iter1 reject; field fusion OFF; ``ml_product_go`` is
    human-promoted True (lab GO; never silent auto-flip). Rank and abstain
    consumers should share :func:`rank_abstain_protocol_dict` (aligned with
    ``RankRejectConfig``) rather than re-encode thr logic.
    """

    product_id: str = DEFAULT_PRODUCT_ID
    ops_product_id: str = OPS_PRODUCT_ID
    product_rail: str = PRODUCT_RAIL
    ops_rail: str = OPS_RAIL
    banner: str = LAB_ML_BANNER
    ml_product_go: bool = ML_PRODUCT_GO_DEFAULT
    field_ops_allow_ml_live_in_fusion: bool = FIELD_OPS_ALLOW_ML_LIVE_IN_FUSION_DEFAULT
    field_ops_ml_live_fusion: str = FIELD_OPS_ML_LIVE_FUSION_DEFAULT
    iou_is_not_ros: bool = IOU_IS_NOT_ROS
    recommended_lab_surface: str = RECOMMENDED_LAB_SURFACE_DEFAULT
    stop_ece_thrash_on_same_test: bool = STOP_ECE_THRASH_ON_SAME_TEST
    thr_tune_split: str = THR_TUNE_SPLIT
    locked_reject_thr: float = LOCKED_REJECT_THR_DEFAULT
    # Provenance IoU value (float); as_dict also emits ProductRails bool flag.
    catalog_holdout_iou_value: float = CATALOG_HOLDOUT_IOU_PROVENANCE_ONLY
    catalog_holdout_iou_provenance_only: bool = True
    # Multi-fire honesty tags (first-class, not ad-hoc)
    multi_fire_tobarra_class: str = "hard"
    multi_fire_tobarra_verdict: str = "KILL"
    multi_fire_w3_external: bool = True
    field_fusion_off: bool = True
    tobarra_keep_reopen_forbidden: bool = True
    val_only_threshold_selection: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Dict aligned with ``product_facade.ProductRails.as_dict`` + integrity tags."""
        d = asdict(self)
        d["field_ops_ml_live_fusion"] = (
            "OFF" if not self.field_ops_allow_ml_live_in_fusion else "ON"
        )
        d["field_fusion_off"] = not bool(self.field_ops_allow_ml_live_in_fusion)
        d["val_only_threshold_selection"] = bool(
            self.val_only_threshold_selection and str(self.thr_tune_split) == THR_TUNE_SPLIT
        )
        d["tobarra_keep_reopen_forbidden"] = True
        d["catalog_holdout_iou_provenance_only"] = True
        d["dead_paths"] = sorted(DEAD_PATHS)
        d["pipeline"] = PIPELINE_FEATURES_TO_SCORECARD
        d["product_facade"] = PRODUCT_FACADE_MODULE
        # Backward-compat: older callers read float under the provenance key.
        d["catalog_holdout_iou_provenance_value"] = float(self.catalog_holdout_iou_value)
        return d


@dataclass(frozen=True)
class RankAbstainProtocol:
    """Shared ranking + abstain (reject) surface protocol.

    Integrity-layer twin of ``product_facade.RankRejectConfig`` (+ dual-rail
    freeze flags). Threshold selection is VAL-only. Default freeze surface is
    iter1 reject. TEST / LOFO / external apply frozen thr only
    (report/rank/abstain). Consumed by Head A / LOFO / selective-SDC /
    ``ClmEnsembleV34Facade`` path — not a second conf implementation.
    """

    thr_tune_split: str = THR_TUNE_SPLIT
    locked_reject_thr: float = LOCKED_REJECT_THR_DEFAULT
    recommended_lab_surface: str = RECOMMENDED_LAB_SURFACE_DEFAULT
    freeze_iter1_reject: bool = True
    stop_ece_thrash_on_same_test: bool = STOP_ECE_THRASH_ON_SAME_TEST
    product_id: str = DEFAULT_PRODUCT_ID
    protocol: str = DEFAULT_PROTOCOL
    # Shared with dual-product rails — never claim field promote from rank path
    ml_product_go: bool = ML_PRODUCT_GO_DEFAULT
    field_ops_allow_ml_live_in_fusion: bool = FIELD_OPS_ALLOW_ML_LIVE_IN_FUSION_DEFAULT
    # RankRejectConfig-aligned aliases (same thr + surface; ranking ≠ thr view)
    reject_thr: float = LOCKED_REJECT_THR_DEFAULT
    surface: str = RECOMMENDED_LAB_SURFACE_DEFAULT
    rank_score_name: str = DEFAULT_RANK_SCORE_NAME
    selective_coverage: float = DEFAULT_SELECTIVE_COVERAGE

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Keep thr/surface aliases in lockstep (RankRejectConfig + integrity keys).
        thr = float(d.get("locked_reject_thr", LOCKED_REJECT_THR_DEFAULT))
        surface = str(d.get("recommended_lab_surface", RECOMMENDED_LAB_SURFACE_DEFAULT))
        d["locked_reject_thr"] = thr
        d["reject_thr"] = thr
        d["recommended_lab_surface"] = surface
        d["surface"] = surface
        d["freeze_iter1_reject"] = surface == RECOMMENDED_LAB_SURFACE_DEFAULT
        d["pipeline"] = PIPELINE_FEATURES_TO_SCORECARD
        d["product_facade"] = PRODUCT_FACADE_MODULE
        d["note"] = (
            "thr_reject and selective_rank share confidences; "
            "ranking curve ≠ thr reject operating point"
        )
        return d

    def to_rank_reject_config_dict(self) -> dict[str, Any]:
        """Payload matching ``product_facade.RankRejectConfig.as_dict``."""
        thr = float(self.locked_reject_thr)
        surface = str(self.recommended_lab_surface)
        return {
            "reject_thr": thr,
            "rank_score_name": self.rank_score_name,
            "selective_coverage": float(self.selective_coverage),
            "surface": surface,
            "note": (
                "thr_reject and selective_rank share confidences; "
                "ranking curve ≠ thr reject operating point"
            ),
        }


class ProtocolRailError(ValueError):
    """Raised when an action is not allowed on a split."""


def default_dual_product_rails() -> DualProductRails:
    """Frozen dual-product defaults (lab ML GO promoted; field fusion OFF)."""
    return DualProductRails()


def dual_product_rails_dict(
    *,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Dict form of dual-product rails for scorecards / CLI / lab modules.

    Shape aligns with ``product_facade.ProductRails.as_dict`` (plus integrity
    tags). ``ml_product_go`` follows product default / overrides (human-promoted
    True allowed). Field fusion keys remain clamped OFF (lab GO ≠ field fusion).
    Call :func:`assert_rails_honest` for a hard raise on untrusted payloads.
    """
    base = default_dual_product_rails().as_dict()
    if overrides:
        base.update(dict(overrides))
    # Clamp field fusion OFF only — ml_product_go is not re-clamped to false
    # (human promote authorized; still refuse auto_* thrash via DEAD_PATHS).
    base["field_ops_allow_ml_live_in_fusion"] = False
    base["field_ops_ml_live_fusion"] = "OFF"
    base["field_fusion_off"] = True
    base["iou_is_not_ros"] = True
    base["tobarra_keep_reopen_forbidden"] = True
    if base.get("locked_reject_thr") is None:
        base["locked_reject_thr"] = LOCKED_REJECT_THR_DEFAULT
    return base


def default_rank_abstain_protocol() -> RankAbstainProtocol:
    """VAL-only thr + freeze-iter1-reject shared protocol for rank and abstain."""
    return RankAbstainProtocol()


def rank_abstain_protocol_dict(
    *,
    locked_reject_thr: float | None = None,
    recommended_lab_surface: str | None = None,
    rank_score_name: str | None = None,
    selective_coverage: float | None = None,
) -> dict[str, Any]:
    """Shared protocol payload for Head A / LOFO / selective-SDC / reject surface.

    Unified with ``product_facade.RankRejectConfig`` / ``ClmEnsembleV34Facade``:
    emits both integrity keys (``locked_reject_thr``, ``recommended_lab_surface``)
    and RankRejectConfig keys (``reject_thr``, ``surface``, ``rank_score_name``,
    ``selective_coverage``) plus the single pipeline pointer.
    """
    thr = float(locked_reject_thr) if locked_reject_thr is not None else LOCKED_REJECT_THR_DEFAULT
    surface = (
        str(recommended_lab_surface)
        if recommended_lab_surface is not None
        else RECOMMENDED_LAB_SURFACE_DEFAULT
    )
    score_name = str(rank_score_name) if rank_score_name is not None else DEFAULT_RANK_SCORE_NAME
    cov = (
        float(selective_coverage) if selective_coverage is not None else DEFAULT_SELECTIVE_COVERAGE
    )
    proto = RankAbstainProtocol(
        locked_reject_thr=thr,
        recommended_lab_surface=surface,
        freeze_iter1_reject=(surface == RECOMMENDED_LAB_SURFACE_DEFAULT),
        reject_thr=thr,
        surface=surface,
        rank_score_name=score_name,
        selective_coverage=cov,
    )
    d = proto.as_dict()
    d["rank_reject_config"] = proto.to_rank_reject_config_dict()
    return d


def assert_split_role(split: str, action: str) -> None:
    """Raise ProtocolRailError if action is not allowed on split."""
    allowed = ALLOWED_ACTIONS.get(str(split))
    if allowed is None:
        raise ProtocolRailError(f"unknown split {split!r}")
    if str(action) not in allowed:
        raise ProtocolRailError(
            f"action {action!r} not allowed on split {split!r}; allowed={sorted(allowed)}"
        )
    if str(action) in TUNE_ACTIONS and str(split) in ("test", "lofo", "external"):
        raise ProtocolRailError(
            f"refusing tune/calibrate action {action!r} on {split!r} (VAL-only protocol integrity)"
        )


def assert_split_context(ctx: SplitContext) -> None:
    assert_split_role(ctx.split, ctx.action)


def assert_thr_tune_split(split: str, action: str = "tune_threshold") -> None:
    """Reject-threshold / rank thr selection is VAL-only (shared rank+abstain)."""
    if str(split) != THR_TUNE_SPLIT:
        raise ProtocolRailError(
            f"reject thr selection action {action!r} requires split={THR_TUNE_SPLIT!r}, got {split!r}"
        )
    assert_split_role(
        str(split), str(action) if str(action) in THR_TUNE_ACTIONS else "tune_threshold"
    )


def assert_no_ml_product_go_auto_flip(ml_product_go: bool) -> None:
    """Human-promoted ``ml_product_go`` may be true; silent auto_* thrash is forbidden.

    Explicit lab GO (owner directive 2026-08-05) is allowed. Silent thrash
    paths ``auto_ml_product_go`` / ``ml_product_go_auto_flip`` remain in
    :data:`DEAD_PATHS` and are refused by :func:`assert_not_forbidden_thrash`.
    Field fusion stays a separate rail (still OFF).
    """
    # Promoted true is honest; do not refuse explicit go. Auto thrash is
    # path-based (DEAD_PATHS), not value-based on this flag.
    _ = bool(ml_product_go)


def assert_field_fusion_off(
    *,
    allow_ml_live_in_fusion: bool = False,
    field_ops_ml_live_fusion: str | None = None,
) -> None:
    """field_ops ML live fusion must remain OFF under default product rails."""
    if bool(allow_ml_live_in_fusion):
        raise ProtocolRailError(
            "field_ops.allow_ml_live_in_fusion=True forbidden without human promote "
            "(dual-product rails: fusion OFF)"
        )
    if field_ops_ml_live_fusion is not None and str(field_ops_ml_live_fusion).upper() == "ON":
        raise ProtocolRailError(
            "field_ops_ml_live_fusion=ON forbidden without human promote (fusion OFF)"
        )


def assert_not_forbidden_thrash(path: str) -> None:
    """Refuse dead thrash / reopen paths (ECE same-holdout, Tobarra KEEP reopen, …)."""
    key = str(path).strip().lower().replace("-", "_").replace(" ", "_")
    if key in DEAD_PATHS or key in FORBIDDEN_THRASH_PATHS:
        raise ProtocolRailError(
            f"forbidden thrash path {path!r} (protocol rails: stop ECE thrash / "
            "no Tobarra KEEP reopen of KILL weights / no go-auto-flip)"
        )


def assert_rails_honest(
    rails: Mapping[str, Any] | DualProductRails | None = None,
    *,
    require_iter1_reject_default: bool = True,
) -> None:
    """Validate a rails payload against dual-product + freeze-iter1 defaults."""
    if rails is None:
        rails = default_dual_product_rails().as_dict()
    elif isinstance(rails, DualProductRails):
        rails = rails.as_dict()
    assert_no_ml_product_go_auto_flip(bool(rails.get("ml_product_go", ML_PRODUCT_GO_DEFAULT)))
    assert_field_fusion_off(
        allow_ml_live_in_fusion=bool(rails.get("field_ops_allow_ml_live_in_fusion", False)),
        field_ops_ml_live_fusion=(
            str(rails["field_ops_ml_live_fusion"])
            if rails.get("field_ops_ml_live_fusion") is not None
            else None
        ),
    )
    if rails.get("iou_is_not_ros") is False:
        raise ProtocolRailError("iou_is_not_ros must be True (IoU ≠ ROS)")
    thr_split = rails.get("thr_tune_split", THR_TUNE_SPLIT)
    # ProductRails uses val_only_threshold_selection bool; accept that path.
    if (
        thr_split is not None
        and str(thr_split) != THR_TUNE_SPLIT
        and rails.get("val_only_threshold_selection") is not True
    ):
        raise ProtocolRailError(f"thr_tune_split must be {THR_TUNE_SPLIT!r}, got {thr_split!r}")
    if require_iter1_reject_default:
        surface = rails.get("recommended_lab_surface", RECOMMENDED_LAB_SURFACE_DEFAULT)
        if surface is None:
            surface = rails.get("surface", RECOMMENDED_LAB_SURFACE_DEFAULT)
        if surface is not None and str(surface) != RECOMMENDED_LAB_SURFACE_DEFAULT:
            # Non-default surfaces (e.g. selective-SDC KEEP) are allowed only when
            # explicitly not requiring freeze-iter1 default; callers pass False.
            raise ProtocolRailError(
                f"recommended_lab_surface default freeze is {RECOMMENDED_LAB_SURFACE_DEFAULT!r}, "
                f"got {surface!r}"
            )


def reject_ros_keys_in_primary(primary: dict) -> None:
    """Fail if primary metrics contain ops ROS keys (dual-product honesty)."""
    if not isinstance(primary, dict):
        return
    bad: set[str] = set(ROS_FORBIDDEN_KEYS.intersection(primary.keys()))
    # also scan one level of nested dicts
    for k, v in primary.items():
        if isinstance(v, dict):
            bad |= set(ROS_FORBIDDEN_KEYS.intersection(v.keys()))
        if k in ROS_FORBIDDEN_KEYS:
            bad.add(k)
    if bad:
        raise ProtocolRailError(f"ROS/ops keys forbidden in ML primary scorecard: {sorted(bad)}")


def validate_scorecard_tuning(tuning: dict | None) -> list[str]:
    """Return gate failure reasons; empty list = pass.

    Requires mix/temperature/uncertainty (and optional reject thr) fit on VAL.
    """
    fails: list[str] = []
    if not tuning:
        fails.append("missing_tuning_block")
        return fails
    for key in ("mix_split", "temperature_split", "uncertainty_calibration_split"):
        val = tuning.get(key)
        if val is None:
            fails.append(f"missing_{key}")
        elif str(val) != "val":
            fails.append(f"{key}_not_val:{val}")
    # Optional but if present must be VAL-only (shared rank+abstain thr protocol)
    for key in ("reject_threshold_split", "thr_split", "reject_thr_split"):
        if key in tuning and tuning.get(key) is not None and str(tuning[key]) != "val":
            fails.append(f"{key}_not_val:{tuning[key]}")
    return fails


def validate_rank_abstain_tuning(tuning: dict | None) -> list[str]:
    """VAL-only thr protocol for ranking and abstain/reject surfaces."""
    fails = validate_scorecard_tuning(tuning)
    if not tuning:
        return fails
    # Prefer explicit thr split key when present; else thr must not claim test/lofo
    thr_keys = ("reject_threshold_split", "thr_split", "reject_thr_split")
    if not any(k in tuning for k in thr_keys):
        # Allow missing optional thr keys when full scorecard tuning already checked
        pass
    surface = tuning.get("recommended_lab_surface", tuning.get("surface"))
    if surface is not None and str(surface) not in (
        RECOMMENDED_LAB_SURFACE_DEFAULT,
        "soft_dice_proxy_ranking",
        "iter1_reject_only",
    ):
        fails.append(f"unknown_lab_surface:{surface}")
    return fails


def multi_fire_honesty_dict() -> dict[str, Any]:
    """First-class multi-fire honesty block (Tobarra hard, W3 external, LOFO/W3).

    Deep copy so callers can annotate without mutating the module constant.
    Nested shape is compatible with both protocol consumers (``verdict``/``class``)
    and ``product_facade.MultiFireHonesty.as_dict`` (``keep_verdict``/``fire_id``).
    """
    return deepcopy(MULTI_FIRE_HONESTY)
