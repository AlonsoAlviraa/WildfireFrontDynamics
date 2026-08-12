#!/usr/bin/env python3
"""Lab ML loop iter 9: multi-fire LOFO scoreboard as first-class architecture output.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05; no auto-flip);
  field fusion stays **OFF** (lab GO ≠ field fusion).
* Single path via ``product_facade`` + ``rank_reject_protocol``:
  features → calibrator → rank/reject (VAL thr freeze) → scorecard.
* Ranking / abstain share one protocol: VAL-only thr; freeze **iter1 reject**
  default (via facade / board — no conf math here).
* LOFO thr/report path is first-class: board ``frozen_thr_report`` +
  ``lofo_clm_ensemble_frozen_surface`` (ClmEnsemble conf → rank_reject metrics).
* Multi-fire honesty first-class: Tobarra hard, W3 external (not ad-hoc).
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen of KILL weights.
* LOFO mask IoU ≠ U1 Head A ECE. Scorecard/report only on LOFO split.

Uses existing ``lofo_v1`` evaluation_metrics + optional Head A caches for thr report.
Does **not** retrain, retune ECE, or flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_lofo_board.py
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_freeze import load_json  # noqa: E402
from wildfire_front.ml.lab_lofo_board import (  # noqa: E402
    LAB_BANNER,
    build_lofo_scoreboard,
    lofo_board_rails,
    lofo_clm_ensemble_frozen_surface,
)
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
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
)
from wildfire_front.ml.rank_reject_protocol import (  # noqa: E402
    DEAD_PROTOCOL_PATHS,
    protocol_payload,
    refuse_dead_protocol_path,
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS) | frozenset(DEAD_PROTOCOL_PATHS)
)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"


def _resolve_locked_thr(board: dict[str, Any]) -> float:
    """VAL-frozen thr only: board rails/protocol, else product_facade lock.

    Never fits or retunes on LOFO. Thr source is iter1 reject freeze.
    """
    rails = board.get("rails") if isinstance(board.get("rails"), dict) else {}
    protocol = board.get("protocol") if isinstance(board.get("protocol"), dict) else {}
    rr = board.get("rank_reject_protocol")
    locked = rails.get("locked_reject_thr")
    if locked is None:
        locked = protocol.get("locked_reject_thr")
    if locked is None and isinstance(rr, dict):
        locked = rr.get("locked_reject_thr")
    if locked is None:
        locked = ITER1_LOCKED_REJECT_THR
    return float(locked)


def _rank_reject_for_board(board: dict[str, Any], *, locked_thr: float) -> dict[str, Any]:
    """Prefer board pack rank_reject_protocol; else shared protocol_payload.

    Thr/report surface is first-class under rank_reject_protocol (not ad-hoc).
    """
    board_rr = board.get("rank_reject_protocol")
    if isinstance(board_rr, dict) and board_rr:
        return {
            **board_rr,
            "product_facade": _FACADE,
            "module": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "thr_source": board_rr.get("thr_source") or "val_iter1_reject_frozen",
            "recommended_lab_surface": board_rr.get("recommended_lab_surface")
            or _RECOMMENDED_SURFACE,
            "locked_reject_thr": float(
                board_rr.get("locked_reject_thr")
                if board_rr.get("locked_reject_thr") is not None
                else locked_thr
            ),
        }
    payload = protocol_payload(locked_reject_thr=float(locked_thr))
    return {
        **payload,
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "thr_source": "val_iter1_reject_frozen",
    }


def _architecture_lofo_board(board: dict[str, Any]) -> dict[str, Any]:
    """First-class architecture card: facade + rank_reject thr/report path."""
    mf = (
        board.get("multi_fire_honesty") if isinstance(board.get("multi_fire_honesty"), dict) else {}
    )
    v = board.get("verdict") if isinstance(board.get("verdict"), dict) else {}
    summ = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    locked_thr = _resolve_locked_thr(board)
    rank_reject = _rank_reject_for_board(board, locked_thr=locked_thr)

    frozen = (
        board.get("frozen_thr_report") if isinstance(board.get("frozen_thr_report"), dict) else {}
    )
    clm = board.get("clm_ensemble_surface")
    if not isinstance(clm, dict) or not clm:
        clm = lofo_clm_ensemble_frozen_surface(locked_reject_thr=locked_thr)

    w3 = mf.get("w3_external_on_disk") or mf.get("w3_external") or {}
    if not isinstance(w3, dict):
        w3 = {}

    return {
        "schema": "wfd_ml_architecture_lofo_board_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "banner": LAB_BANNER,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": float(locked_thr),
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
        "clm_ensemble_surface": clm,
        "frozen_thr_report": frozen,
        "frozen_thr_report_ok": bool(frozen.get("ok") or v.get("frozen_thr_report_ok")),
        "multi_fire_honesty": mf,
        "lofo_board_built": bool(v.get("lofo_board_built") or summ.get("n_folds", 0) >= 1),
        "n_folds": summ.get("n_folds"),
        "hard_folds": list(summ.get("hard_folds") or mf.get("hard_folds") or []),
        "tobarra_hard": bool(v.get("tobarra_hard") or mf.get("tobarra_hard")),
        "w3_external_present": bool(v.get("w3_external_present") or w3.get("present")),
        "note": (
            "Multi-fire LOFO scoreboard is first-class architecture output under "
            "shared product_facade + rank_reject_protocol thr/report path. "
            "LOFO ≠ U1 ECE; IoU ≠ ROS; Tobarra hard; W3 external; fusion OFF."
        ),
    }


def _board_rails() -> dict[str, Any]:
    """Dual-product rails from facade + LOFO board + rank_reject honesty flags."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = lofo_board_rails(r)
    base.update(
        {
            "label": "lab / research_open only",
            "no_ece_retune_same_holdout": True,
            "freeze_iter1_reject": True,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "forbidden_thrash": sorted(_DEAD_PATHS),
            "dead_paths": sorted(_DEAD_PATHS),
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    return base


def _refuse_dead_thrash() -> None:
    """Hard-seal ECE thrash + Tobarra KEEP reopen (facade + rank_reject protocol)."""
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        # expected: sealed
        with contextlib.suppress(ValueError):
            refuse_dead_protocol_path(dead)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument("--md-path", type=Path, default=None)
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Protocol integrity: LOFO is scorecard/report only (never thr/ECE tune).
    assert_split_role("lofo", "scorecard")
    assert_split_role("lofo", "report")
    # Dead thrash must stay closed (architecture refuse — not optional folklore).
    _refuse_dead_thrash()

    repo = args.repo.resolve()
    # Board pack already wires product_facade + rank_reject thr/report path.
    board = build_lofo_scoreboard(repo)
    created = datetime.now(UTC).isoformat()
    built = bool((board.get("verdict") or {}).get("lofo_board_built"))

    # Prefer facade rails; board already carries multi-fire + protocol + thr report.
    rails = _board_rails()
    board_rails = board.get("rails") if isinstance(board.get("rails"), dict) else {}
    rails = {**board_rails, **rails}
    arch = _architecture_lofo_board({**board, "rails": rails})
    locked_thr = float(arch.get("locked_reject_thr") or ITER1_LOCKED_REJECT_THR)
    rank_reject = arch.get("rank_reject_protocol") or _rank_reject_for_board(
        board, locked_thr=locked_thr
    )
    frozen = (
        arch.get("frozen_thr_report") if isinstance(arch.get("frozen_thr_report"), dict) else {}
    )
    clm = (
        arch.get("clm_ensemble_surface")
        if isinstance(arch.get("clm_ensemble_surface"), dict)
        else {}
    )

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_lofo_board_v1",
        "created_utc": created,
        "iteration": 9,
        "product_id": _PRODUCT_ID,
        "banner": LAB_BANNER,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "friction": "lofo_only_thin_table_not_full_scoreboard",
        "control_question": (
            "¿Podemos productizar un scoreboard multi-fuego LOFO (IoU/changed/spread) "
            "y anclar el fold más débil sin retunear ECE same-TEST ni abrir field_ops?"
        ),
        "control_answer": "YES" if built else "NO",
        "architecture_lofo_board": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "clm_ensemble_surface": clm,
        "frozen_thr_report": frozen,
        "multi_fire_honesty": board.get("multi_fire_honesty") or arch.get("multi_fire_honesty"),
        "board": board,
        "verdict": {
            **(board.get("verdict") or {}),
            "iteration": 9,
            "architecture_lofo_board": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "lofo_is_not_u1_ece": True,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "frozen_thr_report_ok": bool(frozen.get("ok") or arch.get("frozen_thr_report_ok")),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_lofo_board_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    summ = board.get("summary") or {}
    hold = board.get("holdout_reference") or {}
    mf = payload.get("multi_fire_honesty") or {}
    w3 = mf.get("w3_external_on_disk") or mf.get("w3_external") or {}
    if not isinstance(w3, dict):
        w3 = {}

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
            },
            **prev_iters,
            "9_lofo_board": "lab_loop_v34_lofo_board_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter9_lofo_board": True,
            "architecture_lofo_board": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "lofo": {
                "n_folds": summ.get("n_folds"),
                "model_iou_mean": summ.get("model_iou_mean"),
                "model_iou_std": summ.get("model_iou_std"),
                "spread_max_minus_min": summ.get("spread_max_minus_min"),
                "weakest_fold": summ.get("weakest_fold"),
                "weakest_iou": summ.get("weakest_iou"),
                "strongest_fold": summ.get("strongest_fold"),
                "n_beats_copy": summ.get("n_beats_copy"),
                "model_iou_changed_mean": summ.get("model_iou_changed_mean"),
                "hard_folds": summ.get("hard_folds") or mf.get("hard_folds"),
            },
            "multi_fire_honesty": {
                "tobarra_hard": bool(mf.get("tobarra_hard") or summ.get("hard_folds")),
                "hard_folds": list(summ.get("hard_folds") or mf.get("hard_folds") or []),
                "w3_external_present": bool(w3.get("present")),
                "w3_fires": w3.get("fires") or [],
                "do_not_reopen_tobarra_keep": True,
                "do_not_universalize_u1": True,
            },
            "generalization_note": hold.get("generalization_note"),
            "holdout_u1_iou": hold.get("u1_test_mean_iou") or prev_sum.get("holdout_u1_iou"),
            "holdout_u1_ece": hold.get("u1_ece") or prev_sum.get("holdout_u1_ece"),
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "thrash_iters_not_promote_path": {
                "2_ece_posthoc": "dead",
                "3_refit": "dead",
            },
            "rank_reject_protocol": rank_reject,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "frozen_thr_report_ok": bool(frozen.get("ok")),
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "lofo_is_not_u1_ece": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_thr,
                "freeze_iter1_reject": True,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "pipeline": _PIPELINE,
            },
            "cli_lofo": "wildfire-front ml lofo",
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_lofo_board.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": built,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "n_folds": summ.get("n_folds"),
                "lofo_iou_mean": summ.get("model_iou_mean"),
                "weakest_fold": summ.get("weakest_fold"),
                "weakest_iou": summ.get("weakest_iou"),
                "spread": summ.get("spread_max_minus_min"),
                "hard_folds": summ.get("hard_folds") or mf.get("hard_folds"),
                "tobarra_hard": bool(mf.get("tobarra_hard") or summ.get("hard_folds")),
                "w3_external_present": bool(w3.get("present")),
                "gap_u1_minus_lofo": hold.get("gap_u1_minus_lofo_mean"),
                "control_answer": payload["control_answer"],
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "ece_thrash_reopen": False,
                "tobarra_keep_reopen": False,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "frozen_thr_report_ok": bool(frozen.get("ok")),
                "pipeline": _PIPELINE,
            },
            indent=2,
        )
    )
    return 0 if built else 2


def _n(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return str(v)


def _render_md(payload: dict[str, Any]) -> str:
    board = payload.get("board") or {}
    s = board.get("summary") or {}
    h = board.get("holdout_reference") or {}
    arch = payload.get("architecture_lofo_board") or {}
    mf = payload.get("multi_fire_honesty") or {}
    tob = mf.get("tobarra") or {}
    w3 = mf.get("w3_external_on_disk") or mf.get("w3_external") or {}
    if not isinstance(w3, dict):
        w3 = {}
    w3_fires = list(w3.get("fires") or [])
    hard = list(s.get("hard_folds") or mf.get("hard_folds") or [])
    frozen = payload.get("frozen_thr_report") or {}
    if not isinstance(frozen, dict):
        frozen = {}
    lines = [
        "# ML lab loop — iter 9 LOFO multi-fire scoreboard",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** freeze + smoke (iters 7–8)  ",
        f"**Banner:** {payload.get('banner') or LAB_BANNER}  ",
        "**Label:** lab / research_open only",
        "",
        "## Architecture (shared rails / protocol)",
        "",
        "| Gate | Value |",
        "|------|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| pipeline | **{_PIPELINE}** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| locked reject thr | **{arch.get('locked_reject_thr')}** |",
        "| freeze iter1 reject | **true** |",
        "| LOFO ≠ U1 ECE | **true** |",
        f"| frozen thr report ok | **{bool(frozen.get('ok') or arch.get('frozen_thr_report_ok'))}** |",
        f"| Tobarra hard | **{arch.get('tobarra_hard')}** |",
        f"| W3 external present | **{arch.get('w3_external_present')}** |",
        "| dead thrash closed | **true** |",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| LOFO = U1 ECE | **never** |",
        "| ECE thrash same TEST | **stopped** |",
        "| Tobarra KEEP reopen | **closed** |",
        f"| Tobarra | **{tob.get('keep_verdict') or tob.get('verdict') or tob.get('role') or 'hard_transfer'}** |",
        f"| W3 external | **{len(w3_fires)} fires ({', '.join(w3_fires) or 'none'})** |",
        f"| hard folds | **{', '.join(hard) or '—'}** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        f"- LOFO mean IoU: **{_n(s.get('model_iou_mean'))}** (n={s.get('n_folds')})",
        f"- spread: **{_n(s.get('spread_max_minus_min'))}**",
        f"- weakest: **{s.get('weakest_fold')}** @ **{_n(s.get('weakest_iou'))}**",
        f"- U1 gap: **{_n(h.get('gap_u1_minus_lofo_mean'))}**",
        f"- note: `{h.get('generalization_note')}`",
        f"- thr report: n_cache_folds=**{frozen.get('n_cache_folds', 0)}** "
        f"(ok={bool(frozen.get('ok'))})",
        "",
        "## Folds",
        "",
        "| Fold | IoU | copy | Δ | changed | role |",
        "|------|----:|-----:|--:|--------:|------|",
    ]
    for r in board.get("folds") or []:
        role = (r.get("honesty") or {}).get("role") or "—"
        lines.append(
            f"| {r.get('fold')} | {_n(r.get('model_iou'))} | "
            f"{_n(r.get('copy_baseline_iou'))} | {_n(r.get('improvement_vs_copy_iou'))} | "
            f"{_n(r.get('model_iou_changed'))} | {role} |"
        )
    lines += [
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml lofo",
        "python -m wildfire_front ml lofo --json",
        "python scripts/run_lab_ml_loop_v34_lofo_board.py",
        "```",
        "",
        "---",
        "*Iteration 9 — multi-fire LOFO board on product_facade + rank_reject_protocol "
        "thr/report path; not field product; thrash closed.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
