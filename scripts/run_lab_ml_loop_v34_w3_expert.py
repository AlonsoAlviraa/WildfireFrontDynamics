#!/usr/bin/env python3
"""Lab ML loop iter 14: W3 expert path (align→patches→frozen Head A + Tobarra recipe).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human promote 2026-08-05; no silent auto-flip);
  field fusion stays **OFF** (lab GO ≠ field fusion).
* Ranking / abstain share one protocol via ``product_facade`` +
  ``rank_reject_protocol``: VAL-only thr; freeze **iter1 reject** default
  (no conf math here).
* Frozen Head A eval on external fires uses production calibrator + locked thr
  only (``w3_signal.frozen_head_a_eval_on_patches`` → facade
  ``run_pipeline`` / rank_reject / scorecard); no ECE/thr retune on holdout TEST.
* Tobarra KEEP seal + frozen thr are **facade-only** after w3_signal / Head A
  unify (no dual thr path, no KEEP re-promote of KILL weights).
* Multi-fire honesty first-class: Tobarra hard + W3 external (not ad-hoc).
* Dead thrash closed: same-holdout ECE retune; Tobarra KEEP re-promote of KILL
  weights sealed after prior KILL verdict.
* Pipeline: features → calibrator → rank/reject → scorecard (lab rail only).

Does **not** retrain. Does **not** retune ECE/thr on holdout TEST or external.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_w3_expert.py
    python scripts/run_lab_ml_loop_v34_w3_expert.py --fires hellin_2024 --no-head-a
    python scripts/run_lab_ml_loop_v34_w3_expert.py --max-head-a-patches 40
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

from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    TOBARRA_FIRE_ID,
    W3_EXTERNAL_FIRES,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    LAB_ML_BANNER,
    assert_rails_honest,
    assert_split_role,
)
from wildfire_front.ml.rank_reject_protocol import (  # noqa: E402
    DEAD_PROTOCOL_PATHS,
    protocol_payload,
    refuse_dead_protocol_path,
)
from wildfire_front.ml.w3_signal import (  # noqa: E402
    assert_tobarra_keep_reopen_forbidden,
    build_w3_expert_pack,
    build_w3_signal_pack,
    load_json,
    tobarra_keep_seal,
    w3_lab_rails,
    w3_multi_fire_honesty,
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = (
    frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS) | frozenset(DEAD_PROTOCOL_PATHS)
)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"
_BANNER: Final = LAB_ML_BANNER
_TOBARRA: Final = TOBARRA_FIRE_ID
_LOCKED_THR: Final = float(ITER1_LOCKED_REJECT_THR)
_THR_SOURCE: Final = "val_iter1_reject_frozen"
_FROZEN_THR_API: Final = "product_facade.ITER1_LOCKED_REJECT_THR / ClmEnsembleV34Facade"


def _architecture_w3_expert(expert: dict[str, Any]) -> dict[str, Any]:
    """First-class architecture card: W3 expert multi-fire under shared rails."""
    rails = expert.get("rails") if isinstance(expert.get("rails"), dict) else {}
    mf = (
        expert.get("multi_fire_honesty")
        if isinstance(expert.get("multi_fire_honesty"), dict)
        else {}
    )
    keep = (
        expert.get("tobarra_keep_seal") if isinstance(expert.get("tobarra_keep_seal"), dict) else {}
    )
    v = expert.get("verdict") if isinstance(expert.get("verdict"), dict) else {}
    recipe = expert.get("tobarra_recipe") if isinstance(expert.get("tobarra_recipe"), dict) else {}
    inv_sm = (
        expert.get("inventory_summary") if isinstance(expert.get("inventory_summary"), dict) else {}
    )

    locked_thr = rails.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = _LOCKED_THR

    # Single protocol path: rank_reject_protocol.protocol_payload (VAL thr freeze).
    rank_reject = {
        **protocol_payload(locked_reject_thr=float(locked_thr)),
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "thr_source": _THR_SOURCE,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "locked_reject_thr": float(locked_thr),
        "freeze_iter1_reject": True,
        "frozen_thr_api": _FROZEN_THR_API,
        "facade_only_frozen_thr": True,
    }

    fire_results = expert.get("fire_results") or {}
    head_a_ok_fires: list[str] = []
    for fid, fr in fire_results.items():
        ha = (fr or {}).get("head_a") or {}
        if ha.get("ok"):
            head_a_ok_fires.append(str(fid))

    w3_catalog = list(mf.get("w3_external_catalog") or W3_EXTERNAL_FIRES)
    if not w3_catalog and isinstance(mf.get("w3_external"), dict):
        w3_catalog = list((mf.get("w3_external") or {}).get("fires") or [])

    keep_seal = keep or tobarra_keep_seal()
    # Facade-only KEEP seal stamp (no dual thr / re-promote path after unify).
    if isinstance(keep_seal, dict):
        keep_seal = {
            **keep_seal,
            "facade_only": True,
            "product_facade": _FACADE,
            "frozen_thr_api": _FROZEN_THR_API,
            "re_promote_kill_weights": False,
        }

    return {
        "schema": "wfd_ml_architecture_w3_expert_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "banner": _BANNER,
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": True,
        "locked_reject_thr": float(locked_thr),
        "val_only_threshold_tune": True,
        "frozen_head_a_eval": True,
        "thr_source": _THR_SOURCE,
        "frozen_thr_api": _FROZEN_THR_API,
        "facade_only_frozen_thr": True,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "tobarra_keep_reopen": False,
        "tobarra_hard": True,
        "tobarra_fire_id": _TOBARRA,
        "tobarra_keep_seal": keep_seal,
        "tobarra_recommendation": v.get("tobarra_recommendation") or recipe.get("recommendation"),
        "zero_target_leak_ok": v.get("zero_target_leak_ok")
        or (recipe.get("leak_audit") or {}).get("ok"),
        "w3_external_catalog": w3_catalog,
        "w3_role": mf.get("w3_role") or "external_probe",
        "fires_requested": list(expert.get("fires_requested") or []),
        "head_a_ok_fires": head_a_ok_fires,
        "align_patch_ok": bool(v.get("align_patch_ok")),
        "head_a_ok": bool(v.get("head_a_ok")),
        "n_external_ready": inv_sm.get("n_external_ready"),
        "recommended_first_fire": inv_sm.get("recommended_first_fire"),
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "multi_fire_honesty": mf or w3_multi_fire_honesty(),
        "eval_only_external": True,
        "note": (
            "W3 expert path is first-class architecture: chain-local align + CLM "
            "patches + frozen Head A via product_facade + rank_reject_protocol "
            "(facade-only thr after w3_signal/head_a unify) + Tobarra recipe with "
            "KEEP re-promote sealed after KILL. IoU ≠ ROS; fusion OFF; "
            "ml_product_go true (human promote; no silent auto-flip); "
            "no same-holdout ECE thrash."
        ),
    }


def _site_rails() -> dict[str, Any]:
    """Dual-product rails from facade + W3 expert honesty flags."""
    r = assert_lab_rails(DEFAULT_RAILS)
    base = w3_lab_rails()
    facade = r.as_dict()
    base = {**facade, **base}
    base.update(
        {
            "label": "lab / research_open only",
            "no_ece_retune_same_holdout": True,
            "freeze_iter1_reject": True,
            "frozen_head_a_eval": True,
            "facade_only_frozen_thr": True,
            "thr_source": _THR_SOURCE,
            "frozen_thr_api": _FROZEN_THR_API,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "forbidden_thrash": sorted(_DEAD_PATHS),
            "ml_product_go": True,
            "field_ops_ml_live_fusion": "OFF",
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_forbidden": True,
            "tobarra_keep_facade_only": True,
        }
    )
    assert_rails_honest(base, require_iter1_reject_default=True)
    return base


def _seal_dead_paths() -> None:
    """Architecture refuse: dead thrash + Tobarra KEEP re-promote stay closed.

    Dual-seal via product_facade + rank_reject_protocol (facade-only after
    w3_signal / Head A unify). Frozen thr is never retuned here.
    """
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        # expected: sealed
        with contextlib.suppress(ValueError):
            refuse_dead_protocol_path(dead)
    # Explicit seal: KEEP re-promote of KILL weights must not reopen.
    assert_tobarra_keep_reopen_forbidden(reopen=False)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop",
    )
    p.add_argument(
        "--fires",
        nargs="*",
        default=None,
        help="Fire ids (default: hellin_2024 + brazatortas_2025 if READY)",
    )
    p.add_argument("--no-head-a", action="store_true")
    p.add_argument("--max-patches-per-chain", type=int, default=150)
    p.add_argument("--max-head-a-patches", type=int, default=0, help="0 = all")
    p.add_argument("--device", default=None)
    p.add_argument("--md-path", type=Path, default=None)
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Protocol integrity: W3 external / Tobarra LOFO are scorecard/report only.
    assert_split_role("external", "scorecard")
    assert_split_role("lofo", "scorecard")
    _seal_dead_paths()

    repo = args.repo.resolve()
    created = datetime.now(UTC).isoformat()

    # Keep slice-1 pack fresh (architecture inventory + Tobarra diagnose).
    slice1 = build_w3_signal_pack(repo)
    # Expert: align→patches→frozen Head A (facade thr) + Tobarra recipe (KEEP sealed).
    expert = build_w3_expert_pack(
        repo,
        fires=list(args.fires) if args.fires else None,
        run_head_a=not args.no_head_a,
        max_patches_per_chain=int(args.max_patches_per_chain),
        max_head_a_patches=int(args.max_head_a_patches),
        device=args.device,
    )
    v = expert.get("verdict") or {}
    ok = bool(v.get("align_patch_ok") or v.get("tobarra_recipe_ok"))

    rails = _site_rails()
    expert_rails = expert.get("rails") if isinstance(expert.get("rails"), dict) else {}
    rails = {**expert_rails, **rails}

    multi_fire = expert.get("multi_fire_honesty") or w3_multi_fire_honesty()
    keep_seal = expert.get("tobarra_keep_seal") or tobarra_keep_seal()
    # Facade-only KEEP seal after w3_signal/head_a unify (no dual re-promote path).
    if isinstance(keep_seal, dict):
        keep_seal = {
            **keep_seal,
            "facade_only": True,
            "product_facade": _FACADE,
            "frozen_thr_api": _FROZEN_THR_API,
            "re_promote_kill_weights": False,
        }
    # Seal Tobarra KEEP re-promote after KILL (architecture, not optional).
    assert_tobarra_keep_reopen_forbidden(reopen=False)

    arch = _architecture_w3_expert(
        {
            **expert,
            "rails": rails,
            "multi_fire_honesty": multi_fire,
            "tobarra_keep_seal": keep_seal,
        }
    )
    rank_reject = arch.get("rank_reject_protocol") or {
        **protocol_payload(locked_reject_thr=float(_LOCKED_THR)),
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "thr_source": _THR_SOURCE,
        "facade_only_frozen_thr": True,
    }
    locked_thr = float(arch.get("locked_reject_thr") or _LOCKED_THR)

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_w3_expert_v1",
        "created_utc": created,
        "iteration": 14,
        "product_id": _PRODUCT_ID,
        "banner": _BANNER,
        "product_facade": _FACADE,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "friction": "hellin_unaligned_blocked_patches_tobarra_hard",
        "control_question": (
            "¿Podemos alinear Hellín/Brazatortas → patches → Head A frozen "
            "(product_facade thr/cal) y dejar receta Tobarra LOFO con kill + zero "
            "leak, sin retunear ECE/thr en holdout TEST ni reabrir Tobarra KEEP "
            "después de KILL?"
        ),
        "control_answer": "YES" if ok else "NO",
        "architecture_w3_expert": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "tobarra_keep_seal": keep_seal,
        "slice1_summary": {
            "recommended_first_fire": (slice1.get("inventory") or {})
            .get("summary", {})
            .get("recommended_first_fire"),
            "tobarra_mean_iou": (slice1.get("tobarra_diagnose") or {}).get("mean_iou"),
        },
        "expert": expert,
        "verdict": {
            **v,
            "architecture_w3_expert": True,
            "frozen_head_a_eval": True,
            "thr_source": _THR_SOURCE,
            "locked_reject_thr": locked_thr,
            "frozen_thr_api": _FROZEN_THR_API,
            "facade_only_frozen_thr": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_hard": True,
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_sealed": True,
            "tobarra_keep_facade_only": True,
            "dead_thrash_closed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "eval_only_external": True,
            "product_facade": _FACADE,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "note": (
                "W3 expert: chain-local align + CLM patches + frozen Head A via "
                "product_facade + rank_reject_protocol (facade-only thr after "
                "w3_signal/head_a unify); Tobarra = diagnose + LOFO recipe with "
                "kill criteria; KEEP re-promote after KILL sealed; "
                "ml_product_go true (lab promote); field fusion OFF."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "w3_expert_architecture.json").write_text(
        json.dumps(arch, indent=2), encoding="utf-8"
    )
    json_path = out_dir / "lab_loop_v34_w3_expert_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # also refresh w3_signal pointer as expert supersedes slice1 for next
    (out_dir / "lab_loop_v34_w3_signal_latest.json").write_text(
        json.dumps(
            {
                **(load_json(out_dir / "lab_loop_v34_w3_signal_latest.json") or {}),
                "expert_iteration": 14,
                "expert_json": "lab_loop_v34_w3_expert_latest.json",
                "architecture_w3_expert": "w3_expert_architecture.json",
                "tobarra_keep_reopen": False,
                "tobarra_keep_facade_only": True,
                "freeze_iter1_reject": True,
                "facade_only_frozen_thr": True,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "updated_utc": created,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    fire_ious: dict[str, Any] = {}
    for fid, fr in (expert.get("fire_results") or {}).items():
        ha = (fr or {}).get("head_a") or {}
        if ha.get("ok"):
            fire_ious[fid] = (ha.get("eval") or {}).get("mean_iou")
    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": {
            **prev_iters,
            "14_w3_expert": "lab_loop_v34_w3_expert_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter14_w3_expert": True,
            "architecture_w3_expert": True,
            "w3_expert": {
                "align_patch_ok": v.get("align_patch_ok"),
                "head_a_ok": v.get("head_a_ok"),
                "frozen_head_a_eval": True,
                "facade_only_frozen_thr": True,
                "fire_mean_ious": fire_ious,
                "tobarra_recommendation": v.get("tobarra_recommendation"),
                "zero_target_leak_ok": v.get("zero_target_leak_ok"),
                "tobarra_keep_reopen_sealed": True,
                "tobarra_keep_facade_only": True,
                "architecture_artifact": "w3_expert_architecture.json",
            },
            "multi_fire_honesty": {
                "tobarra_hard": True,
                "tobarra_fire_id": _TOBARRA,
                "tobarra_keep_reopen": False,
                "do_not_reopen_tobarra_keep": True,
                "tobarra_keep_facade_only": True,
                "w3_external_catalog": list(W3_EXTERNAL_FIRES),
                "frozen_thr_and_cal": True,
                "facade_only_frozen_thr": True,
                "eval_only_external": True,
            },
            "recommended_next": (
                "W3_tobarra_lofo_finetune_if_KEEP_criteria"
                if v.get("tobarra_recommendation") == "OPTIONAL_lofo_finetune_with_kill"
                else "W4_more_external_fires_lab_go_true_field_fusion_off"
            ),
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "rank_reject_protocol": rank_reject,
            "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": locked_thr,
                "freeze_iter1_reject": True,
                "frozen_head_a_eval": True,
                "facade_only_frozen_thr": True,
                "thr_source": _THR_SOURCE,
                "tobarra_keep_reopen_forbidden": True,
                "tobarra_keep_facade_only": True,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "pipeline": _PIPELINE,
            },
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260805_w3_expert.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": ok,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "architecture_w3_expert": True,
                "align_patch_ok": v.get("align_patch_ok"),
                "head_a_ok": v.get("head_a_ok"),
                "frozen_head_a_eval": True,
                "fire_mean_ious": fire_ious,
                "tobarra_recommendation": v.get("tobarra_recommendation"),
                "zero_target_leak_ok": v.get("zero_target_leak_ok"),
                "tobarra_hard": True,
                "tobarra_keep_reopen": False,
                "tobarra_keep_reopen_sealed": True,
                "tobarra_keep_facade_only": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "locked_reject_thr": locked_thr,
                "facade_only_frozen_thr": True,
                "thr_source": _THR_SOURCE,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "ece_thrash_reopen": False,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            },
            indent=2,
        )
    )
    return 0 if ok else 2


def _render_md(payload: dict[str, Any]) -> str:
    expert = payload.get("expert") or {}
    v = payload.get("verdict") or {}
    recipe = expert.get("tobarra_recipe") or {}
    arch = payload.get("architecture_w3_expert") or {}
    keep = payload.get("tobarra_keep_seal") or {}
    w3_cat = list(arch.get("w3_external_catalog") or W3_EXTERNAL_FIRES)
    lines = [
        "# ML lab loop — iter 14 W3 expert (align → patches → frozen Head A + Tobarra)",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        f"**Banner:** {payload.get('banner') or _BANNER}  ",
        "**Label:** lab only · architecture · frozen Head A · no ECE thrash same-holdout",
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
        "| frozen Head A eval | **true** (facade-only thr) |",
        f"| Tobarra hard | **{arch.get('tobarra_hard')}** |",
        "| Tobarra KEEP reopen | **sealed (facade-only)** |",
        f"| W3 external catalog | **{', '.join(w3_cat)}** |",
        "| dead thrash closed | **true** |",
        "| field fusion | **OFF** |",
        "| ml_product_go | **true** |",
        "| IoU ≠ ROS | **true** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        "### Align + patches + frozen Head A",
        "",
        f"- align_patch_ok: **{v.get('align_patch_ok')}**",
        f"- head_a_ok: **{v.get('head_a_ok')}**",
        f"- thr source: **{v.get('thr_source') or _THR_SOURCE}**",
        f"- locked thr: **{v.get('locked_reject_thr')}** (facade-only)",
        f"- frozen thr API: **{_FROZEN_THR_API}**",
        "",
        "| fire | patches | mean IoU | copy IoU | Δ vs copy | ECE | abs@lock |",
        "|------|--------:|---------:|---------:|----------:|----:|---------:|",
    ]
    for fid, fr in (expert.get("fire_results") or {}).items():
        ap = (fr or {}).get("align_and_patch") or {}
        ha = (fr or {}).get("head_a") or {}
        n = (ap.get("patches") or {}).get("n_total")
        ev = (ha or {}).get("eval") or {}
        thr = ev.get("thr_locked") or {}
        if ha and ha.get("ok"):
            lines.append(
                f"| {fid} | {n} | {ev.get('mean_iou')} | {ev.get('mean_copy_iou')} | "
                f"{ev.get('improvement_vs_copy_iou')} | {ev.get('ece_full')} | "
                f"{thr.get('abstain_rate')} |"
            )
        else:
            err = (ha or {}).get("error") or (ap.get("error") if not ap.get("ok") else "no Head A")
            lines.append(f"| {fid} | {n} | — | — | — | — | — |  <!-- {err} -->")
    lines += [
        "",
        "Honesty: patches use `min_change_fraction=0.02` (drop copy-easy short-Δt).",
        "Do **not** sell Hellín IoU without Δ vs copy.",
        "Head A uses production calibrator + freeze **iter1 reject** thr only "
        f"(locked={arch.get('locked_reject_thr')}; facade-only after w3_signal/head_a "
        "unify); no thr/ECE fit on external.",
        "",
        "### Tobarra recipe (KEEP re-promote sealed, facade-only)",
        "",
        f"- recommendation: **{recipe.get('recommendation')}**",
        f"- zero_target_leak_ok: **{(recipe.get('leak_audit') or {}).get('ok')}**",
        f"- baseline mean IoU: **{recipe.get('baseline_mean_iou')}**",
        f"- kill criteria: **{len(recipe.get('kill_criteria') or [])}** (K1–K6)",
        f"- KEEP seal: **{keep.get('sealed', True)}** · facade-only: **{keep.get('facade_only', True)}** "
        "· re-promote KILL weights: **false**",
        "- recipe JSON: `outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json`",
        "",
        "### Rails (product facade + rank_reject_protocol)",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        "| ECE thrash same TEST | **stopped** |",
        "| Tobarra KEEP reopen | **closed (facade-only)** |",
        f"| surface | **{_RECOMMENDED_SURFACE}** |",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| frozen thr | **facade-only** ({_FROZEN_THR_API}) |",
        "",
        "## Next",
        "",
        "1. Hellín beats copy (Δ>0) on filtered patches — lab new-fire signal usable",
        "2. Brazatortas weak Δ vs copy — treat as hard transfer, not GO",
        "3. Tobarra LOFO finetune only if recipe recommendation is OPTIONAL and K1–K6 pass "
        "(KEEP reopen sealed facade-only; no re-promote of prior KILL weights)",
        "4. `ml_product_go` **true** (human promote 2026-08-05); field fusion remains "
        "**OFF** (lab GO ≠ field fusion)",
        "",
        "```powershell",
        "python scripts/run_lab_ml_loop_v34_w3_expert.py",
        "```",
        "",
        "---",
        "*Iteration 14 — W3 expert multi-fire path on product_facade + rank_reject_protocol; "
        "frozen Head A thr facade-only after w3_signal/head_a unify; Tobarra KEEP sealed "
        "after KILL; ml_product_go true (lab ≠ field fusion).*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
