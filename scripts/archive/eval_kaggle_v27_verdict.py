#!/usr/bin/env python3
"""Download v27 outputs if COMPLETE and write docs/archive/V27_TEMPORAL_VERDICT.json."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# scripts/archive/<this file> → repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
KERNEL = "alonsoalviraaaa/wildfire-front-training-v27-temporal-t2"
OUT_DIR = ROOT / "kaggle_outputs_v27"
VERDICT_PATH = ROOT / "docs" / "archive" / "V27_TEMPORAL_VERDICT.json"

V21_IOU = 0.2256
V21_DELTA = 0.0756
G1_IOU = 0.25
G1_DELTA = 0.09


def _status() -> str:
    r = subprocess.run(
        ["kaggle", "kernels", "status", KERNEL],
        capture_output=True,
        text=True,
    )
    return (r.stdout or r.stderr or "").strip()


def main() -> int:
    st = _status()
    print(st)
    if "COMPLETE" not in st.upper():
        payload = {
            "version": "v27_temporal_t2",
            "kernel": KERNEL,
            "status": "RUNNING_OR_PENDING",
            "raw_status": st,
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "verdict": None,
            "note": "Kernel not COMPLETE yet",
        }
        VERDICT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("Wrote pending", VERDICT_PATH)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", KERNEL, "-p", str(OUT_DIR)],
        check=False,
    )
    summary_path = OUT_DIR / "training_summary.json"
    metrics_path = OUT_DIR / "evaluation_metrics.json"
    test_iou = None
    delta = None
    copy_iou = None
    best_epoch = None
    if summary_path.is_file():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        best_epoch = s.get("best_epoch")
        tm = s.get("test_metrics") or {}
        # prefer top-level improvement if present
        if "improvement_vs_copy_iou" in tm:
            delta = float(tm["improvement_vs_copy_iou"])
        if "model_iou" in tm:
            test_iou = float(tm["model_iou"])
        if "copy_baseline_iou" in tm:
            copy_iou = float(tm["copy_baseline_iou"])
        th = tm.get("thresh_0.5") or {}
        if test_iou is None and "model_iou" in th:
            test_iou = float(th["model_iou"])
        if delta is None and "improvement_vs_copy_iou" in th:
            delta = float(th["improvement_vs_copy_iou"])
        if copy_iou is None and "copy_baseline_iou" in th:
            copy_iou = float(th["copy_baseline_iou"])
    if metrics_path.is_file() and (test_iou is None or delta is None):
        m = json.loads(metrics_path.read_text(encoding="utf-8"))
        if test_iou is None:
            test_iou = float(m.get("model_iou") or (m.get("thresh_0.5") or {}).get("model_iou") or 0)
        if delta is None:
            delta = float(
                m.get("improvement_vs_copy_iou")
                or (m.get("thresh_0.5") or {}).get("improvement_vs_copy_iou")
                or 0
            )
        if copy_iou is None:
            copy_iou = float(
                m.get("copy_baseline_iou")
                or (m.get("thresh_0.5") or {}).get("copy_baseline_iou")
                or 0.15
            )

    if test_iou is None or delta is None:
        print("Could not parse metrics", file=sys.stderr)
        return 1

    beats_v21 = (test_iou >= V21_IOU) and (delta >= V21_DELTA)
    g1 = (test_iou >= G1_IOU) and (delta >= G1_DELTA)
    if g1:
        verdict = "PROMOTE_CANDIDATE_G1"
        nxt = "freeze G1; optional cross-eval CLM"
    elif beats_v21:
        verdict = "BEATS_V21_BUT_NOT_G1"
        nxt = "consider T=3 only if delta margin > 0.005; else document plateau"
    else:
        # T=3 only if not much worse than v21
        if test_iou >= V21_IOU - 0.005 or delta >= V21_DELTA - 0.005:
            verdict = "NO_PROMOTE"
            nxt = "optional v27b T=3 once; if fail KILL G1 temporal+features"
        else:
            verdict = "NO_PROMOTE"
            nxt = "KILL G1 temporal+features; pivot LOFO CLM transfer"

    payload = {
        "version": "v27_temporal_t2",
        "kernel": KERNEL,
        "status": "COMPLETE",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "test_iou": round(test_iou, 4),
        "copy_baseline_iou": round(copy_iou, 4) if copy_iou is not None else None,
        "improvement_vs_copy_iou": round(delta, 4),
        "best_epoch": best_epoch,
        "vs_v21": {
            "v21_iou": V21_IOU,
            "v21_delta": V21_DELTA,
            "iou_diff": round(test_iou - V21_IOU, 4),
            "delta_diff": round(delta - V21_DELTA, 4),
            "beats_v21": beats_v21,
        },
        "G1": g1,
        "verdict": verdict,
        "next": nxt,
    }
    VERDICT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print("Wrote", VERDICT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
