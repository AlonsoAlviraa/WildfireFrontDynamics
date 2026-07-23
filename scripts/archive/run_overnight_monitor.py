#!/usr/bin/env python3
"""Monitor overnight mega kernel and auto-promote production if beaten."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# scripts/archive/<this file> → repo root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLUG = "alonsoalviraaaa/wildfire-overnight-mega-training"
OUT = PROJECT_ROOT / "kaggle_outputs_overnight"
PROD = PROJECT_ROOT / "models" / "production"
BASELINE_IOU = 0.2256
BASELINE_DELTA = 0.0756


def _status() -> str:
    r = subprocess.run(["kaggle", "kernels", "status", SLUG], capture_output=True, text=True)
    text = r.stdout or r.stderr
    if "COMPLETE" in text:
        return "complete"
    if "RUNNING" in text or "QUEUED" in text:
        return "running"
    if "ERROR" in text or "FAILED" in text:
        return "failed"
    return "unknown"


def _download() -> dict | None:
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kaggle", "kernels", "output", SLUG, "-p", str(OUT)], check=False)
    report = OUT / "overnight_report.json"
    if report.is_file():
        return json.loads(report.read_text(encoding="utf-8"))
    for p in OUT.rglob("overnight_report.json"):
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _maybe_promote(best: dict) -> None:
    iou = float(best.get("test_iou", 0))
    delta = float(best.get("improvement_vs_copy_iou", 0))
    version = best.get("version", "")
    if iou < BASELINE_IOU - 0.001 and delta <= BASELINE_DELTA:
        print(f"[monitor] No promotion: {version} IoU={iou:.4f}")
        return
    weights = OUT / "experiments" / version / "weights_pretrained_best.pt"
    if not weights.is_file():
        weights = next(OUT.rglob(f"**/experiments/{version}/weights_pretrained_best.pt"), None)
    if not weights or not Path(weights).is_file():
        print(f"[monitor] Weights missing for {version}")
        return
    PROD.mkdir(parents=True, exist_ok=True)
    shutil.copy2(weights, PROD / "weights_v21_best.pt")
    manifest = json.loads((PROD / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest["metrics"]["test_iou"] = iou
    manifest["metrics"]["improvement_vs_copy_iou"] = delta
    (PROD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "export_production_model.py")], check=True)
    print(f"[monitor] PROMOTED {version} to production (IoU={iou:.4f}, delta={delta:+.4f})")


def main() -> int:
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print(f"[monitor] Watching {SLUG} every {interval}s")
    while True:
        st = _status()
        print(f"[monitor] status={st}")
        if st == "complete":
            report = _download()
            if report:
                print(json.dumps(report, indent=2))
                _maybe_promote(report.get("best", {}))
            return 0
        if st == "failed":
            return 1
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
