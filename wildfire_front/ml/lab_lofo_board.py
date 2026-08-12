"""Multi-fire LOFO scoreboard on unified lab product protocol rails.

Sits on ``product_facade`` + ``rank_reject_protocol`` (single product path)::

    features → calibrator → rank/reject (VAL thr freeze) → scorecard

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product: lab ML vs field_ops (IoU ≠ ROS; fusion OFF; no ml_product_go auto-flip).
* LOFO mask IoU board + optional Head A frozen thr report via
  ``ClmEnsembleV34Facade`` / ``rank_reject_protocol`` (report-only; VAL-only thr).
* Ranking / abstain surface default = freeze **iter1 reject** (shared protocol).
* Multi-fire honesty first-class: Tobarra hard, W3 external (not ad-hoc scripts).
* Dead thrash paths closed: same-holdout ECE retune, Tobarra KEEP reopen.

Mask IoU rows come from existing ``lofo_v1`` evaluation_metrics.
Head A frozen thr rows use ``head_a_features.npz`` when present. Does not retrain.
"""

from __future__ import annotations

import contextlib
import json
import math
from pathlib import Path
from typing import Any, Final

import numpy as np

from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    DEFAULT_RANK_SCORE,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    MultiFireHonesty,
    ProductFacadeError,
    ProductRails,
    assert_lab_rails,
    default_facade_from_repo,
    fire_honesty_tag,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    SplitContext,
    assert_split_context,
    assert_split_role,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    apply_reject_thr_metrics,
    protocol_payload,
    refuse_dead_protocol_path,
)
from wildfire_front.ml.rank_reject_protocol import (
    lab_rails as rank_reject_lab_rails,
)
from wildfire_front.ml.rank_reject_protocol import (
    multi_fire_honesty as rank_reject_multi_fire,
)
from wildfire_front.ml.reliability_metrics import ece_patch_conf

# ---------------------------------------------------------------------------
# Protocol identity (LOFO board is lab scorecard, not field product)
# ---------------------------------------------------------------------------

SCHEMA: Final = "wfd_ml_lofo_board_v1"
LOFO_PROTOCOL_NAME: Final = "leave_one_fire_out_mask_iou"
LAB_BANNER: Final = "lab product · not field_ops fusion · IoU ≠ ROS"
_W3_EXTERNAL_DIR: Final = "outputs/ml_eval/w3"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_RANK_REJECT: Final = "wildfire_front.ml.rank_reject_protocol"
_DEAD: Final = frozenset(DEAD_PATHS) | frozenset(DEAD_PROTOCOL_PATHS)

# LOFO split: scorecard/report only — never thr/ECE tune (VAL-only protocol).
_LOFO_BOARD_CTX = SplitContext(split="lofo", action="scorecard")


def lofo_board_rails(rails: ProductRails | None = None) -> dict[str, Any]:
    """Unified dual-product rails for the LOFO board (facade + rank_reject).

    Merges :class:`ProductRails` with ``rank_reject_protocol.lab_rails`` so
    ranking / abstain share one protocol (iter1 reject freeze, fusion OFF).
    """
    r = assert_lab_rails(rails or DEFAULT_RAILS)
    base = r.as_dict()
    # Shared dual-product + pipeline surface (single source with product path).
    base.update(rank_reject_lab_rails())
    base.update(
        {
            "banner": LAB_BANNER,
            "lofo_is_not_u1_ece": True,
            "val_only_threshold_tune": True,
            "val_only_threshold_selection": True,
            "field_ops_ml_live_fusion": "OFF",
            "tobarra_keep_reopen": False,
            "freeze_iter1_reject": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "rank_reject_protocol": _RANK_REJECT,
            "pipeline": _PIPELINE,
            "forbidden_thrash": sorted(_DEAD),
            "dead_paths": sorted(_DEAD),
        }
    )
    return base


def lofo_clm_ensemble_frozen_surface(
    *,
    locked_reject_thr: float | None = None,
) -> dict[str, Any]:
    """ClmEnsembleV34Facade + rank_reject_protocol frozen thr surface (no retrain).

    LOFO report metadata for the single product path. Does not load a calibrator;
    thr is the VAL-locked iter1 reject default (never fit on LOFO).
    """
    thr = float(ITER1_LOCKED_REJECT_THR if locked_reject_thr is None else locked_reject_thr)
    cfg = DEFAULT_RANK_REJECT
    return {
        "facade_class": _FACADE_CLASS,
        "product_facade": _FACADE,
        "product_id": DEFAULT_PRODUCT_ID,
        "pipeline": _PIPELINE,
        "rank_reject_protocol": _RANK_REJECT,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": thr,
        "rank_family": DEFAULT_RANK_SCORE,
        "thr_source": "val_iter1_reject_frozen",
        "val_only_threshold_selection": True,
        "fit_on_lofo": False,
        "split_role": "lofo",
        "allowed_actions": sorted(["report", "stress", "scorecard", "gate", "rank", "abstain"]),
        "rank_reject": {
            **cfg.as_dict(),
            "reject_thr": thr,
            "surface": RECOMMENDED_LAB_SURFACE,
        },
        "protocol": protocol_payload(locked_reject_thr=thr),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "note": (
            "LOFO board reports via ClmEnsembleV34Facade iter1_reject_only surface; "
            "ranking and thr-reject share conf via rank_reject_protocol. "
            "Never retune thr/ECE on LOFO."
        ),
    }


def _assert_dead_paths_closed() -> None:
    """Hard-seal ECE thrash + Tobarra KEEP reopen (architecture refuse)."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        # expected: sealed
        with contextlib.suppress(ValueError):
            refuse_dead_protocol_path(dead)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def classify_fold_honesty(fold_name: str) -> dict[str, Any]:
    """First-class multi-fire honesty via product facade fire tags."""
    tag = fire_honesty_tag(str(fold_name or ""))
    role = str(tag.get("role") or "in_pack_or_unknown")
    hard = role == "hard_transfer"
    in_pack = role in ("easy_in_pack", "in_pack_or_unknown") and not hard
    # Estrella / generic in-pack LOFO still count as in-pack for board summary.
    low = str(fold_name or "").lower()
    if any(t in low for t in ("cardoso", "estrella", "acom")):
        in_pack = True
    if hard:
        note = "Tobarra-class hard fold — do not universalize U1 IoU; KEEP reopen forbidden"
    elif role == "easy_in_pack":
        note = str(tag.get("note") or DEFAULT_MULTI_FIRE.cardoso_lofo_note)
    elif role == "external_probe":
        note = "W3 external probe — frozen thr/cal report only"
        in_pack = False
    else:
        note = "LOFO fold — report-only; thr/ECE not fit here"
        if any(t in low for t in ("cardoso", "estrella", "acom")):
            role = "in_pack"
    return {
        "fold": str(fold_name or ""),
        "role": role if role != "in_pack_or_unknown" or not in_pack else "in_pack",
        "hard": hard,
        "in_pack": in_pack and not hard,
        "facade_tag": tag,
        "note": note,
    }


def collect_w3_external_presence(
    root: Path,
    multi_fire: MultiFireHonesty | None = None,
) -> dict[str, Any]:
    """W3 external multi-fire honesty as a first-class board section."""
    mf = multi_fire or DEFAULT_MULTI_FIRE
    w3_root = root / _W3_EXTERNAL_DIR
    on_disk: list[str] = []
    if w3_root.is_dir():
        on_disk = sorted(p.name for p in w3_root.iterdir() if p.is_dir())
    # Prefer facade catalog of external fires, intersect with disk when present.
    catalog = list(mf.w3_external_fires)
    fires = [f for f in catalog if f in on_disk] or on_disk
    return {
        "root": str(w3_root.as_posix()),
        "present": bool(on_disk),
        "n_fires": len(fires),
        "fires": fires,
        "catalog_fires": catalog,
        "role": mf.w3_role,
        "protocol": "external_multi_fire_head_a_frozen_thr",
        "frozen_thr_and_cal": True,
        "note": (
            "W3 external fires are multi-fire honesty probes (report/gate). "
            "Never thr/ECE fit on held-out fire TEST; not U1 ECE retune."
        ),
        "field_product": False,
    }


def _thresh_iou(em: dict[str, Any], thr_key: str) -> float | None:
    block = em.get(thr_key) or {}
    if not isinstance(block, dict):
        return None
    full = block.get("model_full") or {}
    if not isinstance(full, dict):
        return None
    v = full.get("iou_mean")
    return float(v) if v is not None else None


def collect_lofo_fold(fold_dir: Path) -> dict[str, Any] | None:
    em = load_json(fold_dir / "evaluation_metrics.json")
    if not em:
        return None
    model_iou = em.get("model_iou")
    copy_iou = em.get("copy_baseline_iou")
    delta = em.get("improvement_vs_copy_iou")
    if delta is None and model_iou is not None and copy_iou is not None:
        delta = float(model_iou) - float(copy_iou)
    thr_ious = {
        k: _thresh_iou(em, k) for k in ("thresh_0.3", "thresh_0.4", "thresh_0.5", "thresh_0.6")
    }
    thr_vals = [v for v in thr_ious.values() if v is not None]
    thr_spread = (max(thr_vals) - min(thr_vals)) if len(thr_vals) >= 2 else 0.0
    honesty = classify_fold_honesty(fold_dir.name)
    return {
        "fold": fold_dir.name,
        "model_iou": float(model_iou) if model_iou is not None else None,
        "copy_baseline_iou": float(copy_iou) if copy_iou is not None else None,
        "improvement_vs_copy_iou": float(delta) if delta is not None else None,
        "model_iou_changed": (
            float(em["model_iou_changed"]) if em.get("model_iou_changed") is not None else None
        ),
        "model_iou_growth": (
            float(em["model_iou_growth"]) if em.get("model_iou_growth") is not None else None
        ),
        "beats_copy": bool(delta is not None and float(delta) > 0.0),
        "thresh_model_full_iou": thr_ious,
        "thresh_iou_spread": thr_spread,
        "honesty": honesty,
        "path": str((fold_dir / "evaluation_metrics.json").as_posix()),
    }


def collect_lofo_board(lofo_root: Path) -> list[dict[str, Any]]:
    if not lofo_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for fold_dir in sorted(p for p in lofo_root.iterdir() if p.is_dir()):
        row = collect_lofo_fold(fold_dir)
        if row:
            ha = fold_dir / "head_a_features.npz"
            row["head_a_cache"] = ha.is_file()
            rows.append(row)
    return rows


def _load_head_a_cache(path: Path) -> dict[str, Any] | None:
    """Load LOFO Head A cache for frozen thr report (no fit)."""
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            return {
                "features": np.asarray(z["features"], dtype=np.float64),
                "labels": np.asarray(z["labels"], dtype=np.float64),
                "ious": np.asarray(z["ious"], dtype=np.float64),
            }
    except (OSError, ValueError, KeyError):
        return None


def collect_lofo_frozen_thr_report(root: Path) -> dict[str, Any]:
    """LOFO report-only frozen thr eval via ClmEnsembleV34Facade + rank_reject.

    Uses per-fold ``head_a_features.npz`` when present. Path::

        features → facade confidences → rank_reject thr metrics (frozen iter1)

    Never fits thr/cal on LOFO; locked thr = iter1 reject (VAL freeze).
    Skips ranking bake-off / risk curves (mask IoU board is separate).
    """
    surface = lofo_clm_ensemble_frozen_surface()
    thr = float(ITER1_LOCKED_REJECT_THR)
    protocol = protocol_payload(locked_reject_thr=thr)
    lofo_root = root / "outputs" / "ml_eval" / "lofo_v1"
    cache_folds: list[str] = []
    if lofo_root.is_dir():
        cache_folds = sorted(
            p.name
            for p in lofo_root.iterdir()
            if p.is_dir() and (p / "head_a_features.npz").is_file()
        )
    base: dict[str, Any] = {
        "ok": False,
        "split": "lofo",
        "action": "report",
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "rank_reject_protocol_module": _RANK_REJECT,
        "rank_reject_protocol": protocol,
        "clm_ensemble_surface": surface,
        "locked_reject_thr": thr,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "n_cache_folds": len(cache_folds),
        "cache_folds": cache_folds,
        "folds": {},
        "summary": {"n_folds": 0},
        "note": (
            "Frozen thr LOFO report via ClmEnsembleV34Facade + rank_reject_protocol. "
            "No thr/ECE fit on held-out fire."
        ),
    }
    if not cache_folds:
        base["reason"] = "no_head_a_caches"
        base["blocked"] = True
        return base

    try:
        facade = default_facade_from_repo(root)
    except (OSError, FileNotFoundError, ValueError) as exc:
        base["reason"] = "calibrator_missing"
        base["error"] = str(exc)
        base["blocked"] = True
        return base

    # Protocol: LOFO is report-only (never tune thr/ECE).
    assert_split_role("lofo", "report")
    thr = float(facade.rank_reject_cfg.reject_thr)

    fold_rows: dict[str, Any] = {}
    eces: list[float] = []
    abstains: list[float] = []
    iou_acc: list[float] = []
    for fold in cache_folds:
        cache = lofo_root / fold / "head_a_features.npz"
        data = _load_head_a_cache(cache)
        if not data:
            continue
        # Single product path (light report): conf via facade, thr metrics via protocol.
        conf = facade.confidences(data["features"])
        thr_m = apply_reject_thr_metrics(conf, data["ious"], thr)
        ece = float(ece_patch_conf(conf, data["labels"]))
        slim = {
            "fold": fold,
            "n_patches": int(np.asarray(data["features"]).shape[0]),
            "locked_reject_thr": thr,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "rank_reject_protocol": _RANK_REJECT,
            "ece_full": ece,
            "thr_reject_metrics": thr_m,
            "honesty": fire_honesty_tag(fold),
            "calibrator_id": getattr(facade.cal, "calibrator_id", None),
            "cache": str(cache.as_posix()),
        }
        fold_rows[fold] = slim
        eces.append(ece)
        if thr_m.get("abstain_rate") is not None:
            abstains.append(float(thr_m["abstain_rate"]))
        if thr_m.get("mean_iou_accepted") is not None and math.isfinite(
            float(thr_m["mean_iou_accepted"])
        ):
            iou_acc.append(float(thr_m["mean_iou_accepted"]))

    summary: dict[str, Any] = {
        "n_folds": len(fold_rows),
        "ece_mean": (sum(eces) / len(eces)) if eces else None,
        "locked_abstain_mean": (sum(abstains) / len(abstains)) if abstains else None,
        "locked_iou_accepted_mean": (sum(iou_acc) / len(iou_acc)) if iou_acc else None,
        "locked_reject_thr": thr,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
    }
    base.update(
        {
            "ok": bool(fold_rows),
            "blocked": not bool(fold_rows),
            "locked_reject_thr": thr,
            "folds": fold_rows,
            "summary": summary,
            "multi_fire_honesty": rank_reject_multi_fire(),
            "calibrator_id": getattr(facade.cal, "calibrator_id", None),
        }
    )
    if not fold_rows:
        base["reason"] = "cache_load_failed"
    return base


def summarize_lofo_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ious = [r["model_iou"] for r in rows if r.get("model_iou") is not None]
    deltas = [
        r["improvement_vs_copy_iou"] for r in rows if r.get("improvement_vs_copy_iou") is not None
    ]
    changed = [r["model_iou_changed"] for r in rows if r.get("model_iou_changed") is not None]
    if not ious:
        return {"n_folds": 0}
    mean = sum(ious) / len(ious)
    var = sum((x - mean) ** 2 for x in ious) / len(ious)
    weakest = min(rows, key=lambda r: r.get("model_iou") or 1e9)
    strongest = max(rows, key=lambda r: r.get("model_iou") or -1e9)
    hard = [r["fold"] for r in rows if (r.get("honesty") or {}).get("hard")]
    in_pack = [r["fold"] for r in rows if (r.get("honesty") or {}).get("in_pack")]
    return {
        "n_folds": len(ious),
        "model_iou_mean": mean,
        "model_iou_std": math.sqrt(var),
        "model_iou_min": min(ious),
        "model_iou_max": max(ious),
        "spread_max_minus_min": max(ious) - min(ious),
        "delta_vs_copy_mean": (sum(deltas) / len(deltas)) if deltas else None,
        "n_beats_copy": sum(1 for r in rows if r.get("beats_copy")),
        "model_iou_changed_mean": (sum(changed) / len(changed)) if changed else None,
        "weakest_fold": weakest.get("fold"),
        "weakest_iou": weakest.get("model_iou"),
        "strongest_fold": strongest.get("fold"),
        "strongest_iou": strongest.get("model_iou"),
        "hard_folds": hard,
        "in_pack_folds": in_pack,
        "n_hard_folds": len(hard),
    }


def build_lofo_scoreboard(root: Path) -> dict[str, Any]:
    """Full offline LOFO multi-fire board for ``ml lofo`` on unified rails.

    Mask IoU rows + shared ``rank_reject_protocol`` / ``ClmEnsembleV34Facade``
    frozen thr report (when Head A caches present). Never tunes thr on LOFO.
    """
    # Protocol integrity: LOFO is scorecard/report only (never tune thr/ECE).
    assert_split_context(_LOFO_BOARD_CTX)
    assert_split_role("lofo", "report")
    _assert_dead_paths_closed()
    # Lab rails freeze: fusion OFF, iter1 reject, no ml_product_go auto-flip.
    rails = lofo_board_rails()
    multi_fire_spec = DEFAULT_MULTI_FIRE
    clm_surface = lofo_clm_ensemble_frozen_surface()
    rank_reject = protocol_payload(locked_reject_thr=float(ITER1_LOCKED_REJECT_THR))

    lofo_root = root / "outputs" / "ml_eval" / "lofo_v1"
    rows = collect_lofo_board(lofo_root)
    summary = summarize_lofo_board(rows)
    w3 = collect_w3_external_presence(root, multi_fire_spec)
    # Shared frozen thr path (features→cal→rank/reject→scorecard) when caches exist.
    frozen_thr = collect_lofo_frozen_thr_report(root)

    sc = load_json(root / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    u1_iou = (sc.get("primary") or {}).get("model_iou")
    u1_ece = (sc.get("uncertainty") or {}).get("ece_patch_conf")
    cat = ((sc.get("provenance") or {}).get("catalog_holdout_test_reference") or {}).get("test_iou")

    gen_note = "insufficient_lofo"
    gap = None
    if summary.get("n_folds", 0) >= 2 and u1_iou is not None:
        gap = float(u1_iou) - float(summary["model_iou_mean"])
        if gap > 0.05:
            gen_note = "holdout_u1_higher_than_lofo_mean — do not over-claim single-holdout IoU"
        elif gap < -0.05:
            gen_note = "lofo_mean_higher_than_holdout_u1 — recheck protocols"
        else:
            gen_note = "lofo_mean_near_holdout_u1"

    spread = float(summary.get("spread_max_minus_min") or 0.0)
    hard_folds = list(summary.get("hard_folds") or [])
    multi_fire = {
        **multi_fire_spec.as_dict(),
        **rank_reject_multi_fire(),
        "tobarra_hard": bool(hard_folds),
        "hard_folds": hard_folds,
        "in_pack_folds": list(summary.get("in_pack_folds") or []),
        "w3_external_on_disk": w3,
        "do_not_universalize_u1": True,
        "do_not_reopen_tobarra_keep": True,
        "note": (
            "Multi-fire honesty is first-class via product_facade + "
            "rank_reject_protocol: Tobarra hard_transfer KILL; "
            "W3 external_probe frozen; LOFO ≠ U1 ECE."
        ),
    }

    frozen_ok = bool(frozen_thr.get("ok"))
    blocked = []
    if not frozen_ok:
        blocked.append(
            f"LOFO Head A frozen thr ({frozen_thr.get('reason') or 'caches/calibrator missing'})"
        )
    blocked.extend(
        [
            "Same-holdout ECE post-hoc retune",
            "Tobarra KEEP reopen with same recipe / KILL weights",
        ]
    )

    return {
        "schema": SCHEMA,
        "banner": LAB_BANNER,
        "product_id": DEFAULT_PRODUCT_ID,
        "label": "lab / research_open only — LOFO mask IoU ≠ U1 Head A ECE",
        "rails": rails,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "rank_reject_protocol": rank_reject,
        "clm_ensemble_surface": clm_surface,
        "frozen_thr_report": frozen_thr,
        "protocol": {
            "name": LOFO_PROTOCOL_NAME,
            "root": str(lofo_root.as_posix()),
            "split": "lofo",
            "allowed_actions": sorted(["report", "stress", "scorecard", "gate", "rank", "abstain"]),
            "surface": RECOMMENDED_LAB_SURFACE,
            "val_only_threshold_tune": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "rank_reject_protocol": _RANK_REJECT,
            "rank_reject_surface": RECOMMENDED_LAB_SURFACE,
            "pipeline": _PIPELINE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "thr_source": "val_iter1_reject_frozen",
            "honesty": (
                "LOFO mask IoU rows from training evals + optional Head A frozen thr "
                "report via ClmEnsembleV34Facade / rank_reject_protocol. "
                "LOFO ≠ U1 Head A ECE protocol. Thr selection is VAL-only; "
                "freeze iter1 reject as default. Never fit thr/ECE on LOFO."
            ),
            "blocked_without_new_signal": blocked,
            "forbidden_thrash": sorted(_DEAD),
            "dead_paths": sorted(_DEAD),
        },
        "multi_fire_honesty": multi_fire,
        "holdout_reference": {
            "u1_test_mean_iou": u1_iou,
            "u1_ece": u1_ece,
            "catalog_holdout_iou_provenance_only": cat,
            "gap_u1_minus_lofo_mean": gap,
            "generalization_note": gen_note,
            "lofo_is_not_u1_ece": True,
        },
        "folds": rows,
        "summary": summary,
        "verdict": {
            "lofo_board_built": bool(summary.get("n_folds", 0) >= 1),
            "spread_material": spread >= 0.05,
            "all_folds_beat_copy": bool(
                summary.get("n_folds", 0) > 0
                and summary.get("n_beats_copy") == summary.get("n_folds")
            ),
            "do_not_universalize_u1": bool((gap is not None and gap > 0.05) or bool(hard_folds)),
            "tobarra_hard": bool(hard_folds),
            "w3_external_present": bool(w3.get("present")),
            "ece_holdout_still_unfixed": True,
            "frozen_thr_report_ok": frozen_ok,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "freeze_iter1_reject": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "note": (
                "Multi-fire LOFO scoreboard on product_facade + rank_reject_protocol. "
                "Mask IoU board + ClmEnsemble frozen thr report when Head A caches "
                "present. Weakest / hard folds are teaching anchors. "
                "No ECE thrash; no Tobarra KEEP reopen; fusion OFF."
            ),
        },
        "presence": {
            "lofo_root": lofo_root.is_dir(),
            "n_folds": int(summary.get("n_folds") or 0),
            "w3_external": bool(w3.get("present")),
            "head_a_caches": int(frozen_thr.get("n_cache_folds") or 0),
            "frozen_thr_report": frozen_ok,
        },
    }


def format_lofo_board_human(pack: dict[str, Any]) -> str:
    s = pack.get("summary") or {}
    h = pack.get("holdout_reference") or {}
    rails = pack.get("rails") or {}
    mf = pack.get("multi_fire_honesty") or {}
    ft = pack.get("frozen_thr_report") or {}
    ft_sum = ft.get("summary") if isinstance(ft.get("summary"), dict) else {}
    w3 = mf.get("w3_external_on_disk") or mf.get("w3_external") or {}
    if isinstance(w3, dict) and "fires" in w3 and "n_fires" not in w3:
        # facade as_dict shape: {"fires": [...], "role": ...}
        w3_fires = list(w3.get("fires") or [])
        w3_n = len(w3_fires)
    else:
        w3_fires = list(w3.get("fires") or []) if isinstance(w3, dict) else []
        w3_n = int(w3.get("n_fires", len(w3_fires)) if isinstance(w3, dict) else 0)
    lines = [
        "ML lab LOFO multi-fire board (mask IoU — not U1 ECE / not field)",
        f"  banner:              {pack.get('banner')}",
        f"  product:             {pack.get('product_id')}",
        f"  product_rail:        {rails.get('product_rail')} vs {rails.get('ops_rail') or rails.get('field_rail')}",
        f"  ml_product_go:       {rails.get('ml_product_go')}",
        "  field_ops fusion:    OFF",
        f"  recommended surface: {rails.get('recommended_lab_surface')}",
        f"  locked reject thr:   {_fmt(rails.get('locked_reject_thr'))}",
        f"  val_only thr tune:   {rails.get('val_only_threshold_tune') or rails.get('val_only_threshold_selection')}",
        f"  pipeline:            {pack.get('pipeline') or _PIPELINE}",
        f"  facade:              {pack.get('facade_class') or _FACADE_CLASS}",
        "",
        "Holdout vs LOFO (different protocols — LOFO ≠ U1 ECE)",
        f"  U1 mean IoU:         {_fmt(h.get('u1_test_mean_iou'))}",
        f"  U1 ECE:              {_fmt(h.get('u1_ece'))}",
        f"  LOFO mean IoU:       {_fmt(s.get('model_iou_mean'))}  (n={s.get('n_folds')})",
        f"  LOFO std / spread:   {_fmt(s.get('model_iou_std'))} / {_fmt(s.get('spread_max_minus_min'))}",
        f"  gap U1−LOFO:         {_fmt(h.get('gap_u1_minus_lofo_mean'))}",
        f"  note:                {h.get('generalization_note') or '—'}",
        "",
        f"  weakest:             {s.get('weakest_fold')} @ {_fmt(s.get('weakest_iou'))}",
        f"  strongest:           {s.get('strongest_fold')} @ {_fmt(s.get('strongest_iou'))}",
        f"  beats copy:          {s.get('n_beats_copy')}/{s.get('n_folds')}",
        f"  mean IoU changed:    {_fmt(s.get('model_iou_changed_mean'))}",
        f"  hard folds:          {', '.join(s.get('hard_folds') or []) or '—'}",
        f"  W3 external:         {w3_n} fires ({', '.join(w3_fires) or 'none'})",
        "",
        "Frozen thr report (ClmEnsemble / rank_reject_protocol; VAL thr freeze)",
        f"  ok:                  {ft.get('ok')}",
        f"  n cache folds:       {ft.get('n_cache_folds')}",
        f"  locked thr:          {_fmt(ft.get('locked_reject_thr'))}",
        f"  ece mean:            {_fmt(ft_sum.get('ece_mean'))}",
        f"  abstain mean:        {_fmt(ft_sum.get('locked_abstain_mean'))}",
        f"  IoU accepted mean:   {_fmt(ft_sum.get('locked_iou_accepted_mean'))}",
        "",
        "Folds",
        "  fold                      IoU    copy   Δcopy  changed  thr_spread  role",
    ]
    for r in pack.get("folds") or []:
        role = (r.get("honesty") or {}).get("role") or "—"
        lines.append(
            f"  {str(r.get('fold')):<24}  "
            f"{_fmt(r.get('model_iou'))}  "
            f"{_fmt(r.get('copy_baseline_iou'))}  "
            f"{_fmt(r.get('improvement_vs_copy_iou'))}  "
            f"{_fmt(r.get('model_iou_changed'))}  "
            f"{_fmt(r.get('thresh_iou_spread'))}  "
            f"{role}"
        )
    lines += [
        "",
        f"protocol: {(pack.get('protocol') or {}).get('honesty')}",
        "blocked:  "
        + "; ".join((pack.get("protocol") or {}).get("blocked_without_new_signal") or []),
        f"honesty: {LAB_BANNER}; LOFO ≠ U1 ECE; IoU ≠ ROS; Tobarra hard; "
        "ClmEnsemble frozen thr; fusion OFF",
        "",
    ]
    return "\n".join(lines)


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)
