#!/usr/bin/env python3
"""Run LOFO fine-tune for each held-out source under lofo_v1/."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.unet_train import UNetTrainConfig, run_training  # noqa: E402

LOFO_ROOT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1"
INIT = ROOT / "models" / "production" / "weights_v21_best.pt"
OUT_ROOT = ROOT / "outputs" / "ml_eval" / "lofo_v1"


def run_fold(held: str, epochs: int = 12) -> dict:
    data = LOFO_ROOT / held
    out = OUT_ROOT / held
    out.mkdir(parents=True, exist_ok=True)
    if not (data / "train").is_dir():
        return {"held": held, "status": "missing_split"}
    cfg = UNetTrainConfig(
        epochs=epochs,
        batch_size=8,
        lr=3e-4,
        loss="composite",
        pos_weight=5.0,
        model="small",
        architecture="residual",
        target_mode="delta",
        change_loss_weight=5.0,
        weighted_sampler=True,
        patience=6,
        data_dir=str(data),
        output_dir=str(out),
        version_tag=f"lofo_{held}",
        early_stop_metric="improvement_vs_copy_iou",
        init_weights_path=str(INIT),
    )
    print(f"\n=== LOFO fold held={held} ===", flush=True)
    s = run_training(cfg)
    row = {
        "held": held,
        "status": "ok",
        "test_iou": s.get("test_iou"),
        "copy_baseline_iou": s.get("copy_baseline_iou"),
        "improvement_vs_copy_iou": s.get("improvement_vs_copy_iou"),
        "best_epoch": s.get("best_epoch"),
        "test_samples": s.get("test_samples"),
    }
    print(json.dumps(row, indent=2), flush=True)
    return row


def main() -> int:
    if not INIT.is_file():
        print("missing init weights", INIT, file=sys.stderr)
        return 1
    folds = sorted(p.name for p in LOFO_ROOT.iterdir() if p.is_dir() and (p / "train").is_dir())
    # Prefer not redoing tobarra if already done unless --all
    redo_tobarra = "--all" in sys.argv
    rows = []
    for held in folds:
        if held == "tobarra_20240802" and not redo_tobarra:
            prev = ROOT / "docs" / "V29_LOFO_TOBARRA_VERDICT.json"
            if prev.is_file():
                d = json.loads(prev.read_text(encoding="utf-8"))
                rows.append(
                    {
                        "held": held,
                        "status": "cached",
                        "test_iou": d.get("test_iou"),
                        "copy_baseline_iou": d.get("copy_baseline_iou"),
                        "improvement_vs_copy_iou": d.get("improvement_vs_copy_iou")
                        or d.get("delta"),
                        "best_epoch": d.get("best_epoch"),
                    }
                )
                print("skip tobarra (cached)", flush=True)
                continue
        rows.append(run_fold(held))

    deltas = [
        float(r["improvement_vs_copy_iou"])
        for r in rows
        if r.get("improvement_vs_copy_iou") is not None
    ]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol": "clm_lofo_v1_all_folds",
        "folds": rows,
        "summary": {
            "n_folds": len(rows),
            "mean_delta": sum(deltas) / len(deltas) if deltas else None,
            "min_delta": min(deltas) if deltas else None,
            "all_positive": all(d > 0 for d in deltas) if deltas else False,
        },
    }
    out = ROOT / "docs" / "CLM_LOFO_ALL_FOLDS_REPORT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
