#!/usr/bin/env python3
"""DEPRECATED: Tobarra LOFO KEEP reopen train hook (dead thrash path).

Historical fresh LOFO train (init-v21, 2026-08-05) scored IoU ≈ 0.4776 vs
Head A baseline ≈ 0.489 → **KILL** under K1. This runner is sealed so the
same recipe cannot thrash KEEP or re-promote KILL weights onto product rails.

Product policy (architecture only — no retrain)
-----------------------------------------------
* Rails + dead-path refuse: **product_facade-only** (no ``lab_product_rails``
  dual path). Dual rails lab vs field_ops; IoU ≠ ROS; ``ml_product_go`` never
  auto-flips; field fusion stays **OFF**.
* Default lab surface remains **iter1 reject only** (VAL thr ≈ 0.795) via
  ``product_facade`` + ``rank_reject_protocol``.
* Multi-fire honesty first-class: Tobarra = hard transfer (KILL); W3 external
  report-only.
* Dead paths: ``tobarra_keep_reopen_same_recipe`` /
  ``tobarra_keep_reopen_kill_weights`` / ``tobarra_keep_same_recipe``.

Does **not**: call ``run_training``; copy KILL weights to
``lofo_tobarra_keep_attempt_latest``; flip field rails; retune thr/ECE on test.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_tobarra_lofo_keep_attempt.py
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
    TOBARRA_FIRE_ID,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (  # noqa: E402
    FORBIDDEN_THRASH_PATHS,
)
from wildfire_front.ml.w3_signal import (  # noqa: E402
    tobarra_keep_seal,
)

FOLD = TOBARRA_FIRE_ID  # tobarra_20240802
OUT_BASE = ROOT / "outputs" / "ml_eval"

_DEAD_PATH_ID = "tobarra_keep_reopen_same_recipe"
_FACADE = "wildfire_front.ml.product_facade"
_PIPELINE = "features→calibrator→rank/reject→scorecard"
_DEAD_PATH_ALIASES = frozenset(
    {
        "tobarra_keep_reopen_same_recipe",
        "tobarra_keep_reopen_kill_weights",
        "tobarra_keep_same_recipe",
    }
)
_HISTORICAL_NOTE = (
    "Fresh Tobarra LOFO init-v21 (2026-08-05) IoU 0.4776 < Head A 0.489 → "
    "KILL under K1. Same-recipe KEEP reopen sealed; do not re-promote KILL weights."
)


def _seal_dead_paths() -> None:
    """Hard-refuse via product_facade dead-path surface (no thrash reopen)."""
    for dead in (
        _DEAD_PATH_ID,
        "tobarra_keep_reopen_same_recipe",
        "same_holdout_ece_retune",
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
        "tobarra_keep_reopen": False,
        "tobarra_keep_reopen_forbidden": True,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "freeze_iter1_reject": True,
        "label": "lab / research_open only",
        "dead_path": _DEAD_PATH_ID,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS) | _DEAD_PATH_ALIASES),
        "thrash_sealed": True,
        "train_executed": False,
        "run_training_allowed": False,
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
    # Historical CLI flags kept so old invocations fail closed, not silently train.
    p.add_argument("--epochs", type=int, default=15, help=argparse.SUPPRESS)
    p.add_argument("--batch-size", type=int, default=8, help=argparse.SUPPRESS)
    p.add_argument(
        "--device",
        choices=("cpu", "cuda", "auto"),
        default="auto",
        help=argparse.SUPPRESS,
    )
    p.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--init-weights", type=Path, default=None, help=argparse.SUPPRESS)
    p.add_argument("--out-name", default=None, help=argparse.SUPPRESS)
    p.add_argument(
        "--allow-tobarra-keep-reopen",
        action="store_true",
        help=argparse.SUPPRESS,  # archaeology opt-in is refused; path is sealed
    )
    p.add_argument(
        "--force-train",
        action="store_true",
        help=argparse.SUPPRESS,  # refuse re-open of sealed KEEP train hook
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_BASE,
        help="Directory for seal JSON (default outputs/ml_eval)",
    )
    p.add_argument("--no-md", action="store_true")
    args = p.parse_args(argv)

    # Hard refuse KEEP reopen / KILL re-promote (dead thrash path).
    if args.allow_tobarra_keep_reopen or args.force_train:
        print(
            "REFUSED: Tobarra KEEP reopen / KILL re-promote is sealed "
            f"(forbidden thrash path {_DEAD_PATH_ID!r}). "
            f"{_HISTORICAL_NOTE} "
            f"Default lab surface is {RECOMMENDED_LAB_SURFACE} "
            f"(thr={ITER1_LOCKED_REJECT_THR}). Field fusion OFF.",
            file=sys.stderr,
        )
        return 2

    # product_facade-only rails + refuse_dead_path surface (no lab_product_rails).
    assert _DEAD_PATH_ID in DEAD_PATHS
    assert "tobarra_keep_reopen_kill_weights" in FORBIDDEN_THRASH_PATHS
    assert "tobarra_keep_same_recipe" in FORBIDDEN_THRASH_PATHS
    _seal_dead_paths()
    rails = _rails_payload()
    rank_reject = _rank_reject_protocol()
    multi_fire = DEFAULT_MULTI_FIRE.as_dict()
    keep_seal = tobarra_keep_seal()

    created = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "schema": "tobarra_lofo_keep_attempt_v1",
        "status": "deprecated_thrash_sealed",
        "created_utc": created,
        "product_id": "clm_ensemble_v34",
        "fold": FOLD,
        "deprecated": True,
        "thrash_path": _DEAD_PATH_ID,
        "thrash_sealed": True,
        "train_executed": False,
        "run_training_allowed": False,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "rails": rails,
        "rank_reject_protocol": rank_reject,
        "tobarra_keep_seal": keep_seal,
        "multi_fire_honesty": multi_fire,
        "historical": {
            "fresh_train_utc": "2026-08-05",
            "mean_iou": 0.4776,
            "head_a_baseline_iou": 0.489,
            "k1_pass": False,
            "verdict": "KILL",
            "note": _HISTORICAL_NOTE,
        },
        "verdict": {
            "keep": False,
            "kill": True,
            "re_promote_kill_weights": False,
            "same_recipe_reopen": False,
            "field_product": False,
            "ml_product_go": True,
            "thrash_sealed": True,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
            "product_facade": _FACADE,
            "pipeline": _PIPELINE,
            "note": (
                "Dead thrash path sealed via product_facade.refuse_dead_path: "
                "no Tobarra KEEP reopen train; no re-promote of KILL weights. "
                f"Use {RECOMMENDED_LAB_SURFACE} (thr={ITER1_LOCKED_REJECT_THR}). "
                "Field fusion OFF. Multi-fire: Tobarra hard / W3 external."
            ),
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seal_dir = out_dir / "lofo_tobarra_keep_attempt_sealed"
    seal_dir.mkdir(parents=True, exist_ok=True)
    json_path = seal_dir / "keep_attempt_seal.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Latest pointer: mark thrash stopped; do not copy/re-promote KILL weights.
    latest_ptr = out_dir / "lofo_tobarra_keep_attempt_latest.json"
    latest_ptr.write_text(
        json.dumps(
            {
                "path": str(seal_dir.as_posix()),
                "updated_utc": created,
                "status": "deprecated_thrash_sealed",
                "train_executed": False,
                "thrash_sealed": True,
                "tobarra_keep_reopen": False,
                "ml_product_go": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "product_facade": _FACADE,
                "note": _HISTORICAL_NOTE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md_path: Path | None = None
    if not args.no_md:
        md_path = ROOT / "docs" / "ML_LOOP_ITERATIONS" / "iter_tobarra_keep_or_kill_sealed.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_md(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "deprecated": True,
                "thrash_sealed": True,
                "train_executed": False,
                "run_training_allowed": False,
                "json": str(json_path),
                "latest_ptr": str(latest_ptr),
                "md": str(md_path) if md_path else None,
                "fold": FOLD,
                "verdict": "KILL",
                "tobarra_keep_reopen": False,
                "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
                "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
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
    h = payload.get("historical") or {}
    return f"""# Tobarra LOFO KEEP attempt (**DEPRECATED / SEALED**)

**UTC:** {payload.get("created_utc")}
**Status:** **deprecated_thrash_sealed**
**Label:** **lab / research_open only**
**Fold:** `{FOLD}`
**product_facade:** `{_FACADE}`
**pipeline:** `{_PIPELINE}`

## Rails (product_facade-only product policy)

| Rail | Value |
|------|--------|
| product_facade | **{_FACADE}** |
| rank_reject_protocol | **wildfire_front.ml.rank_reject_protocol** |
| ml_product_go | **false** |
| field_ops ML live fusion | **OFF** |
| IoU as ROS | **never** |
| recommended_lab_surface | **{RECOMMENDED_LAB_SURFACE}** |
| locked_reject_thr | **{ITER1_LOCKED_REJECT_THR}** |
| Tobarra KEEP reopen | **SEALED (dead thrash)** |
| re-promote KILL weights | **forbidden** |

## Why sealed

{_HISTORICAL_NOTE}

Historical: mean_iou={h.get("mean_iou")} vs Head A {h.get("head_a_baseline_iou")} → KILL (K1 fail).

This runner **does not**:

1. Call ``run_training`` / reopen same LOFO KEEP recipe.
2. Copy weights into ``lofo_tobarra_keep_attempt_latest`` (no KILL re-promote).
3. Fit thr/ECE on Tobarra test or flip field rails.
4. Dual-import ``lab_product_rails`` (facade-only rails + refuse_dead_path).

## Verdict

- keep: **{v.get("keep")}**
- kill: **{v.get("kill")}**
- thrash_sealed: **{v.get("thrash_sealed")}**
- Field product: **false**
- Use: **iter1 reject only** (``product_facade`` + ``rank_reject_protocol``)
- Multi-fire: Tobarra hard transfer; W3 external report-only

## How to run (seal only)

```powershell
$env:PYTHONPATH = "."
python scripts\\run_tobarra_lofo_keep_attempt.py
python -m wildfire_front ml show
```

`--force-train` / `--allow-tobarra-keep-reopen` are **refused**.

Machine: `outputs/ml_eval/lofo_tobarra_keep_attempt_sealed/keep_attempt_seal.json`

---
*Tobarra KEEP reopen sealed — not tactical dispatch; not a promote path.*
"""


if __name__ == "__main__":
    raise SystemExit(main())
