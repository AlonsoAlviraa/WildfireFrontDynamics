#!/usr/bin/env python3
"""DEPRECATED: same-holdout ECE retune thrash path (lab loop iter 2).

Historical VAL-only post-hoc ECE (temperature / Platt on conf logits) did
**not** improve TEST ECE. This runner is sealed so it cannot re-open that
thrash path or re-promote post-hoc lab calibrators.

Product policy (architecture only — no retrain)
-----------------------------------------------
* Rails + dead-path refuse: **product_facade-only** (no ``lab_product_rails``
  dual path). Dual rails lab vs field_ops; IoU ≠ ROS; ``ml_product_go`` default
  **True** (human promote 2026-08-05), never auto-flips; field fusion stays **OFF**.
* Default lab surface remains **iter1 reject only** (VAL thr ≈ 0.795) via
  ``product_facade`` + ``rank_reject_protocol``.
* Multi-fire honesty first-class (Tobarra hard, W3 external report-only).
* Dead path: ``same_holdout_ece_retune`` (``refuse_dead_path``).

Does **not**: call ``tune_ece_recalibration``; write
``uncertainty_calibration_v1_lab_ece.json``; flip field rails.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_ece.py
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

_DEAD_PATH_ID = "same_holdout_ece_retune"
_FACADE = "wildfire_front.ml.product_facade"
_PIPELINE = "features→calibrator→rank/reject→scorecard"
_HISTORICAL_NOTE = (
    "Iter2 VAL post-hoc ECE (temperature/Platt) did not improve TEST ECE "
    "(baseline ~0.15 → worse or flat). Thrash stopped; freeze iter1 reject."
)


def _seal_dead_paths() -> None:
    """Hard-refuse via product_facade dead-path surface (no thrash reopen)."""
    for dead in (
        _DEAD_PATH_ID,
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
        "tobarra_keep_reopen_forbidden": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "freeze_iter1_reject": True,
        "label": "lab / research_open only",
        "dead_path": _DEAD_PATH_ID,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS)),
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
        "--allow-same-holdout-ece-thrash",
        action="store_true",
        help=argparse.SUPPRESS,  # archaeology opt-in is refused; path is sealed
    )
    args = p.parse_args(argv)

    # Hard refuse re-promote of post-hoc ECE calibrators (dead thrash path).
    if args.write_lab_calibrator:
        print(
            "REFUSED: --write-lab-calibrator re-promotes post-hoc ECE calibrators "
            f"(dead thrash path {_DEAD_PATH_ID!r}). "
            f"Default lab surface is {RECOMMENDED_LAB_SURFACE} "
            f"(thr={ITER1_LOCKED_REJECT_THR}).",
            file=sys.stderr,
        )
        return 2

    if args.allow_same_holdout_ece_thrash:
        print(
            "REFUSED: same-holdout ECE retune is sealed "
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
        "schema": "ml_lab_loop_v34_ece_v1",
        "status": "deprecated_thrash_sealed",
        "created_utc": created,
        "product_id": "clm_ensemble_v34",
        "protocol": "clm_holdout_test_seed42_v1",
        "iteration": 2,
        "continues_from": "iter_20260804_reject_calibration (reject surface)",
        "friction": "calibration_ece_imperfect_overconfidence",
        "control_question": ("¿Mejorar ECE con post-hoc VAL-only sin producto de campo?"),
        "control_answer": "NO",  # historical TEST did not improve; thrash stopped
        "deprecated": True,
        "thrash_path": _DEAD_PATH_ID,
        "thrash_sealed": True,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "multi_fire_honesty": multi_fire,
        "prior_iter1_reject": {
            "abstain_threshold": float(ITER1_LOCKED_REJECT_THR),
            "lab_reject_surface_improved": True,
            "frozen_default": True,
            "note": "iter1 reject is the only promoted lab surface",
        },
        "ece_recalibration": {
            "method": "none",
            "temperature": 1.0,
            "platt_a": None,
            "platt_b": None,
            "val_ece_baseline": None,
            "val_ece_tuned": None,
            "test_ece_baseline": None,
            "test_ece_tuned": None,
            "test_mean_conf_baseline": None,
            "test_mean_conf_tuned": None,
            "improved_on_test": False,
            "delta_test_ece": None,
            "protocol_note": (
                "Same-holdout ECE retune is sealed. No retune executed. " + _HISTORICAL_NOTE
            ),
            "retune_executed": False,
            "write_lab_calibrator": False,
        },
        "combined_reject_after_ece": {
            "note": (
                "Combined ECE+reject retune removed. Use frozen iter1 reject "
                f"(thr={ITER1_LOCKED_REJECT_THR}) via product_facade + "
                "rank_reject_protocol."
            ),
            "abstain_threshold": float(ITER1_LOCKED_REJECT_THR),
            "retune_executed": False,
        },
        "verdict": {
            "ece_improved_on_test": False,
            "reject_surface_still_available": True,
            "field_product": False,
            "ml_product_go": True,
            "stop_ece_thrash_on_same_test": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "thrash_sealed": True,
            "write_lab_calibrator_refused": True,
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "note": (
                "Dead thrash path sealed via product_facade.refuse_dead_path: "
                "no same-holdout ECE retune; no post-hoc lab calibrator re-promote. "
                f"Use {RECOMMENDED_LAB_SURFACE} (thr={ITER1_LOCKED_REJECT_THR}). "
                "Field fusion OFF."
            ),
        },
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "lab_loop_v34_ece_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Latest pointer: mark thrash stopped; do not re-promote ECE surface.
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
        "iter1_reject": "lab_loop_v34_reject_latest.json",
        "iter2_ece": "lab_loop_v34_ece_latest.json",
        "iterations": {
            **prev_iters,
            "1_reject": "lab_loop_v34_reject_latest.json",
            "2_ece_posthoc": "lab_loop_v34_ece_latest.json",
        },
        "summary": {
            **prev_sum,
            "iter2_ece": {
                "method": "none",
                "status": "deprecated_thrash_sealed",
                "improved": False,
                "retune_executed": False,
            },
            "iter2_ece_improved": False,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "stop_ece_thrash_on_same_test": True,
            "no_ece_retune_same_holdout": True,
            "rails": {
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "field_ops_ml_live_fusion": "OFF",
                "iou_is_not_ros": True,
                "label": "lab / research_open only",
                "no_ece_retune_same_holdout": True,
                "stop_ece_thrash_on_same_test": True,
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
            ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_20260804_ece_recalibration.md"
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
                "retune_executed": False,
                "write_lab_calibrator_allowed": False,
                "ece_improved_on_test": False,
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
    return f"""# ML lab loop — iter 2 ECE recalibration (**DEPRECATED / SEALED**)

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
| same-holdout ECE retune | **SEALED (dead thrash)** |

## Why sealed

{_HISTORICAL_NOTE}

This runner **does not**:

1. Call ``tune_ece_recalibration`` (quarantined thrash API).
2. Write ``uncertainty_calibration_v1_lab_ece.json`` (no re-promote).
3. Re-tune reject thr after post-hoc ECE.

## Verdict

- ECE improved on TEST: **{v.get("ece_improved_on_test")}**
- stop_ece_thrash_on_same_test: **{v.get("stop_ece_thrash_on_same_test")}**
- thrash_sealed: **{v.get("thrash_sealed")}**
- Field product: **false**
- Use: **iter1 reject only** (``product_facade`` + ``rank_reject_protocol``)

## How to run (seal only)

```powershell
$env:PYTHONPATH = "."
python scripts\\run_lab_ml_loop_v34_ece.py
python -m wildfire_front ml show
```

`--write-lab-calibrator` and thrash re-open flags are **refused**.

Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_ece_latest.json`

---
*Iteration 2 sealed — not tactical dispatch; not a promote path.*
"""


if __name__ == "__main__":
    raise SystemExit(main())
