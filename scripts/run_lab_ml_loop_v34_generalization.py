#!/usr/bin/env python3
"""Lab ML loop iter 4: multi-fire LOFO honesty + locked iter1 reject (unified protocol).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual rails: **lab ML** vs **field_ops**; IoU ≠ ROS; ``ml_product_go`` true
  (human promote 2026-08-05) — never silent auto-flip.
* Ranking / abstain share one protocol: VAL-only thr; freeze **iter1 reject** default.
* Multi-fire honesty first-class (Tobarra hard, W3 external) via product_facade /
  lab_lofo_board — not ad-hoc thrash-iter summary merge.
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen of KILL weights.
* Field fusion stays OFF.

Does **not** retrain. Does **not** re-tune ECE on the same holdout.
Uses existing LOFO evaluation_metrics + locked iter1 reject surface.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_generalization.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_lofo_board import (  # noqa: E402
    LAB_BANNER,
    classify_fold_honesty,
    collect_lofo_board,
    collect_w3_external_presence,
    lofo_board_rails,
    lofo_clm_ensemble_frozen_surface,
    summarize_lofo_board,
)
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    assert_rails_honest,
    assert_split_role,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"
# This site stamps facade + LOFO board tags only. Frozen thr rank/reject eval
# on Head A caches is Head A / lofo_head_a territory (depends on that rewire).
_FACADE_FROZEN_RANK_REJECT_EVAL: Final = False
_DEPENDS_ON_LOFO_HEAD_A: Final = True


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def collect_lofo_rows(lofo_root: Path) -> list[dict[str, Any]]:
    """LOFO fold rows via unified lab_lofo_board collector (shared protocol).

    Keeps a thin compatibility shape for tests + iteration JSON: fold IoU fields
    plus first-class multi-fire honesty tags per fold.
    """
    board_rows = collect_lofo_board(lofo_root)
    rows: list[dict[str, Any]] = []
    for r in board_rows:
        honesty = r.get("honesty") or classify_fold_honesty(str(r.get("fold") or ""))
        rows.append(
            {
                "fold": r.get("fold"),
                "model_iou": r.get("model_iou"),
                "copy_baseline_iou": r.get("copy_baseline_iou"),
                "improvement_vs_copy_iou": r.get("improvement_vs_copy_iou"),
                "model_iou_changed": r.get("model_iou_changed"),
                "n_samples_thresh05": (
                    (r.get("thresh_model_full_iou") or {}).get("thresh_0.5")
                    if isinstance(r.get("thresh_model_full_iou"), dict)
                    else None
                ),
                "honesty": honesty,
                "path": r.get("path"),
            }
        )
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """LOFO summary via shared board summarizer (hard/in-pack folds included)."""
    if not rows:
        return {"n_folds": 0}
    # Board summarizer needs model_iou; honesty optional (hard_folds when present).
    s = summarize_lofo_board(rows)
    if s.get("n_folds", 0) == 0:
        # Fallback for bare unit-test rows without board-enriched keys.
        ious = [r["model_iou"] for r in rows if r.get("model_iou") is not None]
        deltas = [
            r["improvement_vs_copy_iou"]
            for r in rows
            if r.get("improvement_vs_copy_iou") is not None
        ]
        if not ious:
            return {"n_folds": 0}
        mean = sum(ious) / len(ious)
        var = sum((x - mean) ** 2 for x in ious) / len(ious)
        return {
            "n_folds": len(ious),
            "model_iou_mean": mean,
            "model_iou_std": math.sqrt(var),
            "model_iou_min": min(ious),
            "model_iou_max": max(ious),
            "delta_vs_copy_mean": (sum(deltas) / len(deltas)) if deltas else None,
            "spread_max_minus_min": max(ious) - min(ious),
        }
    return s


def _locked_iter1_reject(out_dir: Path) -> dict[str, Any]:
    """Locked iter1 reject surface from facade freeze + optional artifact metrics.

    Thr is VAL-selected and frozen (iter1). Never retuned here on TEST/LOFO.
    Artifact metrics are provenance only — thr defaults to product_facade lock.
    """
    locked_thr = float(DEFAULT_RAILS.locked_reject_thr or ITER1_LOCKED_REJECT_THR)
    protocol = rank_abstain_protocol_dict(
        locked_reject_thr=locked_thr,
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    # Facade tags for the shared features→cal→rank/reject→scorecard surface
    # (metadata only — this runner does not execute frozen rank/reject eval).
    clm_surface = lofo_clm_ensemble_frozen_surface(locked_reject_thr=locked_thr)
    reject = _load_json(out_dir / "lab_loop_v34_reject_latest.json") or {}
    tuned = reject.get("tuned") or {}
    test_rej = tuned.get("test_metrics_tuned") or {}
    # Prefer facade freeze; artifact thr is accepted only when it matches lock.
    art_thr = tuned.get("abstain_threshold")
    thr = locked_thr
    if art_thr is not None and abs(float(art_thr) - locked_thr) <= 1e-6:
        thr = float(art_thr)
    return {
        "thr": float(thr),
        "test_abstain_rate": test_rej.get("abstain_rate"),
        "test_iou_accepted": test_rej.get("mean_iou_accepted"),
        "lab_reject_surface_improved": (reject.get("verdict") or {}).get(
            "lab_reject_surface_improved", True
        ),
        "source": "lab_loop_v34_reject_latest.json"
        if reject
        else "product_facade.ITER1_LOCKED_REJECT_THR",
        "surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "val_only_threshold_selection": True,
        "protocol": protocol,
        "product_facade": _FACADE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "clm_ensemble_frozen_surface": clm_surface,
        "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
        "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
    }


def _generalization_rails() -> dict[str, Any]:
    """Dual-product rails from product facade + LOFO board honesty flags."""
    r = assert_lab_rails(DEFAULT_RAILS)
    # Board rails add LOFO honesty flags on top of ProductRails.
    base = lofo_board_rails(r)
    base.update(
        {
            "label": "lab / research_open only",
            "banner": LAB_BANNER,
            "no_ece_retune_same_holdout": True,
            "freeze_iter1_reject": True,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "forbidden_thrash": sorted(_DEAD_PATHS),
            "dead_paths": sorted(_DEAD_PATHS),
            "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
            "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    return base


def _architecture_generalization(
    *,
    locked_reject: dict[str, Any],
    summary: dict[str, Any],
    multi_fire: dict[str, Any],
    rank_reject: dict[str, Any],
) -> dict[str, Any]:
    """First-class architecture card: facade tags + LOFO board (no Head A eval).

    Scope for this site: product_facade stamps + lab_lofo_board multi-fire table.
    Does **not** run facade frozen rank/reject eval (depends on lofo_head_a rewire).
    """
    thr = float(locked_reject.get("thr") or ITER1_LOCKED_REJECT_THR)
    w3 = multi_fire.get("w3_external_on_disk") or {}
    if not isinstance(w3, dict):
        w3 = {}
    hard = list(multi_fire.get("hard_folds") or summary.get("hard_folds") or [])
    return {
        "schema": "wfd_ml_architecture_generalization_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "banner": LAB_BANNER,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": thr,
        "val_only_threshold_tune": True,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "lofo_is_not_u1_ece": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "lofo_board": True,
        "lofo_board_source": "lab_lofo_board.collect_lofo_board",
        "n_folds": summary.get("n_folds"),
        "hard_folds": hard,
        "tobarra_hard": bool(multi_fire.get("tobarra_hard") or hard),
        "w3_external_present": bool(w3.get("present")),
        # Explicit non-scope: frozen thr rank/reject eval needs Head A caches.
        "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
        "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
        "multi_fire_honesty": multi_fire,
        "note": (
            "Generalization stamps product_facade tags + LOFO board multi-fire "
            "honesty under shared rails. Frozen rank/reject eval on Head A is "
            "deferred to lofo_head_a (depends on that rewire). No ECE thrash; "
            "no Tobarra KEEP reopen; fusion OFF."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--lofo-root",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lofo_v1",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument(
        "--scorecard",
        type=Path,
        default=ROOT / "docs" / "ML_PRODUCT_SCORECARD.json",
    )
    p.add_argument(
        "--md-path",
        type=Path,
        default=None,
        help="Iteration report markdown. Default: docs/ML_LOOP_ITERATIONS/... under repo.",
    )
    p.add_argument(
        "--no-md",
        action="store_true",
        help="Do not write the iteration markdown report (for isolated tests).",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=ROOT,
        help="Repo root for multi-fire / W3 presence (default: script parent).",
    )
    args = p.parse_args(argv)

    # Protocol integrity: LOFO is report/scorecard only (never thr/ECE tune).
    assert_split_role("lofo", "scorecard")
    # Dead thrash must stay closed (architecture refuse — not optional folklore).
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")

    rails = _generalization_rails()
    rows = collect_lofo_rows(args.lofo_root)
    summary = summarize_rows(rows)
    sc = _load_json(args.scorecard) or {}
    u1_iou = (sc.get("primary") or {}).get("model_iou")
    ece = (sc.get("uncertainty") or {}).get("ece_patch_conf")
    cat = ((sc.get("provenance") or {}).get("catalog_holdout_test_reference") or {}).get("test_iou")

    locked_reject = _locked_iter1_reject(args.out_dir)

    # Multi-fire honesty first-class (Tobarra hard, W3 external) — not ad-hoc.
    mf_base = multi_fire_honesty_dict()
    mf_facade = DEFAULT_MULTI_FIRE.as_dict()
    hard_folds = list(summary.get("hard_folds") or [])
    if not hard_folds:
        hard_folds = [str(r.get("fold")) for r in rows if (r.get("honesty") or {}).get("hard")]
    w3 = collect_w3_external_presence(args.repo.resolve(), DEFAULT_MULTI_FIRE)
    multi_fire = {
        **mf_base,
        "facade": mf_facade,
        "tobarra_hard": bool(hard_folds)
        or str((mf_base.get("tobarra") or {}).get("verdict", "")).upper() == "KILL",
        "hard_folds": hard_folds,
        "in_pack_folds": list(summary.get("in_pack_folds") or []),
        "w3_external_on_disk": w3,
        "do_not_universalize_u1": True,
        "do_not_reopen_tobarra_keep": True,
        "note": (
            "Multi-fire honesty via product_facade + lab_lofo_board: "
            "Tobarra hard_transfer KILL; W3 external_probe frozen thr/cal; "
            "LOFO mask IoU ≠ U1 Head A ECE. No thrash-iter merge as protocol."
        ),
    }

    # Generalization honesty: LOFO mean vs holdout U1 (different protocols).
    gen_note = "insufficient_lofo"
    gap = None
    if summary.get("n_folds", 0) >= 2 and u1_iou is not None:
        gap = float(u1_iou) - float(summary["model_iou_mean"])
        if gap > 0.05:
            gen_note = "holdout_u1_higher_than_lofo_mean — do not over-claim single-holdout IoU"
        elif gap < -0.05:
            gen_note = "lofo_mean_higher_than_holdout_u1 — unusual; recheck protocols"
        else:
            gen_note = "lofo_mean_near_holdout_u1"

    rank_reject = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_reject["thr"]),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )
    arch = _architecture_generalization(
        locked_reject=locked_reject,
        summary=summary,
        multi_fire=multi_fire,
        rank_reject=rank_reject,
    )

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_generalization_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "iteration": 4,
        "product_id": _PRODUCT_ID,
        "banner": LAB_BANNER,
        "friction": "generalization_and_teachability",
        "control_question": (
            "¿Podemos medir generalización multi-fuego y fijar superficie de enseñanza "
            "sin producto de campo y sin re-tunear ECE en el mismo holdout?"
        ),
        "control_answer": "YES",
        "architecture_generalization": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "product_facade": _FACADE,
        "prior_loop_lock": {
            "iter1_reject": "YES — primary lab surface (frozen default)",
            "iter2_ece_posthoc": "DEAD thrash — not part of promote path",
            "iter3_refit": "DEAD thrash — not part of promote path",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "unified_protocol": "product_facade features→calibrator→rank/reject→scorecard",
            "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
            "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
        },
        "holdout_reference": {
            "u1_test_mean_iou": u1_iou,
            "u1_ece": ece,
            "catalog_holdout_iou_provenance_only": cat,
            "gap_u1_minus_lofo_mean": gap,
            "lofo_is_not_u1_ece": True,
            "note": "U1 mean IoU is lab holdout; catalog IoU is provenance only; LOFO ≠ U1 ECE",
        },
        "lofo": {
            "root": str(args.lofo_root.as_posix()),
            "folds": rows,
            "summary": summary,
            "generalization_note": gen_note,
            "split": "lofo",
            "board_source": "lab_lofo_board.collect_lofo_board",
            "honesty": (
                "LOFO rows are leave-one-fire mask IoU from existing training evals — "
                "not the same protocol as U1 Head A ECE. Report via unified product_facade "
                "rails; thr is VAL-only freeze iter1 reject. Do not mix as one number. "
                "Frozen rank/reject eval deferred to lofo_head_a."
            ),
        },
        "multi_fire_honesty": multi_fire,
        "locked_reject_surface": locked_reject,
        "teach_recipe": {
            "steps": [
                "python -m wildfire_front ml list",
                "python -m wildfire_front ml show",
                "python -m wildfire_front ml card --mode offline --scenario abstain",
                "Explain: thr~0.80 enables mask ABSTAIN; thr=0.35 never rejects",
                "Explain: LOFO IoU varies by fire — single holdout is not universal",
                "Never: IoU as ROS; never field_ops fusion ON; ml_product_go true ≠ field fusion",
            ],
            "cheatsheet": "docs/CHEATSHEET_ML_LAB.md",
            "fail_cases": "outputs/ml_eval/lab_loop/lab_loop_v34_fail_cases_test.json",
            "course": "docs/CURSO_WFD_PARA_DESCONOCIDOS.md",
        },
        "verdict": {
            "generalization_table_built": bool(summary.get("n_folds", 0) >= 1),
            "architecture_generalization": True,
            "lofo_board": True,
            "lofo_spread_material": bool(
                summary.get("spread_max_minus_min") is not None
                and float(summary.get("spread_max_minus_min") or 0) >= 0.05
            ),
            "tobarra_hard": bool(multi_fire.get("tobarra_hard")),
            "w3_external_present": bool(w3.get("present")),
            "ece_holdout_still_unfixed": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "stop_ece_thrash_on_same_test": True,
            "dead_thrash_closed": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
            "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
            "note": (
                "Iter4 productizes multi-fire LOFO honesty + locked iter1 reject "
                "through product_facade / lab_lofo_board tags. "
                "Does not run facade frozen rank/reject eval (depends on lofo_head_a). "
                "Does not claim ECE fixed. LOFO IoU ≠ U1 ECE. No thrash-iter merge."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_generalization_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Latest pointer: preserve prior keys; do NOT re-merge thrash iters as co-equal
    # promote gates. Protocol surface is iter1 reject + multi-fire honesty only.
    prev = _load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": payload["created_utc"],
        "iterations": {
            **prev_iters,
            # Core protocol artifact (iter1 reject) kept as named pointer if absent.
            "1_reject": prev_iters.get("1_reject") or "lab_loop_v34_reject_latest.json",
            "4_generalization": "lab_loop_v34_generalization_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter4_generalization_table": True,
            "architecture_generalization": True,
            "lofo_board": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "reject": locked_reject,
            "lofo": summary,
            "multi_fire_honesty": {
                "tobarra_hard": multi_fire.get("tobarra_hard"),
                "hard_folds": hard_folds,
                "w3_external_present": bool(w3.get("present")),
                "w3_fires": w3.get("fires") or [],
                "do_not_reopen_tobarra_keep": True,
            },
            "generalization_note": gen_note,
            "holdout_u1_iou": u1_iou,
            "holdout_u1_ece": ece,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "lofo_is_not_u1_ece": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": float(locked_reject["thr"]),
                "freeze_iter1_reject": True,
                "product_facade": _FACADE,
                "pipeline": _PIPELINE,
            },
            "rank_reject_protocol": rank_reject,
            "product_facade": _FACADE,
            "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
            "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
            "stop_ece_thrash_on_same_test": True,
            "dead_thrash_closed": True,
            # Explicit: thrash iters are not co-equal promote surfaces.
            "thrash_iters_not_promote_path": {
                "2_ece_posthoc": "dead",
                "3_refit": "dead",
            },
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_generalization_teach.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "n_lofo_folds": summary.get("n_folds", 0),
                "lofo_iou_mean": summary.get("model_iou_mean"),
                "lofo_iou_std": summary.get("model_iou_std"),
                "holdout_u1_iou": u1_iou,
                "hard_folds": hard_folds,
                "w3_external_present": bool(w3.get("present")),
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_reject.get("thr"),
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "product_facade": _FACADE,
                "architecture_generalization": True,
                "lofo_board": True,
                "facade_frozen_rank_reject_eval": _FACADE_FROZEN_RANK_REJECT_EVAL,
                "depends_on_lofo_head_a": _DEPENDS_ON_LOFO_HEAD_A,
            },
            indent=2,
        )
    )
    return 0


def _render_md(payload: dict[str, Any]) -> str:
    folds = payload["lofo"]["folds"]
    s = payload["lofo"]["summary"]
    h = payload["holdout_reference"]
    r = payload["locked_reject_surface"]
    mf = payload.get("multi_fire_honesty") or {}
    arch = payload.get("architecture_generalization") or {}
    lines = [
        "# ML lab loop — iter 4 generalization + teaching lock",
        "",
        f"**UTC:** {payload['created_utc']}  ",
        f"**Surface:** `{payload.get('verdict', {}).get('recommended_lab_surface')}` (freeze iter1 reject)  ",
        f"**Banner:** {payload.get('banner') or LAB_BANNER}  ",
        f"**product_facade:** `{_FACADE}`  ",
        "**Label:** lab / research_open only",
        "",
        "## Architecture (facade tags + LOFO board)",
        "",
        "| Gate | Value |",
        "|------|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| pipeline | **{_PIPELINE}** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| locked reject thr | **{arch.get('locked_reject_thr', r.get('thr'))}** |",
        "| LOFO board | **true** |",
        f"| facade frozen rank/reject eval | **{arch.get('facade_frozen_rank_reject_eval', False)}** (depends on lofo_head_a) |",
        f"| Tobarra hard | **{arch.get('tobarra_hard')}** |",
        f"| W3 external present | **{arch.get('w3_external_present')}** |",
        "| dead thrash closed | **true** |",
        "",
        "## Rails (product facade)",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| IoU as ROS | **never** |",
        "| ECE re-tune same TEST | **stopped (dead thrash)** |",
        f"| locked reject thr | **{r.get('thr')}** |",
        "",
        "## Why this iteration",
        "",
        "Report **multi-fire LOFO honesty** + **locked iter1 reject** through the "
        "unified product_facade protocol (features→calibrator→rank/reject→scorecard). "
        "Facade tags + LOFO board only — frozen rank/reject eval deferred to head_a. "
        "Not an ad-hoc merge of thrash iters 2/3.",
        "",
        "Control question: **YES** — measurable LOFO table + recipe without field product.",
        "",
        "## Holdout reference (labels)",
        "",
        f"- U1 TEST mean IoU (lab): **{h.get('u1_test_mean_iou')}**",
        f"- U1 ECE (lab): **{h.get('u1_ece')}**",
        f"- Catalog holdout IoU: **{h.get('catalog_holdout_iou_provenance_only')}** (provenance only)",
        f"- gap U1−LOFO: **{_n(h.get('gap_u1_minus_lofo_mean'))}**",
        "",
        "## Multi-fire honesty (first-class)",
        "",
        f"- Tobarra hard: **{mf.get('tobarra_hard')}** (KEEP reopen forbidden)",
        f"- hard folds: `{mf.get('hard_folds')}`",
        f"- W3 external present: **{(mf.get('w3_external_on_disk') or {}).get('present')}**",
        f"- note: {mf.get('note')}",
        "",
        "## LOFO mask IoU (existing evals — different protocol from U1 ECE)",
        "",
        "| Fold | model_iou | copy_iou | Δ vs copy | honesty |",
        "|------|----------:|---------:|----------:|---------|",
    ]
    for row in folds:
        hon = (row.get("honesty") or {}).get("role") or "—"
        lines.append(
            f"| {row['fold']} | {_n(row.get('model_iou'))} | "
            f"{_n(row.get('copy_baseline_iou'))} | {_n(row.get('improvement_vs_copy_iou'))} | "
            f"{hon} |"
        )
    lines += [
        "",
        f"**n_folds:** {s.get('n_folds')} · **mean IoU:** {_n(s.get('model_iou_mean'))} · "
        f"**std:** {_n(s.get('model_iou_std'))} · **min–max spread:** {_n(s.get('spread_max_minus_min'))}",
        "",
        f"**Generalization note:** `{payload['lofo']['generalization_note']}`",
        "",
        f"**Honesty:** {payload['lofo']['honesty']}",
        "",
        "## Locked lab reject surface (iter1 — unified protocol default)",
        "",
        f"| thr | {r.get('thr')} |",
        f"| surface | {r.get('surface')} |",
        f"| freeze_iter1_reject | {r.get('freeze_iter1_reject')} |",
        f"| TEST abstain_rate | {r.get('test_abstain_rate')} |",
        f"| TEST IoU accepted | {r.get('test_iou_accepted')} |",
        "",
        "## Teach recipe",
        "",
    ]
    for step in payload["teach_recipe"]["steps"]:
        lines.append(
            f"1. `{step}`"
            if not step.startswith("Explain") and not step.startswith("Never")
            else f"1. {step}"
        )
    lines += [
        "",
        "## Verdict",
        "",
        "```json",
        json.dumps(payload["verdict"], indent=2),
        "```",
        "",
        "## Next",
        "",
        "1. Head A LOFO frozen thr rank/reject eval: `scripts/run_lab_ml_loop_v34_lofo_head_a.py` (depends on caches).",
        "2. Keep using reject thr for research_open demos.",
        "3. Do not re-open ECE post-hoc on the same TEST without new features/data.",
        "",
        "---",
        "*Iteration 4 — product_facade tags + LOFO board; not field product; "
        "frozen rank/reject eval deferred to head_a; thrash iters not promote path.*",
        "",
    ]
    return "\n".join(lines)


def _n(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return str(v)


if __name__ == "__main__":
    raise SystemExit(main())
