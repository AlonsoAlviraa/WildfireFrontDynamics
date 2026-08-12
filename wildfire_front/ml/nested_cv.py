"""VAL-only nested CV — calibrator-fit stage of the product facade path.

Product ROI architecture (lab ML rail; no retrain)
--------------------------------------------------
Single product path (orchestration in ``product_facade``)::

    features → calibrator (this module: VAL nested fit) → conf
      → rank/reject thr (``rank_reject_protocol.select_thr_val_only``)
      → scorecard

Authority split (no parallel thr path)
--------------------------------------
* **This module** — VAL nested **calibrator** fit / L2 / logistic ECE diagnostics
  only (``val_nested_fit``). Never retunes reject thr on TEST / LOFO / external.
* **rank_reject_protocol.select_thr_val_only** — sole VAL thr selection for
  reject / CRC-lite (not reimplemented here).
* **product_facade** — dual rails + default surface freeze **iter1_reject_only**
  (locked thr ≈ 0.795); ``ml_product_go`` true; field fusion **OFF**; IoU ≠ ROS.
* Multi-fire honesty first-class (Tobarra hard KILL; W3 external / LOFO
  report-only with frozen thr/cal).
* Dead thrash closed: same-holdout ECE retune; Tobarra KEEP reopen of KILL weights.

Protocol rails
--------------
* Only callable with ``SplitContext(split='val', action in
  {'fit_uncertainty','calibrate'})``.
* Never accepts test / lofo / external context for fit. Nested metrics are lab
  diagnostics on VAL; fusion promote still requires frozen-calibrator U1 on
  **TEST** (report only).

Two-stage preferred protocol (honesty protocol **b**)
-----------------------------------------------------
1. ``val_nested_fit_eval`` → ``nested_val_ece_mean`` is **logistic-only** ECE on
   outer folds (outer never used for that fold's logistic fit, and **never** used
   for Platt/temperature inside nested scoring).
2. Final calibrator (fit script): logistic on VAL-inner + optional temperature/Platt
   on a **post-nested** VAL outer holdout (or full-VAL logistic if second_stage=none).
3. Reject thr via ``select_thr_val_only`` (VAL only) or frozen iter1 surface from
   ``product_facade``; evaluate on TEST / LOFO / W3 frozen — never fit thr/cal there.

``second_stage`` on nested is retained only as a **label of intended final-fit
post-hoc**; it does **not** change nested outer scoring (avoids same-outer optimism).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from wildfire_front.ml.product_facade import (
    DEAD_PATHS as FACADE_DEAD_PATHS,
)
from wildfire_front.ml.product_facade import (
    DEFAULT_MULTI_FIRE,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    MULTI_FIRE_HONESTY,
    THR_TUNE_SPLIT,
    ProtocolRailError,
    SplitContext,
    assert_not_forbidden_thrash,
    assert_split_context,
    multi_fire_honesty_dict,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEFAULT_REJECT_THR,
    LOCKED_ITER1_THR,
    frozen_thr_from_val_selection,
    protocol_payload,
    select_thr_val_only,
)
from wildfire_front.ml.rank_reject_protocol import (
    lab_rails as protocol_lab_rails,
)
from wildfire_front.ml.rank_reject_protocol import (
    multi_fire_honesty as protocol_multi_fire_honesty,
)
from wildfire_front.ml.reliability_metrics import (
    ece_patch_conf,
    selective_beats_random,
    selective_iou_at_coverage,
)
from wildfire_front.ml.uncertainty import (
    LogisticCalibrator,
    fit_logistic_calibrator,
    fit_platt_on_logits,
    fit_temperature_on_logits,
    predict_proba_rows,
)

DEFAULT_L2_GRID: tuple[float, ...] = (1e-3, 1e-2, 5e-2, 1e-1, 5e-1, 1.0)
DEFAULT_N_FOLDS = 5
DEFAULT_SEED = 42

# Pipeline module ids (single path — not parallel thr authority).
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT: Final = "wildfire_front.ml.rank_reject_protocol"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"

# Nested VAL fit = calibrator hyperparam / ECE authority only (not reject thr).
NESTED_FIT_AUTHORITY: Final = "val_nested_fit"
# Reject thr authority is shared protocol (VAL-only); surface freeze is facade.
THR_SELECT_AUTHORITY: Final = "rank_reject_protocol.select_thr_val_only"
# Back-compat alias: cal fit + thr both VAL-only; thr math is select_thr_val_only.
THR_CALIBRATE_SPLIT: Final = THR_TUNE_SPLIT  # always "val"
LOCKED_REJECT_THR: Final = float(ITER1_LOCKED_REJECT_THR)  # facade / protocol freeze
RECOMMENDED_SURFACE: Final = str(RECOMMENDED_LAB_SURFACE)  # iter1_reject_only
ALLOWED_NESTED_ACTIONS: Final[frozenset[str]] = frozenset({"fit_uncertainty", "calibrate"})
# Splits that may only *report* frozen thr/cal — never nest-fit or retune.
REPORT_ONLY_SPLITS: Final[frozenset[str]] = frozenset({"test", "lofo", "external"})

HONEST_NESTED_ECE_NOTE = (
    "nested_val_ece_mean is logistic-only ECE on outer folds "
    "(outer never used for that fold's logistic fit; second_stage not fit on outer). "
    "Platt/temperature is fit only post-nested on a VAL outer holdout for the final "
    "calibrator. Reject thr is rank_reject_protocol.select_thr_val_only (VAL only) "
    "or product_facade iter1_reject_only freeze — never retune thr/cal on "
    "TEST/LOFO/external; promote requires u1_test_honest on frozen cal."
)

# Explicitly closed via this stage (facade + protocol_rails + nested fit seals).
NESTED_DEAD_PATHS: Final[frozenset[str]] = (
    frozenset(FORBIDDEN_THRASH_PATHS)
    | frozenset(FACADE_DEAD_PATHS)
    | frozenset(
        {
            "same_holdout_ece_retune",
            "ece_posthoc_same_test",
            "nested_fit_on_test",
            "nested_fit_on_lofo",
            "nested_fit_on_external",
            "lofo_thr_retune",
            "test_thr_retune",
            "tobarra_keep_reopen_kill_weights",
            "tobarra_keep_reopen_same_recipe",
            "ml_product_go_auto_flip",
            "field_ops_fusion_auto_on",
            "auto_ml_product_go",
            "field_ops_ml_live_fusion_on",
        }
    )
)


def nested_protocol_rails() -> dict[str, Any]:
    """Canonical dual-product rails via product_facade (nested cal-fit stage).

    Reject thr selection is **not** owned here — see
    ``rank_reject_protocol.select_thr_val_only`` / ``protocol_payload``.
    Surface freeze is product_facade ``iter1_reject_only``.
    """
    r = assert_lab_rails(DEFAULT_RAILS)
    base = r.as_dict()
    thr = float(LOCKED_REJECT_THR)
    base.update(
        {
            "banner": LAB_ML_BANNER,
            "product_rail": "lab_ml",
            "ops_rail": "field_ops",
            "iou_is_not_ros": True,
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            # Calibrator fit authority (this module); thr select is rank_reject.
            "calibrate_authority": NESTED_FIT_AUTHORITY,
            "thr_select_authority": THR_SELECT_AUTHORITY,
            "thr_calibrate_authority": NESTED_FIT_AUTHORITY,  # cal-fit; thr via select
            "thr_calibrate_split": THR_CALIBRATE_SPLIT,
            "val_only_threshold_selection": True,
            "recommended_lab_surface": RECOMMENDED_SURFACE,
            "locked_reject_thr": thr,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen_forbidden": True,
            "report_only_splits": sorted(REPORT_ONLY_SPLITS),
            "dead_paths": sorted(NESTED_DEAD_PATHS),
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT,
            "rank_reject": protocol_payload(locked_reject_thr=thr),
            "rank_reject_config": DEFAULT_RANK_REJECT.as_dict(),
            "protocol_lab_rails": protocol_lab_rails(),
            "multi_fire_honesty": {
                **multi_fire_honesty_dict(),
                **protocol_multi_fire_honesty(),
                **DEFAULT_MULTI_FIRE.as_dict(),
            },
        }
    )
    return base


def select_reject_thr_val_only(
    conf: np.ndarray | Sequence[float],
    ious: np.ndarray | Sequence[float],
    *,
    risk_alpha: float = 0.15,
    thr_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    """VAL-only reject thr — delegates to rank_reject_protocol (no parallel thr).

    Nested CV does **not** retune thr on outer folds. Call this after a frozen
    (or final VAL-fit) calibrator produces confidences, or use the product
    facade surface freeze thr (``LOCKED_REJECT_THR`` / iter1_reject_only).
    """
    return select_thr_val_only(
        np.asarray(conf, dtype=np.float64),
        np.asarray(ious, dtype=np.float64),
        risk_alpha=risk_alpha,
        thr_grid=thr_grid,
        split="val",
    )


def frozen_reject_thr_from_val(
    selection: dict[str, Any] | None = None,
    *,
    fallback: float | None = None,
) -> float:
    """Extract thr from VAL selection or default product_facade iter1 freeze."""
    fb = float(fallback) if fallback is not None else float(LOCKED_REJECT_THR)
    if selection is None:
        return fb
    return float(frozen_thr_from_val_selection(selection, fallback=fb))


def assert_no_nested_retune_on_report_split(split: str) -> None:
    """Refuse calibrator nested-fit / thr retune on test, LOFO, or external."""
    s = str(split).strip().lower()
    if s in REPORT_ONLY_SPLITS:
        raise ProtocolRailError(
            f"nested cal-fit / thr retune refused on split={split!r} "
            f"(calibrate_authority={NESTED_FIT_AUTHORITY!r}; "
            f"thr_select_authority={THR_SELECT_AUTHORITY!r}; "
            f"{s} is report-only with frozen thr/cal)"
        )
    if s != THR_CALIBRATE_SPLIT:
        raise ProtocolRailError(
            f"nested cal-fit requires split={THR_CALIBRATE_SPLIT!r}, got {split!r}"
        )


def assert_val_nested_context(split_context: SplitContext) -> None:
    """Hard rails: nested fit/eval only on VAL calibrate/fit_uncertainty.

    Calibrator-fit gate only — reject thr is ``select_thr_val_only`` (VAL) or
    facade surface freeze. No test/LOFO/external retune; no dead thrash reopen.
    """
    if not isinstance(split_context, SplitContext):
        raise TypeError("split_context must be a SplitContext instance")
    assert_split_context(split_context)
    assert_no_nested_retune_on_report_split(str(split_context.split))
    if str(split_context.split) != "val":
        raise ProtocolRailError(
            f"val_nested_fit_eval only allows split=val, got {split_context.split!r} "
            "(never nested-fit on test/lofo/external; cal-fit is VAL-only; "
            "thr is rank_reject_protocol.select_thr_val_only or facade freeze)"
        )
    if str(split_context.action) not in ALLOWED_NESTED_ACTIONS:
        raise ProtocolRailError(
            f"val_nested_fit_eval requires action in "
            f"{sorted(ALLOWED_NESTED_ACTIONS)!r}, got {split_context.action!r}"
        )
    # Close dead thrash ids if a caller smuggles them as protocol labels.
    proto = str(getattr(split_context, "protocol", "") or "")
    if proto:
        key = proto.strip().lower().replace("-", "_").replace(" ", "_")
        if key in NESTED_DEAD_PATHS:
            try:
                refuse_dead_path(key)
            except ProductFacadeError as exc:
                raise ProtocolRailError(str(exc)) from exc
            assert_not_forbidden_thrash(key)


def _nested_authority_block() -> dict[str, Any]:
    """Compact authority + facade/protocol surface for metrics / provenance."""
    mf = MULTI_FIRE_HONESTY
    facade_mf = DEFAULT_MULTI_FIRE.as_dict()
    thr = float(LOCKED_REJECT_THR)
    return {
        "calibrate_authority": NESTED_FIT_AUTHORITY,
        "thr_select_authority": THR_SELECT_AUTHORITY,
        # Back-compat: cal-fit authority name (thr is select_thr_val_only).
        "thr_calibrate_authority": NESTED_FIT_AUTHORITY,
        "thr_calibrate_split": THR_CALIBRATE_SPLIT,
        "val_only": True,
        "no_test_lofo_retune": True,
        "second_stage_in_nested_scoring": False,
        "recommended_lab_surface": RECOMMENDED_SURFACE,
        "locked_reject_thr": thr,
        "default_reject_thr": float(DEFAULT_REJECT_THR),
        "locked_iter1_thr": float(LOCKED_ITER1_THR),
        "ml_product_go": True,
        "field_ops_ml_live_fusion": "OFF",
        "iou_is_not_ros": True,
        "banner": LAB_ML_BANNER,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": _RANK_REJECT,
        "rank_reject_config": DEFAULT_RANK_REJECT.as_dict(),
        "dead_paths_closed": True,
        "multi_fire": {
            "tobarra_class": (mf.get("tobarra") or {}).get("class")
            or (facade_mf.get("tobarra") or {}).get("role"),
            "tobarra_verdict": (mf.get("tobarra") or {}).get("verdict")
            or facade_mf.get("tobarra_keep_verdict")
            or "KILL",
            "w3_role": (mf.get("w3_external") or {}).get("role") or facade_mf.get("w3_role"),
            "w3_frozen_thr_and_cal": True,
            "lofo_first_class": True,
        },
    }


def make_kfold_indices(
    n: int,
    n_folds: int = DEFAULT_N_FOLDS,
    *,
    seed: int = DEFAULT_SEED,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return list of (train_idx, outer_idx) arrays for K-fold.

    Uses a single shuffle then contiguous blocks (not label-stratified) for
    determinism without sklearn. Callers with severe imbalance should pass
    ``class_weight=True`` into the logistic fit.
    """
    if n <= 0:
        return []
    k = int(n_folds)
    if k < 2:
        raise ValueError(f"n_folds must be >= 2, got {n_folds}")
    if n < k:
        k = max(2, n) if n >= 2 else 2
        if n < 2:
            return []
    gen = np.random.default_rng(int(seed))
    order = gen.permutation(n)
    folds: list[np.ndarray] = []
    sizes = [n // k] * k
    for i in range(n % k):
        sizes[i] += 1
    start = 0
    for sz in sizes:
        folds.append(order[start : start + sz])
        start += sz
    pairs: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(k):
        outer = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        pairs.append((train.astype(np.int64), outer.astype(np.int64)))
    return pairs


def make_holdout_indices(
    n: int,
    *,
    inner_frac: float = 0.7,
    seed: int = DEFAULT_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """Single 70/30-style split: (inner_fit_idx, outer_calibrate_idx)."""
    if n < 2:
        idx = np.arange(n, dtype=np.int64)
        return idx, idx
    frac = float(inner_frac)
    if not (0.05 < frac < 0.95):
        raise ValueError(f"inner_frac must be in (0.05, 0.95), got {inner_frac}")
    gen = np.random.default_rng(int(seed))
    order = gen.permutation(n)
    n_inner = max(1, min(n - 1, int(round(frac * n))))
    return order[:n_inner].astype(np.int64), order[n_inner:].astype(np.int64)


def _select_l2_on_inner(
    X_inner: np.ndarray,
    y_inner: np.ndarray,
    *,
    split_context: SplitContext,
    l2_grid: Sequence[float],
    n_iter: int,
    class_weight: bool,
    seed: int,
    val_frac: float = 0.25,
) -> tuple[float, float]:
    """Pick L2 by min ECE on a mini-holdout of the inner train fold only."""
    n = X_inner.shape[0]
    if n < 4 or not l2_grid:
        return float(l2_grid[0]) if l2_grid else 1e-2, float("nan")
    gen = np.random.default_rng(int(seed))
    order = gen.permutation(n)
    n_fit = max(2, int(round((1.0 - val_frac) * n)))
    n_fit = min(n_fit, n - 1)
    fit_idx, hold_idx = order[:n_fit], order[n_fit:]
    best_l2 = float(l2_grid[0])
    best_ece = float("inf")
    for l2 in l2_grid:
        cal = fit_logistic_calibrator(
            [X_inner[i] for i in fit_idx],
            [float(y_inner[i]) for i in fit_idx],
            split_context=split_context,
            l2=float(l2),
            n_iter=int(n_iter),
            class_weight=bool(class_weight),
        )
        confs = predict_proba_rows(cal, [X_inner[i] for i in hold_idx])
        ece = ece_patch_conf(confs, [float(y_inner[i]) for i in hold_idx], n_bins=10)
        if np.isfinite(ece) and ece < best_ece:
            best_ece = float(ece)
            best_l2 = float(l2)
    return best_l2, best_ece if np.isfinite(best_ece) else float("nan")


def apply_second_stage(
    cal: LogisticCalibrator,
    X_outer: Sequence[np.ndarray],
    y_outer: Sequence[float],
    *,
    second_stage: str,
) -> LogisticCalibrator:
    """Fit temperature or Platt on outer logits (post-nested final-fit only).

    **Not** used inside nested outer scoring (protocol b).
    """
    stage = str(second_stage or "none").lower()
    if stage in ("", "none", "off"):
        return cal
    logits = []
    for row in X_outer:
        x = np.asarray(row, dtype=np.float64).ravel()
        if cal.weights.size == x.size + 1:
            logits.append(float(np.dot(cal.weights[:-1], x) + cal.weights[-1]))
        else:
            logits.append(0.0)
    y = np.asarray(y_outer, dtype=np.float64).ravel()
    if stage == "temperature":
        t = fit_temperature_on_logits(logits, y)
        return cal.with_temperature(t)
    if stage == "platt":
        a, b = fit_platt_on_logits(logits, y)
        return cal.with_platt(a, b)
    raise ValueError(f"unknown second_stage {second_stage!r}; use none|temperature|platt")


# Back-compat alias
_apply_second_stage = apply_second_stage


def val_nested_fit_eval(
    feature_rows: Sequence[np.ndarray],
    labels: Sequence[int | float | bool],
    *,
    split_context: SplitContext,
    ious: Sequence[float] | None = None,
    n_folds: int = DEFAULT_N_FOLDS,
    seed: int = DEFAULT_SEED,
    l2_grid: Sequence[float] | None = None,
    n_iter: int = 800,
    class_weight: bool = True,
    second_stage: str = "none",
    coverage: float = 0.8,
    n_bins: int = 10,
) -> dict[str, Any]:
    """K-fold nested protocol on VAL features only (no weights / no TEST).

    For each fold (honest nested ECE protocol **b**):
      * optionally select L2 on an inner mini-holdout of the train fold
      * fit logistic Head A on train fold **only**
      * score ECE / selective U1 on outer fold with **raw logistic** confidences
      * **do not** fit temperature/Platt on the outer fold used for scoring

    ``second_stage`` is recorded as the *intended* final-fit post-hoc method only
    (fit script applies it post-nested on a VAL outer holdout). Nested metrics
    remain logistic-only so hyperparam selection is not biased by same-outer
    second-stage optimism.

    Returns metrics including ``nested_val_ece_mean`` (= logistic outer ECE),
    ``nested_logistic_ece_mean`` (alias), fold details, and ``recommended_l2``.
    """
    assert_val_nested_context(split_context)

    X = [np.asarray(r, dtype=np.float64).ravel() for r in feature_rows]
    y = np.asarray([(1.0 if float(v) >= 0.5 else 0.0) for v in labels], dtype=np.float64)
    n = len(X)
    stage_label = str(second_stage or "none")
    if n == 0 or n != y.size:
        return {
            "k": int(n_folds),
            "n_patches": n,
            "nested_val_ece_mean": float("nan"),
            "nested_val_ece_std": float("nan"),
            "nested_logistic_ece_mean": float("nan"),
            "mean_ece": float("nan"),
            "mean_u1b": float("nan"),
            "folds": [],
            "recommended_l2": 1e-2,
            "second_stage": stage_label,
            "second_stage_in_nested_scoring": False,
            "protocol_note": "empty feature matrix",
            "honesty": HONEST_NESTED_ECE_NOTE,
            "authority": _nested_authority_block(),
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT,
            "recommended_lab_surface": RECOMMENDED_SURFACE,
            "locked_reject_thr": float(LOCKED_REJECT_THR),
        }

    grid = tuple(float(x) for x in (l2_grid if l2_grid is not None else DEFAULT_L2_GRID))
    pairs = make_kfold_indices(n, n_folds=n_folds, seed=seed)
    iou_arr = (
        np.asarray(ious, dtype=np.float64).ravel() if ious is not None and len(ious) == n else None
    )

    fold_metrics: list[dict[str, Any]] = []
    eces: list[float] = []
    u1bs: list[float] = []
    u1as: list[float] = []
    l2s: list[float] = []
    pooled_outer_logits: list[float] = []
    pooled_outer_y: list[float] = []

    for fold_i, (tr, te) in enumerate(pairs):
        X_tr = [X[i] for i in tr]
        y_tr = [float(y[i]) for i in tr]
        X_te = [X[i] for i in te]
        y_te = [float(y[i]) for i in te]

        l2_sel, l2_inner_ece = _select_l2_on_inner(
            np.stack(X_tr, axis=0),
            np.asarray(y_tr, dtype=np.float64),
            split_context=split_context,
            l2_grid=grid,
            n_iter=n_iter,
            class_weight=class_weight,
            seed=seed + fold_i * 17,
        )
        l2s.append(float(l2_sel))

        # Logistic only on train folds — never Platt/temp on outer (protocol b).
        cal = fit_logistic_calibrator(
            X_tr,
            y_tr,
            split_context=split_context,
            l2=float(l2_sel),
            n_iter=int(n_iter),
            class_weight=bool(class_weight),
        )
        confs = predict_proba_rows(cal, X_te)
        ece = float(ece_patch_conf(confs, y_te, n_bins=n_bins))
        eces.append(ece)

        # Collect raw outer logits for optional diagnostic (not used for nested ECE).
        for row, yi in zip(X_te, y_te, strict=False):
            x = np.asarray(row, dtype=np.float64).ravel()
            if cal.weights.size == x.size + 1:
                pooled_outer_logits.append(float(np.dot(cal.weights[:-1], x) + cal.weights[-1]))
                pooled_outer_y.append(float(yi))

        fold_doc: dict[str, Any] = {
            "fold": fold_i,
            "n_train": int(len(tr)),
            "n_outer": int(len(te)),
            "l2": float(l2_sel),
            "l2_inner_ece": float(l2_inner_ece) if np.isfinite(l2_inner_ece) else None,
            "ece": ece,
            "ece_kind": "logistic_outer",
            "second_stage_fit_on_outer": False,
            "positive_rate_outer": float(np.mean(y_te)) if y_te else None,
            "mean_confidence_outer": float(np.mean(confs)) if confs else None,
        }

        if iou_arr is not None:
            iou_te = [float(iou_arr[i]) for i in te]
            sel = selective_iou_at_coverage(iou_te, confs, coverage=coverage)
            full_mean = float(np.mean(iou_te)) if iou_te else float("nan")
            sel_iou = float(sel.get("selective_iou") or float("nan"))
            u1a = bool(np.isfinite(sel_iou) and sel_iou >= full_mean - 0.01)
            u1 = selective_beats_random(
                iou_te, confs, coverage=coverage, n_trials=40, seed=seed + fold_i, margin=0.01
            )
            u1b = bool(u1.get("beats_random"))
            u1as.append(1.0 if u1a else 0.0)
            u1bs.append(1.0 if u1b else 0.0)
            fold_doc.update(
                {
                    "selective_iou": sel_iou if np.isfinite(sel_iou) else None,
                    "full_mean_iou": full_mean if np.isfinite(full_mean) else None,
                    "u1a": u1a,
                    "u1b": u1b,
                    "delta_vs_random": u1.get("delta_vs_random"),
                }
            )
        fold_metrics.append(fold_doc)

    ece_arr = np.asarray(eces, dtype=np.float64)
    rec_l2 = float(np.median(np.asarray(l2s, dtype=np.float64))) if l2s else 1e-2
    nested_mean = float(np.nanmean(ece_arr)) if ece_arr.size else float("nan")
    nested_std = float(np.nanstd(ece_arr)) if ece_arr.size else float("nan")

    return {
        "k": len(pairs),
        "n_folds_requested": int(n_folds),
        "n_patches": n,
        "seed": int(seed),
        "l2_grid": list(grid),
        "recommended_l2": rec_l2,
        "fold_l2": l2s,
        # Intended final-fit second stage (not applied in nested scoring).
        "second_stage": stage_label,
        "second_stage_in_nested_scoring": False,
        "second_stage_note": (
            f"second_stage={stage_label!r} is for final post-nested VAL outer fit only; "
            "nested_val_ece_mean is logistic-only on outer folds."
        ),
        "n_iter": int(n_iter),
        "class_weight": bool(class_weight),
        # Canonical nested ECE = logistic outer only (protocol b).
        "nested_val_ece_mean": nested_mean,
        "nested_val_ece_std": nested_std,
        "nested_logistic_ece_mean": nested_mean,
        "nested_logistic_ece_std": nested_std,
        "mean_ece": nested_mean,
        "mean_u1a": float(np.mean(u1as)) if u1as else None,
        "mean_u1b": float(np.mean(u1bs)) if u1bs else None,
        "folds": fold_metrics,
        "n_pooled_outer_logits": len(pooled_outer_logits),
        "protocol": str(split_context.protocol),
        "split": "val",
        "action": str(split_context.action),
        "honesty": HONEST_NESTED_ECE_NOTE,
        # Unified path: nested VAL cal-fit; thr via select_thr_val_only / facade freeze.
        "authority": _nested_authority_block(),
        "rails": nested_protocol_rails(),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": _RANK_REJECT,
        "recommended_lab_surface": RECOMMENDED_SURFACE,
        "locked_reject_thr": float(LOCKED_REJECT_THR),
    }


def val_inner_outer_fit_eval(
    feature_rows: Sequence[np.ndarray],
    labels: Sequence[int | float | bool],
    *,
    split_context: SplitContext,
    ious: Sequence[float] | None = None,
    inner_frac: float = 0.7,
    seed: int = DEFAULT_SEED,
    l2: float = 1e-2,
    l2_grid: Sequence[float] | None = None,
    n_iter: int = 800,
    class_weight: bool = True,
    second_stage: str = "temperature",
    n_bins: int = 10,
    coverage: float = 0.8,
) -> dict[str, Any]:
    """Single 70/30 inner-logistic / outer-second-stage protocol on VAL.

    Metrics:
    * ``nested_val_ece_mean`` / ``outer_logistic_ece``: logistic-only ECE on outer
      (honest for logistic; used as nested-style ECE for selection)
    * ``outer_second_stage_ece``: ECE after second-stage fit **on the same outer**
      (labeled optimistic for the post-hoc stage; not nested_val_ece_mean)
    * final ``calibrator`` includes second stage for operator freeze use
    """
    assert_val_nested_context(split_context)
    X = [np.asarray(r, dtype=np.float64).ravel() for r in feature_rows]
    y = np.asarray([(1.0 if float(v) >= 0.5 else 0.0) for v in labels], dtype=np.float64)
    n = len(X)
    stage = str(second_stage or "none")
    if n == 0 or n != y.size:
        return {
            "mode": "inner_outer",
            "nested_val_ece_mean": float("nan"),
            "mean_ece": float("nan"),
            "recommended_l2": float(l2),
            "second_stage": stage,
            "honesty": HONEST_NESTED_ECE_NOTE,
            "authority": _nested_authority_block(),
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT,
            "recommended_lab_surface": RECOMMENDED_SURFACE,
            "locked_reject_thr": float(LOCKED_REJECT_THR),
        }
    inner_idx, outer_idx = make_holdout_indices(n, inner_frac=inner_frac, seed=seed)
    X_in = [X[i] for i in inner_idx]
    y_in = [float(y[i]) for i in inner_idx]
    X_out = [X[i] for i in outer_idx]
    y_out = [float(y[i]) for i in outer_idx]

    grid = tuple(float(x) for x in (l2_grid if l2_grid is not None else (float(l2),)))
    if len(grid) > 1:
        l2_sel, _ = _select_l2_on_inner(
            np.stack(X_in, axis=0),
            np.asarray(y_in, dtype=np.float64),
            split_context=split_context,
            l2_grid=grid,
            n_iter=n_iter,
            class_weight=class_weight,
            seed=seed,
        )
    else:
        l2_sel = float(grid[0])

    cal_log = fit_logistic_calibrator(
        X_in,
        y_in,
        split_context=split_context,
        l2=float(l2_sel),
        n_iter=int(n_iter),
        class_weight=bool(class_weight),
    )
    confs_log = predict_proba_rows(cal_log, X_out)
    ece_log = float(ece_patch_conf(confs_log, y_out, n_bins=n_bins))

    cal = apply_second_stage(cal_log, X_out, y_out, second_stage=stage)
    confs_ss = predict_proba_rows(cal, X_out)
    ece_ss = float(ece_patch_conf(confs_ss, y_out, n_bins=n_bins))

    out: dict[str, Any] = {
        "mode": "inner_outer",
        "inner_frac": float(inner_frac),
        "n_inner": int(len(inner_idx)),
        "n_outer": int(len(outer_idx)),
        "recommended_l2": float(l2_sel),
        "second_stage": stage,
        # Canonical nested-style ECE remains logistic-only (protocol b).
        "nested_val_ece_mean": ece_log,
        "nested_logistic_ece_mean": ece_log,
        "mean_ece": ece_log,
        "outer_logistic_ece": ece_log,
        "outer_second_stage_ece": ece_ss,
        "outer_second_stage_ece_note": (
            "outer_second_stage_ece fits and scores second_stage on the same outer "
            "holdout — diagnostic/optimistic for post-hoc only; not nested_val_ece_mean."
        ),
        "k": 1,
        "seed": int(seed),
        "second_stage_in_nested_scoring": False,
        "honesty": HONEST_NESTED_ECE_NOTE,
        "split": "val",
        "action": str(split_context.action),
        "authority": _nested_authority_block(),
        "rails": nested_protocol_rails(),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": _RANK_REJECT,
        "recommended_lab_surface": RECOMMENDED_SURFACE,
        "locked_reject_thr": float(LOCKED_REJECT_THR),
    }
    confs_for_u1 = confs_log  # U1 nested-style uses logistic confs
    if ious is not None and len(ious) == n:
        iou_out = [float(ious[i]) for i in outer_idx]
        sel = selective_iou_at_coverage(iou_out, confs_for_u1, coverage=coverage)
        full_mean = float(np.mean(iou_out))
        sel_iou = float(sel.get("selective_iou") or float("nan"))
        u1a = bool(np.isfinite(sel_iou) and sel_iou >= full_mean - 0.01)
        u1 = selective_beats_random(
            iou_out, confs_for_u1, coverage=coverage, n_trials=40, seed=seed, margin=0.01
        )
        out.update(
            {
                "mean_u1a": 1.0 if u1a else 0.0,
                "mean_u1b": 1.0 if bool(u1.get("beats_random")) else 0.0,
                "selective_iou": sel_iou if np.isfinite(sel_iou) else None,
                "delta_vs_random": u1.get("delta_vs_random"),
            }
        )
    out["calibrator"] = cal
    return out


def confidences_from_calibrator(
    cal: LogisticCalibrator,
    feature_rows: Sequence[np.ndarray],
) -> list[float]:
    """Public helper: batch confidences (used by fit/eval scripts)."""
    return predict_proba_rows(cal, feature_rows)


def nested_cv_provenance_block(nested: dict[str, Any]) -> dict[str, Any]:
    """Compact scorecard/calibrator provenance fields for nested CV.

    Stamps VAL nested **calibrator** fit authority and points thr select at
    ``rank_reject_protocol.select_thr_val_only`` + product_facade surface freeze
    so scorecards / LOFO / reject boards cannot claim test/LOFO thr retune or a
    parallel thr path.
    """
    auth = nested.get("authority")
    if not isinstance(auth, dict):
        auth = _nested_authority_block()
    thr = auth.get("locked_reject_thr", LOCKED_REJECT_THR)
    return {
        "k": nested.get("k") or nested.get("n_folds_requested"),
        "mean_ece": nested.get("mean_ece")
        if nested.get("mean_ece") is not None
        else nested.get("nested_val_ece_mean"),
        "nested_val_ece_mean": nested.get("nested_val_ece_mean"),
        "nested_val_ece_std": nested.get("nested_val_ece_std"),
        "nested_logistic_ece_mean": nested.get("nested_logistic_ece_mean")
        or nested.get("nested_val_ece_mean"),
        "mean_u1a": nested.get("mean_u1a"),
        "mean_u1b": nested.get("mean_u1b"),
        "recommended_l2": nested.get("recommended_l2"),
        "second_stage": nested.get("second_stage"),
        "second_stage_in_nested_scoring": bool(nested.get("second_stage_in_nested_scoring", False)),
        "seed": nested.get("seed"),
        "n_patches": nested.get("n_patches"),
        "mode": nested.get("mode", "kfold"),
        "honesty": nested.get("honesty") or HONEST_NESTED_ECE_NOTE,
        "calibrate_authority": auth.get("calibrate_authority", NESTED_FIT_AUTHORITY),
        "thr_select_authority": auth.get("thr_select_authority", THR_SELECT_AUTHORITY),
        "thr_calibrate_authority": auth.get("thr_calibrate_authority", NESTED_FIT_AUTHORITY),
        "thr_calibrate_split": auth.get("thr_calibrate_split", THR_CALIBRATE_SPLIT),
        "no_test_lofo_retune": bool(auth.get("no_test_lofo_retune", True)),
        "recommended_lab_surface": auth.get("recommended_lab_surface", RECOMMENDED_SURFACE),
        "locked_reject_thr": float(thr) if thr is not None else float(LOCKED_REJECT_THR),
        "pipeline": auth.get("pipeline", _PIPELINE),
        "product_facade": auth.get("product_facade", _FACADE),
        "rank_reject_protocol": auth.get("rank_reject_protocol", _RANK_REJECT),
        "authority": auth,
    }
