#!/usr/bin/env python3
"""DEPRECATED: same-holdout logistic refit thrash path (lab loop iter 3).

Historical VAL-only full logistic re-fit of Head A (optional Platt/temperature
second stage) did **not** improve TEST ECE (baseline ~0.15 → worse). This
runner is sealed so it cannot re-open that thrash path or re-promote lab
refit calibrators.

Paired with iter2 ECE post-hoc thrash (``run_lab_ml_loop_v34_ece.py``).

Product policy (architecture only — no retrain)
-----------------------------------------------
* Dual rails: **lab ML** vs **field_ops**; IoU ≠ ROS; ``ml_product_go`` **true**
  (human promote 2026-08-05; no auto-flip); field fusion stays **OFF**.
* Default lab surface remains **iter1 reject only** (VAL thr ≈ 0.795).
* Multi-fire honesty first-class (Tobarra hard, W3 external report-only).
* Dead path: ``logistic_refit_same_test`` / same-holdout logistic refit.
* Single path: ``product_facade`` + ``rank_reject_protocol``
  (features→calibrator→rank/reject→scorecard). No ``lab_product_rails`` dual.

Does **not**: call ``fit_logistic_calibrator``; write
``uncertainty_calibration_v1_lab_refit.json``; flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_refit.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.product_facade import (  # noqa: E402
    DEAD_PATHS,
    DEFAULT_MULTI_FIRE,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
)

_DEAD_PATH_ID = "logistic_refit_same_test"
_FACADE = "wildfire_front.ml.product_facade"
_PIPELINE = "features→calibrator→rank/reject→scorecard"
_HISTORICAL_NOTE = (
    "Iter3 VAL full logistic re-fit (+ optional Platt/temperature) did not "
    "improve TEST ECE (baseline ~0.1528 → ~0.1782). lab_refit_recommended=false. "
    "Thrash stopped; freeze iter1 reject as default lab surface."
)


def _seal_dead_paths() -> None:
    """Hard-refuse via product_facade dead-path surface (no thrash reopen)."""
    for dead in (
        _DEAD_PATH_ID,  # logistic_refit_same_test — same-holdout thrash
        "same_holdout_ece_retune",
        "ece_posthoc_same_test",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected — path is sealed
        else:
            raise ProductFacadeError(f"dead path still open: {dead!r}")


def _rails_payload() -> dict[str, Any]:
    """product_facade-only dual rails (no lab_product_rails dual path)."""
    facade_rails = assert_lab_rails(DEFAULT_RAILS)
    return {
        **facade_rails.as_dict(),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "fit_split": "val",
        "val_only_threshold_selection": True,
        "test_never_used_for_tune": True,
        "no_ece_retune_same_holdout": True,
        "stop_ece_thrash_on_same_test": True,
        "no_logistic_refit_same_holdout": True,
        "tobarra_keep_reopen_forbidden": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "freeze_iter1_reject": True,
        "label": "lab / research_open only",
        "dead_path": _DEAD_PATH_ID,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS) | {_DEAD_PATH_ID}),
        "thrash_sealed": True,
        "write_lab_calibrator_allowed": False,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
    }


def _rank_reject_protocol() -> dict[str, Any]:
    """Shared rank/reject surface (VAL thr freeze; iter1 reject default)."""
    return {
        **DEFAULT_RANK_REJECT.as_dict(),
        "thr_source": "val_iter1_reject_frozen",
        "thr_tune_split": "val",
        "freeze_iter1_reject": True,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "module": "wildfire_front.ml.rank_reject_protocol",
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
        help="Optional markdown path (default docs/ML_LOOP_ITERATIONS seal note)",
    )
    p.add_argument("--no-md", action="store_true")
    p.add_argument(
        "--write-lab-calibrator",
        action="store_true",
        help=argparse.SUPPRESS,  # kept so old invocations fail closed, not silently
    )
    p.add_argument(
        "--allow-same-holdout-logistic-refit",
        action="store_true",
        help=argparse.SUPPRESS,  # archaeology opt-in is refused; path is sealed
    )
    # Legacy flags (accepted then ignored) so old CLI invocations still seal closed.
    p.add_argument("--baseline-calibrator", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--val-npz", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--test-npz", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--l2", type=float, default=None, help=argparse.SUPPRESS)
    p.add_argument("--export-fail-cases", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    # Hard refuse re-promote of logistic refit calibrators (dead thrash path).
    if args.write_lab_calibrator:
        print(
            "REFUSED: --write-lab-calibrator re-promotes logistic refit calibrators "
            f"(dead thrash path {_DEAD_PATH_ID!r}). "
            f"Default lab surface is {RECOMMENDED_LAB_SURFACE} "
            f"(thr={ITER1_LOCKED_REJECT_THR}).",
            file=sys.stderr,
        )
        return 2

    if args.allow_same_holdout_logistic_refit:
        print(
            "REFUSED: same-holdout logistic refit is sealed "
            f"(forbidden thrash path {_DEAD_PATH_ID!r}). "
            "Do not re-open; freeze iter1 reject as default.",
            file=sys.stderr,
        )
        return 2

    # product_facade-only rails + refuse_dead_path surface (no lab_product_rails).
    assert _DEAD_PATH_ID in FORBIDDEN_THRASH_PATHS or _DEAD_PATH_ID in DEAD_PATHS
    _seal_dead_paths()
    rails = _rails_payload()
    rank_reject = _rank_reject_protocol()
    multi_fire = DEFAULT_MULTI_FIRE.as_dict()

    created = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "schema": "ml_lab_loop_v34_refit_v1",
        "status": "deprecated_thrash_sealed",
        "created_utc": created,
        "product_id": "clm_ensemble_v34",
        "protocol": "clm_holdout_test_seed42_v1",
        "iteration": 3,
        "friction": "calibration_ece_after_posthoc_failed",
        "control_question": ("¿Re-fit logistic Head A en VAL baja ECE TEST y mantiene reject?"),
        "control_answer": "NO",  # historical TEST did not improve; thrash stopped
        "deprecated": True,
        "thrash_path": _DEAD_PATH_ID,
        "thrash_sealed": True,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "prior": {
            "iter1_reject": "YES lab promote (abstain surface) — frozen default",
            "iter2_ece_posthoc": "NO TEST ECE gain — sealed thrash",
        },
        "fit": {
            "method": "none",
            "refit_executed": False,
            "second_stage": "none",
            "second_stage_params": {},
            "protocol_note": (
                "Same-holdout logistic refit is sealed. No re-fit executed. " + _HISTORICAL_NOTE
            ),
        },
        "metrics": {
            "note": (
                "Historical metrics archived; no new same-holdout fit. "
                "See prior lab_loop_v34_refit artifacts if present."
            ),
            "refit_executed": False,
            "lab_refit_recommended": False,
        },
        "verdict": {
            "ece_improved_on_test": False,
            "reject_surface_available": True,
            "lab_refit_recommended": False,
            "field_product": False,
            "ml_product_go": True,
            "stop_ece_thrash_on_same_test": True,
            "no_logistic_refit_same_holdout": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "thrash_sealed": True,
            "write_lab_calibrator_refused": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "note": (
                "Dead thrash path sealed via product_facade.refuse_dead_path: "
                "no same-holdout logistic refit; no lab_refit calibrator re-promote. "
                f"Use {RECOMMENDED_LAB_SURFACE} (thr={ITER1_LOCKED_REJECT_THR}). "
                "Field fusion OFF."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_refit_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Latest pointer: mark thrash stopped; do not re-promote refit surface.
    prev_path = out_dir / "lab_loop_v34_latest.json"
    prev: dict[str, Any] = {}
    if prev_path.is_file():
        try:
            loaded = json.loads(prev_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prev = loaded
        except (OSError, json.JSONDecodeError):
            prev = {}
    prev_sum = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
    prev_iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}

    combined = {
        "schema": "ml_lab_loop_v34_latest_v1",
        "updated_utc": created,
        "iterations": {
            **prev_iters,
            "1_reject": "lab_loop_v34_reject_latest.json",
            "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
            "3_refit": "lab_loop_v34_refit_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter3_refit": {
                "method": "none",
                "status": "deprecated_thrash_sealed",
                "improved": False,
                "refit_executed": False,
            },
            "iter3_ece_improved": False,
            "iter3_method": "none",
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "stop_ece_thrash_on_same_test": True,
            "no_ece_retune_same_holdout": True,
            "no_logistic_refit_same_holdout": True,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "stop_ece_thrash_on_same_test": True,
                "no_logistic_refit_same_holdout": True,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "product_facade": _FACADE,
                "pipeline": _PIPELINE,
            },
            "product_facade": _FACADE,
            "rank_reject_protocol": rank_reject,
        },
    }
    prev_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    md_path: Path | None = None
    if not args.no_md:
        md_path = args.md_path or (
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_refit_logistic.md"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "deprecated": True,
                "thrash_sealed": True,
                "json": str(json_path),
                "md": str(md_path) if md_path else None,
                "combined": str(prev_path),
                "lab_calibrator": None,
                "method": "none",
                "refit_executed": False,
                "write_lab_calibrator_allowed": False,
                "ece_improved": False,
                "lab_refit_recommended": False,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": ITER1_LOCKED_REJECT_THR,
                "stop_ece_thrash_on_same_test": True,
                "ml_product_go": True,
                "field_ops_fusion": "OFF",
                "product_facade": _FACADE,
                "pipeline": _PIPELINE,
            },
            indent=2,
        )
    )
    return 0


def _render_md(payload: dict[str, Any]) -> str:
    v = payload.get("verdict") or {}
    return f"""# ML lab loop — iter 3 re-fit logistic Head A (**DEPRECATED / SEALED**)

**UTC:** {payload.get("created_utc")}
**Status:** **deprecated_thrash_sealed**
**Label:** **lab / research_open only**

## Rails (unchanged product policy)

| Rail | Value |
|------|--------|
| ml_product_go | **true** |
| field_ops ML live fusion | **OFF** |
| IoU as ROS | **never** |
| recommended_lab_surface | **{RECOMMENDED_LAB_SURFACE}** |
| locked_reject_thr | **{ITER1_LOCKED_REJECT_THR}** |
| same-holdout logistic refit | **SEALED (dead thrash)** |
| product_facade | **{_FACADE}** |
| pipeline | **{_PIPELINE}** |

## Why sealed

{_HISTORICAL_NOTE}

Paired dead path: iter2 ECE post-hoc (``same_holdout_ece_retune``).

This runner **does not**:

1. Call ``fit_logistic_calibrator`` (no VAL re-fit thrash).
2. Write ``uncertainty_calibration_v1_lab_refit.json`` (no re-promote).
3. Re-tune reject thr on refit confidences.
4. Dual-import ``lab_product_rails`` (facade-only rails + refuse_dead_path).

## Verdict

- ECE improved on TEST: **{v.get("ece_improved_on_test")}**
- lab_refit_recommended: **{v.get("lab_refit_recommended")}**
- thrash_sealed: **{v.get("thrash_sealed")}**
- Field product: **false**
- Use: **iter1 reject only** (``product_facade`` + ``rank_reject_protocol``)

## How to run (seal only)

```powershell
$env:PYTHONPATH = "."
python scripts\\run_lab_ml_loop_v34_refit.py
python -m wildfire_front ml show
```

`--write-lab-calibrator` and thrash re-open flags are **refused**.

Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_refit_latest.json`

---
*Iteration 3 sealed — not tactical dispatch; not a promote path.*
"""


if __name__ == "__main__":
    raise SystemExit(main())
