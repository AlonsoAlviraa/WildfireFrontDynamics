#!/usr/bin/env python3
"""Lab ML metrics lift board writer (E0 instrumentation).

Seals LOFO / U1 baselines and optionally scores a candidate root into
``outputs/ml_eval/lab_loop/lab_loop_v34_metrics_lift_latest.json``.

Does **not** retrain. Does **not** claim KEEP without kill scoring.

Usage::

    $env:PYTHONPATH = "."
    python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only
    python scripts/run_lab_ml_loop_v34_metrics_lift.py \\
        --candidate-root outputs/ml_eval/lofo_v1_recover_v2_kaggle \\
        --experiment-id E_recover_v2_sealed_multi_if --kill-verdict KEEP
    python scripts/run_lab_ml_loop_v34_metrics_lift.py --candidate-board outputs/ml_eval/lab_loop/lab_loop_v34_lofo_board_latest.json
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

from wildfire_front.ml.lab_metrics_lift import (  # noqa: E402
    SCHEMA,
    build_metrics_lift_board,
    format_board_human,
    write_metrics_lift_board,
)
from wildfire_front.ml.product_facade import DEFAULT_PRODUCT_ID  # noqa: E402

_FACADE: Final = "wildfire_front.ml.product_facade"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"


def main(argv: list[str] | None = None) -> int:
    # Reject deprecated flag name before argparse (KD14: --candidate-root only)
    raw = list(argv if argv is not None else sys.argv[1:])
    if any(a == "--candidate-dir" or a.startswith("--candidate-dir=") for a in raw):
        print(
            "error: --candidate-dir is deprecated; use --candidate-root only",
            file=sys.stderr,
        )
        return 2

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <repo>/outputs/ml_eval/lab_loop",
    )
    p.add_argument(
        "--candidate-root",
        type=Path,
        default=None,
        help="Root with {FOLD}/evaluation_metrics.json children (canonical)",
    )
    p.add_argument(
        "--candidate-board",
        type=Path,
        default=None,
        help="Optional pre-built LOFO board JSON instead of scanning folds",
    )
    p.add_argument(
        "--baselines-only",
        action="store_true",
        help="Seal baselines; no candidate metrics",
    )
    p.add_argument("--experiment-id", type=str, default=None)
    p.add_argument("--champion-candidate", action="store_true")
    p.add_argument(
        "--kill-verdict",
        type=str,
        default="PENDING",
        choices=["PENDING", "KEEP", "KILL", "INCONCLUSIVE"],
    )
    p.add_argument("--u1-iou", type=float, default=None)
    p.add_argument(
        "--u1-status",
        type=str,
        default=None,
        choices=["SKIPPED", "MEASURED", "REQUIRED_MISSING"],
    )
    p.add_argument("--json", action="store_true", help="Print full board JSON")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)

    repo = args.repo.resolve()
    out_dir = (args.out_dir or (repo / "outputs" / "ml_eval" / "lab_loop")).resolve()
    baselines_only = bool(args.baselines_only) or (
        args.candidate_root is None and args.candidate_board is None
    )
    if args.baselines_only:
        baselines_only = True

    exp_id = args.experiment_id
    if exp_id is None:
        exp_id = "baselines_only" if baselines_only else "candidate"

    board = build_metrics_lift_board(
        repo,
        candidate_root=args.candidate_root,
        candidate_board=args.candidate_board,
        experiment_id=exp_id,
        champion_candidate=bool(args.champion_candidate),
        kill_verdict=args.kill_verdict,
        u1_iou=args.u1_iou,
        u1_status=args.u1_status,
        baselines_only=baselines_only,
    )

    out_path = out_dir / "lab_loop_v34_metrics_lift_latest.json"
    if not args.no_write:
        write_metrics_lift_board(board, out_path)
        # Update latest pointer lightly
        latest_path = out_dir / "lab_loop_v34_latest.json"
        prev: dict[str, Any] = {}
        if latest_path.is_file():
            try:
                prev = json.loads(latest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                prev = {}
        iters = prev.get("iterations") if isinstance(prev.get("iterations"), dict) else {}
        summ = prev.get("summary") if isinstance(prev.get("summary"), dict) else {}
        latest = {
            **prev,
            "schema": prev.get("schema") or "ml_lab_loop_v34_latest_v1",
            "updated_utc": datetime.now(UTC).isoformat(),
            "iterations": {
                **iters,
                "metrics_lift": "lab_loop_v34_metrics_lift_latest.json",
            },
            "summary": {
                **summ,
                "metrics_lift": {
                    "schema": SCHEMA,
                    "experiment_id": (board.get("candidate") or {}).get("experiment_id"),
                    "kill_verdict": board.get("kill_verdict"),
                    "tier": board.get("tier"),
                    "north_star_g1_met": board.get("north_star_g1_met"),
                    "north_star_g2_met": board.get("north_star_g2_met"),
                    "design_success_closed": board.get("design_success_closed"),
                    "candidate_status": (board.get("candidate") or {}).get("status"),
                },
            },
        }
        latest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")

    summary = {
        "ok": True,
        "schema": board.get("schema"),
        "product_id": DEFAULT_PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "out": str(out_path) if not args.no_write else None,
        "baselines_only": baselines_only,
        "baselines": {
            "lofo_mean_iou": (board.get("baselines") or {}).get("lofo_mean_iou"),
            "lofo_min_iou": (board.get("baselines") or {}).get("lofo_min_iou"),
            "u1_test_mean_iou": (board.get("baselines") or {}).get("u1_test_mean_iou"),
        },
        "candidate": board.get("candidate"),
        "north_star": board.get("north_star"),
        "kill_verdict": board.get("kill_verdict"),
        "tier": board.get("tier"),
        "rails_ok": board.get("rails_ok"),
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
    }
    if args.json:
        print(json.dumps(board, indent=2))
    else:
        sys.stdout.write(format_board_human(board))
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
