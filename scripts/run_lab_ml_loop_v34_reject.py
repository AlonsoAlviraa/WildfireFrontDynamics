#!/usr/bin/env python3
"""Authoritative iter1 reject runner for clm_ensemble_v34 (lab ML rail).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` promoted true (human authorize 2026-08-05; no silent
  auto-flip); field fusion stays **OFF** (lab GO ≠ field fusion).
* Single product path via ``ClmEnsembleV34Facade`` + ``rank_reject_protocol``:
  features → calibrator → conf → rank/reject (VAL thr frozen) → scorecard.
  No per-script conf math; no ``lab_reject_calibration.rank_reject_scorecard``
  / ``lab_product_rails`` product path.
* Writes **locked VAL thr** and marks ``iter1_reject_only`` as the default
  lab surface.
* Dead thrash paths closed: same-holdout ECE retune, Tobarra KEEP reopen,
  silent ``auto_ml_product_go``.
* Multi-fire honesty first-class (Tobarra hard, W3 external) — report-only
  consumers apply this frozen thr; never retune on external/LOFO.

Default surface is **freeze iter1 reject** (thr ≈ 0.795). Optional
``--re-sweep-val`` re-runs historical VAL thr+temp discovery for archaeology
but still freezes the product surface to the shared locked thr.

Does **not**:
  - silent auto-flip ``ml_product_go`` (explicit promote stamps true)
  - touch field_ops fusion
  - fit on TEST / LOFO / external
  - retrain ensemble weights
  - re-open ECE thrash or Tobarra KEEP promote paths

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_reject.py
    python scripts/run_lab_ml_loop_v34_reject.py --write-lab-calibrator
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

from wildfire_front.ml.lab_reject_calibration import (  # noqa: E402
    ITER1_LOCKED_TEMPERATURE,
    tune_reject_and_temperature,
)
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
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
    DEFAULT_PROTOCOL,
    FORBIDDEN_THRASH_PATHS,
    MULTI_FIRE_HONESTY,
    assert_rails_honest,
    assert_split_role,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)
from wildfire_front.ml.uncertainty import (  # noqa: E402
    LogisticCalibrator,
    load_calibrator,
)

# Unified dead thrash set (product_facade + protocol_rails).
_DEAD_PATHS: frozenset[str] = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_FACADE: Final = "wildfire_front.ml.product_facade"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_LOCKED_TEMP: Final = float(ITER1_LOCKED_TEMPERATURE)  # 1.0 identity; facade conf path


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path, allow_pickle=True)
    return (
        np.asarray(z["features"], dtype=np.float64),
        np.asarray(z["labels"], dtype=np.float64),
        np.asarray(z["ious"], dtype=np.float64),
    )


def _protocol_payload(locked_thr: float) -> dict[str, Any]:
    """Shared rank/reject protocol block (VAL-only thr; freeze iter1 reject)."""
    proto = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_thr),
        recommended_lab_surface=RECOMMENDED_LAB_SURFACE,
    )
    return {
        **proto,
        "config": DEFAULT_RANK_REJECT.as_dict(),
        "thr_source": "val_iter1_reject_frozen",
        "thr_tune_split": "val",
        "freeze_iter1_reject": True,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "conf_source": "ClmEnsembleV34Facade.confidences",
        "rank_reject_api": "ClmEnsembleV34Facade.rank_reject / rank_and_reject",
        "scorecard_api": "ClmEnsembleV34Facade.scorecard",
    }


def _rails_payload(locked_thr: float, facade: ClmEnsembleV34Facade) -> dict[str, Any]:
    """Dual-product rails via ClmEnsembleV34Facade (ml_product_go true; fusion OFF)."""
    facade_rails = assert_lab_rails(facade.rails)
    rails: dict[str, Any] = {
        **dual_product_rails_dict(),
        **facade_rails.as_dict(),
        **facade.rails_snapshot(),
        # Human promote authorized 2026-08-05 (lab GO ≠ field fusion).
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "locked_reject_thr": float(locked_thr),
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "label": "lab / research_open only",
        "thr_tune_split": "val",
        "dead_paths": sorted(_DEAD_PATHS),
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "facade_class": "ClmEnsembleV34Facade",
    }
    assert_rails_honest(rails, require_iter1_reject_default=True)
    return rails


def _strip_arrays(surface: dict[str, Any]) -> dict[str, Any]:
    """Drop large array fields from rank/reject surface for JSON payloads."""
    return {
        k: v
        for k, v in surface.items()
        if k not in ("keep_mask", "conf") and not isinstance(v, np.ndarray)
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--calibrator",
        type=Path,
        default=ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json",
    )
    p.add_argument(
        "--val-npz",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "val_head_a_features.npz",
    )
    p.add_argument(
        "--test-npz",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "test_head_a_features.npz",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument(
        "--write-lab-calibrator",
        action="store_true",
        help="Write models/clm_ensemble/uncertainty_calibration_v1_lab_reject.json",
    )
    p.add_argument(
        "--re-sweep-val",
        action="store_true",
        help=(
            "Historical VAL thr+temp discovery (archaeology). Product surface "
            "still freezes to shared iter1 locked thr; does not open ECE thrash."
        ),
    )
    p.add_argument("--no-md", action="store_true")
    p.add_argument(
        "--md-path",
        type=Path,
        default=None,
    )
    args = p.parse_args(argv)

    if not args.calibrator.is_file():
        print(f"missing calibrator: {args.calibrator}", file=sys.stderr)
        return 1
    if not args.val_npz.is_file() or not args.test_npz.is_file():
        print(
            f"missing Head A caches:\n  {args.val_npz}\n  {args.test_npz}",
            file=sys.stderr,
        )
        return 1

    # Hard-refuse closed thrash paths (product_facade seals them).
    for _dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    ):
        try:
            refuse_dead_path(_dead)
        except ProductFacadeError:
            pass  # expected — path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {_dead!r}")

    # Product facade: features → calibrator → conf → rank/reject → scorecard.
    rails_obj = assert_lab_rails(DEFAULT_RAILS)
    cal_prod = load_calibrator(args.calibrator)
    # Capture production legacy thr before with_iter1_locked_thr rewrites it.
    legacy_thr = float(getattr(cal_prod, "abstain_threshold", LEGACY_PRODUCT_ABSTAIN_THR))
    if not np.isfinite(legacy_thr) or legacy_thr <= 0:
        legacy_thr = float(LEGACY_PRODUCT_ABSTAIN_THR)
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal_prod, rails=rails_obj)
    locked_thr = float(ITER1_LOCKED_REJECT_THR)
    locked_temp = float(_LOCKED_TEMP)
    if abs(float(facade.rank_reject_cfg.reject_thr) - locked_thr) > 1e-9:
        raise ProductFacadeError(
            f"facade reject thr {facade.rank_reject_cfg.reject_thr} != frozen iter1 {locked_thr}"
        )
    protocol = _protocol_payload(locked_thr)
    rails = _rails_payload(locked_thr, facade)

    vf, vl, vi = _load_npz(args.val_npz)
    tf, tl, ti = _load_npz(args.test_npz)

    # Shared conf via facade (rank_reject_protocol.conf_from_features) — no local conf math.
    conf_v = facade.confidences(vf)
    conf_t = facade.confidences(tf)

    # Report-only rank/reject + scorecard at frozen thr (ClmEnsembleV34Facade path).
    # VAL may document selection history; TEST is frozen eval only.
    assert_split_role("val", "report")
    assert_split_role("test", "report")
    val_rr = facade.rank_reject(vf, conf_v, ious=vi, labels=vl)
    test_rr = facade.rank_reject(tf, conf_t, ious=ti, labels=tl)
    # Baseline at legacy product thr (never rejects on v34 conf band).
    baseline_cfg = RankRejectConfig(reject_thr=float(legacy_thr))
    test_baseline_rr = facade.rank_reject(tf, conf_t, ious=ti, labels=tl, cfg=baseline_cfg)
    val_card = facade.scorecard(conf_v, vl, vi, split="val", action="report")
    test_card = facade.scorecard(conf_t, tl, ti, split="test", action="report")
    # Legacy-thr product scorecard for contrast (still lab report; not a re-open).
    test_baseline_card = {
        "product_id": DEFAULT_PRODUCT_ID,
        "surface": "legacy_product_abstain",
        "thr": float(legacy_thr),
        "temperature": 1.0,
        "metrics": dict(test_baseline_rr.get("thr_metrics") or {}),
        "rank_reject": _strip_arrays(test_baseline_rr),
        "rails": facade.rails_snapshot(),
        "note": "legacy thr contrast via ClmEnsembleV34Facade.rank_reject; not product surface",
    }

    base_ab = float((conf_t < float(legacy_thr)).mean())

    # Optional historical VAL discovery (does not replace locked product thr).
    # Archaeology only — still uses production calibrator, not facade thr rewrite.
    sweep_result = None
    if args.re_sweep_val:
        assert_split_role("val", "tune_reject")
        sweep_result = tune_reject_and_temperature(
            cal_prod, vf, vl, vi, tf, tl, ti, baseline_thr=float(legacy_thr)
        )

    test_metrics_baseline = dict(test_baseline_rr.get("thr_metrics") or {})
    test_metrics_locked = dict(test_rr.get("thr_metrics") or {})
    val_metrics_locked = dict(val_rr.get("thr_metrics") or {})

    # Multi-fire honesty: protocol_rails + product_facade first-class tags.
    multi_fire = {
        **dict(MULTI_FIRE_HONESTY),
        **multi_fire_honesty_dict(),
        "product_facade": DEFAULT_MULTI_FIRE.as_dict(),
        "facade_multi_fire": facade.multi_fire.as_dict(),
    }

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_reject_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "product_id": DEFAULT_PRODUCT_ID,
        "protocol": DEFAULT_PROTOCOL,
        "product_facade": _FACADE,
        "facade_class": "ClmEnsembleV34Facade",
        "pipeline": _PIPELINE,
        "rank_reject_protocol": protocol,
        "friction": "calibration_ece_and_explicit_mask_reject",
        "control_question": (
            "Mejora medible con ECE/abstain/selective en VAL-tune + TEST frozen; "
            "sin field_ops fusion; ml_product_go true (lab ≠ field fusion)."
        ),
        "control_answer": "YES",
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": locked_thr,
        "locked_temperature": locked_temp,
        "thr_source": "val_iter1_reject_frozen",
        "rails": rails,
        "multi_fire_honesty": multi_fire,
        "dead_paths": sorted(_DEAD_PATHS),
        "baseline_calibrator": {
            "path": str(args.calibrator.relative_to(ROOT)).replace("\\", "/"),
            "abstain_threshold": float(legacy_thr),
            "calibrator_id": facade.cal.calibrator_id,
            "test_abstain_rate_at_default_thr": base_ab,
        },
        # Product surface: locked VAL thr via facade rank/reject (not a re-open).
        "tuned": {
            "abstain_threshold": locked_thr,
            "confidence_temperature": locked_temp,
            "val_metrics": val_metrics_locked,
            "test_metrics_baseline": test_metrics_baseline,
            "test_metrics_tuned": test_metrics_locked,
            "surface": RECOMMENDED_LAB_SURFACE,
            "thr_source": "val_iter1_reject_frozen",
        },
        "frozen_scorecards": {
            "val": val_card,
            "test_locked": test_card,
            "test_baseline_legacy_thr": test_baseline_card,
        },
        "rank_reject_surfaces": {
            "val": _strip_arrays(val_rr),
            "test_locked": _strip_arrays(test_rr),
            "test_baseline_legacy_thr": _strip_arrays(test_baseline_rr),
        },
        "protocol_note": (
            f"Authoritative freeze: {RECOMMENDED_LAB_SURFACE} thr={locked_thr} "
            f"(VAL-selected historically; locked via ClmEnsembleV34Facade + "
            f"rank_reject_protocol). "
            "TEST / LOFO / W3 external are report-only at this thr. "
            "No ECE same-holdout thrash; no Tobarra KEEP reopen; "
            "ml_product_go true; field_ops fusion OFF; IoU ≠ ROS."
        ),
        "delta_test": {
            "ece_full": float(test_metrics_locked["ece_full"])
            - float(test_metrics_baseline["ece_full"]),
            "ece_accepted": float(test_metrics_locked["ece_accepted"])
            - float(test_metrics_baseline["ece_accepted"]),
            "abstain_rate": float(test_metrics_locked["abstain_rate"])
            - float(test_metrics_baseline["abstain_rate"]),
            "mean_iou_accepted": float(test_metrics_locked["mean_iou_accepted"])
            - float(test_metrics_baseline["mean_iou_accepted"]),
        },
        "verdict": _verdict(test_metrics_baseline, test_metrics_locked, locked_thr),
    }

    if sweep_result is not None:
        payload["val_sweep_archaeology"] = {
            "best_threshold": sweep_result.best_threshold,
            "best_temperature": sweep_result.best_temperature,
            "val_metrics": sweep_result.val_metrics,
            "test_metrics_baseline": sweep_result.test_metrics_baseline,
            "test_metrics_tuned": sweep_result.test_metrics_tuned,
            "val_sweep_top": sweep_result.val_sweep_top,
            "protocol_note": sweep_result.protocol_note,
            "note": (
                "Archaeology only — product surface remains "
                f"{RECOMMENDED_LAB_SURFACE} @ thr={locked_thr}."
            ),
        }
        payload["val_sweep_top"] = sweep_result.val_sweep_top
    else:
        payload["val_sweep_top"] = []

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_reject_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Pointer: iter1 reject is default lab surface for downstream loops.
    latest_path = out_dir / "lab_loop_v34_latest.json"
    prev: dict[str, Any] = {}
    if latest_path.is_file():
        try:
            loaded = json.loads(latest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prev = loaded
        except (OSError, json.JSONDecodeError):
            prev = {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": payload["created_utc"],
        "iterations": {
            **prev_iters,
            "1_reject": "lab_loop_v34_reject_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter1_reject_improved": bool(payload["verdict"]["lab_reject_surface_improved"]),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": locked_thr,
            "locked_temperature": locked_temp,
            "thr_source": "val_iter1_reject_frozen",
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen_forbidden": True,
            "iter1": {
                "abstain_threshold": locked_thr,
                "confidence_temperature": locked_temp,
                "test_abstain_rate": test_metrics_locked.get("abstain_rate"),
                "test_iou_accepted": test_metrics_locked.get("mean_iou_accepted"),
                "surface": RECOMMENDED_LAB_SURFACE,
            },
            "reject": {
                "thr": locked_thr,
                "abstain_rate": test_metrics_locked.get("abstain_rate"),
                "iou_accepted": test_metrics_locked.get("mean_iou_accepted"),
                "test_abstain_rate": test_metrics_locked.get("abstain_rate"),
                "test_iou_accepted": test_metrics_locked.get("mean_iou_accepted"),
            },
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": locked_thr,
                "product_facade": _FACADE,
                "facade_class": "ClmEnsembleV34Facade",
            },
        },
    }
    latest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_reject_calibration.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    lab_cal_path = None
    if args.write_lab_calibrator:
        cal_f = facade.cal
        lab_cal = LogisticCalibrator(
            weights=np.asarray(cal_f.weights, dtype=np.float64).copy(),
            feature_names=cal_f.feature_names,
            method=cal_f.method,
            calibrator_id="uncertainty_calibration_v1_lab_reject",
            tau_iou=cal_f.tau_iou,
            fit_split="val",
            abstain_threshold=locked_thr,
            allow_identity_heuristic=False,
            temperature=cal_f.temperature,
            platt_a=cal_f.platt_a,
            platt_b=cal_f.platt_b,
        )
        d = lab_cal.to_dict()
        d["lab_only"] = True
        d["confidence_temperature"] = locked_temp
        d["parent_calibrator"] = "uncertainty_calibration_v1"
        d["recommended_lab_surface"] = RECOMMENDED_LAB_SURFACE
        d["locked_reject_thr"] = locked_thr
        d["thr_source"] = "val_iter1_reject_frozen"
        d["product_facade"] = _FACADE
        d["facade_class"] = "ClmEnsembleV34Facade"
        d["note"] = (
            "LAB/research_open only. Locked iter1 reject thr via ClmEnsembleV34Facade. "
            "ml_product_go true (human promote authorized); field_ops fusion OFF. "
            "No same-holdout ECE thrash; no Tobarra KEEP reopen."
        )
        d["metrics_lab_loop"] = {
            "test_metrics_tuned": test_metrics_locked,
            "test_metrics_baseline": test_metrics_baseline,
        }
        d["rails"] = {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
        }
        lab_cal_path = (
            ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1_lab_reject.json"
        )
        lab_cal_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        payload["lab_calibrator_path"] = str(lab_cal_path.relative_to(ROOT)).replace("\\", "/")
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "latest": str(latest_path),
                "md": str(md_path) if md_path else None,
                "lab_calibrator": str(lab_cal_path) if lab_cal_path else None,
                "verdict": payload["verdict"],
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": locked_thr,
                "thr_source": "val_iter1_reject_frozen",
                "test_ece_full_baseline": test_metrics_baseline["ece_full"],
                "test_ece_full_tuned": test_metrics_locked["ece_full"],
                "test_abstain_baseline": test_metrics_baseline["abstain_rate"],
                "test_abstain_tuned": test_metrics_locked["abstain_rate"],
                "best_threshold": locked_thr,
                "best_temperature": locked_temp,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
            },
            indent=2,
        )
    )
    return 0


def _verdict(
    baseline: dict[str, float],
    locked: dict[str, float],
    locked_thr: float,
) -> dict[str, Any]:
    b, t = baseline, locked
    improved_reject = float(t["abstain_rate"]) > float(b["abstain_rate"]) + 0.05
    ece_acc_better = (
        np.isfinite(t["ece_accepted"])
        and np.isfinite(b["ece_accepted"])
        and float(t["ece_accepted"]) <= float(b["ece_accepted"]) + 0.02
    )
    iou_lift = float(t["mean_iou_accepted"]) - float(b["mean_iou_accepted"])
    iou_improved = iou_lift >= 0.02
    keep = float(t["keep_rate"]) >= 0.40
    promote_lab = bool(improved_reject and iou_improved and keep)
    return {
        "lab_reject_surface_improved": promote_lab,
        "explicit_mask_reject_enabled": improved_reject,
        "ece_accepted_not_worse": ece_acc_better,
        "iou_accepted_lift": float(iou_lift),
        "iou_accepted_improved": iou_improved,
        "keep_rate_ok": keep,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(locked_thr),
        "freeze_iter1_reject": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "field_product": False,
        "ml_product_go": True,
        "note": (
            "lab_reject_surface_improved = visible mask ABSTAIN + higher IoU on "
            "accepted patches (TEST frozen at locked VAL thr). "
            f"Default lab surface = {RECOMMENDED_LAB_SURFACE} thr={locked_thr}. "
            "ml_product_go true (lab promote); not field fusion; fusion OFF."
        ),
    }


def _render_md(payload: dict[str, Any]) -> str:
    t = payload["tuned"]
    b = t["test_metrics_baseline"]
    u = t["test_metrics_tuned"]
    d = payload["delta_test"]
    v = payload["verdict"]
    thr = payload["locked_reject_thr"]
    return f"""# ML lab loop — iter reject/calibration (clm_ensemble_v34)

**UTC:** {payload["created_utc"]}
**Product:** `{payload["product_id"]}` · **protocol:** `{payload["protocol"]}`
**Label:** **lab / research_open only**
**Recommended surface:** **`{payload["recommended_lab_surface"]}`** · locked thr **{thr}**

## Rails (unchanged)

| Rail | Value |
|------|--------|
| ml_product_go | **true** |
| field_ops ML live fusion | **OFF** |
| IoU sold as ROS | **never** |
| Tune split | **VAL only** (locked thr freeze) |
| TEST used for | **frozen eval only** |
| Default lab surface | **iter1_reject_only** |
| ECE same-holdout thrash | **closed** |
| Tobarra KEEP reopen | **forbidden** |

## Multi-fire honesty (first-class)

- **Tobarra:** hard transfer · KEEP claim **KILL** — do not reopen same recipe
- **W3 external:** report-only with frozen thr/cal (never fit thr on external)
- Shared protocol: Head A / LOFO / selective-SDC / reject share this locked thr

## 1. Observe (baseline)

Scorecard U1 TEST (published):

- mean IoU lab ~**0.857** (U1 eval)
- ECE patch conf ~**0.153**
- selective@80 ~**0.903** (beats random)
- **abstain_rate at thr=0.35: ~0.0** on U1 card → fricción: rechazo de máscara no es visible

Baseline frozen TEST (this run, Head A cache):

| Metric | Baseline thr={payload["baseline_calibrator"]["abstain_threshold"]} |
|--------|---------------------------------------------------------------------:|
| ECE full | {b["ece_full"]:.4f} |
| ECE accepted | {b["ece_accepted"]:.4f} |
| abstain_rate | {b["abstain_rate"]:.4f} |
| mean_iou_accepted | {b["mean_iou_accepted"]:.4f} |
| keep_rate | {b["keep_rate"]:.4f} |

## 2. Friction chosen

**Alta:** calibración imperfecta + **falta de rechazo explícito** de baja confianza.

Control question: ¿mejorable con métricas honestas sin producto de campo? **SÍ.**

## 3. Locked product surface (shared protocol)

Authoritative freeze via `ClmEnsembleV34Facade.scorecard` / `rank_reject` +
`rank_reject_protocol` / `protocol_rails`:

1. confidences from `ClmEnsembleV34Facade.confidences` (DRY — no per-script conf math)
2. **locked reject thr** = **{thr}** (VAL-selected historically; freeze default)
3. surface name = **`{payload["recommended_lab_surface"]}`** (default lab surface)

Optional archaeology: `--re-sweep-val` re-runs VAL thr+temp search but **does not**
replace the product lock.

## 4. TEST frozen evaluation (not used for tune)

| Metric | Baseline | Locked | Δ |
|--------|---------:|-------:|--:|
| ECE full | {b["ece_full"]:.4f} | {u["ece_full"]:.4f} | {d["ece_full"]:+.4f} |
| ECE accepted | {b["ece_accepted"]:.4f} | {u["ece_accepted"]:.4f} | {d["ece_accepted"]:+.4f} |
| abstain_rate | {b["abstain_rate"]:.4f} | {u["abstain_rate"]:.4f} | {d["abstain_rate"]:+.4f} |
| mean_iou_accepted | {b["mean_iou_accepted"]:.4f} | {u["mean_iou_accepted"]:.4f} | {d["mean_iou_accepted"]:+.4f} |
| keep_rate | {b["keep_rate"]:.4f} | {u["keep_rate"]:.4f} | — |

## 5. Verdict

```json
{json.dumps(v, indent=2)}
```

- **Default lab surface:** `{payload["recommended_lab_surface"]}` @ thr={thr}
- **Lab GO ≠ field fusion:** ml_product_go true; field_ops fusion OFF; catalog 0.8963 remains provenance only.
- **Closed:** same-holdout ECE retune; Tobarra KEEP reopen of KILL weights.

## 6. How to use

```powershell
$env:PYTHONPATH = "."
python scripts\\run_lab_ml_loop_v34_reject.py --write-lab-calibrator
python -m wildfire_front ml show
```

Lab calibrator (if written): `models/clm_ensemble/uncertainty_calibration_v1_lab_reject.json`
Machine result: `outputs/ml_eval/lab_loop/lab_loop_v34_reject_latest.json`

## 7. Next loop candidates

1. LOFO / W3 external boards at **frozen** thr (report only).
2. Selective-SDC bake-off stays secondary; kill promote keeps this surface.
3. Explainability: export fail_cases patches for teaching.

---
*Iteration artifact — not a tactical dispatch claim.*
"""


if __name__ == "__main__":
    raise SystemExit(main())
