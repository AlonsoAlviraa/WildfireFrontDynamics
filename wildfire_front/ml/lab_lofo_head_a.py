"""Per-fire Head A eval for LOFO / multi-fire honesty.

Sits on ``product_facade`` + ``rank_reject_protocol`` (single product path)::

    features -> production calibrator -> frozen rank/reject thr -> scorecard

Dual-product rails
------------------
* Lab ML product (``clm_ensemble_v34``) — this module.
* field_ops fusion stays **OFF**; ``ml_product_go`` default **True** (human promote 2026-08-05); never auto-flips.
* IoU != ROS (mask lab metric only).

Protocol integrity
------------------
* Shared frozen thr / rank-reject via ``product_facade`` (VAL-tuned thr only).
* Default locked thr = **iter1 reject** (~0.795); never refit on LOFO/TEST.
* Ranking family = logistic conf (iter1 reject surface).
* LOFO / held-out fire is report/scorecard/gate only — **no fit**.
* Dead thrash sealed: same-holdout ECE retune; Tobarra KEEP re-promote of KILL weights.
* Multi-fire honesty first-class (Tobarra hard, W3 external, LOFO in-pack).

Does not retrain. Does not reimplement conf math.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import numpy as np

from wildfire_front.ml.lab_reject_calibration import (
    conf_band_summary,
    metrics_at_threshold,
)
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_SCORE,
    ITER1_LOCKED_REJECT_THR,
    LEGACY_PRODUCT_ABSTAIN_THR,
    assert_lab_rails,
    confidences_from_head_a,
    features_from_diag,
    fire_honesty_tag,
)
from wildfire_front.ml.product_facade import (
    RECOMMENDED_LAB_SURFACE as _RECOMMENDED_LAB_SURFACE,
)
from wildfire_front.ml.protocol_rails import assert_split_role
from wildfire_front.ml.rank_reject_protocol import lab_rails as rank_reject_lab_rails
from wildfire_front.ml.reliability_metrics import ece_patch_conf
from wildfire_front.ml.uncertainty import LogisticCalibrator

# Product identity (aliases to shared facade constants).
DEFAULT_PRODUCT: Final = DEFAULT_PRODUCT_ID
DEFAULT_PROTOCOL: Final = "clm_lofo_fire_head_a_v1"
DEFAULT_MASK_THR: Final = 0.5
DEFAULT_TAU_IOU: Final = 0.5

# Shared frozen rank/reject protocol (VAL-only thr; freeze iter1 reject as default).
FROZEN_ITER1_REJECT_THR: Final[float] = float(ITER1_LOCKED_REJECT_THR)
DEFAULT_CALIBRATOR_THR: Final[float] = float(LEGACY_PRODUCT_ABSTAIN_THR)
RANK_FAMILY_ITER1: Final[str] = DEFAULT_RANK_SCORE  # logistic_conf
# Re-export facade surface name for callers / scripts.
RECOMMENDED_LAB_SURFACE: Final[str] = _RECOMMENDED_LAB_SURFACE
THR_SOURCE: Final[str] = "val_iter1_reject_frozen"

_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"

# LOFO-specific notes layered on product_facade fire tags (first-class multi-fire).
_LOFO_FOLD_NOTES: Final[dict[str, dict[str, str]]] = {
    "tobarra_20240802": {
        "severity": "hard",
        "note": (
            "Hard multi-fire honesty anchor (Tobarra). "
            "Reject thr lifts IoU accepted; do not re-promote KEEP thrash."
        ),
    },
    "CARDOSO": {
        "severity": "easy",
        "note": ("LOFO CARDOSO ~= holdout TEST family; not independent multi-fire gen."),
    },
    "LA_ESTRELLA_ACOM1": {
        "severity": "medium",
        "note": "In-pack Estrella ACOM1 LOFO fold.",
    },
    "LA_ESTRELLA_ACOM2": {
        "severity": "medium",
        "note": "Weakest in-pack Estrella ACOM2 LOFO fold.",
    },
    "hellin_2024": {
        "severity": "external",
        "note": "W3 external primary new-fire signal; thr/cal frozen.",
    },
    "brazatortas_2025": {
        "severity": "hard",
        "note": "W3 external hard growth; report delta vs copy.",
    },
    "retuerta_2025": {
        "severity": "hard",
        "note": "W3 external hard probe; thr/cal frozen.",
    },
}


def multi_fire_honesty_for(fold: str | None) -> dict[str, str]:
    """Return honesty tag for a LOFO / W3 fire id (first-class multi-fire surface).

    Delegates role / board mapping to ``product_facade.fire_honesty_tag``; LOFO
    fold notes are thin overlays only (no second honesty catalog).
    """
    if not fold:
        return {
            "role": "unknown_fire",
            "severity": "unknown",
            "note": "Fold id not provided; treat as held-out fire report-only.",
        }
    key = str(fold)
    tag = fire_honesty_tag(key)
    role = str(tag.get("role") or "held_out_fire")

    # Prefer exact / canonical note overlays; fall back via facade role + substring.
    overlay: dict[str, str] | None = _LOFO_FOLD_NOTES.get(key)
    if overlay is None:
        low = key.lower()
        if "tobarra" in low:
            overlay = _LOFO_FOLD_NOTES["tobarra_20240802"]
        elif "hellin" in low:
            overlay = _LOFO_FOLD_NOTES["hellin_2024"]
        elif "brazatortas" in low:
            overlay = _LOFO_FOLD_NOTES["brazatortas_2025"]
        elif "retuerta" in low:
            overlay = _LOFO_FOLD_NOTES["retuerta_2025"]
        elif key.upper() == "CARDOSO" or key.upper().startswith("CARDOSO"):
            overlay = _LOFO_FOLD_NOTES["CARDOSO"]

    if overlay is not None:
        severity = overlay["severity"]
        note = overlay["note"]
    elif role == "hard_transfer":
        severity = "hard"
        note = "Hard multi-fire honesty anchor. Do not re-promote KEEP thrash / KILL weights."
    elif role == "external_probe":
        severity = "external"
        note = "W3 external probe; thr/cal frozen from VAL; report-only."
    elif role == "easy_in_pack":
        severity = "easy"
        note = str(tag.get("note") or DEFAULT_MULTI_FIRE.cardoso_lofo_note)
    else:
        severity = "unknown"
        note = f"Held-out fire {key!r}: frozen thr report only; no LOFO fit."

    out: dict[str, str] = {
        "role": role if role != "in_pack_or_unknown" else "held_out_fire",
        "severity": severity,
        "note": note,
    }
    if tag.get("board"):
        out["board"] = str(tag["board"])
    if tag.get("keep_reopen") is False:
        out["keep_reopen"] = "false"
    if tag.get("frozen_eval_only"):
        out["frozen_eval_only"] = "true"
    return out


def lab_product_rails() -> dict[str, Any]:
    """Immutable lab rails snapshot via product_facade (fusion OFF; human-promoted GO; no auto-flip)."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    # rank_reject_protocol dual-product rails (shared lab surface).
    base.update(rank_reject_lab_rails())
    base.update(
        {
            "fit_on_lofo": False,
            "test_never_used_for_tune": True,
            "no_ece_retune_same_holdout": True,
            "label": "lab / research_open only",
            "field_ops_ml_live_fusion": "OFF",
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "forbidden_thrash": sorted(DEAD_PATHS),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(FROZEN_ITER1_REJECT_THR),
        }
    )
    return base


def frozen_rank_reject_protocol(
    *,
    locked_thr: float | None = None,
    default_thr: float | None = None,
) -> dict[str, Any]:
    """Describe the shared frozen thr / rank-reject protocol (no LOFO fit).

    Constants and rails come from ``product_facade`` / ``rank_reject_protocol``;
    this is LOFO scorecard metadata only — never a second conf implementation.
    """
    thr_lock = float(FROZEN_ITER1_REJECT_THR) if locked_thr is None else float(locked_thr)
    thr_def = float(DEFAULT_CALIBRATOR_THR) if default_thr is None else float(default_thr)
    return {
        "name": DEFAULT_PROTOCOL,
        "product_id": DEFAULT_PRODUCT,
        "rank_family": RANK_FAMILY_ITER1,
        "locked_reject_thr": thr_lock,
        "default_thr": thr_def,
        "thr_source": THR_SOURCE,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "fit_on_eval_split": False,
        "split_role": "lofo",
        "allowed_actions": ["report", "stress", "scorecard", "gate"],
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "dead_paths": sorted(DEAD_PATHS),
        "honesty": (
            "Head A confidences from production calibrator on held-out fire "
            "patches via product_facade. Rank/reject thr is frozen from VAL "
            "iter1 reject — never refit on LOFO/TEST/new-fire."
        ),
    }


def eval_rank_reject_frozen(
    cal: LogisticCalibrator,
    features: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    *,
    locked_thr: float | None = None,
    default_thr: float | None = None,
    fold: str | None = None,
    split: str = "lofo",
) -> dict[str, Any]:
    """Shared frozen protocol: features -> cal conf -> rank/reject metrics.

    Confidences route through ``product_facade.confidences_from_head_a`` (single
    product path). Never fits calibrator, temperature, or thr on the eval split.
    ``split`` must be report-only (lofo / test); VAL tune stays elsewhere.
    """
    assert_split_role(str(split), "scorecard")
    thr_lock = float(FROZEN_ITER1_REJECT_THR) if locked_thr is None else float(locked_thr)
    thr_def = float(DEFAULT_CALIBRATOR_THR) if default_thr is None else float(default_thr)
    feats = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    iou = np.asarray(ious, dtype=np.float64)
    # Single product path: product_facade conf (not local confidences_from_features).
    conf = confidences_from_head_a(cal, feats)
    ece = float(ece_patch_conf(conf, y))
    m_def = metrics_at_threshold(conf, y, iou, thr=thr_def)
    m_lock = metrics_at_threshold(conf, y, iou, thr=thr_lock)
    band = conf_band_summary(conf)
    return {
        "n_patches": int(feats.shape[0]),
        "mean_iou": float(np.mean(iou)) if iou.size else float("nan"),
        "ece_full": ece,
        "conf_band": band,
        "thr_default": m_def,
        "thr_locked": m_lock,
        "rank_family": RANK_FAMILY_ITER1,
        "locked_thr": thr_lock,
        "default_thr": thr_def,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "protocol": frozen_rank_reject_protocol(locked_thr=thr_lock, default_thr=thr_def),
        "rails": lab_product_rails(),
        "multi_fire_honesty": multi_fire_honesty_for(fold),
        "fold": fold,
    }


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def list_lofo_folds(lofo_patches_root: Path) -> list[str]:
    if not lofo_patches_root.is_dir():
        return []
    names: list[str] = []
    for d in sorted(p for p in lofo_patches_root.iterdir() if p.is_dir()):
        if (d / "test").is_dir():
            names.append(d.name)
    return names


def fold_test_dir(lofo_patches_root: Path, fold: str) -> Path:
    return lofo_patches_root / fold / "test"


def fold_cache_path(lofo_out_root: Path, fold: str) -> Path:
    return lofo_out_root / fold / "head_a_features.npz"


def build_fold_head_a_cache(
    *,
    fold: str,
    test_dir: Path,
    out_path: Path,
    predictor: Any,
    product_id: str = DEFAULT_PRODUCT,
    protocol: str = DEFAULT_PROTOCOL,
    mask_threshold: float = DEFAULT_MASK_THR,
    tau_iou: float = DEFAULT_TAU_IOU,
    max_patches: int = 0,
    progress_every: int = 25,
) -> dict[str, Any]:
    """Run ensemble Head A extraction on fold test NPZs; write cache.

    Cache is **fit_split=lofo_test** — never use for calibrator/thr fit.
    Features via ``product_facade.features_from_diag`` (single entry point).
    """
    from wildfire_front.ml.ndws_metrics import evaluate_sample

    # Building features is report-side extraction, not a tune action.
    assert_split_role("lofo", "report")

    paths = sorted(test_dir.glob("*.npz"))
    if max_patches and max_patches > 0:
        paths = paths[: int(max_patches)]

    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    ious: list[float] = []
    skipped = 0

    for i, path in enumerate(paths):
        with np.load(path) as data:
            if "target_fire" not in data.files:
                skipped += 1
                continue
            seq = data["sequence"]
            current_fire = data["current_fire"]
            target_fire = data["target_fire"]
        pred = predictor.predict_with_uncertainty(
            seq,
            current_fire,
            threshold=float(mask_threshold),
            product_id=product_id,
            protocol=protocol,
        )
        sample = evaluate_sample(
            pred.prob, current_fire, target_fire, threshold=float(mask_threshold)
        )
        iou = float(sample["model_full"].iou)
        y = 1 if iou >= float(tau_iou) else 0
        feature_rows.append(features_from_diag(pred.diagnostics))
        labels.append(y)
        ious.append(iou)
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  [{fold}] patches {i + 1}/{len(paths)}", flush=True)

    if not feature_rows:
        return {
            "fold": fold,
            "ok": False,
            "n_patches": 0,
            "skipped": skipped,
            "path": str(out_path),
            "error": "no patches with target_fire",
            "multi_fire_honesty": multi_fire_honesty_for(fold),
            "rails": lab_product_rails(),
            "product_facade": _FACADE,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        features=np.stack(feature_rows, axis=0),
        labels=np.asarray(labels, dtype=np.int64),
        ious=np.asarray(ious, dtype=np.float64),
        fit_split=np.asarray("lofo_test"),  # never use for fit
        product_id=np.asarray(str(product_id)),
        protocol=np.asarray(str(protocol)),
        fold=np.asarray(str(fold)),
        test_dir=np.asarray(str(test_dir.resolve())),
        n_patches=np.asarray(len(labels), dtype=np.int64),
        mask_threshold=np.asarray(float(mask_threshold)),
        tau_iou=np.asarray(float(tau_iou)),
    )
    return {
        "fold": fold,
        "ok": True,
        "n_patches": len(labels),
        "skipped": skipped,
        "path": str(out_path.as_posix()),
        "mean_iou": float(np.mean(ious)),
        "positive_rate": float(np.mean(labels)),
        "multi_fire_honesty": multi_fire_honesty_for(fold),
        "rails": lab_product_rails(),
        "fit_split": "lofo_test",
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "note": "Cache for frozen rank/reject eval only; do not fit thr/cal here.",
    }


def load_head_a_cache(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as z:
        out: dict[str, Any] = {
            "features": np.asarray(z["features"], dtype=np.float64),
            "labels": np.asarray(z["labels"], dtype=np.float64),
            "ious": np.asarray(z["ious"], dtype=np.float64),
        }
        if "fold" in z.files:
            try:
                out["fold"] = str(z["fold"].item() if hasattr(z["fold"], "item") else z["fold"])
            except (ValueError, AttributeError):
                out["fold"] = str(z["fold"])
        return out


def eval_fold_with_calibrator(
    cache_path: Path,
    cal: LogisticCalibrator,
    *,
    locked_thr: float | None = None,
    default_thr: float | None = None,
    fold: str | None = None,
) -> dict[str, Any]:
    """Frozen per-fire Head A eval via product_facade rank/reject (no LOFO fit).

    Defaults: locked thr = iter1 reject (``FROZEN_ITER1_REJECT_THR``),
    default thr = legacy product calibrator thr (``DEFAULT_CALIBRATOR_THR``).
    """
    data = load_head_a_cache(cache_path)
    fold_id = fold or (str(data["fold"]) if data.get("fold") else None)
    if fold_id is None:
        # Best-effort: parent dir name is the LOFO fold when path is .../fold/head_a_features.npz
        try:
            fold_id = cache_path.parent.name
        except Exception:  # noqa: BLE001
            fold_id = None
    ev = eval_rank_reject_frozen(
        cal,
        data["features"],
        data["labels"],
        data["ious"],
        locked_thr=locked_thr,
        default_thr=default_thr,
        fold=fold_id,
        split="lofo",
    )
    ev["cache"] = str(cache_path.as_posix())
    return ev


def summarize_lofo_head_a_evals(
    fold_evals: dict[str, dict[str, Any]],
    *,
    holdout_ece: float | None = None,
    holdout_iou: float | None = None,
) -> dict[str, Any]:
    """Aggregate multi-fire Head A honesty surface (frozen thr, no LOFO fit)."""
    if not fold_evals:
        return {
            "n_folds": 0,
            "rails": lab_product_rails(),
            "protocol": frozen_rank_reject_protocol(),
            "multi_fire_honesty_surface": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
        }
    eces = [float(v["ece_full"]) for v in fold_evals.values()]
    ious = [float(v["mean_iou"]) for v in fold_evals.values()]
    abs_rates = [float(v["thr_locked"]["abstain_rate"]) for v in fold_evals.values()]
    iou_acc = [
        float(v["thr_locked"]["mean_iou_accepted"])
        for v in fold_evals.values()
        if np.isfinite(v["thr_locked"].get("mean_iou_accepted", float("nan")))
    ]
    mean_ece = sum(eces) / len(eces)

    per_fire: dict[str, Any] = {}
    hard_fires: list[str] = []
    for name, v in fold_evals.items():
        hon = v.get("multi_fire_honesty") or multi_fire_honesty_for(name)
        per_fire[name] = {
            "mean_iou": float(v["mean_iou"]),
            "ece_full": float(v["ece_full"]),
            "abstain_locked": float(v["thr_locked"]["abstain_rate"]),
            "iou_accepted_locked": v["thr_locked"].get("mean_iou_accepted"),
            "honesty": hon,
        }
        if str(hon.get("severity") or "") == "hard":
            hard_fires.append(name)

    weakest = min(fold_evals.items(), key=lambda kv: float(kv[1]["mean_iou"]))
    return {
        "n_folds": len(fold_evals),
        "ece_mean": mean_ece,
        "ece_std": float(np.std(eces)),
        "ece_min": min(eces),
        "ece_max": max(eces),
        "mean_iou_mean": sum(ious) / len(ious),
        "locked_abstain_mean": sum(abs_rates) / len(abs_rates),
        "locked_iou_accepted_mean": (sum(iou_acc) / len(iou_acc) if iou_acc else None),
        "holdout_ece": holdout_ece,
        "holdout_iou": holdout_iou,
        "ece_vs_holdout_delta": (
            mean_ece - float(holdout_ece) if holdout_ece is not None else None
        ),
        "worse_ece_than_holdout": (
            bool(mean_ece > float(holdout_ece) + 0.01) if holdout_ece is not None else None
        ),
        "weakest_fold": weakest[0],
        "weakest_mean_iou": float(weakest[1]["mean_iou"]),
        "hard_fires": hard_fires,
        "per_fire": per_fire,
        "multi_fire_honesty_surface": True,
        "protocol": frozen_rank_reject_protocol(),
        "rails": lab_product_rails(),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "note": (
            "Multi-fire Head A honesty via product_facade: frozen iter1 reject thr; "
            "no thr/ECE fit on LOFO; Tobarra hard; CARDOSO!=independent gen; "
            "field fusion OFF."
        ),
    }
