#!/usr/bin/env python3
"""Download v27b T=3 outputs and write docs/V27B_TEMPORAL_VERDICT.json; KILL G1 if fail."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = "alonsoalviraaaa/wildfire-front-training-v27b-temporal-t3"
OUT_DIR = ROOT / "kaggle_outputs_v27b"
VERDICT = ROOT / "docs" / "V27B_TEMPORAL_VERDICT.json"
KILL = ROOT / "docs" / "G1_KILL_FEATURES_TEMPORAL.json"

V21_IOU, V21_DELTA = 0.2256, 0.0756
G1_IOU, G1_DELTA = 0.25, 0.09


def main() -> int:
    st = subprocess.run(
        ["kaggle", "kernels", "status", KERNEL], capture_output=True, text=True
    )
    status_line = (st.stdout or st.stderr or "").strip()
    print(status_line)
    if "COMPLETE" not in status_line.upper():
        VERDICT.write_text(
            json.dumps(
                {
                    "status": "PENDING",
                    "raw": status_line,
                    "checked_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", KERNEL, "-p", str(OUT_DIR)], check=False
    )
    summary = json.loads((OUT_DIR / "training_summary.json").read_text(encoding="utf-8"))
    tm = summary.get("test_metrics") or {}
    th = tm.get("thresh_0.5") or {}
    test_iou = float(tm.get("model_iou") or th.get("model_iou") or 0)
    delta = float(tm.get("improvement_vs_copy_iou") or th.get("improvement_vs_copy_iou") or 0)
    copy = float(tm.get("copy_baseline_iou") or th.get("copy_baseline_iou") or 0.15)
    g1 = test_iou >= G1_IOU and delta >= G1_DELTA
    beats = test_iou >= V21_IOU and delta >= V21_DELTA
    if g1:
        verdict, nxt = "PROMOTE_CANDIDATE_G1", "freeze G1"
        kill = False
    elif beats:
        verdict, nxt = "BEATS_V21_NOT_G1", "plateau; KILL further G1 temporal/features"
        kill = True
    else:
        verdict, nxt = "NO_PROMOTE", "KILL G1 features+temporal rails"
        kill = True

    payload = {
        "version": "v27b_temporal_t3",
        "kernel": KERNEL,
        "status": "COMPLETE",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "test_iou": round(test_iou, 4),
        "copy_baseline_iou": round(copy, 4),
        "improvement_vs_copy_iou": round(delta, 4),
        "best_epoch": summary.get("best_epoch"),
        "vs_v21": {
            "iou_diff": round(test_iou - V21_IOU, 4),
            "delta_diff": round(delta - V21_DELTA, 4),
            "beats_v21": beats,
        },
        "G1": g1,
        "verdict": verdict,
        "next": nxt,
    }
    VERDICT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if kill:
        KILL.write_text(
            json.dumps(
                {
                    "gate": "G1",
                    "status": "KILLED",
                    "reason": "features (v25/v26) and temporal (v27/v27b) failed to beat v21/G1",
                    "production_ndws": "ndws_v21 frozen",
                    "checked_at_utc": datetime.now(UTC).isoformat(),
                    "evidence": {
                        "v25": "NO_PROMOTE",
                        "v26": "NO_PROMOTE IoU 0.221",
                        "v27": "NO_PROMOTE IoU 0.2253",
                        "v27b": payload,
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("Wrote", KILL)
    print(json.dumps(payload, indent=2))
    print("Wrote", VERDICT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
