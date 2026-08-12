#!/usr/bin/env python3
"""Lab ML loop iter 10: next-signal readiness gate (W3 external + frozen reject).

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` is **promoted true** (explicit stamp; no silent auto thrash);
  field fusion stays **OFF**.
* Single path via ``product_facade`` + ``rank_reject_protocol``:
  features→calibrator→rank/reject→scorecard. Readiness core is ``lab_next``
  which hard-seals dead thrash via ``refuse_dead_path``; this runner prefers
  gate rails / rank_reject and does not reimplement conf math.
* Ranking / abstain share one protocol: VAL-only thr; freeze **iter1 reject**
  default (``iter1_reject_only``).
* Dead thrash **dropped** as READY work: same-holdout ECE retune and Tobarra
  KEEP reopen of KILL weights are sealed closed paths, never recommended_next.
* Multi-fire honesty first-class: Tobarra hard; LOFO/W3 first-class; next
  metric path routes to **W3 external** under frozen thr/cal + iter1 reject.
* Does **not** build caches, retune ECE, or flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_next_gate.py
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

from wildfire_front.ml.lab_next import build_next_gate, load_json  # noqa: E402
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_PRODUCT_ID,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    MULTI_FIRE_HONESTY,
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

# Work-item ids / tokens that must never appear as READY next-gate work.
_THRASH_WORK_TOKENS: Final = frozenset(
    {
        "same_holdout_ece_retune",
        "ece_posthoc",
        "ece_thrash",
        "tobarra_keep",
        "tobarra_finetune_keep",
        "keep_reopen",
        "2_ece_posthoc",
        "3_refit",
    }
)

# Core loop artifacts (promoted path). Dead thrash iters are archaeology only.
_CORE_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "1_reject": "lab_loop_v34_reject_latest.json",
    "4_generalization": "lab_loop_v34_generalization_latest.json",
    "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
    "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
    "7_freeze": "lab_loop_v34_freeze_latest.json",
    "8_smoke": "lab_loop_v34_smoke_latest.json",
    "9_lofo_board": "lab_loop_v34_lofo_board_latest.json",
}
_DEAD_THRASH_ITER_ARTIFACTS: Final[dict[str, str]] = {
    "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
    "3_refit": "lab_loop_v34_refit_latest.json",
}


def _is_thrash_work_item(item: dict[str, Any]) -> bool:
    """True if a work item is ECE thrash or Tobarra KEEP reopen (must drop/seal)."""
    blob = " ".join(str(item.get(k) or "") for k in ("id", "title", "why", "status")).lower()
    if any(tok in blob for tok in _THRASH_WORK_TOKENS):
        # Allow W3 text that *closes* KEEP without reopening it
        if ("keep reopen" in blob or "keep_reopen" in blob) and (
            "closed" in blob or "forbidden" in blob or "dead" in blob
        ):
            return False
        # Explicit reopen / retune ids
        wid = str(item.get("id") or "").lower()
        if any(
            t in wid
            for t in (
                "ece_thrash",
                "ece_retune",
                "ece_posthoc",
                "tobarra_keep",
                "keep_reopen",
            )
        ):
            return True
        if "reopen" in blob and "tobarra" in blob and "keep" in blob:
            return True
        if ("same-holdout" in blob or "same_holdout" in blob or "same test" in blob) and (
            "ece" in blob and ("retune" in blob or "thrash" in blob or "posthoc" in blob)
        ):
            return True
    return False


def _seal_work_items(work_items: list[Any]) -> list[dict[str, Any]]:
    """Drop thrash READY items; seal any leftover thrash as CLOSED_DEAD."""
    sealed: list[dict[str, Any]] = []
    for raw in work_items or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if _is_thrash_work_item(item):
            # Never surface thrash as READY/PARTIAL/IN_PROGRESS
            item["status"] = "CLOSED_DEAD"
            item["ready_path"] = False
            item["promoted_lab"] = False
            item.setdefault(
                "why",
                "Dead thrash path sealed (ECE same-holdout / Tobarra KEEP reopen).",
            )
            item["closed_paths"] = sorted(
                set(item.get("closed_paths") or [])
                | {
                    "same_holdout_ece_retune",
                    "tobarra_keep_reopen_kill_weights",
                }
            )
            # Drop from active board entirely when it was a pure thrash id
            wid = str(item.get("id") or "").lower()
            if any(
                t in wid
                for t in (
                    "ece_thrash",
                    "ece_retune",
                    "ece_posthoc",
                    "tobarra_keep",
                    "keep_reopen",
                    "2_ece",
                    "3_refit",
                )
            ):
                continue  # hard drop pure thrash work items
        sealed.append(item)
    return sealed


def _route_recommended(
    gate: dict[str, Any], work_items: list[dict[str, Any]]
) -> tuple[str, str | None]:
    """Prefer W3 external + frozen reject once LOFO Head A path is done.

    Never recommend ECE thrash or Tobarra KEEP reopen.
    """
    rec = str(
        gate.get("recommended_next") or (gate.get("verdict") or {}).get("recommended_next") or ""
    )
    # Readiness core (lab_next) puts primary_blocker on verdict; prefer that.
    primary = gate.get("primary_blocker")
    if primary is None:
        primary = (gate.get("verdict") or {}).get("primary_blocker")
    if isinstance(primary, str) and any(
        t in primary.lower() for t in ("ece_thrash", "ece_retune", "tobarra_keep", "keep_reopen")
    ):
        primary = "w3_external_stress"

    # If gate already points at thrash, force W3 external route
    if any(
        t in rec.lower()
        for t in ("ece_thrash", "ece_retune", "ece_posthoc", "tobarra_keep", "keep_reopen")
    ):
        rec = "W3_new_features_or_data"
        primary = primary or "w3_external_stress"

    # Prefer W3 when W1/W2 done (multi-fire honesty next)
    statuses = {w.get("id"): w.get("status") for w in work_items}
    w1 = statuses.get("W1_lofo_head_a_caches")
    w2 = statuses.get("W2_lofo_ece_reject_eval")
    if w1 == "DONE" and w2 == "DONE":
        rec = "W3_new_features_or_data"
        mf = gate.get("multi_fire_honesty") or {}
        w3_present = bool((mf.get("w3_external") or {}).get("present"))
        primary = "w3_external_stress" if not w3_present else primary or "tobarra_hard_transfer"

    return rec, primary if isinstance(primary, str) else None


def _rank_reject_for_gate(gate: dict[str, Any], *, locked_thr: float) -> dict[str, Any]:
    """Prefer lab_next gate rank_reject (product_facade-integrated); else protocol dict.

    Single features→calibrator→rank/reject→scorecard path — no conf math here.
    """
    gate_rr = gate.get("rank_reject_protocol")
    if isinstance(gate_rr, dict) and gate_rr:
        return {
            **gate_rr,
            "product_facade": _FACADE,
            "module": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "recommended_lab_surface": gate_rr.get("recommended_lab_surface")
            or _RECOMMENDED_SURFACE,
            "locked_reject_thr": float(
                gate_rr.get("locked_reject_thr")
                if gate_rr.get("locked_reject_thr") is not None
                else locked_thr
            ),
            "freeze_iter1_reject": True,
            "val_only_threshold_tune": True,
        }
    # Single path fallback: rank_reject_protocol (not ad-hoc protocol_rails conf).
    proto = protocol_payload(locked_reject_thr=float(locked_thr))
    return {
        **proto,
        "product_facade": _FACADE,
        "module": _RANK_REJECT_PROTOCOL,
        "pipeline": _PIPELINE,
        "recommended_lab_surface": proto.get("recommended_lab_surface") or _RECOMMENDED_SURFACE,
        "locked_reject_thr": float(
            proto.get("locked_reject_thr")
            if proto.get("locked_reject_thr") is not None
            else locked_thr
        ),
        "freeze_iter1_reject": True,
        "val_only_threshold_tune": True,
    }


def _architecture_next_gate(gate: dict[str, Any]) -> dict[str, Any]:
    """Architecture card: product_facade rails + rank_reject + refuse_dead_path."""
    rails = gate.get("rails") if isinstance(gate.get("rails"), dict) else {}
    checks = gate.get("checks") if isinstance(gate.get("checks"), dict) else {}
    mf = gate.get("multi_fire_honesty")
    if not isinstance(mf, dict):
        facade_mf = DEFAULT_MULTI_FIRE.as_dict()
        mf = {
            "tobarra": {
                **dict(MULTI_FIRE_HONESTY.get("tobarra") or {}),
                **dict(facade_mf.get("tobarra") or {}),
            },
            "w3_external": {
                **dict(MULTI_FIRE_HONESTY.get("w3_external") or {}),
                **dict(facade_mf.get("w3_external") or {}),
            },
            "lofo_first_class": True,
            "do_not_reopen_tobarra_keep": True,
            "product_facade": _FACADE,
        }
    locked_thr = rails.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR
    rank_reject = _rank_reject_for_gate(gate, locked_thr=float(locked_thr))
    dead_refused = bool(
        checks.get("product_facade_dead_paths_refused")
        or (gate.get("verdict") or {}).get("dead_paths_refused")
        or True
    )
    return {
        "schema": "wfd_ml_architecture_next_gate_v1",
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
        "stop_ece_thrash_on_same_test": True,
        "ece_thrash_reopen": False,
        "tobarra_keep_reopen": False,
        "dead_thrash_closed": True,
        "dead_paths": sorted(_DEAD_PATHS),
        "product_facade_dead_paths_refused": dead_refused,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "multi_fire_honesty": mf,
        "route_next_metric": "W3_external_frozen_reject",
        "note": (
            "Next-gate readiness under shared product_facade + rank_reject_protocol "
            "(lab_next refuse_dead_path integrated). ECE same-holdout thrash and "
            "Tobarra KEEP reopen are closed (not READY). Route metric work to W3 "
            "external + frozen iter1 reject; ml_product_go promoted true; fusion OFF."
        ),
    }


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

    # Dead thrash must stay sealed (architecture refuse — not optional folklore).
    # Runner-level refuse pairs with lab_next.build_next_gate refuse_dead_path
    # (product_facade + rank_reject_protocol dual seal).
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected: path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")
        try:
            refuse_dead_protocol_path(dead)
        except ValueError:
            pass  # expected: sealed
        else:
            raise ProductFacadeError(f"dead protocol path still open: {dead!r}")

    repo = args.repo.resolve()
    # Readiness core (lab_next) integrates product_facade rails + refuse_dead_path.
    gate = build_next_gate(repo)
    created = datetime.now(UTC).isoformat()
    built = bool((gate.get("verdict") or {}).get("next_gate_built"))
    checks = gate.get("checks") if isinstance(gate.get("checks"), dict) else {}
    # Prefer lab_next product_facade_dead_paths_refused; require true for READY.
    dead_refused = bool(checks.get("product_facade_dead_paths_refused"))
    if not dead_refused:
        dead_refused = bool((gate.get("verdict") or {}).get("dead_paths_refused"))
    if not dead_refused:
        raise ProductFacadeError(
            "lab_next readiness core missing product_facade refuse_dead_path integration"
        )

    # Drop thrash work items; seal any leftover; route to W3 + frozen reject.
    raw_items = list(gate.get("work_items") or [])
    work_items = _seal_work_items(raw_items)
    recommended, primary_blocker = _route_recommended(gate, work_items)

    # Patch gate view for payload (do not mutate thrash back in).
    # Prefer facade fields already attached by lab_next readiness core.
    gate_out = dict(gate)
    gate_out["work_items"] = work_items
    gate_out["recommended_next"] = recommended
    gate_out["primary_blocker"] = primary_blocker
    gate_out["product_facade"] = gate_out.get("product_facade") or _FACADE
    gate_out["pipeline"] = gate_out.get("pipeline") or _PIPELINE
    gate_out["closed_ready_paths"] = sorted(
        set(gate.get("closed_ready_paths") or []) | set(_DEAD_PATHS)
    )
    if not isinstance(gate_out.get("multi_fire_honesty"), dict):
        facade_mf = DEFAULT_MULTI_FIRE.as_dict()
        gate_out["multi_fire_honesty"] = {
            "tobarra": {
                **dict(MULTI_FIRE_HONESTY.get("tobarra") or {}),
                **dict(facade_mf.get("tobarra") or {}),
            },
            "w3_external": {
                **dict(MULTI_FIRE_HONESTY.get("w3_external") or {}),
                **dict(facade_mf.get("w3_external") or {}),
            },
            "do_not_reopen_tobarra_keep": True,
            "lofo_first_class": True,
            "product_facade": _FACADE,
        }

    arch = _architecture_next_gate(gate_out)
    # Prefer pack rails (already product_facade via lab_next); stamp facade ids.
    rails = dict(gate_out.get("rails") or {})
    rails.update(
        {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "field_ops_ml_live_fusion": "OFF",
            "iou_is_not_ros": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "pipeline": _PIPELINE,
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "dead_paths": sorted(_DEAD_PATHS),
            "route_next_metric": "W3_external_frozen_reject",
        }
    )
    if rails.get("locked_reject_thr") is None:
        rails["locked_reject_thr"] = float(ITER1_LOCKED_REJECT_THR)

    rank_reject = arch.get("rank_reject_protocol") or _rank_reject_for_gate(
        gate_out, locked_thr=float(rails["locked_reject_thr"])
    )
    gate_out["rank_reject_protocol"] = rank_reject
    gate_out["rails"] = rails

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_next_gate_v1",
        "created_utc": created,
        "iteration": 10,
        "product_id": _PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "friction": "next_metric_path_not_instrumented",
        "control_question": (
            "¿Podemos instrumentar el siguiente trabajo métrico (W3 external + "
            "frozen iter1 reject) con probes READY/BLOCKED sin retunear ECE "
            "same-holdout, sin reabrir Tobarra KEEP, ni abrir field_ops?"
        ),
        "control_answer": "YES" if built else "NO",
        "architecture_next_gate": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": gate_out.get("multi_fire_honesty") or arch.get("multi_fire_honesty"),
        "gate": gate_out,
        "verdict": {
            **(gate.get("verdict") or {}),
            "iteration": 10,
            "architecture_next_gate": True,
            "recommended_next": recommended,
            "primary_blocker": primary_blocker,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "tobarra_keep_reopen_allowed": False,
            "ece_thrash_allowed": False,
            "dead_thrash_closed": True,
            "dead_paths_refused": dead_refused,
            "product_facade_dead_paths_refused": dead_refused,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "multi_fire_honesty_first_class": True,
            "route_next_metric": "W3_external_frozen_reject",
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "note": (
                "Next-gate readiness only via product_facade + lab_next "
                "refuse_dead_path. Dead thrash (ECE same-holdout, Tobarra KEEP "
                "reopen) dropped as READY work. Route metric path to W3 external "
                "under frozen iter1 reject; field fusion OFF."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_next_gate_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
    counts = (gate_out.get("lofo_fold_probe") or {}).get("counts") or {}
    mf = payload.get("multi_fire_honesty") or {}
    w3 = mf.get("w3_external") or {}
    if not isinstance(w3, dict):
        w3 = {}

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": {
            **_CORE_ITER_ARTIFACTS,
            **{
                # Dead thrash archaeology only — not promote/ready paths
                **_DEAD_THRASH_ITER_ARTIFACTS,
            },
            **prev_iters,
            "10_next_gate": "lab_loop_v34_next_gate_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter10_next_gate": True,
            "architecture_next_gate": True,
            "recommended_next": recommended,
            "primary_blocker": primary_blocker,
            "lofo_head_a_caches": counts.get("n_head_a_caches"),
            "lofo_weights": counts.get("n_weights"),
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "thrash_iters_not_promote_path": {
                "2_ece_posthoc": "dead",
                "3_refit": "dead",
            },
            "route_next_metric": "W3_external_frozen_reject",
            "multi_fire_honesty": {
                "tobarra_hard": True,
                "tobarra_verdict": (mf.get("tobarra") or {}).get("verdict") or "KILL",
                "w3_external_present": bool(w3.get("present")),
                "w3_fires": w3.get("fires_present") or w3.get("fires") or [],
                "do_not_reopen_tobarra_keep": True,
                "do_not_universalize_u1": True,
            },
            "rank_reject_protocol": rank_reject,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "product_facade_dead_paths_refused": dead_refused,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": float(rails["locked_reject_thr"]),
                "freeze_iter1_reject": True,
                "tobarra_keep_reopen": False,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "pipeline": _PIPELINE,
            },
            "cli_next": "wildfire-front ml next",
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_next_gate.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": built,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "recommended_next": recommended,
                "primary_blocker": primary_blocker,
                "route_next_metric": "W3_external_frozen_reject",
                "lofo_head_a_caches": counts.get("n_head_a_caches"),
                "lofo_weights": counts.get("n_weights"),
                "lofo_folds": counts.get("n_folds"),
                "control_answer": payload["control_answer"],
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "ece_thrash_reopen": False,
                "tobarra_keep_reopen": False,
                "dead_thrash_closed": True,
                "product_facade": _FACADE,
                "product_facade_dead_paths_refused": dead_refused,
            },
            indent=2,
        )
    )
    return 0 if built else 2


def _render_md(payload: dict[str, Any]) -> str:
    gate = payload.get("gate") or {}
    v = payload.get("verdict") or {}
    arch = payload.get("architecture_next_gate") or {}
    mf = payload.get("multi_fire_honesty") or {}
    tob = mf.get("tobarra") or {}
    w3 = mf.get("w3_external") or {}
    counts = (gate.get("lofo_fold_probe") or {}).get("counts") or {}
    lines = [
        "# ML lab loop — iter 10 next-signal readiness gate",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** freeze + smoke + LOFO board (7–9)  ",
        "**Label:** lab / research_open only",
        "",
        "## Architecture",
        "",
        "| Gate | Value |",
        "|------|--------|",
        f"| route_next_metric | **{arch.get('route_next_metric') or 'W3_external_frozen_reject'}** |",
        f"| freeze iter1 reject | **true** (thr={arch.get('locked_reject_thr')}) |",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        f"| pipeline | **{_PIPELINE}** |",
        f"| refuse_dead_path | **{v.get('product_facade_dead_paths_refused', True)}** |",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        "| ECE thrash same TEST | **stopped / not READY** |",
        "| Tobarra KEEP reopen | **CLOSED** |",
        "| auto unfreeze | **false** |",
        "",
        "## Multi-fire honesty (first-class)",
        "",
        f"- Tobarra: **{tob.get('verdict') or tob.get('keep_verdict') or 'KILL'}** / "
        f"**{tob.get('class') or tob.get('role') or 'hard'}** (KEEP reopen closed)",
        f"- W3 external: **{w3.get('n_fires', len(w3.get('fires') or w3.get('fires_present') or []))}** "
        "fires (frozen thr/cal report-only)",
        f"- LOFO first-class: **{mf.get('lofo_first_class', True)}**",
        f"- note: {mf.get('note') or 'Tobarra hard · LOFO/W3 · no thrash reopen'}",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        f"- recommended_next: **{v.get('recommended_next')}**",
        f"- primary_blocker: **{v.get('primary_blocker')}**",
        "- route: **W3 external + frozen iter1 reject**",
        f"- LOFO folds/weights/head_a: "
        f"**{counts.get('n_folds')}/{counts.get('n_weights')}/{counts.get('n_head_a_caches')}**",
        "",
        "## Work items (thrash dropped)",
        "",
        "| ID | Status | Title |",
        "|----|--------|-------|",
    ]
    for w in gate.get("work_items") or []:
        lines.append(f"| {w.get('id')} | {w.get('status')} | {w.get('title')} |")
    lines += [
        "",
        "### Closed (not READY) — product_facade.refuse_dead_path",
        "",
        "- same-holdout ECE retune / ECE post-hoc thrash",
        "- Tobarra KEEP reopen of KILL weights",
        "- `ml_product_go` auto-flip; field_ops fusion auto-on",
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml next",
        "python -m wildfire_front ml next --json",
        "```",
        "",
        "---",
        "*Iteration 10 — readiness via product_facade + lab_next refuse_dead_path; "
        "thrash sealed; W3 + frozen reject route; not a metric win; not field promote.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
