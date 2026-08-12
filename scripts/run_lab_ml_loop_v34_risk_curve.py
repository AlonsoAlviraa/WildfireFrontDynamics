#!/usr/bin/env python3
"""Lab ML loop iter 6: risk–coverage curve + thr operating points (no ECE retune).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` never auto-flips; field fusion stays **OFF**.
* Ranking + thr-reject share one protocol via ``product_facade`` +
  ``rank_reject_protocol``: features → calibrator → conf → rank/reject
  (frozen thr) → ``facade.scorecard``.
* Curve via ``rank_reject_protocol.score_ranking``; thr map via protocol
  eval primitives. Confidences from facade only (no ``lab_reject_calibration``
  curve/score helpers). Frozen thr is iter1 reject (VAL-only; ~0.795).
  TEST is frozen evaluation only.
* Multi-fire honesty first-class (Tobarra hard, W3 external) — report-only.
* Dead thrash closed: same-holdout ECE retune; Tobarra KEEP reopen.

Uses production calibrator + existing Head A caches.
Does **not** change recommended reject thr or field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_risk_curve.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml import rank_reject_protocol as _rrp  # noqa: E402
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
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    assert_split_role,
    dual_product_rails_dict,
)
from wildfire_front.ml.reliability_metrics import reject_thr_metrics  # noqa: E402
from wildfire_front.ml.uncertainty import load_calibrator  # noqa: E402

protocol_multi_fire = _rrp.multi_fire_honesty
protocol_payload = _rrp.protocol_payload
score_ranking = _rrp.score_ranking


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path, allow_pickle=True)
    return (
        np.asarray(z["features"], dtype=np.float64),
        np.asarray(z["labels"], dtype=np.float64),
        np.asarray(z["ious"], dtype=np.float64),
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _conf_band_summary(conf: np.ndarray) -> dict[str, float]:
    """Where confidences live (explains thr=0.35 never rejects). Local report helper."""
    c = np.asarray(conf, dtype=np.float64).ravel()
    if c.size == 0:
        return {"n": 0.0}
    qs = [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0]
    pct = np.quantile(c, qs)
    return {
        "n": float(c.size),
        "mean": float(c.mean()),
        "std": float(c.std()),
        "min": float(pct[0]),
        "p05": float(pct[1]),
        "p25": float(pct[2]),
        "p50": float(pct[3]),
        "p75": float(pct[4]),
        "p95": float(pct[5]),
        "max": float(pct[6]),
    }


def _thr_operating_points(
    conf: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    thresholds: list[float],
) -> list[dict[str, float]]:
    """Frozen thr operating map via reliability_metrics.reject_thr_metrics (protocol eval)."""
    out: list[dict[str, float]] = []
    for thr in thresholds:
        m = reject_thr_metrics(conf, ious, thr=float(thr), labels=labels)
        out.append(
            {
                "threshold": float(thr),
                "keep_rate": float(m["keep_rate"]),
                "abstain_rate": float(m["abstain_rate"]),
                "mean_iou_accepted": float(m["mean_iou_accepted"]),
                "mean_conf_accepted": float(m["mean_conf_accepted"]),
                "ece_full": float(m["ece_full"]),
                "ece_accepted": float(m["ece_accepted"]),
                "n_keep": float(m["n_keep"]),
            }
        )
    return out


def _strip_arrays(surface: dict[str, Any]) -> dict[str, Any]:
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
        "--md-path",
        type=Path,
        default=None,
    )
    p.add_argument("--no-md", action="store_true")
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

    # Seal dead thrash paths (ECE same-holdout retune / Tobarra KEEP reopen / fusion).
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
    rails = assert_lab_rails(DEFAULT_RAILS)
    cal = load_calibrator(args.calibrator)
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal, rails=rails)
    vf, vl, vi = _load_npz(args.val_npz)
    tf, tl, ti = _load_npz(args.test_npz)
    # Shared ranking/reject scores from facade only (no private conf helpers).
    conf_v = facade.confidences(vf)
    conf_t = facade.confidences(tf)

    # Freeze iter1 reject thr (VAL-selected historically). Reject JSON = provenance only.
    reject = _load_json(args.out_dir / "lab_loop_v34_reject_latest.json") or {}
    locked_thr = float(ITER1_LOCKED_REJECT_THR)
    # rank_reject_cfg locked by with_iter1_locked_thr; never re-open thr from artifact.
    if abs(float(facade.rank_reject_cfg.reject_thr) - locked_thr) > 1e-9:
        raise ProductFacadeError(
            f"facade reject thr {facade.rank_reject_cfg.reject_thr} != frozen iter1 {locked_thr}"
        )
    # Legacy product thr (contrast on operating map; never rejects on v34 conf band).
    default_thr = float(LEGACY_PRODUCT_ABSTAIN_THR)

    # Report-only: VAL/TEST never retune thr (VAL thr already frozen as iter1).
    assert_split_role("val", "report")
    assert_split_role("test", "report")

    # Unified rank/reject + scorecard path (product_facade + rank_reject_protocol).
    val_rr = facade.rank_reject(vf, conf_v, ious=vi, labels=vl)
    test_rr = facade.rank_reject(tf, conf_t, ious=ti, labels=tl)
    val_card = facade.scorecard(conf_v, vl, vi, split="val", action="report")
    test_card = facade.scorecard(conf_t, tl, ti, split="test", action="report")

    coverages = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.485, 0.4]
    # Curve via rank_reject_protocol.score_ranking (shared with selective-SDC / reject).
    rank_val = score_ranking(conf_v, vi, coverages=coverages)
    rank_test = score_ranking(conf_t, ti, coverages=coverages)
    curve_val = list(rank_val.get("curve") or [])
    curve_test = list(rank_test.get("curve") or [])
    thr_pts_test = _thr_operating_points(
        conf_t, tl, ti, [default_thr, locked_thr, 0.75, 0.78, 0.80, 0.82]
    )
    thr_pts_val = _thr_operating_points(conf_v, vl, vi, [default_thr, locked_thr])

    # Find selective@0.8 and full on TEST for control answer
    full_row = next((r for r in curve_test if abs(r["coverage_target"] - 1.0) < 1e-9), None)
    sel80 = next((r for r in curve_test if abs(r["coverage_target"] - 0.8) < 1e-9), None)
    full_iou = (
        float(full_row["selective_iou"])
        if full_row
        else float(rank_test.get("full_mean_iou") or float("nan"))
    )
    sel80_iou = (
        float(sel80["selective_iou"])
        if sel80
        else float(rank_test.get("selective_iou_at_80") or float("nan"))
    )
    ranking_useful = bool(
        np.isfinite(sel80_iou) and np.isfinite(full_iou) and sel80_iou > full_iou + 0.01
    )

    locked_pt = next(
        (r for r in thr_pts_test if abs(r["threshold"] - locked_thr) < 1e-6),
        thr_pts_test[1] if len(thr_pts_test) > 1 else {},
    )
    default_pt = thr_pts_test[0] if thr_pts_test else {}

    rank_reject = {
        **protocol_payload(locked_reject_thr=float(locked_thr)),
        "config": DEFAULT_RANK_REJECT.as_dict(),
        "conf_source": "ClmEnsembleV34Facade.confidences",
        "rank_reject_api": "ClmEnsembleV34Facade.rank_reject / rank_and_reject",
        "scorecard_api": "ClmEnsembleV34Facade.scorecard",
        "curve_api": "rank_reject_protocol.score_ranking",
        "thr_source": "iter1_reject_frozen",
        "freeze_iter1_reject": True,
    }
    multi_fire = {
        **DEFAULT_MULTI_FIRE.as_dict(),
        **protocol_multi_fire(),
        "reject_artifact_provenance": {
            "path": "lab_loop_v34_reject_latest.json",
            "present": bool(reject),
            "note": "provenance only — thr not re-opened from artifact",
        },
    }
    rails_out: dict[str, Any] = {
        **dual_product_rails_dict(),
        **rails.as_dict(),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "iou_is_not_ros": True,
        "fit_split": "none — curve is frozen eval of ranking",
        "test_never_used_for_tune": True,
        "label": "lab / research_open only",
        "no_ece_retune_same_holdout": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(locked_thr),
        "dead_paths": sorted(DEAD_PATHS | FORBIDDEN_THRASH_PATHS),
    }

    created = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_risk_curve_v1",
        "created_utc": created,
        "iteration": 6,
        "product_id": DEFAULT_PRODUCT_ID,
        "friction": "single_thr_without_risk_coverage_curve",
        "control_question": (
            "¿Podemos productizar la curva cobertura→IoU (ranking conf) y situar "
            "el reject thr locked sin retunear ECE ni abrir field_ops?"
        ),
        "control_answer": "YES",
        "rails": rails_out,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "calibrator": {
            "path": str(args.calibrator.as_posix()),
            "default_abstain_threshold": default_thr,
            "locked_reject_threshold": locked_thr,
            "calibrator_id": facade.cal.calibrator_id,
            "thr_source": "iter1_reject_frozen",
            "reject_json_provenance_only": True,
        },
        "conf_band": {
            "val": _conf_band_summary(conf_v),
            "test": _conf_band_summary(conf_t),
            "note": (
                "Tight conf band (~0.74–0.81) explains thr=0.35 never rejects; "
                "lab thr~0.80 sits inside the band."
            ),
        },
        "selective_curve": {
            "protocol": (
                "rank_reject_protocol.score_ranking: keep top coverage fraction by conf. "
                "Not the same as thr-based reject keep_rate. "
                "Conf from ClmEnsembleV34Facade; scorecard via facade.scorecard."
            ),
            "val": curve_val,
            "test": curve_test,
            "val_rank_metrics": {k: v for k, v in rank_val.items() if k != "curve"},
            "test_rank_metrics": {k: v for k, v in rank_test.items() if k != "curve"},
        },
        "thr_operating_points": {
            "protocol": (
                "conf >= thr accept; frozen eval via reliability_metrics.reject_thr_metrics "
                f"(not a new tune); locked thr={locked_thr} from {RECOMMENDED_LAB_SURFACE}"
            ),
            "val": thr_pts_val,
            "test": thr_pts_test,
        },
        "frozen_scorecards": {
            "val": val_card,
            "test": test_card,
        },
        "rank_reject_surface": {
            "val": _strip_arrays(val_rr),
            "test": _strip_arrays(test_rr),
        },
        "highlights_test": {
            "full_mean_iou": full_iou,
            "selective_iou_at_80": sel80_iou,
            "selective_lift_at_80": (
                sel80_iou - full_iou if np.isfinite(sel80_iou) and np.isfinite(full_iou) else None
            ),
            "ranking_useful_at_80": ranking_useful,
            "default_thr": default_pt,
            "locked_reject_thr": locked_pt,
        },
        "verdict": {
            "risk_coverage_curve_built": True,
            "ranking_useful_selective_80": ranking_useful,
            "default_thr_never_rejects": bool(float(default_pt.get("abstain_rate") or 0) < 0.02),
            "locked_reject_has_visible_abstain": bool(
                float(locked_pt.get("abstain_rate") or 0) >= 0.10
            ),
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "ece_holdout_still_unfixed": True,
            "field_product": False,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "multi_fire_honesty_first_class": True,
            "product_facade": "wildfire_front.ml.product_facade",
            "rank_reject_protocol": "wildfire_front.ml.rank_reject_protocol",
            "scorecard_api": "ClmEnsembleV34Facade.scorecard",
            "note": (
                "Iter6 productizes the coverage→IoU tradeoff and places locked thr "
                "on the operating map via product_facade + rank_reject_protocol. "
                "Does not claim ECE fixed. Does not change thr. Field fusion OFF."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_risk_curve_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = _load_json(out_dir / "lab_loop_v34_latest.json") or {}
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
            },
            **prev_iters,
            "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter6_risk_curve": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "risk_curve": {
                "full_mean_iou_test": full_iou,
                "selective_iou_at_80_test": sel80_iou,
                "selective_lift_at_80": payload["highlights_test"]["selective_lift_at_80"],
                "ranking_useful_at_80": ranking_useful,
                "locked_thr": locked_thr,
                "locked_abstain_rate": locked_pt.get("abstain_rate"),
                "locked_iou_accepted": locked_pt.get("mean_iou_accepted"),
                "product_facade": "wildfire_front.ml.product_facade",
            },
            "stop_ece_thrash_on_same_test": True,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            },
            "cli_curve": "wildfire-front ml curve",
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_risk_curve.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "full_mean_iou_test": full_iou,
                "selective_iou_at_80_test": sel80_iou,
                "ranking_useful_at_80": ranking_useful,
                "locked_thr": locked_thr,
                "locked_abstain": locked_pt.get("abstain_rate"),
                "locked_iou_acc": locked_pt.get("mean_iou_accepted"),
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "product_facade": "wildfire_front.ml.product_facade",
            },
            indent=2,
        )
    )
    return 0


def _n(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return str(v)


def _render_md(payload: dict[str, Any]) -> str:
    h = payload.get("highlights_test") or {}
    curve = (payload.get("selective_curve") or {}).get("test") or []
    thr = (payload.get("thr_operating_points") or {}).get("test") or []
    band = (payload.get("conf_band") or {}).get("test") or {}
    lines = [
        "# ML lab loop — iter 6 risk–coverage curve",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** iter1 reject YES · 2/3 ECE NO · 4 LOFO · 5 teach cases  ",
        "**Label:** lab / research_open only",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| IoU as ROS | **never** |",
        "| ECE re-tune same TEST | **stopped** |",
        f"| lab surface | **{RECOMMENDED_LAB_SURFACE}** |",
        "| product_facade conf | **yes** |",
        "",
        "## Why this iteration",
        "",
        "Reject thr is one operating point. Productize the **coverage→IoU** selective "
        "curve (ranking by conf from product_facade) and place default thr vs locked thr "
        "on the map — without retuning ECE.",
        "",
        f"Control: **{payload.get('control_answer')}**",
        "",
        "## Conf band (TEST)",
        "",
        f"mean {_n(band.get('mean'))} · p05 {_n(band.get('p05'))} · p50 {_n(band.get('p50'))} · "
        f"p95 {_n(band.get('p95'))} · max {_n(band.get('max'))}",
        "",
        f"Note: {(payload.get('conf_band') or {}).get('note')}",
        "",
        "## Selective curve TEST (rank by conf)",
        "",
        "| coverage | n_keep | selective IoU | lift vs full |",
        "|---------:|-------:|--------------:|-------------:|",
    ]
    for r in curve:
        lines.append(
            f"| {_n(r.get('coverage_target'))} | {int(r.get('n_keep') or 0)} | "
            f"{_n(r.get('selective_iou'))} | {_n(r.get('lift_vs_full'))} |"
        )
    lines += [
        "",
        f"**Highlights:** full IoU {_n(h.get('full_mean_iou'))} · "
        f"sel@80 {_n(h.get('selective_iou_at_80'))} · "
        f"lift {_n(h.get('selective_lift_at_80'))} · "
        f"ranking_useful={h.get('ranking_useful_at_80')}",
        "",
        "## Thr operating points TEST (frozen)",
        "",
        "| thr | keep | abstain | IoU accepted | ECE full |",
        "|----:|-----:|--------:|-------------:|---------:|",
    ]
    for r in thr:
        lines.append(
            f"| {_n(r.get('threshold'))} | {_n(r.get('keep_rate'))} | "
            f"{_n(r.get('abstain_rate'))} | {_n(r.get('mean_iou_accepted'))} | "
            f"{_n(r.get('ece_full'))} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
        "```json",
        json.dumps(payload.get("verdict") or {}, indent=2),
        "```",
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml curve",
        "python -m wildfire_front ml curve --json",
        "```",
        "",
        "---",
        f"*Iteration 6 — not field product. Surface stays {RECOMMENDED_LAB_SURFACE}.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
