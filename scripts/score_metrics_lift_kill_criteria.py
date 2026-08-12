#!/usr/bin/env python3
"""Score metrics-lift kill criteria L1–L9 for profiles E2/E3/E4/E5.

Does **not** train. Reads candidate LOFO metrics + optional leak audit.
Writes ``outputs/ml_eval/lab_loop/metrics_lift_{experiment_id}_kill.json``.

T1 KEEP ≠ T2 north-star (G1∧G2 stamped honestly, may be false while KEEP).

Usage::

    $env:PYTHONPATH = "."
    python scripts/score_metrics_lift_kill_criteria.py --profile E2 --baselines-as-candidate
    python scripts/score_metrics_lift_kill_criteria.py --profile E3 \\
        --candidate-root outputs/ml_eval/lofo_v2 --experiment-id E3a_hellin_train_pool
    python scripts/score_metrics_lift_kill_criteria.py --profile E3 --smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.lab_metrics_lift import (  # noqa: E402
    BASELINE_LOFO_MEAN,
    BASELINE_LOFO_MIN,
    CORE3_FOLD_BASELINES,
    DEFAULT_LEAK_AUDIT_PATH,
    build_metrics_lift_board,
    collect_candidate_from_board,
    collect_candidate_from_root,
    load_json,
    score_kill_criteria,
    write_metrics_lift_board,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--profile",
        type=str,
        required=True,
        choices=["E2", "E3", "E4", "E5", "e2", "e3", "e4", "e5"],
    )
    p.add_argument("--experiment-id", type=str, default=None)
    p.add_argument("--candidate-root", type=Path, default=None)
    p.add_argument("--candidate-board", type=Path, default=None)
    p.add_argument(
        "--baselines-as-candidate",
        action="store_true",
        help="Score locked baselines as candidate (honest no-lift reference)",
    )
    p.add_argument("--champion-candidate", action="store_true")
    p.add_argument("--u1-iou", type=float, default=None)
    p.add_argument(
        "--u1-status",
        type=str,
        default=None,
        choices=["SKIPPED", "MEASURED", "REQUIRED_MISSING"],
    )
    p.add_argument(
        "--leak-audit",
        type=Path,
        default=None,
        help="lofo_pack_leak_audit JSON (default lab_loop latest if present)",
    )
    p.add_argument("--n-leaked", type=int, default=None)
    p.add_argument("--train-incomplete", action="store_true")
    p.add_argument("--tobarra-keep-claim", action="store_true")
    p.add_argument("--test-thr-ece-fit", action="store_true")
    p.add_argument("--larger-unet-default", action="store_true")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Kill JSON path (default lab_loop/metrics_lift_{id}_kill.json)",
    )
    p.add_argument(
        "--write-board",
        action="store_true",
        help="Also write metrics lift board with kill_verdict",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="CI smoke: score synthetic incomplete path; exit 0; never claim KEEP",
    )
    args = p.parse_args(argv)

    repo = args.repo.resolve()
    profile = str(args.profile).upper()
    exp_id = args.experiment_id or f"{profile.lower()}_metrics_lift"

    if args.smoke:
        # Deterministic incomplete → INCONCLUSIVE/KILL, never KEEP
        kill = score_kill_criteria(
            profile=profile,
            experiment_id=f"{exp_id}_smoke",
            lofo_mean=None,
            lofo_min=None,
            fold_rows={},
            champion_candidate=False,
            train_complete=False,
        )
        out = args.out or (
            repo / "outputs" / "ml_eval" / "lab_loop" / f"metrics_lift_{exp_id}_smoke_kill.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(kill, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "smoke": True,
                    "verdict": kill["verdict"],
                    "out": str(out),
                    "note": "smoke incomplete train — never KEEP",
                },
                indent=2,
            )
        )
        assert kill["verdict"] != "KEEP"
        return 0

    folds: dict[str, dict[str, Any]] = {}
    mean: float | None = None
    mn: float | None = None
    train_complete = not args.train_incomplete

    if args.baselines_as_candidate:
        mean = BASELINE_LOFO_MEAN
        mn = BASELINE_LOFO_MIN
        for fname, iou in CORE3_FOLD_BASELINES.items():
            # approximate copy deltas from locked board (design §3)
            copy_deltas = {
                "CARDOSO": 0.15600850763683827,
                "LA_ESTRELLA_ACOM1": 0.42383156310067677,
                "LA_ESTRELLA_ACOM2": 0.32333844124651756,
            }
            folds[fname] = {
                "fold": fname,
                "model_iou": iou,
                "improvement_vs_copy_iou": copy_deltas.get(fname),
                "n_test": 200,
            }
        exp_id = args.experiment_id or "BASELINE_REFERENCE"
    elif args.candidate_root is not None:
        collected = collect_candidate_from_root(Path(args.candidate_root))
        folds = collected.get("folds") or {}
        mean = collected["core3"].get("mean")
        mn = collected["core3"].get("min")
        train_complete = train_complete and bool(collected.get("complete"))
    elif args.candidate_board is not None:
        board = load_json(Path(args.candidate_board)) or {}
        collected = collect_candidate_from_board(board)
        folds = collected.get("folds") or {}
        mean = collected["core3"].get("mean")
        mn = collected["core3"].get("min")
        train_complete = train_complete and (bool(collected.get("complete")) or mean is not None)
    else:
        # default: try lofo_v1 eval root
        default_root = repo / "outputs" / "ml_eval" / "lofo_v1"
        if default_root.is_dir():
            collected = collect_candidate_from_root(default_root)
            folds = collected.get("folds") or {}
            mean = collected["core3"].get("mean")
            mn = collected["core3"].get("min")
            train_complete = train_complete and bool(collected.get("complete"))
            exp_id = args.experiment_id or "BASELINE_REFERENCE"
        else:
            train_complete = False

    # Leak audit
    n_leaked = args.n_leaked
    leak_path = args.leak_audit
    if n_leaked is None:
        candidates = []
        if leak_path:
            candidates.append(Path(leak_path))
        candidates.append(repo / DEFAULT_LEAK_AUDIT_PATH)
        n_leaked = 0
        for lp in candidates:
            d = load_json(lp)
            if d:
                n_leaked = int(d.get("n_leaked_train_val") or 0)
                leak_path = lp
                break

    kill = score_kill_criteria(
        profile=profile,
        experiment_id=exp_id,
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=folds,
        champion_candidate=bool(args.champion_candidate),
        u1_iou=args.u1_iou,
        u1_status=args.u1_status,
        n_leaked_train_val=int(n_leaked or 0),
        leak_audit_path=str(leak_path.as_posix()) if leak_path else None,
        train_complete=train_complete,
        larger_unet_default=bool(args.larger_unet_default),
        tobarra_keep_claim=bool(args.tobarra_keep_claim),
        test_thr_ece_fit=bool(args.test_thr_ece_fit),
    )

    out = args.out or (
        repo / "outputs" / "ml_eval" / "lab_loop" / f"metrics_lift_{exp_id}_kill.json"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kill, indent=2), encoding="utf-8")

    if args.write_board:
        board = build_metrics_lift_board(
            repo,
            candidate_root=args.candidate_root,
            candidate_board=args.candidate_board,
            experiment_id=exp_id,
            champion_candidate=bool(args.champion_candidate),
            kill_verdict=kill["verdict"],
            u1_iou=args.u1_iou,
            u1_status=args.u1_status or ("SKIPPED" if args.u1_iou is None else "MEASURED"),
            baselines_only=False if (mean is not None) else args.baselines_as_candidate,
            extra_candidate={
                "lofo_mean_iou": mean,
                "lofo_min_iou": mn,
                "status": "BASELINE_REFERENCE"
                if args.baselines_as_candidate
                else ("MEASURED" if train_complete else "PARTIAL"),
                "delta_lofo_mean": (float(mean) - BASELINE_LOFO_MEAN) if mean is not None else None,
                "delta_lofo_min": (float(mn) - BASELINE_LOFO_MIN) if mn is not None else None,
            },
        )
        # force north_star / kill from scorer
        board["kill_verdict"] = kill["verdict"]
        board["tier"] = kill["tier"]
        board["north_star_g1_met"] = kill["north_star_g1_met"]
        board["north_star_g2_met"] = kill["north_star_g2_met"]
        board["design_success_closed"] = kill["design_success_closed"]
        board["north_star"] = {
            "g1_met": kill["north_star_g1_met"],
            "g2_met": kill["north_star_g2_met"],
            "design_success_closed": kill["design_success_closed"],
        }
        if args.baselines_as_candidate:
            board["candidate"]["lofo_mean_iou"] = mean
            board["candidate"]["lofo_min_iou"] = mn
            board["candidate"]["delta_lofo_mean"] = 0.0
            board["candidate"]["delta_lofo_min"] = 0.0
            board["candidate"]["status"] = "BASELINE_REFERENCE"
            board["north_star"] = {
                "g1_met": False,
                "g2_met": False,
                "design_success_closed": False,
            }
            board["north_star_g1_met"] = False
            board["north_star_g2_met"] = False
            board["design_success_closed"] = False
        write_metrics_lift_board(
            board,
            repo / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_metrics_lift_latest.json",
        )

    print(
        json.dumps(
            {
                "ok": True,
                "verdict": kill["verdict"],
                "status": kill["status"],
                "tier": kill["tier"],
                "north_star_g1_met": kill["north_star_g1_met"],
                "north_star_g2_met": kill["north_star_g2_met"],
                "design_success_closed": kill["design_success_closed"],
                "profile": profile,
                "experiment_id": exp_id,
                "out": str(out),
                "lofo_mean": mean,
                "lofo_min": mn,
                "L1_pass": kill["checks"]["L1_lofo_mean_lift"]["pass"],
                "L2_pass": kill["checks"]["L2_weak_floor"]["L2_pass"],
                "L2_target_met": kill["checks"]["L2_weak_floor"]["L2_target_met"],
                "L4_status": kill["checks"]["L4_u1_no_silent_regress"]["status"],
                "field_ops_allow_ml_live_in_fusion": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
