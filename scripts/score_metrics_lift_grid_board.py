#!/usr/bin/env python3
"""Score every config under a downloaded Kaggle LOFO grid board/root.

Usage::

    python scripts/score_metrics_lift_grid_board.py \\
        --grid-root outputs/kaggle_metrics_lift_grid/grid \\
        --profile E2
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--grid-root",
        type=Path,
        default=ROOT / "outputs" / "kaggle_metrics_lift_grid" / "grid",
    )
    p.add_argument(
        "--board",
        type=Path,
        default=ROOT / "outputs" / "kaggle_metrics_lift_grid" / "metrics_lift_grid_board.json",
    )
    p.add_argument("--profile", default="E2")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "grid_scores",
    )
    args = p.parse_args()

    configs: list[Path] = []
    if args.grid_root.is_dir():
        configs = sorted([d for d in args.grid_root.iterdir() if d.is_dir()])
    if not configs and args.board.is_file():
        board = json.loads(args.board.read_text(encoding="utf-8"))
        print("board leaderboard only (no fold trees):")
        print(json.dumps(board.get("leaderboard") or board, indent=2)[:4000])
        return 0
    if not configs:
        print("no grid configs found", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for cfg_dir in configs:
        # stage candidate root
        cand = args.out_dir / f"cand_{cfg_dir.name}"
        if cand.exists():
            shutil.rmtree(cand)
        cand.mkdir(parents=True)
        ok = 0
        for fold in CORE3:
            src = cfg_dir / fold
            if not src.is_dir():
                continue
            dst = cand / fold
            dst.mkdir(parents=True)
            for f in src.glob("*"):
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
            em = dst / "evaluation_metrics.json"
            if em.is_file():
                j = json.loads(em.read_text(encoding="utf-8"))
                if "model_iou" not in j:
                    j["model_iou"] = j.get("test_iou")
                    em.write_text(json.dumps(j, indent=2), encoding="utf-8")
                ok += 1
        if ok < 3:
            rows.append({"config": cfg_dir.name, "status": "incomplete", "n_folds": ok})
            continue
        exp = f"grid_{cfg_dir.name}"
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "score_metrics_lift_kill_criteria.py"),
            "--profile",
            args.profile,
            "--candidate-root",
            str(cand),
            "--experiment-id",
            exp,
            "--out",
            str(args.out_dir / f"{exp}_kill.json"),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        kill_path = args.out_dir / f"{exp}_kill.json"
        verdict = None
        mean = min_ = None
        if kill_path.is_file():
            k = json.loads(kill_path.read_text(encoding="utf-8"))
            verdict = k.get("verdict")
            mean = k.get("lofo_mean") or (k.get("candidate") or {}).get("lofo_mean_iou")
            min_ = k.get("lofo_min") or (k.get("candidate") or {}).get("lofo_min_iou")
            if mean is None and "checks" in k:
                l1 = (k.get("checks") or {}).get("L1_lofo_mean_lift") or {}
                mean = l1.get("value_mean")
        rows.append(
            {
                "config": cfg_dir.name,
                "verdict": verdict,
                "mean": mean,
                "min": min_,
                "scorer_rc": r.returncode,
            }
        )
        print(cfg_dir.name, verdict, mean, min_, flush=True)

    rows_sorted = sorted(
        rows,
        key=lambda x: (
            1 if x.get("verdict") == "KEEP" else 0,
            float(x["mean"] or -1),
            float(x["min"] or -1),
        ),
        reverse=True,
    )
    out = {
        "schema": "wfd_metrics_lift_grid_score_summary_v1",
        "profile": args.profile,
        "n": len(rows_sorted),
        "rows": rows_sorted,
    }
    out_path = args.out_dir / "grid_score_summary.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
