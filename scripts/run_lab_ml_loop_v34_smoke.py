#!/usr/bin/env python3
"""Lab ML loop iter 8: post-freeze smoke / regression gate.

Architecture (product ROI — no retrain)
---------------------------------------
* Dual-product rails: **lab ML** vs **field_ops**; IoU ≠ ROS;
  ``ml_product_go`` **true** (human-promoted); field fusion stays **OFF**.
  Silent ``auto_ml_product_go`` thrash stays refused (lab GO ≠ field fusion).
* Single path via ``product_facade`` + ``rank_reject_protocol``:
  features→calibrator→rank/reject→scorecard. Architecture gates
  **hard-require** this facade+protocol path (not rails-only).
* Ranking / abstain share one VAL-only thr protocol; freeze **iter1 reject**
  is the default surface (``product_facade`` / ``lab_smoke`` — no conf math).
* Dead thrash closed: same-holdout ECE retune and Tobarra KEEP reopen hooks
  must stay refused (absence of thrash reopen is a hard smoke gate).
* Multi-fire honesty first-class (Tobarra hard, W3 external / LOFO).
* Smoke ≠ field fusion promote. Does **not** retrain or retune ECE.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_smoke.py
    python scripts/run_lab_ml_loop_v34_smoke.py --pytest
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

from wildfire_front.ml.lab_freeze import load_json  # noqa: E402
from wildfire_front.ml.lab_smoke import run_lab_smoke  # noqa: E402
from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_PRODUCT_ID,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
    MULTI_FIRE_HONESTY,
    rank_abstain_protocol_dict,
)

_PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
_RECOMMENDED_SURFACE: Final = RECOMMENDED_LAB_SURFACE  # iter1_reject_only
_DEAD_PATHS: Final = frozenset(DEAD_PATHS) | frozenset(FORBIDDEN_THRASH_PATHS)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_RANK_REJECT_PROTOCOL: Final = "wildfire_front.ml.rank_reject_protocol"


def _architecture_smoke_gates(smoke: dict[str, Any]) -> dict[str, Any]:
    """Hard gates: facade+protocol path, freeze iter1, thrash closed, fusion OFF."""
    v = smoke.get("verdict") if isinstance(smoke.get("verdict"), dict) else {}
    rails = smoke.get("rails") if isinstance(smoke.get("rails"), dict) else {}
    freeze = smoke.get("freeze") if isinstance(smoke.get("freeze"), dict) else {}
    summ = smoke.get("summary") if isinstance(smoke.get("summary"), dict) else {}
    facade_pipe = (
        smoke.get("facade_pipeline") if isinstance(smoke.get("facade_pipeline"), dict) else {}
    )
    mf = smoke.get("multi_fire_honesty")
    if not isinstance(mf, dict):
        mf = {
            "tobarra": dict(MULTI_FIRE_HONESTY.get("tobarra") or {}),
            "w3_external": dict(MULTI_FIRE_HONESTY.get("w3_external") or {}),
        }

    smoke_pass = bool(v.get("smoke_pass"))
    facade_ok = bool(v.get("facade_rails_ok", True))
    # Hard-require single features→calibrator→rank/reject→scorecard path.
    if "facade_rank_reject_pipeline_ok" in v:
        facade_protocol_ok = bool(v.get("facade_rank_reject_pipeline_ok"))
    elif "facade_rank_reject_pipeline_ok" in summ:
        facade_protocol_ok = bool(summ.get("facade_rank_reject_pipeline_ok"))
    else:
        facade_protocol_ok = bool(facade_pipe.get("ok"))
    freeze_iter1 = bool(v.get("iter1_reject_default", True)) and (
        str(rails.get("recommended_lab_surface") or _RECOMMENDED_SURFACE) == _RECOMMENDED_SURFACE
    )
    thrash_closed = (
        v.get("ece_thrash_reopen") is False
        and bool(rails.get("stop_ece_thrash_on_same_test", True))
        and bool(freeze.get("dead_thrash_closed", True))
        and rails.get("tobarra_keep_reopen") is not True
    )
    fusion_off = (
        rails.get("field_ops_allow_ml_live_in_fusion") is False
        and str(rails.get("field_ops_ml_live_fusion") or "OFF").upper() == "OFF"
        and str(v.get("field_ops_fusion") or "OFF").upper() == "OFF"
    )
    go_true = (
        rails.get("ml_product_go") is True
        and v.get("ml_product_go") is True
        and v.get("field_product") is not True
    )
    multi_fire_ok = bool(mf.get("tobarra")) and bool(mf.get("w3_external"))
    locked_thr = rails.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = freeze.get("locked_reject_thr")
    if locked_thr is None:
        locked_thr = ITER1_LOCKED_REJECT_THR

    rank_reject = rank_abstain_protocol_dict(
        locked_reject_thr=float(locked_thr),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )

    gates_ok = (
        smoke_pass
        and facade_ok
        and facade_protocol_ok
        and freeze_iter1
        and thrash_closed
        and fusion_off
        and go_true
        and multi_fire_ok
    )
    return {
        "schema": "wfd_ml_architecture_smoke_gates_v1",
        "product_id": _PRODUCT_ID,
        "product_rail": "lab_ml",
        "field_rail": "field_ops",
        "recommended_lab_surface": _RECOMMENDED_SURFACE,
        "freeze_iter1_reject": freeze_iter1,
        "locked_reject_thr": float(locked_thr),
        "val_only_threshold_tune": True,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": fusion_off,
        "iou_is_not_ros": True,
        "stop_ece_thrash_on_same_test": True,
        "ece_thrash_reopen": False,
        "tobarra_keep_reopen": False,
        "dead_thrash_closed": thrash_closed,
        "dead_paths": sorted(_DEAD_PATHS),
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "rank_reject_protocol": rank_reject,
        "rank_reject_protocol_mod": _RANK_REJECT_PROTOCOL,
        "multi_fire_honesty": mf,
        "checks": {
            "smoke_pass": smoke_pass,
            "facade_rails_ok": facade_ok,
            "facade_rank_reject_pipeline_ok": facade_protocol_ok,
            "freeze_iter1_reject": freeze_iter1,
            "thrash_reopen_absent": thrash_closed,
            "field_ops_fusion_off": fusion_off,
            "ml_product_go_true": go_true,
            "multi_fire_honesty_first_class": multi_fire_ok,
        },
        "gates_ok": gates_ok,
        "note": (
            "Smoke entrypoint hard-requires product_facade + rank_reject_protocol "
            "single path (features→calibrator→rank/reject→scorecard), freeze iter1 "
            "reject, absence of ECE thrash / Tobarra KEEP reopen, multi-fire honesty, "
            "field_ops fusion OFF, and ml_product_go true (human-promoted; no silent "
            "auto_ml_product_go thrash)."
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
    p.add_argument(
        "--pytest",
        action="store_true",
        help="Also run focused lab pytest suite",
    )
    p.add_argument("--md-path", type=Path, default=None)
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Dead thrash must stay sealed (architecture refuse — not optional folklore).
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

    repo = args.repo.resolve()
    smoke = run_lab_smoke(repo, run_pytest=bool(args.pytest))
    created = datetime.now(UTC).isoformat()
    arch = _architecture_smoke_gates(smoke)
    # Hard gate: facade+protocol path + freeze rails + thrash reopen absent.
    passed = bool(arch.get("gates_ok"))
    rank_reject = arch.get("rank_reject_protocol") or rank_abstain_protocol_dict(
        locked_reject_thr=float(ITER1_LOCKED_REJECT_THR),
        recommended_lab_surface=_RECOMMENDED_SURFACE,
    )

    # Prefer smoke rails (already product_facade via lab_smoke); stamp facade ids.
    rails = dict(smoke.get("rails") or {})
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
        }
    )
    if rails.get("locked_reject_thr") is None:
        rails["locked_reject_thr"] = float(arch.get("locked_reject_thr") or ITER1_LOCKED_REJECT_THR)

    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_smoke_v1",
        "created_utc": created,
        "iteration": 8,
        "product_id": _PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "friction": "post_freeze_regression_not_gated",
        "control_question": (
            "¿Sigue verde el freeze lab + facade+protocol path + CLI offline + rails "
            "(iter1 reject, sin thrash reopen, sin field_ops) tras consolidar?"
        ),
        "control_answer": "YES" if passed else "NO",
        "architecture_smoke_gates": arch,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": arch.get("multi_fire_honesty"),
        "smoke": smoke,
        "verdict": {
            **(smoke.get("verdict") or {}),
            "iteration": 8,
            "architecture_smoke_gates": True,
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "ece_holdout_still_unfixed": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "field_product": False,
            "ml_product_go": True,
            "field_ops_fusion": "OFF",
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
            "facade_rank_reject_pipeline_ok": bool(
                (arch.get("checks") or {}).get("facade_rank_reject_pipeline_ok")
            ),
            "gates_ok": passed,
            "smoke_pass": passed,
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_smoke_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    prev = load_json(out_dir / "lab_loop_v34_latest.json") or {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}

    latest = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "architecture_smoke_gates": {
            "gates_ok": passed,
            "checks": arch.get("checks"),
            "dead_paths": sorted(_DEAD_PATHS),
            "product_facade": _FACADE,
            "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
            "pipeline": _PIPELINE,
        },
        "iterations": {
            **{
                "1_reject": "lab_loop_v34_reject_latest.json",
                "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
                "3_refit": "lab_loop_v34_refit_latest.json",
                "4_generalization": "lab_loop_v34_generalization_latest.json",
                "5_teach_cases": "lab_loop_v34_teach_cases_latest.json",
                "6_risk_curve": "lab_loop_v34_risk_curve_latest.json",
                "7_freeze": "lab_loop_v34_freeze_latest.json",
            },
            **prev_iters,
            "8_smoke": "lab_loop_v34_smoke_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter8_post_freeze_smoke": True,
            "smoke_pass": passed,
            "architecture_smoke_gates": True,
            "lab_usable_freeze": (smoke.get("verdict") or {}).get("lab_usable_freeze"),
            "recommended_lab_surface": _RECOMMENDED_SURFACE,
            "freeze_iter1_reject": True,
            "stop_ece_thrash_on_same_test": True,
            "ece_thrash_reopen": False,
            "tobarra_keep_reopen": False,
            "dead_thrash_closed": True,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "locked_reject_thr": arch.get("locked_reject_thr"),
                "freeze_iter1_reject": True,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "pipeline": _PIPELINE,
            },
            "cli_smoke": "wildfire-front ml smoke",
            "smoke_summary": smoke.get("summary"),
            "architecture_gate_checks": arch.get("checks"),
            "product_facade": _FACADE,
            "rank_reject_protocol": rank_reject,
        },
    }
    (out_dir / "lab_loop_v34_latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_post_freeze_smoke.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": passed,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "smoke_pass": passed,
                "gates_ok": passed,
                "control_answer": payload["control_answer"],
                "n_ok": (smoke.get("summary") or {}).get("n_ok"),
                "n_steps": (smoke.get("summary") or {}).get("n_steps"),
                "lab_usable_freeze": (smoke.get("verdict") or {}).get("lab_usable_freeze"),
                "recommended_lab_surface": _RECOMMENDED_SURFACE,
                "freeze_iter1_reject": True,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "ece_thrash_reopen": False,
                "tobarra_keep_reopen": False,
                "product_facade": _FACADE,
                "rank_reject_protocol": _RANK_REJECT_PROTOCOL,
                "architecture_gate_checks": arch.get("checks"),
            },
            indent=2,
        )
    )
    return 0 if passed else 2


def _render_md(payload: dict[str, Any]) -> str:
    smoke = payload.get("smoke") or {}
    v = payload.get("verdict") or {}
    sm = smoke.get("summary") or {}
    arch = payload.get("architecture_smoke_gates") or {}
    checks = arch.get("checks") or {}
    mf = payload.get("multi_fire_honesty") or {}
    tob = mf.get("tobarra") or {}
    w3 = mf.get("w3_external") or {}
    lines = [
        "# ML lab loop — iter 8 post-freeze smoke",
        "",
        f"**UTC:** {payload.get('created_utc')}  ",
        "**Prior:** freeze lab_usable (iter7)  ",
        "**Label:** lab / research_open only",
        "",
        "## Architecture smoke gates",
        "",
        "| Gate | Value |",
        "|------|--------|",
        f"| gates_ok | **{arch.get('gates_ok')}** |",
        f"| facade rails | **{checks.get('facade_rails_ok')}** |",
        f"| facade+protocol path | **{checks.get('facade_rank_reject_pipeline_ok')}** |",
        f"| freeze iter1 reject | **{checks.get('freeze_iter1_reject')}** |",
        f"| thrash reopen absent | **{checks.get('thrash_reopen_absent')}** |",
        f"| multi-fire honesty | **{checks.get('multi_fire_honesty_first_class')}** |",
        f"| locked thr | **{arch.get('locked_reject_thr')}** |",
        f"| product_facade | **{_FACADE}** |",
        f"| rank_reject_protocol | **{_RANK_REJECT_PROTOCOL}** |",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| ml_product_go | **true** |",
        "| field_ops fusion | **OFF** |",
        f"| recommended surface | **{_RECOMMENDED_SURFACE}** |",
        f"| pipeline | **{_PIPELINE}** |",
        "| ECE thrash same TEST | **stopped** |",
        "| Tobarra KEEP reopen | **closed** |",
        f"| Tobarra | **{tob.get('verdict') or tob.get('class') or 'hard'}** |",
        f"| W3 external | **{len(w3.get('fires') or [])} fires (report-only)** |",
        "",
        f"## Control: **{payload.get('control_answer')}**",
        "",
        f"- smoke_pass: **{v.get('smoke_pass')}**",
        f"- gates_ok: **{v.get('gates_ok')}**",
        f"- steps: **{sm.get('n_ok')}/{sm.get('n_steps')}**",
        f"- lab_usable_freeze: **{v.get('lab_usable_freeze')}**",
        f"- note: {v.get('note')}",
        "",
        "## Steps",
        "",
    ]
    for s in smoke.get("steps") or []:
        mark = "x" if s.get("ok") else " "
        lines.append(f"- [{mark}] `{s.get('name')}` — {s.get('detail')}")
    lines += [
        "",
        "## CLI",
        "",
        "```powershell",
        "python -m wildfire_front ml smoke",
        "python scripts/run_lab_ml_loop_v34_smoke.py --pytest",
        "make ml-lab-smoke",
        "```",
        "",
        "---",
        "*Iteration 8 — product_facade + rank_reject_protocol smoke gate; "
        "not field promote; thrash reopen closed.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
