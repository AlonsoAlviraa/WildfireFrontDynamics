#!/usr/bin/env python3
"""Lab ML loop iter 5: productize fail-cases + LOFO board as teach surface.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05); field fusion stays **OFF**.
* Shared rank/reject / LOFO surface: VAL-only thr; freeze **iter1 reject**
  as default via ``product_facade`` + ``rank_reject_protocol`` /
  ``lab_teach_cases`` (features→calibrator→rank/reject→scorecard).
* Multi-fire honesty first-class (Tobarra hard, W3 external) via teach pack.
* Dead thrash sealed: same-holdout ECE retune / refit and Tobarra KEEP reopen
  are **stripped** from latest iteration pointers (never chained).
* DRY rails/protocol come from ``lab_teach_cases`` pack (facade scorecard
  path) — runner only tags + freezes latest pointer (no conf math).

Does **not** retrain. Does **not** re-tune ECE. Does **not** flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_teach_cases.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_teach_cases import (  # noqa: E402
    build_teach_cases_pack,
    load_json,
    teach_facade_rails,
    teach_rank_reject_surface,
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
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_FACADE_CLASS: Final = "ClmEnsembleV34Facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"
_SCORECARD_API: Final = "ClmEnsembleV34Facade.scorecard"
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)

# Core promote-path artifacts (shared reject / LOFO / teach). Never chain thrash here.
_CORE_ITER_ARTIFACTS: dict[str, str] = {
    "1_reject": "lab_loop_v34_reject_latest.json",
    "4_generalization": "lab_loop_v34_generalization_latest.json",
    "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
}
# Dead thrash artifact names (documentation only — never written into latest iters).
_DEAD_THRASH_ITER_ARTIFACTS: dict[str, str] = {
    "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
    "3_refit": "lab_loop_v34_refit_latest.json",
}
_THRASH_ITER_KEYS: frozenset[str] = frozenset(_DEAD_THRASH_ITER_ARTIFACTS)


def _sealed_thrash_summary() -> dict[str, Any]:
    """Mark same-holdout ECE/refit + Tobarra KEEP thrash sealed in latest summary."""
    return {
        "iter2_ece": {
            "method": "none",
            "status": "deprecated_thrash_sealed",
            "improved": False,
            "retune_executed": False,
        },
        "iter2_ece_improved": False,
        "iter3_refit": {
            "method": "none",
            "status": "deprecated_thrash_sealed",
            "improved": False,
            "refit_executed": False,
        },
        "iter3_ece_improved": False,
        "stop_ece_thrash_on_same_test": True,
        "no_ece_retune_same_holdout": True,
        "ece_thrash_reopen": False,
        "tobarra_keep_reopen": False,
        "thrash_sealed": True,
        "dead_thrash_closed": True,
        "thrash_iters_not_promote_path": {
            "2_ece_posthoc": "dead",
            "3_refit": "dead",
        },
        "dead_paths": sorted(_DEAD_PATHS),
    }


def _latest_iterations(prev_iters: dict[str, Any]) -> dict[str, Any]:
    """Build latest iteration map: freeze on reject/LOFO/teach only.

    Strip ECE/refit thrash keys even if present in prev — teaching must not
    chain dead thrash artifacts into the promote-path latest pointer.
    Core surface always: iter1 reject + LOFO/generalization + teach.
    """
    non_thrash_prev = {k: v for k, v in prev_iters.items() if k not in _THRASH_ITER_KEYS}
    return {
        **non_thrash_prev,
        **_CORE_ITER_ARTIFACTS,
        "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
    }


def _architecture_teach_cases(
    pack: dict[str, Any],
    *,
    locked_thr: float,
    rails: dict[str, Any],
    rank_reject: dict[str, Any],
    multi_fire: dict[str, Any],
) -> dict[str, Any]:
    """First-class architecture card: facade scorecard path + dual rails."""
    return {
        "schema": "wfd_ml_architecture_teach_cases_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
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
        "ece_thrash_reopen": False,
        "tobarra_keep_reopen": False,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "facade_class": rails.get("facade_class") or pack.get("facade_class") or _FACADE_CLASS,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "scorecard_api": _SCORECARD_API,
        "multi_fire_honesty": multi_fire,
        "rails": {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "locked_reject_thr": float(locked_thr),
            "product_facade": rails.get("product_facade") or _FACADE,
            "facade_class": rails.get("facade_class") or _FACADE_CLASS,
            "pipeline": rails.get("pipeline") or _PIPELINE,
            "rank_reject_protocol": rails.get("rank_reject_protocol") or _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
        },
        "teach_pack_schema": pack.get("schema"),
        "teach_pack_facade_path": {
            "product_facade": pack.get("product_facade") or _FACADE,
            "facade_class": pack.get("facade_class") or _FACADE_CLASS,
            "pipeline": pack.get("pipeline") or _PIPELINE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
        },
        "note": (
            "Teach surface under shared product_facade + rank_reject_protocol "
            f"({_PIPELINE}; {_SCORECARD_API}). Pack from lab_teach_cases facade "
            "scorecard path; runner tags + freezes latest pointer (no conf math). "
            "LOFO/W3 first-class; Tobarra hard; ECE thrash sealed; fusion OFF."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument(
        "--md-path",
        type=Path,
        default=None,
        help="Iteration report markdown (default under docs/ML_LOOP_ITERATIONS).",
    )
    p.add_argument(
        "--no-md",
        action="store_true",
        help="Skip writing markdown (for isolated tests).",
    )
    p.add_argument(
        "--repo",
        type=Path,
        default=ROOT,
        help="Repo root for pack inputs (default: script parent).",
    )
    args = p.parse_args(argv)

    # Dead thrash must stay sealed (architecture refuse — not optional folklore).
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")

    # Dual rails: product facade honesty (pack carries full facade scorecard path).
    assert_lab_rails(DEFAULT_RAILS)

    repo = args.repo.resolve()
    pack = build_teach_cases_pack(repo)
    created = datetime.now(UTC).isoformat()

    fc = pack.get("fail_cases") or {}
    lofo = pack.get("lofo") or {}
    rej = pack.get("locked_reject") or {}
    locked_thr = float(rej.get("thr_value") or rej.get("thr") or ITER1_LOCKED_REJECT_THR)

    # Prefer pack rails/rank_reject (lab_teach_cases facade scorecard path);
    # fall back to teach_* helpers only if pack omitted them.
    pack_rails = pack.get("rails") if isinstance(pack.get("rails"), dict) else {}
    rails = (
        dict(pack_rails)
        if pack_rails
        else teach_facade_rails(
            locked_reject_thr=locked_thr,
            recommended_surface=_RECOMMENDED_SURFACE,
        )
    )
    # Force freeze surface (teach never re-opens thrash or field).
    rails["recommended_lab_surface"] = _RECOMMENDED_SURFACE
    rails["ml_product_go"] = True
    rails["field_ops_allow_ml_live_in_fusion"] = False
    rails["iou_is_not_ros"] = True
    rails["stop_ece_thrash_on_same_test"] = True
    rails["no_ece_retune_same_holdout"] = True
    rails["field_ops_ml_live_fusion"] = "OFF"
    rails["field_fusion_off"] = True
    rails["product_facade"] = rails.get("product_facade") or _FACADE
    rails["facade_class"] = rails.get("facade_class") or _FACADE_CLASS
    rails["pipeline"] = rails.get("pipeline") or _PIPELINE
    rails["rank_reject_protocol"] = rails.get("rank_reject_protocol") or _RANK_REJECT_PROTOCOL
    rails["scorecard_api"] = _SCORECARD_API
    rails["locked_reject_thr"] = locked_thr
    rails.setdefault("label", "lab / research_open only")
    rails.setdefault("dead_paths", sorted(_DEAD_PATHS))
    # Pack must already expose the unified facade scorecard path (no dual conf path).
    pack_pipeline = pack.get("pipeline") or (pack.get("rails") or {}).get("pipeline")
    if pack_pipeline and pack_pipeline != _PIPELINE:
        raise ProductFacadeError(
            f"teach pack pipeline {pack_pipeline!r} != facade path {_PIPELINE!r}"
        )
    assert_rails_honest(
        {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            "iou_is_not_ros": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "thr_tune_split": "val",
        },
        require_iter1_reject_default=True,
    )

    multi_fire = pack.get("multi_fire_honesty") or {}
    rank_reject = pack.get("rank_reject_protocol") or teach_rank_reject_surface(
        locked_reject_thr=locked_thr,
        recommended_surface=_RECOMMENDED_SURFACE,
    )
    arch = _architecture_teach_cases(
        pack,
        locked_thr=locked_thr,
        rails=rails,
        rank_reject=rank_reject,
        multi_fire=multi_fire,
    )

    control_yes = bool(fc.get("present") and fc.get("n_rows", 0) > 0)
    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_teach_cases_v1",
        "created_utc": created,
        "iteration": 5,
        "product_id": _PRODUCT_ID,
        "product_facade": _FACADE,
        "facade_class": _FACADE_CLASS,
        "pipeline": _PIPELINE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "scorecard_api": _SCORECARD_API,
        "friction": "teach_cases_not_productized",
        "control_question": (
            "¿Se puede productizar fail_cases + LOFO + reject lock en CLI/curso "
            "sin re-tunear ECE ni abrir field_ops?"
        ),
        "control_answer": "YES" if control_yes else "PARTIAL",
        "architecture_teach_cases": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "prior_loop_lock": {
            "iter1_reject": "YES — primary lab surface (frozen default)",
            "iter2_ece_posthoc": "NO TEST ECE gain — sealed thrash",
            "iter3_refit": "NO TEST ECE gain — sealed thrash",
            "iter4_generalization": "YES LOFO table; surface stays iter1",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "thrash_sealed": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "scorecard_api": _SCORECARD_API,
        },
        "teach_pack": pack,
        "verdict": {
            "fail_cases_productized": control_yes,
            "cli_surface": "wildfire-front ml cases",
            "n_fail_rows": fc.get("n_rows", 0),
            "buckets": fc.get("buckets") or {},
            "lofo_n_folds": lofo.get("n_folds"),
            "lofo_iou_mean": lofo.get("model_iou_mean"),
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "locked_reject_thr": locked_thr,
            "ece_holdout_still_unfixed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "thrash_sealed": True,
            "dead_thrash_closed": True,
            "lofo_is_not_u1_ece": True,
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
            "architecture_teach_cases": True,
            "note": (
                "Iter5 wires teaching product surface around locked iter1 reject + "
                "iter4 LOFO honesty + fail buckets + multi-fire honesty via "
                f"product_facade ({_PIPELINE}; {_SCORECARD_API}). "
                "No metric retune; ECE thrash sealed in latest pointer."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_teach_cases_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Preserve prior latest fields when present; seal thrash (do not re-promote).
    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    sealed = _sealed_thrash_summary()

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": _latest_iterations(prev_iters),
        "summary": {
            **prev_sum,
            **sealed,
            "iter1_reject_improved": prev_sum.get("iter1_reject_improved", True),
            "iter4_generalization_table": prev_sum.get("iter4_generalization_table", True),
            "iter5_teach_cases_productized": control_yes,
            "architecture_teach_cases": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "reject": prev_sum.get("reject")
            or {
                "thr": locked_thr,
                "test_abstain_rate": rej.get("test_abstain_rate"),
                "test_iou_accepted": rej.get("test_iou_accepted"),
                "surface": _RECOMMENDED_SURFACE,
                "thr_source": "val_iter1_reject_frozen",
            },
            "lofo": prev_sum.get("lofo") or lofo,
            "generalization_note": prev_sum.get("generalization_note")
            or lofo.get("generalization_note"),
            "holdout_u1_iou": prev_sum.get("holdout_u1_iou")
            or (pack.get("holdout") or {}).get("u1_mean_iou"),
            "holdout_u1_ece": prev_sum.get("holdout_u1_ece")
            or (pack.get("holdout") or {}).get("u1_ece"),
            "fail_cases": {
                "n_rows": fc.get("n_rows", 0),
                "buckets": fc.get("buckets") or {},
                "path": "lab_loop_v34_fail_cases_test.json",
            },
            "multi_fire_honesty": multi_fire,
            "rank_reject_protocol": rank_reject,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "iou_is_not_ros": True,
                "lofo_is_not_u1_ece": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "stop_ece_thrash_on_same_test": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_thr,
                "freeze_iter1_reject": True,
                "field_ops_ml_live_fusion": "OFF",
                "field_fusion_off": True,
                "thrash_sealed": True,
                "tobarra_keep_reopen": False,
                "product_facade": _FACADE,
                "facade_class": _FACADE_CLASS,
                "pipeline": _PIPELINE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "scorecard_api": _SCORECARD_API,
            },
            "product_facade": _FACADE,
            "facade_class": _FACADE_CLASS,
            "pipeline": _PIPELINE,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "scorecard_api": _SCORECARD_API,
            "cli_cases": "wildfire-front ml cases",
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_teach_cases.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "n_fail_rows": fc.get("n_rows", 0),
                "buckets": fc.get("buckets"),
                "lofo_iou_mean": lofo.get("model_iou_mean"),
                "control_answer": payload["control_answer"],
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_thr,
                "freeze_iter1_reject": True,
                "thrash_sealed": True,
                "ece_thrash_reopen": False,
                "tobarra_keep_reopen": False,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "product_facade": _FACADE,
                "facade_class": _FACADE_CLASS,
                "pipeline": _PIPELINE,
                "scorecard_api": _SCORECARD_API,
            },
            indent=2,
        )
    )
    return 0


def _render_md(payload: dict[str, Any]) -> str:
    pack = payload.get("teach_pack") or {}
    fc = pack.get("fail_cases") or {}
    lofo = pack.get("lofo") or {}
    rej = pack.get("locked_reject") or {}
    hold = pack.get("holdout") or {}
    mf = payload.get("multi_fire_honesty") or pack.get("multi_fire_honesty") or {}
    rails = payload.get("rails") or {}
    thr = rej.get("thr_value") or rej.get("thr") or ITER1_LOCKED_REJECT_THR
    lines = [
        "# ML lab loop — iter 5 teach-cases productization",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** iter1 reject YES · iter2/3 ECE thrash **SEALED** · iter4 LOFO YES  ",
        "**Label:** lab / research_open only",
        f"**Surface:** `{_RECOMMENDED_SURFACE}` (frozen; thr~{thr})",
        f"**product_facade:** `{_FACADE}`",
        f"**facade_class:** `{_FACADE_CLASS}`",
        f"**pipeline:** `{_PIPELINE}`",
        f"**scorecard_api:** `{_SCORECARD_API}`",
        "",
        "## Rails (product facade scorecard path)",
        "",
        "| Rail | Value |",
        "|------|--------|",
        f"| product_facade | **{_FACADE}** |",
        f"| facade_class | **{_FACADE_CLASS}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| scorecard_api | **{_SCORECARD_API}** |",
        f"| product_rail | **{rails.get('product_rail', 'lab_ml')}** |",
        f"| field_rail | **{rails.get('field_rail', 'field_ops')}** |",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| IoU as ROS | **never** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| pipeline | **{_PIPELINE}** |",
        "| ECE re-tune same TEST | **SEALED (dead thrash)** |",
        "",
        "## Why this iteration",
        "",
        "Fail cases + LOFO board existed as files but were not a first-class CLI/course surface. "
        "Productize teaching on the **shared reject/LOFO freeze** via product_facade "
        f"({_PIPELINE}) without metric thrash. "
        "Latest pointer no longer re-promotes ECE/refit thrash as active surfaces.",
        "",
        f"Control question: **{payload.get('control_answer')}**",
        "",
        "## Locked reject + holdout/LOFO",
        "",
        f"- reject thr: **{thr}**",
        f"- abstain / IoU acc: **{rej.get('test_abstain_rate')}** / **{rej.get('test_iou_accepted')}**",
        f"- U1 IoU / ECE: **{hold.get('u1_mean_iou')}** / **{hold.get('u1_ece')}**",
        f"- LOFO mean IoU (n={lofo.get('n_folds')}): **{lofo.get('model_iou_mean')}**",
        f"- note: `{lofo.get('generalization_note')}`",
        f"- honesty: `{lofo.get('honesty')}`",
        "",
        "## Multi-fire honesty (first-class)",
        "",
        f"- Tobarra: **{(mf.get('tobarra') or {}).get('verdict') or 'hard/KILL'}**",
        f"- W3 external: **{(mf.get('w3_external') or {}).get('role') or 'external_stress'}**",
        f"- note: {mf.get('note') or 'Tobarra hard · W3 external report-only · LOFO ≠ U1 ECE'}",
        "",
        "## Fail-case buckets",
        "",
        f"- n_rows: **{fc.get('n_rows')}**",
        f"- buckets: `{fc.get('buckets')}`",
        "",
    ]
    for b, text in (fc.get("bucket_teach") or {}).items():
        lines.append(f"- **{b}:** {text}")
    lines += [
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml cases",
        "python -m wildfire_front ml cases --json",
        "python -m wildfire_front ml cases --bucket accepted_low_iou",
        "```",
        "",
        "## Verdict",
        "",
        "```json",
        json.dumps(payload.get("verdict") or {}, indent=2),
        "```",
        "",
        "## Do not",
        "",
        "- Re-open same-holdout ECE post-hoc / logistic refit (thrash sealed)",
        "- Re-promote Tobarra KEEP / KILL weights",
        "- Flip field_ops fusion ON (lab GO ≠ field fusion)",
        "- Claim IoU = ROS",
        "- Bypass product_facade / rank_reject_protocol for conf or thr",
        "",
        "## Next",
        "",
        "1. Optional: per-fire Head A caches for LOFO ECE/reject (inference).",
        "2. New data/features before any same-TEST ECE post-hoc.",
        "3. H1 human demo remains outside this ML track.",
        "",
        "---",
        f"*Iteration 5 — not field product. ECE thrash sealed. Freeze iter1 reject via {_FACADE}.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
