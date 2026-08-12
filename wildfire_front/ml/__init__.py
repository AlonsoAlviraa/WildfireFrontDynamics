# Módulo de Machine Learning para Wildfire Front Dynamics
#
# Product ROI surface (clm_ensemble_v34 lab ML rail):
#   features -> calibrator conf -> rank/reject (VAL thr; freeze iter1 reject) -> scorecard
# Dual rails: lab ML vs field_ops (IoU != ROS; field fusion OFF;
#   ml_product_go promoted true / human authorize 2026-08-05; no silent auto-flip).
# assert_no_ml_product_go_auto_flip refuses auto thrash only; explicit promote true is allowed.
# Lab scripts and cli_ml should import facade / rank_reject_protocol / protocol_rails
# entrypoints from here -- do not reimplement conf or VAL thr selection.

from typing import TYPE_CHECKING, Any

# -- Product facade + shared protocol entrypoints (no torch required) ----------
from .product_facade import (
    ClmEnsembleV34Facade,
    DEAD_PATHS,
    DEFAULT_PRODUCT_ID,
    DEFAULT_PROTOCOL,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    MultiFireHonesty,
    OPS_PRODUCT_ID,
    ProductFacadeError,
    ProductRails,
    RECOMMENDED_LAB_SURFACE,
    RankRejectConfig,
    apply_thr_reject,
    assert_lab_rails,
    build_scorecard,
    confidence_from_diag,
    confidences_from_head_a,
    default_facade_from_repo,
    features_from_diag,
    fire_honesty_tag,
    head_a_feature_names,
    rank_and_reject,
    ranking_scores,
    refuse_dead_path,
    selective_rank_metrics,
    stack_head_a_features,
)
from .rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    DEFAULT_LAB_SURFACE,
    DEFAULT_REJECT_THR,
    LAB_RAILS,
    LOCKED_ITER1_THR,
    apply_reject_thr_metrics,
    aurc_from_curve,
    conf_from_features,
    default_val_thr_grid,
    frozen_thr_from_val_selection,
    lab_rails,
    rank_reject_val_then_test,
    refuse_dead_protocol_path,
    score_ranking,
    select_thr_val_only,
)
from .protocol_rails import (
    DualProductRails,
    RankAbstainProtocol,
    assert_field_fusion_off,
    assert_no_ml_product_go_auto_flip,
    assert_not_forbidden_thrash,
    assert_split_role,
    default_dual_product_rails,
    default_rank_abstain_protocol,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)

# -- Torch-optional training / dataset (legacy package surface) ----------------
if TYPE_CHECKING:
    from .dataset import NpzWildfireDataset as NpzWildfireDataset
    from .dataset import WildfireDataset as WildfireDataset
    from .train import fine_tune_model as fine_tune_model
else:
    try:
        from .dataset import NpzWildfireDataset, WildfireDataset
        from .train import fine_tune_model
    except ModuleNotFoundError as exc:
        if exc.name != "torch":
            raise
        WildfireDataset: Any = None
        NpzWildfireDataset: Any = None
        fine_tune_model: Any = None

__all__ = [
    # Product facade (clm_ensemble_v34)
    "ClmEnsembleV34Facade",
    "DEAD_PATHS",
    "DEFAULT_PRODUCT_ID",
    "DEFAULT_PROTOCOL",
    "DEFAULT_RAILS",
    "DEFAULT_RANK_REJECT",
    "ITER1_LOCKED_REJECT_THR",
    "MultiFireHonesty",
    "OPS_PRODUCT_ID",
    "ProductFacadeError",
    "ProductRails",
    "RECOMMENDED_LAB_SURFACE",
    "RankRejectConfig",
    "apply_thr_reject",
    "assert_lab_rails",
    "build_scorecard",
    "confidence_from_diag",
    "confidences_from_head_a",
    "default_facade_from_repo",
    "features_from_diag",
    "fire_honesty_tag",
    "head_a_feature_names",
    "rank_and_reject",
    "ranking_scores",
    "refuse_dead_path",
    "selective_rank_metrics",
    "stack_head_a_features",
    # Rank/reject protocol (features -> conf -> VAL thr -> scorecard)
    "DEAD_PROTOCOL_PATHS",
    "DEFAULT_LAB_SURFACE",
    "DEFAULT_REJECT_THR",
    "LAB_RAILS",
    "LOCKED_ITER1_THR",
    "apply_reject_thr_metrics",
    "aurc_from_curve",
    "conf_from_features",
    "default_val_thr_grid",
    "frozen_thr_from_val_selection",
    "lab_rails",
    "rank_reject_val_then_test",
    "refuse_dead_protocol_path",
    "score_ranking",
    "select_thr_val_only",
    # Shared dual-product / rank-abstain protocol rails
    "DualProductRails",
    "RankAbstainProtocol",
    "assert_field_fusion_off",
    "assert_no_ml_product_go_auto_flip",
    "assert_not_forbidden_thrash",
    "assert_split_role",
    "default_dual_product_rails",
    "default_rank_abstain_protocol",
    "dual_product_rails_dict",
    "multi_fire_honesty_dict",
    "rank_abstain_protocol_dict",
    # Legacy training surface
    "WildfireDataset",
    "NpzWildfireDataset",
    "fine_tune_model",
]
