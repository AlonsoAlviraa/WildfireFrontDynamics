#!/usr/bin/env python3
"""Deep-research S1: Soft Dice Confidence proxy ranking bake-off (lab only).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05; no silent auto-flip);
  field fusion stays **OFF** (lab GO ≠ field fusion).
* Single path via ``product_facade`` + ``rank_reject_protocol``:
  features → calibrator → conf → rank bake-off + VAL thr → scorecard.
  ``lab_selective_sdc`` owns **SDC ranking families / verdict only**
  (``bakeoff_rankings`` / ``decide_sdc_verdict``) — not conf, thr, or rails.
* VAL selects ranking family; product reject thr freezes **iter1** via facade
  (``ITER1_LOCKED_REJECT_THR`` ≈ 0.795). CRC-lite is report-only with the
  same facade thr as fallback — never a divergent 0.80 default.
* Frozen product reject surface: **iter1_reject_only** (default).
  ``KILL_SDC_PROMOTE`` keeps that surface; even ``KEEP_SDC_PROXY_LAB``
  does **not** auto-promote over iter1 or open field_ops.
* Multi-fire honesty first-class (Tobarra hard, W3 external) — report-only.
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen,
  silent ``auto_ml_product_go``, ``sdc_auto_promote_over_iter1``.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_selective_sdc.py
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

from wildfire_front.ml.lab_selective_sdc import (  # noqa: E402
    bakeoff_rankings,
    decide_sdc_verdict,
)
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ClmEnsembleV34Facade,
    ProductFacadeError,
    assert_lab_rails,
    frozen_thr_from_val_selection,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    assert_rails_honest,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)
from wildfire_front.ml.rank_reject_protocol import (  # noqa: E402
    apply_reject_thr_metrics,
)
from wildfire_front.ml.uncertainty import load_calibrator  # noqa: E402

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_BANNER: Final = "lab product · not field_ops fusion · IoU ≠ ROS"


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path, allow_pickle=True)
    return (
        np.asarray(z["features"], dtype=np.float64),
        np.asarray(z["labels"], dtype=np.float64),
        np.asarray(z["ious"], dtype=np.float64),
    )


def _strip_bake(bake: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Drop curve arrays from bake-off rows for JSON board payloads."""
    return {k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in bake.items()}


def _seal_dead_paths() -> None:
    """Hard-refuse closed thrash / SDC auto-promote / field fusion hooks."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
        "sdc_auto_promote_over_iter1",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected — path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")


def _rails_payload(locked_thr: float, facade: ClmEnsembleV34Facade) -> dict[str, Any]:
    """Dual-product rails via product_facade (ml_product_go true; fusion OFF)."""
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
        "val_only_selection": True,
        "lab_only": True,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "locked_reject_thr": float(locked_thr),
        "freeze_iter1_reject": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen_forbidden": True,
        "sdc_auto_promote_over_iter1": False,
        "label": "lab / research_open only",
        "dead_paths": sorted(_DEAD_PATHS),
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "banner": _BANNER,
    }
    assert_rails_honest(rails, require_iter1_reject_default=True)
    return rails


def _rank_reject_protocol(locked_thr: float) -> dict[str, Any]:
    """Shared rank + abstain protocol (VAL thr; freeze iter1 reject via facade)."""
    proto = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_thr),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    return {
        **proto,
        "config": DEFAULT_RANK_REJECT.as_dict(),
        "thr_source": "val_iter1_reject_frozen",
        "thr_tune_split": "val",
        "freeze_iter1_reject": True,
        "fallback_thr": float(locked_thr),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "conf_source": "ClmEnsembleV34Facade.confidences",
        "ranking_api": (
            "lab_selective_sdc.bakeoff_rankings (families) + "
            "rank_reject_protocol.score_ranking (metrics) via facade conf"
        ),
        "note": (
            "Ranking bake-off and thr-reject share Head A confidences from "
            "product_facade; product surface thr is facade iter1 lock only; "
            "SDC family preference never flips frozen reject surface or field_ops."
        ),
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
        default=ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260805_selective_sdc.md",
    )
    p.add_argument("--no-md", action="store_true")
    p.add_argument("--min-lift-sel80", type=float, default=0.02)
    p.add_argument("--risk-alpha", type=float, default=0.15)
    args = p.parse_args(argv)

    if not args.calibrator.is_file():
        print(f"missing calibrator: {args.calibrator}", file=sys.stderr)
        return 1
    if not args.val_npz.is_file() or not args.test_npz.is_file():
        print("missing Head A caches", file=sys.stderr)
        return 1

    # Seal dead thrash / auto-promote paths (architecture refuse, not folklore).
    _seal_dead_paths()

    # Product facade: features → calibrator → shared conf → rank/reject surface.
    rails_obj = assert_lab_rails(DEFAULT_RAILS)
    cal = load_calibrator(args.calibrator)
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal, rails=rails_obj)
    locked_thr = float(ITER1_LOCKED_REJECT_THR)
    if abs(float(facade.rank_reject_cfg.reject_thr) - locked_thr) > 1e-9:
        raise ProductFacadeError(
            f"facade reject thr {facade.rank_reject_cfg.reject_thr} != frozen iter1 {locked_thr}"
        )

    vf, _, vi = _load_npz(args.val_npz)
    tf, _, ti = _load_npz(args.test_npz)

    # Shared conf via facade only (no lab_selective_sdc conf / thr orchestration).
    conf_v = facade.confidences(vf)
    conf_t = facade.confidences(tf)

    # SDC ranking families only (bake-off metrics via rank_reject_protocol).
    val_bake = bakeoff_rankings(vf, conf_v, vi)
    test_bake = bakeoff_rankings(tf, conf_t, ti)
    verdict = dict(decide_sdc_verdict(val_bake, min_lift_sel80=float(args.min_lift_sel80)))
    # Product surface always freezes iter1 reject — KILL keeps it; KEEP ranking
    # is lab-only family preference, never field promote / surface auto-flip.
    verdict["recommended_lab_surface"] = _RECOMMENDED_SURFACE
    verdict["freeze_iter1_reject"] = True
    verdict["sdc_auto_promote_over_iter1"] = False
    verdict["field_product"] = False
    verdict["ml_product_go"] = True
    verdict["locked_reject_thr"] = locked_thr

    # CRC-lite VAL thr report only; fallback = facade iter1 lock (never 0.80).
    conf_crc = facade.select_thr_on_val(conf_v, vi, risk_alpha=float(args.risk_alpha))
    crc_thr = frozen_thr_from_val_selection(conf_crc, fallback=locked_thr)
    test_at_crc = apply_reject_thr_metrics(conf_t, ti, crc_thr)
    # Product surface rank/reject at frozen facade thr (iter1).
    val_rr = facade.rank_reject(vf, conf_v, ious=vi)
    test_rr = facade.rank_reject(tf, conf_t, ious=ti)

    rails = _rails_payload(locked_thr, facade)
    rank_reject = _rank_reject_protocol(locked_thr)
    multi_fire = {
        **DEFAULT_MULTI_FIRE.as_dict(),
        **multi_fire_honesty_dict(),
        "facade_multi_fire": facade.multi_fire.as_dict(),
        "note": (
            "SDC bake-off is U1 holdout Head A ranking; Tobarra hard / W3 external "
            "remain first-class multi-fire boards under the same frozen thr surface."
        ),
    }

    conformal_crc_lite: dict[str, Any] = {
        "val": conf_crc,
        "test_at_val_thr": test_at_crc,
        "score_space": "logistic_conf",
        "frozen_thr": float(crc_thr),
        "fallback_thr": float(locked_thr),
        "thr_source": "val_crc_lite_or_iter1_facade_fallback",
        "product_surface_thr": float(locked_thr),
        "product_surface": _RECOMMENDED_SURFACE,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "note": (
            "CRC thr is report-only; product reject surface stays facade "
            f"iter1 lock thr={locked_thr} (not a parallel 0.80 default)."
        ),
    }

    board: dict[str, Any] = {
        "schema": "lab_loop_v34_selective_sdc_v1",
        "iteration": "selective_sdc_s1",
        "created_utc": datetime.now(UTC).isoformat(),
        "product_id": _PRODUCT_ID,
        "banner": _BANNER,
        "product_facade": _FACADE,
        "facade_class": "ClmEnsembleV34Facade",
        "pipeline": _PIPELINE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "deep_research": "docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md",
        "strategy": "S1_soft_dice_confidence_proxy",
        "control_question": (
            "Does Soft Dice Confidence proxy beat inv_entropy ranking on VAL "
            "sel@80 by +0.02 without AURC collapse?"
        ),
        "control_answer": verdict["verdict"],
        "verdict": verdict["verdict"],
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": locked_thr,
        "sdc_verdict": verdict,
        "val_bakeoff": _strip_bake(val_bake),
        "test_bakeoff": _strip_bake(test_bake),
        "conformal_crc_lite": conformal_crc_lite,
        "product_rank_reject": {
            "val": {
                k: v
                for k, v in val_rr.items()
                if k not in ("keep_mask", "conf") and not isinstance(v, np.ndarray)
            },
            "test": {
                k: v
                for k, v in test_rr.items()
                if k not in ("keep_mask", "conf") and not isinstance(v, np.ndarray)
            },
            "thr": locked_thr,
            "surface": _RECOMMENDED_SURFACE,
            "source": "ClmEnsembleV34Facade.rank_reject",
        },
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "honesty": [
            "SDC is a proxy from Head A (conf × margin soft-dice), not pixel soft-masks",
            "VAL selects ranking; TEST is one-shot report",
            "KILL_SDC_PROMOTE keeps iter1 reject thr surface",
            "KEEP_SDC_PROXY_LAB is ranking family only — no surface/field promote",
            "IoU ≠ ROS; ml_product_go true (lab promote); field fusion OFF",
            "Unified API: product_facade features→calibrator→rank/reject→scorecard",
            "lab_selective_sdc owns ranking families only; thr/conf via facade",
        ],
        "field_product": False,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out_dir / "lab_loop_v34_selective_sdc_latest.json"
    out_json.write_text(json.dumps(board, indent=2), encoding="utf-8")
    # also stamp latest pointer lightly
    latest = args.out_dir / "lab_loop_v34_latest.json"
    latest.write_text(
        json.dumps(
            {
                "schema": "lab_loop_v34_latest_pointer",
                "updated_utc": board["created_utc"],
                "iteration": board["iteration"],
                "path": str(out_json.as_posix()),
                "verdict": board["verdict"],
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "locked_reject_thr": locked_thr,
                "rails": {
                    "ml_product_go": True,
                    "field_ops_allow_ml_live_in_fusion": False,
                    "field_ops_ml_live_fusion": "OFF",
                    "iou_is_not_ros": True,
                    "recommended_lab_surface": _RECOMMENDED_SURFACE,
                },
                "product_facade": _FACADE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if not args.no_md:
        args.md_path.parent.mkdir(parents=True, exist_ok=True)
        vb = board["val_bakeoff"]
        tb = board["test_bakeoff"]
        lines = [
            "# Lab loop — Selective SDC (deep research S1)",
            "",
            f"**UTC:** {board['created_utc']}",
            f"**Verdict:** **{verdict['verdict']}**",
            f"**Recommended surface:** `{_RECOMMENDED_SURFACE}` (frozen; no SDC auto-promote)",
            f"**Product facade:** `{_FACADE}`",
            f"**Locked reject thr:** **{locked_thr}** (facade iter1; not 0.80)",
            "",
            "## Kill bar",
            "",
            f"- VAL sel@80 lift SDC vs inv_entropy ≥ **+{args.min_lift_sel80}**",
            f"- Observed lift: **{verdict['val_lift_sel80']:.4f}**",
            f"- VAL AURC SDC / entropy: {verdict['val_aurc_champion']:.4f} / {verdict['val_aurc_baseline']:.4f}",
            "",
            "## VAL bake-off (sel@80 · AURC lower better)",
            "",
            "| Score | sel@80 | lift vs full | AURC |",
            "|-------|-------:|-------------:|-----:|",
        ]
        for name, row in sorted(vb.items()):
            lines.append(
                f"| {name} | {row['selective_iou_at_80']:.4f} | "
                f"{row['lift_vs_full_at_80']:+.4f} | {row['aurc']:.4f} |"
            )
        lines += [
            "",
            "## TEST report (one-shot, not for thrash)",
            "",
            "| Score | sel@80 | lift vs full | AURC |",
            "|-------|-------:|-------------:|-----:|",
        ]
        for name, row in sorted(tb.items()):
            lines.append(
                f"| {name} | {row['selective_iou_at_80']:.4f} | "
                f"{row['lift_vs_full_at_80']:+.4f} | {row['aurc']:.4f} |"
            )
        crc = conformal_crc_lite
        sel = (crc.get("val") or {}).get("selected") or {}
        test_crc = crc.get("test_at_val_thr") or {}
        lines += [
            "",
            "## CRC-lite (VAL thr · TEST once · report only)",
            "",
            f"- risk_alpha: **{args.risk_alpha}**",
            f"- VAL thr: **{sel.get('thr')}** · risk {sel.get('risk')} · abstain {sel.get('abstain_rate')}",
            f"- TEST @ thr: IoU_acc **{test_crc.get('mean_iou_accepted')}** · "
            f"risk {test_crc.get('risk')} · abstain {test_crc.get('abstain_rate')}",
            f"- CRC fallback thr: **{locked_thr}** (facade iter1; never 0.80)",
            f"- Frozen product surface thr: **{locked_thr}** (`{_RECOMMENDED_SURFACE}`)",
            "",
            "## Rails",
            "",
            "- ml_product_go: **true**",
            "- field_ops fusion: **OFF**",
            "- IoU ≠ ROS · lab only",
            f"- recommended surface: **{_RECOMMENDED_SURFACE}** (KILL/KEEP both freeze; no field promote)",
            f"- pipeline: `{_PIPELINE}`",
            f"- conf/thr: `ClmEnsembleV34Facade` + `{_RANK_REJECT_PROTOCOL}`",
            "",
            f"Machine: `{out_json.as_posix()}`",
            "",
        ]
        args.md_path.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "verdict": verdict["verdict"],
                "val_lift_sel80": verdict["val_lift_sel80"],
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "locked_reject_thr": locked_thr,
                "ml_product_go": True,
                "out": str(out_json),
                "md": None if args.no_md else str(args.md_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
