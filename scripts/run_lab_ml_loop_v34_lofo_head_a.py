#!/usr/bin/env python3
"""Lab ML loop iter 11: LOFO Head A caches (W1) + frozen reject/ECE eval (W2).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05; no auto-flip);
  field fusion stays **OFF**.
* Single path via ``ClmEnsembleV34Facade`` + ``rank_reject_protocol``:
  features → calibrator → conf → rank/reject (VAL thr freeze) → scorecard.
* Ranking / abstain share one protocol: VAL-only thr; freeze **iter1 reject**
  default (no conf math / dual rails in this script).
* Head A LOFO evaluates via facade rank/reject with **locked VAL thr only**
  (no per-fire retune on LOFO/TEST).
* Multi-fire honesty first-class: Tobarra hard, W3 external (not ad-hoc).
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen of KILL weights.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_lofo_head_a.py --build --max-patches 16
    python scripts/run_lab_ml_loop_v34_lofo_head_a.py --build
    python scripts/run_lab_ml_loop_v34_lofo_head_a.py   # eval only if caches exist
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_lofo_head_a import (  # noqa: E402
    DEFAULT_PRODUCT,
    fold_cache_path,
    list_lofo_folds,
    load_head_a_cache,
    load_json,
    multi_fire_honesty_for,
    summarize_lofo_head_a_evals,
)
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_SCORE,
    ITER1_LOCKED_REJECT_THR,
    LEGACY_PRODUCT_ABSTAIN_THR,
    RECOMMENDED_LAB_SURFACE,
    ClmEnsembleV34Facade,
    ProductFacadeError,
    RankRejectConfig,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    assert_rails_honest,
    assert_split_role,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)
from wildfire_front.ml.uncertainty import load_calibrator  # noqa: E402

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_RANK_REJECT_API: Final = "ClmEnsembleV34Facade.rank_reject / rank_and_reject"
_SCORECARD_API: Final = "ClmEnsembleV34Facade.scorecard"
_CONF_SOURCE: Final = "ClmEnsembleV34Facade.confidences"
# Locked VAL thr only — never retune per LOFO fire.
_LOCKED_THR: Final = float(ITER1_LOCKED_REJECT_THR)
_DEFAULT_THR: Final = float(LEGACY_PRODUCT_ABSTAIN_THR)


def _strip_arrays(surface: dict[str, Any]) -> dict[str, Any]:
    """Drop large array fields from rank/reject surface for JSON payloads."""
    return {
        k: v
        for k, v in surface.items()
        if k not in ("keep_mask", "conf") and not isinstance(v, np.ndarray)
    }


def _protocol_payload(*, locked_thr: float, default_thr: float) -> dict[str, Any]:
    """Shared rank/reject protocol block (VAL-only thr; freeze iter1 reject)."""
    proto = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_thr),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    return {
        **proto,
        "name": "clm_lofo_fire_head_a_v1",
        "product_id": _PRODUCT_ID,
        "rank_family": DEFAULT_RANK_SCORE,
        "locked_reject_thr": float(locked_thr),
        "default_thr": float(default_thr),
        "thr_source": "val_iter1_reject_frozen",
        "thr_tune_split": "val",
        "freeze_iter1_reject": True,
        "fit_on_eval_split": False,
        "split_role": "lofo",
        "allowed_actions": ["report", "stress", "scorecard", "gate"],
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "conf_source": _CONF_SOURCE,
        "rank_reject_api": _RANK_REJECT_API,
        "scorecard_api": _SCORECARD_API,
        "dead_paths": sorted(_DEAD_PATHS),
        "honesty": (
            "Head A confidences from ClmEnsembleV34Facade on held-out fire "
            "patches. Rank/reject thr is frozen from VAL iter1 reject — never "
            "refit on LOFO/TEST/new-fire."
        ),
    }


def _head_a_rails(*, locked_thr: float, facade: ClmEnsembleV34Facade) -> dict[str, Any]:
    """Dual-product rails via ClmEnsembleV34Facade (fusion OFF; no go auto-flip)."""
    facade_rails = assert_lab_rails(facade.rails)
    rails: dict[str, Any] = {
        **dual_product_rails_dict(),
        **facade_rails.as_dict(),
        **facade.rails_snapshot(),
        "product_id": facade_rails.product_id,
        "ops_product_id": facade_rails.ops_product_id,
        "product_rail": facade_rails.product_rail,
        "ops_rail": facade_rails.ops_rail,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "locked_reject_thr": float(locked_thr),
        "freeze_iter1_reject": True,
        "val_only_threshold_selection": True,
        "no_per_fire_thr_retune": True,
        "fit_on_lofo": False,
        "test_never_used_for_tune": True,
        "no_ece_retune_same_holdout": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "label": "lab / research_open only",
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "forbidden_thrash": sorted(_DEAD_PATHS),
        "dead_paths": sorted(_DEAD_PATHS),
        "banner": "lab product · not field_ops fusion · IoU ≠ ROS",
    }
    assert_rails_honest(rails, require_iter1_reject_default=True)
    return rails


def _eval_fold_via_facade(
    cache_path: Path,
    facade: ClmEnsembleV34Facade,
    *,
    locked_thr: float,
    default_thr: float,
    fold: str | None = None,
) -> dict[str, Any]:
    """Frozen per-fire Head A eval via ClmEnsembleV34Facade only (no LOFO fit).

    features → facade.confidences → rank_reject (locked + legacy thr) → scorecard.
    """
    data = load_head_a_cache(cache_path)
    fold_id = fold or (str(data["fold"]) if data.get("fold") else None)
    if fold_id is None:
        try:
            fold_id = cache_path.parent.name
        except Exception:  # noqa: BLE001
            fold_id = None

    features = np.asarray(data["features"], dtype=np.float64)
    labels = np.asarray(data["labels"], dtype=np.float64)
    ious = np.asarray(data["ious"], dtype=np.float64)

    # Single product path: ClmEnsembleV34Facade conf + rank/reject + scorecard.
    conf = facade.confidences(features)
    locked_rr = facade.rank_reject(features, conf, ious=ious, labels=labels)
    baseline_cfg = RankRejectConfig(reject_thr=float(default_thr))
    default_rr = facade.rank_reject(features, conf, ious=ious, labels=labels, cfg=baseline_cfg)
    card = facade.scorecard(conf, labels, ious, split="lofo", action="scorecard", fire_id=fold_id)

    thr_locked = dict(locked_rr.get("thr_metrics") or {})
    thr_default = dict(default_rr.get("thr_metrics") or {})
    ece = locked_rr.get("ece_full")
    if ece is None:
        ece = thr_locked.get("ece_full")

    return {
        "n_patches": int(features.shape[0]),
        "mean_iou": float(np.mean(ious)) if ious.size else float("nan"),
        "ece_full": float(ece) if ece is not None else float("nan"),
        "thr_default": thr_default,
        "thr_locked": thr_locked,
        "rank_family": DEFAULT_RANK_SCORE,
        "locked_thr": float(locked_thr),
        "default_thr": float(default_thr),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "conf_source": _CONF_SOURCE,
        "rank_reject_api": _RANK_REJECT_API,
        "scorecard_api": _SCORECARD_API,
        "rank_reject": _strip_arrays(locked_rr),
        "rank_reject_default_thr": _strip_arrays(default_rr),
        "scorecard": card,
        "rails": facade.rails_snapshot(),
        "multi_fire_honesty": multi_fire_honesty_for(fold_id),
        "fold": fold_id,
        "cache": str(cache_path.as_posix()),
    }


def _architecture_lofo_head_a(
    *,
    locked_thr: float,
    default_thr: float,
    fold_evals: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """First-class architecture card: facade rank/reject + multi-fire honesty."""
    rank_reject = _protocol_payload(locked_thr=locked_thr, default_thr=default_thr)
    mf_surface = {fold: multi_fire_honesty_for(fold) for fold in fold_evals}
    mf_global = multi_fire_honesty_dict()
    mf_global["product_facade"] = DEFAULT_MULTI_FIRE.as_dict()
    mf_global["per_fold"] = mf_surface
    tobarra_present = any("tobarra" in str(f).lower() for f in fold_evals) or any(
        str((ev.get("multi_fire_honesty") or {}).get("role") or "") == "hard_transfer"
        for ev in fold_evals.values()
    )
    return {
        "schema": "wfd_ml_architecture_lofo_head_a_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": float(locked_thr),
        "default_thr": float(default_thr),
        "val_only_threshold_tune": True,
        "no_per_fire_thr_retune": True,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "conf_source": _CONF_SOURCE,
        "rank_reject_api": _RANK_REJECT_API,
        "scorecard_api": _SCORECARD_API,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": mf_global,
        "tobarra_hard": tobarra_present,
        "n_folds_eval": len(fold_evals),
        "lofo_ece_mean": summary.get("ece_mean"),
        "note": (
            "LOFO Head A eval under ClmEnsembleV34Facade rank/reject protocol. "
            "VAL-locked thr only (no per-fire retune). Tobarra hard; fusion OFF."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--patches-root",
        type=Path,
        default=ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1",
    )
    p.add_argument(
        "--lofo-out-root",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lofo_v1",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument(
        "--calibrator",
        type=Path,
        default=ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json",
    )
    p.add_argument("--product", default=DEFAULT_PRODUCT)
    p.add_argument("--build", action="store_true", help="Build missing Head A caches")
    p.add_argument("--rebuild", action="store_true", help="Force rebuild caches")
    p.add_argument("--max-patches", type=int, default=0)
    p.add_argument("--device", default=None)
    p.add_argument("--folds", nargs="*", default=None)
    p.add_argument("--md-path", type=Path, default=None)
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Protocol integrity: LOFO is scorecard/report only (never thr/ECE tune).
    assert_split_role("lofo", "scorecard")
    # Dead thrash must stay closed (architecture refuse — not optional folklore).
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")

    preferred = [
        "CARDOSO",
        "LA_ESTRELLA_ACOM1",
        "LA_ESTRELLA_ACOM2",
        "tobarra_20240802",
    ]
    folds = args.folds
    if not folds:
        available = list_lofo_folds(args.patches_root)
        folds = [f for f in preferred if f in available] or available
    # fall back to out-root fold dirs
    if not folds and args.lofo_out_root.is_dir():
        folds = sorted(
            d.name
            for d in args.lofo_out_root.iterdir()
            if d.is_dir() and (d / "evaluation_metrics.json").is_file()
        )
    if not folds:
        print("ERROR: no LOFO folds found", file=sys.stderr)
        return 2

    build_results: list[dict[str, Any]] = []
    if args.build or args.rebuild:
        from scripts.build_lofo_head_a_caches import main as build_main

        b_argv = [
            "--patches-root",
            str(args.patches_root),
            "--out-root",
            str(args.lofo_out_root),
            "--product",
            args.product,
            "--folds",
            *folds,
            "--max-patches",
            str(args.max_patches),
        ]
        if args.device:
            b_argv += ["--device", args.device]
        if args.build and not args.rebuild:
            b_argv.append("--skip-existing")
        rc = build_main(b_argv)
        if rc != 0:
            print(f"WARN: build returned {rc}", file=sys.stderr)

    if not args.calibrator.is_file():
        print(f"ERROR: missing calibrator {args.calibrator}", file=sys.stderr)
        return 1

    # Product facade: features → calibrator → conf → rank/reject → scorecard.
    rails_obj = assert_lab_rails(DEFAULT_RAILS)
    cal = load_calibrator(args.calibrator)
    # Capture production legacy thr before with_iter1_locked_thr rewrites it.
    default_thr = float(getattr(cal, "abstain_threshold", None) or _DEFAULT_THR)
    if not np.isfinite(default_thr) or default_thr <= 0:
        default_thr = float(_DEFAULT_THR)
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal, rails=rails_obj)
    # Frozen VAL thr only (iter1 reject); never re-open thr from LOFO/artifact.
    locked_thr = float(_LOCKED_THR)
    if abs(float(facade.rank_reject_cfg.reject_thr) - locked_thr) > 1e-9:
        raise ProductFacadeError(
            f"facade reject thr {facade.rank_reject_cfg.reject_thr} != frozen iter1 {locked_thr}"
        )
    rails = _head_a_rails(locked_thr=locked_thr, facade=facade)
    rank_reject = _protocol_payload(locked_thr=locked_thr, default_thr=default_thr)
    protocol = {
        **rank_reject,
        "predictor": "production clm_ensemble_v34 on LOFO fold test patches",
        "calibrator": str(args.calibrator.as_posix()),
        "no_per_fire_thr_retune": True,
    }

    sc = load_json(ROOT / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    holdout_ece = (sc.get("uncertainty") or {}).get("ece_patch_conf")
    holdout_iou = (sc.get("primary") or {}).get("model_iou")

    fold_evals: dict[str, Any] = {}
    missing: list[str] = []
    for fold in folds:
        cache = fold_cache_path(args.lofo_out_root, fold)
        if not cache.is_file():
            missing.append(fold)
            continue
        # Single path: ClmEnsembleV34Facade conf → rank/reject → scorecard (no LOFO fit).
        fold_evals[fold] = _eval_fold_via_facade(
            cache,
            facade,
            locked_thr=locked_thr,
            default_thr=default_thr,
            fold=fold,
        )

    summary = summarize_lofo_head_a_evals(
        fold_evals, holdout_ece=holdout_ece, holdout_iou=holdout_iou
    )
    # Seal residual dual rails: summarize embeds lab_lofo_head_a.lab_product_rails();
    # payload rails/protocol must stay ClmEnsembleV34Facade-only.
    summary["rails"] = rails
    summary["protocol"] = rank_reject
    summary["product_facade"] = _FACADE
    summary["facade_class"] = _FACADE_CLASS
    summary["pipeline"] = _PIPELINE
    arch = _architecture_lofo_head_a(
        locked_thr=locked_thr,
        default_thr=default_thr,
        fold_evals=fold_evals,
        summary=summary,
    )
    w1_done = len(fold_evals) >= 1 and not missing
    w1_partial = len(fold_evals) >= 1 and bool(missing)
    created = datetime.now(UTC).isoformat()

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_lofo_head_a_v1",
        "created_utc": created,
        "iteration": 12 if "tobarra_20240802" in fold_evals or "tobarra_20240802" in folds else 11,
        "product_id": _PRODUCT_ID,
        "banner": "lab product · not field_ops fusion · IoU ≠ ROS",
        "friction": "lofo_head_a_caches_missing_or_incomplete_fire_set",
        "control_question": (
            "¿Podemos construir caches Head A por fuego LOFO (incl. Tobarra) y medir "
            "ECE/reject multi-fuego con calibrador de producción frozen (sin retunear thr)?"
        ),
        "control_answer": "YES" if fold_evals else "NO",
        "architecture_lofo_head_a": arch,
        "rails": rails,
        "rank_reject_protocol": arch.get("rank_reject_protocol") or rank_reject,
        "multi_fire_honesty": arch.get("multi_fire_honesty"),
        "protocol": protocol,
        "build": {
            "requested": bool(args.build or args.rebuild),
            "max_patches": int(args.max_patches),
            "results": build_results,
        },
        "folds_requested": folds,
        "folds_missing_cache": missing,
        "fold_evals": fold_evals,
        "summary": summary,
        "holdout_reference": {
            "u1_ece": holdout_ece,
            "u1_mean_iou": holdout_iou,
        },
        "verdict": {
            "w1_caches_built": w1_done or w1_partial,
            "w1_complete_all_folds": w1_done and len(fold_evals) >= 4,
            "w1_partial": w1_partial,
            "w2_eval_done": bool(fold_evals),
            "architecture_lofo_head_a": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "locked_reject_thr": float(locked_thr),
            "no_per_fire_thr_retune": True,
            "ece_holdout_still_unfixed": True,
            "lofo_ece_mean": summary.get("ece_mean"),
            "lofo_locked_abstain_mean": summary.get("locked_abstain_mean"),
            "lofo_locked_iou_accepted_mean": summary.get("locked_iou_accepted_mean"),
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "conf_source": _CONF_SOURCE,
            "rank_reject_api": _RANK_REJECT_API,
            "scorecard_api": _SCORECARD_API,
            "pipeline": _PIPELINE,
            "note": (
                "W1/W2 progress: multi-fire Head A ECE/reject measured with frozen "
                "VAL thr via ClmEnsembleV34Facade rank/reject protocol. "
                "Does not promote field product. Surface remains iter1 reject only."
                if fold_evals
                else "No caches yet — run with --build (needs weights + time)."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_lofo_head_a_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": {
            **{
                "1_reject": "lab_loop_v34_reject_latest.json",
                "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
                "3_refit": "lab_loop_v34_refit_latest.json",
                "4_generalization": "lab_loop_v34_generalization_latest.json",
                "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
                "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
                "7_freeze": "lab_loop_v34_freeze_latest.json",
                "8_smoke": "lab_loop_v34_smoke_latest.json",
                "9_lofo_board": "lab_loop_v34_lofo_board_latest.json",
                "10_next_gate": "lab_loop_v34_next_gate_latest.json",
            },
            **prev_iters,
            "11_lofo_head_a": "lab_loop_v34_lofo_head_a_latest.json",
            "12_lofo_head_a_expand": "lab_loop_v34_lofo_head_a_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter11_lofo_head_a": True,
            "iter12_lofo_head_a_expand": True,
            "w1_lofo_head_a_caches": len(fold_evals),
            "w1_complete_all_folds": bool(payload["verdict"]["w1_complete_all_folds"]),
            "lofo_head_a_folds": list(fold_evals.keys()),
            "lofo_head_a": summary,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "locked_reject_thr": float(locked_thr),
                "no_per_fire_thr_retune": True,
                "product_facade": _FACADE,
                "facade_class": _FACADE_CLASS,
            },
            "rank_reject_protocol": rank_reject,
            "cli_lofo_head_a": "python scripts/run_lab_ml_loop_v34_lofo_head_a.py",
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_lofo_head_a.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": bool(fold_evals),
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "n_folds_eval": len(fold_evals),
                "missing_caches": missing,
                "ece_mean": summary.get("ece_mean"),
                "locked_abstain_mean": summary.get("locked_abstain_mean"),
                "locked_iou_accepted_mean": summary.get("locked_iou_accepted_mean"),
                "locked_reject_thr": float(locked_thr),
                "holdout_ece": holdout_ece,
                "control_answer": payload["control_answer"],
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "product_facade": _FACADE,
                "facade_class": _FACADE_CLASS,
                "pipeline": _PIPELINE,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
            },
            indent=2,
        )
    )
    return 0 if fold_evals else 2


def _n(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return str(v)


def _render_md(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    folds = payload.get("fold_evals") or {}
    proto = payload.get("protocol") or {}
    lines = [
        "# ML lab loop — iter 11 LOFO Head A (W1/W2)",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** next-gate said W1 BLOCKED  ",
        "**Label:** lab / research_open only",
        f"**Pipeline:** `{_PIPELINE}`  ",
        f"**product_facade:** `{_FACADE}` / `{_FACADE_CLASS}`",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| fit on LOFO | **false** |",
        "| thr retune | **false** (locked VAL / iter1) |",
        "| per-fire thr retune | **false** |",
        f"| product_facade | **{_FACADE_CLASS}** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        f"- locked thr: **{proto.get('locked_reject_thr')}** (VAL-only freeze)",
        f"- LOFO ECE mean: **{_n(s.get('ece_mean'))}** (holdout {_n(s.get('holdout_ece'))})",
        f"- locked abstain mean: **{_n(s.get('locked_abstain_mean'))}**",
        f"- locked IoU accepted mean: **{_n(s.get('locked_iou_accepted_mean'))}**",
        "",
        "## Per-fold",
        "",
        "| Fold | n | mean IoU | ECE | abstain@lock | IoU acc@lock | honesty |",
        "|------|--:|---------:|----:|-------------:|-------------:|---------|",
    ]
    for fold, ev in folds.items():
        tl = ev.get("thr_locked") or {}
        hon = (ev.get("multi_fire_honesty") or {}).get("role") or "—"
        lines.append(
            f"| {fold} | {ev.get('n_patches')} | {_n(ev.get('mean_iou'))} | "
            f"{_n(ev.get('ece_full'))} | {_n(tl.get('abstain_rate'))} | "
            f"{_n(tl.get('mean_iou_accepted'))} | {hon} |"
        )
    if payload.get("folds_missing_cache"):
        lines += ["", f"Missing caches: {payload.get('folds_missing_cache')}"]
    lines += [
        "",
        "## CLI",
        "",
        "```powershell",
        "python scripts/build_lofo_head_a_caches.py",
        "python scripts/run_lab_ml_loop_v34_lofo_head_a.py --build",
        "```",
        "",
        "---",
        "*Iteration 11 — multi-fire Head A via ClmEnsembleV34Facade rank/reject; "
        "VAL-locked thr only; not field promote.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
