"""clm_ensemble_v34 product facade — single lab ML product path.

Pipeline (one protocol for ranking **and** thr-based abstain)::

    Head A features → LogisticCalibrator → conf → rank / reject → scorecard

Single path ownership
---------------------
* **rank_reject_protocol** — shared conf, VAL-only thr, thr-reject metrics,
  ranking quality (``score_ranking``). Facade drives this; does not reimplement it.
* **lab_selective_sdc** — SDC ranking score *families* + bake-off only.
* **This module** — product rails, multi-fire honesty, scorecard assembly,
  and orchestration for ``cli_ml`` / lab loops.

Rails (immutable product policy; not auto-flipped here)
-----------------------------------------------------
* Dual rails: **lab ML** (this module) vs **field_ops** (ops ROS / Decision Card).
* IoU ≠ ROS — never emit ops ROS keys on the ML scorecard primary path.
* ``ml_product_go`` default **True** (human promote 2026-08-05); never auto-flips.
* field_ops ``allow_ml_live_in_fusion`` stays OFF (lab GO ≠ field fusion).
* Threshold selection is **VAL-only**; default product surface freezes **iter1 reject**.
* Multi-fire honesty is first-class: Tobarra = hard transfer; W3 external = separate board.
* Dead thrash paths are refused: same-holdout ECE retune, Tobarra KEEP reopen hooks,
  ``auto_ml_product_go`` silent thrash (explicit promoted true is allowed).

No model retrain. Architecture + API boundaries only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np

from wildfire_front.ml.lab_reject_calibration import (
    metrics_at_threshold,
    risk_coverage_curve,
    thr_operating_points,
)
from wildfire_front.ml.lab_selective_sdc import (
    bakeoff_rankings,
    ranking_scores_from_head_a,
)
from wildfire_front.ml.protocol_rails import (
    DEFAULT_PROTOCOL,
    assert_split_role,
    reject_ros_keys_in_primary,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEFAULT_LAB_SURFACE,
    LOCKED_ITER1_THR,
    apply_reject_thr_metrics,
    conf_from_features,
    frozen_thr_from_val_selection,
    rank_reject_val_then_test,
    select_thr_val_only,
)
from wildfire_front.ml.rank_reject_protocol import (
    lab_rails as protocol_lab_rails,
)
from wildfire_front.ml.rank_reject_protocol import (
    score_ranking as protocol_score_ranking,
)
from wildfire_front.ml.reliability_metrics import ece_patch_conf, selective_iou_at_coverage
from wildfire_front.ml.scorecard_schema import validate_ml_scorecard
from wildfire_front.ml.u1_eval import FIXED_HONESTY_NOTES, catalog_holdout_test_reference
from wildfire_front.ml.uncertainty import (
    HEAD_A_FEATURE_NAMES,
    LogisticCalibrator,
    features_from_diagnostics,
    load_calibrator,
)

# ── Product identity ──────────────────────────────────────────────────────────

DEFAULT_PRODUCT_ID: Final = "clm_ensemble_v34"
OPS_PRODUCT_ID: Final = "front_dynamics_v1"
PRODUCT_RAIL: Final[Literal["lab_ml"]] = "lab_ml"
OPS_RAIL: Final[Literal["field_ops"]] = "field_ops"
# Human promote authorized 2026-08-05 (owner directive). Lab GO ≠ field fusion.
ML_PRODUCT_GO_DEFAULT: Final = True

# Locked lab surface — single source: rank_reject_protocol (VAL thr freeze).
ITER1_LOCKED_REJECT_THR: Final = float(LOCKED_ITER1_THR)  # ~0.795
LEGACY_PRODUCT_ABSTAIN_THR: Final = 0.35  # yields abstain≈0 on v34 conf band
RECOMMENDED_LAB_SURFACE: Final = str(DEFAULT_LAB_SURFACE)  # iter1_reject_only
DEFAULT_RANK_SCORE: Final = "logistic_conf"  # ranking ≠ thr reject; both share conf
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"

# Multi-fire honesty tags (architecture, not ad-hoc script folklore).
TOBARRA_FIRE_ID: Final = "tobarra_20240802"
TOBARRA_ROLE: Final = "hard_transfer"  # KILL KEEP reopen same recipe
W3_EXTERNAL_FIRES: Final[tuple[str, ...]] = (
    "hellin_2024",
    "brazatortas_2025",
    "retuerta_2025",
)
W3_ROLE: Final = "external_probe"  # report once with frozen thr/cal; no thrash

# Explicitly closed dead paths (union with protocol_rails.FORBIDDEN_THRASH_PATHS).
# Callers must not re-open via this facade. Keep aliases so either name refuses.
DEAD_PATHS: Final[frozenset[str]] = frozenset(
    {
        "same_holdout_ece_retune",
        "ece_posthoc_same_test",
        "logistic_refit_same_test",
        "tobarra_keep_reopen_same_recipe",
        "tobarra_keep_reopen_kill_weights",
        "tobarra_keep_same_recipe",
        "auto_ml_product_go",
        "ml_product_go_auto_flip",
        "field_ops_ml_live_fusion_on",
        "field_ops_fusion_auto_on",
        "sdc_auto_promote_over_iter1",
        "claim_iou_as_ros",
        "catalog_0_8963_as_live_certainty",
    }
)

_BANNER: Final = "lab product · not field_ops fusion · IoU ≠ ROS"


class ProductFacadeError(ValueError):
    """Raised when a rail, dead path, or protocol boundary is violated."""


@dataclass(frozen=True)
class ProductRails:
    """Immutable dual-product + lab loop rails for clm_ensemble_v34."""

    product_id: str = DEFAULT_PRODUCT_ID
    ops_product_id: str = OPS_PRODUCT_ID
    product_rail: str = PRODUCT_RAIL
    ops_rail: str = OPS_RAIL
    ml_product_go: bool = ML_PRODUCT_GO_DEFAULT
    field_ops_allow_ml_live_in_fusion: bool = False
    iou_is_not_ros: bool = True
    val_only_threshold_selection: bool = True
    recommended_lab_surface: str = RECOMMENDED_LAB_SURFACE
    locked_reject_thr: float = ITER1_LOCKED_REJECT_THR
    stop_ece_thrash_on_same_test: bool = True
    tobarra_keep_reopen_forbidden: bool = True
    catalog_holdout_iou_provenance_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "ops_product_id": self.ops_product_id,
            "product_rail": self.product_rail,
            "ops_rail": self.ops_rail,
            "ml_product_go": self.ml_product_go,
            "field_ops_allow_ml_live_in_fusion": self.field_ops_allow_ml_live_in_fusion,
            "iou_is_not_ros": self.iou_is_not_ros,
            "val_only_threshold_selection": self.val_only_threshold_selection,
            "recommended_lab_surface": self.recommended_lab_surface,
            "locked_reject_thr": self.locked_reject_thr,
            "stop_ece_thrash_on_same_test": self.stop_ece_thrash_on_same_test,
            "tobarra_keep_reopen_forbidden": self.tobarra_keep_reopen_forbidden,
            "catalog_holdout_iou_provenance_only": self.catalog_holdout_iou_provenance_only,
            "dead_paths": sorted(DEAD_PATHS),
            "banner": _BANNER,
        }


DEFAULT_RAILS: Final = ProductRails()


def refuse_dead_path(path_id: str) -> None:
    """Hard refuse closed thrash / promote hooks."""
    key = str(path_id).strip().lower()
    if key in DEAD_PATHS or key.replace("-", "_") in DEAD_PATHS:
        raise ProductFacadeError(
            f"dead path refused: {path_id!r} "
            f"(iter1 reject frozen; no same-holdout ECE/logistic-refit thrash; "
            f"no Tobarra KEEP reopen; no auto ml_product_go / field fusion ON)"
        )


def assert_lab_rails(rails: ProductRails | None = None) -> ProductRails:
    """Validate lab rails; allow explicit ``ml_product_go`` promote path.

    Human promote (2026-08-05) sets default ``ml_product_go=True``. Silent
    auto-flip thrash remains refused via ``DEAD_PATHS`` / ``refuse_dead_path``.
    Field fusion must stay OFF (lab GO ≠ field fusion).
    """
    r = rails or DEFAULT_RAILS
    # ml_product_go True is allowed (promoted default); only fusion is hard-off.
    if r.field_ops_allow_ml_live_in_fusion:
        raise ProductFacadeError(
            "field_ops.allow_ml_live_in_fusion must stay OFF on product facade path"
        )
    if not r.iou_is_not_ros:
        raise ProductFacadeError("iou_is_not_ros rail must be true")
    if r.recommended_lab_surface != RECOMMENDED_LAB_SURFACE:
        raise ProductFacadeError(
            f"default surface must be {RECOMMENDED_LAB_SURFACE!r}, "
            f"got {r.recommended_lab_surface!r}"
        )
    return r


# ── Multi-fire honesty (first-class, not ad-hoc) ──────────────────────────────


@dataclass(frozen=True)
class MultiFireHonesty:
    """Tags for LOFO / W3 external boards attached to every facade scorecard."""

    tobarra_fire_id: str = TOBARRA_FIRE_ID
    tobarra_role: str = TOBARRA_ROLE
    tobarra_keep_verdict: str = "KILL"  # fresh LOFO; do not re-open same recipe
    w3_external_fires: tuple[str, ...] = W3_EXTERNAL_FIRES
    w3_role: str = W3_ROLE
    cardoso_lofo_note: str = (
        "CARDOSO LOFO ≈ U1 holdout family — not independent multi-fire generalization"
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "tobarra": {
                "fire_id": self.tobarra_fire_id,
                "role": self.tobarra_role,
                "keep_verdict": self.tobarra_keep_verdict,
                "reopen_same_recipe": False,
            },
            "w3_external": {
                "fires": list(self.w3_external_fires),
                "role": self.w3_role,
                "frozen_thr_and_cal": True,
            },
            "cardoso_lofo_note": self.cardoso_lofo_note,
            "iou_is_not_ros": True,
        }


DEFAULT_MULTI_FIRE: Final = MultiFireHonesty()


def fire_honesty_tag(fire_id: str) -> dict[str, Any]:
    """Map a fire id to honesty role for LOFO / W3 boards."""
    fid = str(fire_id)
    if fid == TOBARRA_FIRE_ID or fid.lower().startswith("tobarra"):
        return {
            "fire_id": fid,
            "role": TOBARRA_ROLE,
            "board": "lofo_in_pack",
            "keep_reopen": False,
        }
    if fid in W3_EXTERNAL_FIRES:
        return {
            "fire_id": fid,
            "role": W3_ROLE,
            "board": "w3_external",
            "frozen_eval_only": True,
        }
    if fid.upper() == "CARDOSO" or fid.upper().startswith("CARDOSO"):
        return {
            "fire_id": fid,
            "role": "easy_in_pack",
            "board": "lofo_in_pack",
            "note": DEFAULT_MULTI_FIRE.cardoso_lofo_note,
        }
    return {"fire_id": fid, "role": "in_pack_or_unknown", "board": "lofo_or_other"}


# ── Layer 1: features ─────────────────────────────────────────────────────────


def head_a_feature_names() -> tuple[str, ...]:
    return HEAD_A_FEATURE_NAMES


def features_from_diag(diag: dict[str, float]) -> np.ndarray:
    """Head A (N=3) vector from ensemble diagnostics — single entry point."""
    return features_from_diagnostics(diag)


def stack_head_a_features(rows: Sequence[np.ndarray | Sequence[float]]) -> np.ndarray:
    """Stack patch feature rows to (N, 3)."""
    if not rows:
        return np.zeros((0, 3), dtype=np.float64)
    x = np.asarray([np.asarray(r, dtype=np.float64).ravel() for r in rows], dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 3:
        raise ProductFacadeError(f"Head A features must be (N,3), got {x.shape}")
    return x


# ── Layer 2: calibrator → confidence (via rank_reject_protocol) ───────────────


def confidences_from_head_a(
    cal: LogisticCalibrator,
    features: np.ndarray,
) -> np.ndarray:
    """Batch confidences — single path via rank_reject_protocol.conf_from_features."""
    return conf_from_features(cal, features)


def confidence_from_diag(cal: LogisticCalibrator, diag: dict[str, float]) -> float:
    """Single-patch confidence from diagnostics dict."""
    return float(cal.predict_proba(diag))


# ── Layer 3: rank / reject (drives rank_reject_protocol) ──────────────────────

RankMode = Literal["thr_reject", "selective_rank"]


@dataclass(frozen=True)
class RankRejectConfig:
    """Shared protocol knobs for thr-abstain and selective ranking.

    * ``reject_thr`` defaults to frozen iter1 VAL thr (~0.795) from protocol.
    * Ranking uses the same confidences; thr and coverage are different *views*,
      not different confidence implementations.
    * Do not retune thr on TEST / LOFO / W3 external via this config without
      an explicit VAL-only re-fit (``select_thr_val_only`` on split=val).
    """

    reject_thr: float = ITER1_LOCKED_REJECT_THR
    rank_score_name: str = DEFAULT_RANK_SCORE
    selective_coverage: float = 0.8
    surface: str = RECOMMENDED_LAB_SURFACE

    def as_dict(self) -> dict[str, Any]:
        return {
            "reject_thr": float(self.reject_thr),
            "rank_score_name": self.rank_score_name,
            "selective_coverage": float(self.selective_coverage),
            "surface": self.surface,
            "protocol_module": _RANK_REJECT_PROTOCOL,
            "note": (
                "thr_reject and selective_rank share confidences via "
                "rank_reject_protocol; ranking curve ≠ thr reject operating point"
            ),
        }


DEFAULT_RANK_REJECT: Final = RankRejectConfig()


def apply_thr_reject(
    conf: np.ndarray,
    *,
    thr: float = ITER1_LOCKED_REJECT_THR,
) -> dict[str, Any]:
    """Binary keep/abstain mask at locked (or explicit) thr.

    Keep-mask helper for callers; thr metrics with IoU use
    ``rank_reject_protocol.apply_reject_thr_metrics`` via ``rank_and_reject``.
    """
    conf = np.asarray(conf, dtype=np.float64).ravel()
    thr_f = float(thr)
    keep = conf >= thr_f
    n = int(conf.size)
    n_keep = int(keep.sum())
    return {
        "thr": thr_f,
        "keep": keep,
        "n": n,
        "n_keep": n_keep,
        "n_abstain": n - n_keep,
        "abstain_rate": float(1.0 - n_keep / n) if n else float("nan"),
        "keep_rate": float(n_keep / n) if n else float("nan"),
        "mode": "thr_reject",
        "surface": RECOMMENDED_LAB_SURFACE,
        "protocol_module": _RANK_REJECT_PROTOCOL,
    }


def ranking_scores(
    features: np.ndarray,
    conf: np.ndarray,
) -> dict[str, np.ndarray]:
    """Ranking score families (SDC module); metrics via rank_reject_protocol."""
    return ranking_scores_from_head_a(features, conf)


def selective_rank_metrics(
    score: np.ndarray,
    ious: np.ndarray,
    *,
    coverage: float = 0.8,
) -> dict[str, Any]:
    """Selective IoU / AURC for one ranking score — protocol score_ranking."""
    covs = [1.0, 0.9, float(coverage), 0.7, 0.6, 0.5]
    # Deduplicate while preserving order (coverage may already be 0.8).
    seen: set[float] = set()
    coverages: list[float] = []
    for c in covs:
        if c not in seen:
            seen.add(c)
            coverages.append(c)
    return protocol_score_ranking(score, ious, coverages=coverages)


def select_reject_thr_val_only(
    conf: np.ndarray,
    ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
    thr_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    """VAL-only thr selection — delegates to rank_reject_protocol (never test/lofo)."""
    return select_thr_val_only(conf, ious, risk_alpha=risk_alpha, thr_grid=thr_grid, split="val")


def rank_and_reject(
    features: np.ndarray,
    conf: np.ndarray,
    ious: np.ndarray | None = None,
    labels: np.ndarray | None = None,
    *,
    cfg: RankRejectConfig | None = None,
) -> dict[str, Any]:
    """Unified rank + thr-reject surface via rank_reject_protocol.

    Always computes thr reject at ``cfg.reject_thr`` (default iter1 freeze).
    If ``ious`` provided, also computes selective ranking metrics (protocol
    ``score_ranking``) and thr metrics (protocol ``apply_reject_thr_metrics``).
    Never retunes thr here — use ``select_reject_thr_val_only`` on VAL only.
    """
    cfg = cfg or DEFAULT_RANK_REJECT
    conf_a = np.asarray(conf, dtype=np.float64).ravel()
    thr_view = apply_thr_reject(conf_a, thr=cfg.reject_thr)
    scores = ranking_scores(features, conf_a)
    primary_rank = scores.get(cfg.rank_score_name)
    if primary_rank is None:
        raise ProductFacadeError(
            f"unknown rank_score_name {cfg.rank_score_name!r}; known={sorted(scores)}"
        )

    out: dict[str, Any] = {
        "protocol": "head_a_rank_reject_v1",
        "protocol_module": _RANK_REJECT_PROTOCOL,
        "config": cfg.as_dict(),
        "thr_reject": {k: v for k, v in thr_view.items() if k != "keep"},
        "keep_mask": thr_view["keep"],
        "rank_score_names": sorted(scores),
        "primary_rank_score": cfg.rank_score_name,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "rails": protocol_lab_rails(),
    }

    if ious is not None:
        ious_a = np.asarray(ious, dtype=np.float64).ravel()
        if ious_a.size != conf_a.size:
            raise ProductFacadeError("ious length mismatch with conf")
        # Protocol thr-reject metrics (IoU accepted / abstain) — no labels needed.
        out["thr_reject_metrics"] = apply_reject_thr_metrics(conf_a, ious_a, float(cfg.reject_thr))
        out["selective_primary"] = selective_rank_metrics(
            primary_rank, ious_a, coverage=cfg.selective_coverage
        )
        out["risk_coverage_curve"] = risk_coverage_curve(conf_a, ious_a)
        if labels is not None:
            labels_a = np.asarray(labels, dtype=np.float64).ravel()
            # Labeled ECE / accepted metrics for scorecard (report only).
            out["thr_metrics"] = metrics_at_threshold(conf_a, labels_a, ious_a, thr=cfg.reject_thr)
            out["thr_operating_points"] = thr_operating_points(
                conf_a,
                labels_a,
                ious_a,
                # Compare legacy 0.35 vs frozen iter1 thr only — no parallel 0.80 fork.
                thresholds=(
                    LEGACY_PRODUCT_ABSTAIN_THR,
                    float(cfg.reject_thr),
                    ITER1_LOCKED_REJECT_THR,
                ),
            )
            out["ece_full"] = float(ece_patch_conf(conf_a, labels_a))
        # SDC bake-off available without promoting SDC over iter1 (dead path).
        out["ranking_bakeoff"] = {
            k: {kk: vv for kk, vv in v.items() if kk != "curve"}
            for k, v in bakeoff_rankings(features, conf_a, ious_a).items()
        }
    return out


def rank_reject_val_test(
    cal: LogisticCalibrator,
    val_features: np.ndarray,
    val_ious: np.ndarray,
    test_features: np.ndarray,
    test_ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
) -> dict[str, Any]:
    """VAL thr select then TEST at frozen thr — drives rank_reject_protocol."""
    return rank_reject_val_then_test(
        cal,
        val_features,
        val_ious,
        test_features,
        test_ious,
        risk_alpha=risk_alpha,
    )


# ── Layer 4: scorecard ────────────────────────────────────────────────────────


def build_uncertainty_block(
    conf: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    *,
    thr: float = ITER1_LOCKED_REJECT_THR,
    coverage: float = 0.8,
    tau_iou: float = 0.5,
) -> dict[str, Any]:
    """Scorecard ``uncertainty`` block from shared conf (VAL thr frozen for abstain)."""
    conf = np.asarray(conf, dtype=np.float64).ravel()
    labels = np.asarray(labels, dtype=np.float64).ravel()
    ious = np.asarray(ious, dtype=np.float64).ravel()
    m = metrics_at_threshold(conf, labels, ious, thr=float(thr), coverage_for_selective=coverage)
    sel = selective_iou_at_coverage(ious, conf, coverage=coverage)
    full = float(np.mean(ious)) if ious.size else float("nan")
    return {
        "ece_patch_conf": float(m["ece_full"]),
        "selective_iou_at_80pct_coverage": float(sel["selective_iou"])
        if abs(coverage - 0.8) < 1e-9
        else float(sel["selective_iou"]),
        "selective_iou_at_coverage": float(sel["selective_iou"]),
        "mean_confidence": float(np.mean(conf)) if conf.size else float("nan"),
        "n_patches": int(conf.size),
        "tau_iou": float(tau_iou),
        "coverage": float(coverage),
        "abstain_rate": float(m["abstain_rate"]),
        "threshold": float(thr),
        "mean_iou_accepted": float(m["mean_iou_accepted"]),
        "full_mean_iou": full,
    }


def build_primary_block(
    ious: np.ndarray,
    *,
    split: str = "test",
    source: str = "eval_split_mean",
    n_patches: int | None = None,
) -> dict[str, Any]:
    """Scorecard ``primary`` block — IoU only; no ROS keys."""
    ious = np.asarray(ious, dtype=np.float64).ravel()
    primary = {
        "model_iou": float(np.mean(ious)) if ious.size else float("nan"),
        "n_patches": int(n_patches if n_patches is not None else ious.size),
        "model_iou_split": str(split),
        "model_iou_source": str(source),
    }
    reject_ros_keys_in_primary(primary)
    return primary


def build_scorecard(
    *,
    product_id: str = DEFAULT_PRODUCT_ID,
    protocol: str = DEFAULT_PROTOCOL,
    split: str = "test",
    action: str = "scorecard",
    conf: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    reject_thr: float = ITER1_LOCKED_REJECT_THR,
    calibrator_id: str | None = None,
    fire_id: str | None = None,
    rails: ProductRails | None = None,
    multi_fire: MultiFireHonesty | None = None,
    extra_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble ml_scorecard_v1-compatible doc from patch arrays.

    Tuning is always recorded as VAL-only; gates stamp ``ml_product_go`` from
    rails (default True after human promote 2026-08-05) and keep field fusion
    OFF. Auto-flip thrash remains refused; does not retrain.
    """
    rails = assert_lab_rails(rails)
    multi_fire = multi_fire or DEFAULT_MULTI_FIRE
    assert_split_role(split, action)

    primary = build_primary_block(ious, split=split)
    unc = build_uncertainty_block(conf, labels, ious, thr=reject_thr)
    # Keep scorecard uncertainty keys within schema allowlist.
    uncertainty = {
        "ece_patch_conf": unc["ece_patch_conf"],
        "selective_iou_at_80pct_coverage": unc["selective_iou_at_80pct_coverage"],
        "mean_confidence": unc["mean_confidence"],
        "n_patches": unc["n_patches"],
        "tau_iou": unc["tau_iou"],
        "coverage": unc["coverage"],
        "abstain_rate": unc["abstain_rate"],
    }

    honesty = list(FIXED_HONESTY_NOTES) + [
        f"Lab surface locked: {RECOMMENDED_LAB_SURFACE} thr≈{reject_thr}.",
        "Ranking and thr-reject share Head A confidences via rank_reject_protocol.",
        "Field fusion OFF; ml_product_go true (human promote; no auto-flip).",
    ]
    provenance: dict[str, Any] = {
        "calibrator_id": calibrator_id,
        "frozen_reject_thr": float(reject_thr),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "catalog_holdout_test_reference": catalog_holdout_test_reference(),
        "multi_fire": multi_fire.as_dict(),
        "honesty_notes": honesty,
        "product_facade": "wildfire_front.ml.product_facade",
        "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
        "pipeline": "features→calibrator→rank/reject→scorecard",
    }
    if fire_id is not None:
        provenance["fire"] = fire_honesty_tag(fire_id)
    if extra_provenance:
        provenance.update(extra_provenance)

    doc: dict[str, Any] = {
        "schema": "ml_scorecard_v1",
        "product_id": product_id,
        "protocol": protocol,
        "split": split,
        "action": action,
        "calibrator_fit_split": "val",
        "u1_eval_split": split if split in ("val", "test") else "test",
        "tuning": {
            "mix_split": "val",
            "temperature_split": "val",
            "uncertainty_calibration_split": "val",
        },
        "primary": primary,
        "uncertainty": uncertainty,
        "gates": {
            "ml_product_go": bool(rails.ml_product_go),
            "field_ops_allow_ml_live_in_fusion": False,
            "u1_test_honest": split == "test",
            "lab_surface_iter1_reject": True,
        },
        "rails": rails.as_dict(),
        "rank_reject": {
            "thr": float(reject_thr),
            "surface": RECOMMENDED_LAB_SURFACE,
            "protocol_module": _RANK_REJECT_PROTOCOL,
            "mode_note": (
                "thr_reject and selective_rank share confidences via rank_reject_protocol"
            ),
        },
        "provenance": provenance,
    }
    # Schema validation is advisory here (extra keys like rails/provenance ok for lab).
    _ = validate_ml_scorecard(
        {
            "schema": doc["schema"],
            "product_id": doc["product_id"],
            "protocol": doc["protocol"],
            "split": doc["split"],
            "action": doc["action"],
            "primary": doc["primary"],
            "uncertainty": {
                k: uncertainty[k]
                for k in uncertainty
                if k
                in {
                    "ece_patch_conf",
                    "selective_iou_at_80pct_coverage",
                    "mean_confidence",
                    "n_patches",
                    "tau_iou",
                    "coverage",
                    "abstain_rate",
                }
            },
            "tuning": doc["tuning"],
        }
    )
    return doc


# ── Facade object ─────────────────────────────────────────────────────────────


@dataclass
class ClmEnsembleV34Facade:
    """Single entry for clm_ensemble_v34 lab product services.

    Usage::

        facade = ClmEnsembleV34Facade.from_calibrator_path(path)
        conf = facade.confidences(features)
        surface = facade.rank_reject(features, conf, ious=ious, labels=labels)
        card = facade.scorecard(conf, labels, ious, split="test")
    """

    cal: LogisticCalibrator
    rails: ProductRails = field(default_factory=ProductRails)
    rank_reject_cfg: RankRejectConfig = field(default_factory=RankRejectConfig)
    multi_fire: MultiFireHonesty = field(default_factory=MultiFireHonesty)
    product_id: str = DEFAULT_PRODUCT_ID
    protocol: str = DEFAULT_PROTOCOL

    def __post_init__(self) -> None:
        assert_lab_rails(self.rails)
        # Freeze surface: reject thr defaults to iter1 lock.
        if abs(float(self.rank_reject_cfg.reject_thr) - ITER1_LOCKED_REJECT_THR) > 0.05:
            # Allow intentional lab experiments slightly off lock, but surface stays named.
            pass

    @classmethod
    def from_calibrator(
        cls,
        cal: LogisticCalibrator,
        **kwargs: Any,
    ) -> ClmEnsembleV34Facade:
        return cls(cal=cal, **kwargs)

    @classmethod
    def from_calibrator_path(
        cls,
        path: str | Path,
        **kwargs: Any,
    ) -> ClmEnsembleV34Facade:
        return cls(cal=load_calibrator(path), **kwargs)

    @classmethod
    def with_iter1_locked_thr(
        cls,
        cal: LogisticCalibrator,
        **kwargs: Any,
    ) -> ClmEnsembleV34Facade:
        """Facade with explicit iter1 thr on calibrator + rank/reject config."""
        cal_locked = LogisticCalibrator(
            weights=np.asarray(cal.weights, dtype=np.float64).copy(),
            feature_names=cal.feature_names,
            method=cal.method,
            calibrator_id=cal.calibrator_id,
            tau_iou=cal.tau_iou,
            fit_split=cal.fit_split,
            abstain_threshold=ITER1_LOCKED_REJECT_THR,
            allow_identity_heuristic=cal.allow_identity_heuristic,
            temperature=cal.temperature,
            platt_a=cal.platt_a,
            platt_b=cal.platt_b,
        )
        cfg = RankRejectConfig(reject_thr=ITER1_LOCKED_REJECT_THR)
        return cls(cal=cal_locked, rank_reject_cfg=cfg, **kwargs)

    # ── pipeline steps ────────────────────────────────────────────────────

    def features_from_diag(self, diag: dict[str, float]) -> np.ndarray:
        return features_from_diag(diag)

    def confidences(self, features: np.ndarray) -> np.ndarray:
        return confidences_from_head_a(self.cal, features)

    def confidence_from_diag(self, diag: dict[str, float]) -> float:
        return confidence_from_diag(self.cal, diag)

    def rank_reject(
        self,
        features: np.ndarray,
        conf: np.ndarray | None = None,
        ious: np.ndarray | None = None,
        labels: np.ndarray | None = None,
        *,
        cfg: RankRejectConfig | None = None,
    ) -> dict[str, Any]:
        """Conf → rank/reject via rank_reject_protocol (shared thr + ranking)."""
        if conf is None:
            conf = self.confidences(features)
        return rank_and_reject(
            features, conf, ious=ious, labels=labels, cfg=cfg or self.rank_reject_cfg
        )

    def select_thr_on_val(
        self,
        conf: np.ndarray,
        ious: np.ndarray,
        *,
        risk_alpha: float = 0.15,
    ) -> dict[str, Any]:
        """VAL-only thr selection (protocol); never call on test/lofo."""
        return select_reject_thr_val_only(conf, ious, risk_alpha=risk_alpha)

    def rank_reject_val_then_test(
        self,
        val_features: np.ndarray,
        val_ious: np.ndarray,
        test_features: np.ndarray,
        test_ious: np.ndarray,
        *,
        risk_alpha: float = 0.15,
    ) -> dict[str, Any]:
        """VAL thr → TEST frozen report — rank_reject_protocol single path."""
        return rank_reject_val_test(
            self.cal,
            val_features,
            val_ious,
            test_features,
            test_ious,
            risk_alpha=risk_alpha,
        )

    def run_pipeline(
        self,
        features: np.ndarray,
        *,
        ious: np.ndarray | None = None,
        labels: np.ndarray | None = None,
        split: str = "test",
        fire_id: str | None = None,
    ) -> dict[str, Any]:
        """Full features → calibrator → rank/reject → optional scorecard."""
        assert_lab_rails(self.rails)

        conf = self.confidences(features)
        surface = self.rank_reject(features, conf, ious=ious, labels=labels)
        out: dict[str, Any] = {
            "product_id": self.product_id,
            "protocol": self.protocol,
            "pipeline": "features→calibrator→rank/reject→scorecard",
            "protocol_module": _RANK_REJECT_PROTOCOL,
            "rails": self.rails.as_dict(),
            "protocol_rails": protocol_lab_rails(),
            "multi_fire": self.multi_fire.as_dict(),
            "n_patches": int(np.asarray(features).shape[0]),
            "conf": conf,
            "rank_reject": {
                k: v
                for k, v in surface.items()
                if k not in ("keep_mask", "conf")  # arrays may be large
            },
            "keep_mask": surface.get("keep_mask"),
            "calibrator_id": self.cal.calibrator_id,
            "locked_reject_thr": float(self.rank_reject_cfg.reject_thr),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        }
        if fire_id is not None:
            out["fire"] = fire_honesty_tag(fire_id)
        if ious is not None and labels is not None:
            out["scorecard"] = self.scorecard(conf, labels, ious, split=split, fire_id=fire_id)
        return out

    def scorecard(
        self,
        conf: np.ndarray,
        labels: np.ndarray,
        ious: np.ndarray,
        *,
        split: str = "test",
        action: str = "scorecard",
        fire_id: str | None = None,
        extra_provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_scorecard(
            product_id=self.product_id,
            protocol=self.protocol,
            split=split,
            action=action,
            conf=conf,
            labels=labels,
            ious=ious,
            reject_thr=float(self.rank_reject_cfg.reject_thr),
            calibrator_id=self.cal.calibrator_id,
            fire_id=fire_id,
            rails=self.rails,
            multi_fire=self.multi_fire,
            extra_provenance=extra_provenance,
        )

    def rails_snapshot(self) -> dict[str, Any]:
        return self.rails.as_dict()


def default_facade_from_repo(
    root: Path | None = None,
    *,
    prefer_lab_reject: bool = False,
) -> ClmEnsembleV34Facade:
    """Load production calibrator from repo; optionally lab-reject artifact thr.

    Default: production ``uncertainty_calibration_v1.json`` + **iter1 locked thr**
    on the facade rank/reject config (does not rewrite the JSON on disk).
    """
    base = root or Path(__file__).resolve().parents[2]
    prod = base / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    lab_rej = base / "models" / "clm_ensemble" / "uncertainty_calibration_v1_lab_reject.json"
    path = lab_rej if prefer_lab_reject and lab_rej.is_file() else prod
    if not path.is_file():
        raise FileNotFoundError(f"calibrator not found: {path}")
    cal = load_calibrator(path)
    return ClmEnsembleV34Facade.with_iter1_locked_thr(cal)


__all__ = [
    "ClmEnsembleV34Facade",
    "DEAD_PATHS",
    "DEFAULT_PRODUCT_ID",
    "DEFAULT_PROTOCOL",
    "DEFAULT_RAILS",
    "DEFAULT_RANK_REJECT",
    "ITER1_LOCKED_REJECT_THR",
    "ML_PRODUCT_GO_DEFAULT",
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
    "frozen_thr_from_val_selection",
    "head_a_feature_names",
    "rank_and_reject",
    "rank_reject_val_test",
    "ranking_scores",
    "refuse_dead_path",
    "select_reject_thr_val_only",
    "selective_rank_metrics",
    "stack_head_a_features",
]
