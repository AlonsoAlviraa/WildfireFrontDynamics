#!/usr/bin/env python3
"""Diagnose Tobarra Head A IoU/conf (frozen production calibrator).

Usage::

    $env:PYTHONPATH = "."
    python scripts/diagnose_tobarra_head_a.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.w3_signal import diagnose_tobarra_head_a  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "tobarra_head_a_diagnose.json",
    )
    p.add_argument("--locked-thr", type=float, default=0.795)
    args = p.parse_args(argv)
    diag = diagnose_tobarra_head_a(args.repo.resolve(), locked_thr=float(args.locked_thr))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(diag, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(diag.get("ok")),
                "out": str(args.out),
                "mean_iou": diag.get("mean_iou"),
                "bimodal_hint": diag.get("bimodal_hint"),
                "abstain": (diag.get("reject_locked") or {}).get("abstain_rate"),
                "iou_acc": (diag.get("reject_locked") or {}).get("mean_iou_accepted"),
                "frac_iou_lt_0_1": diag.get("frac_iou_lt_0_1"),
            },
            indent=2,
        )
    )
    return 0 if diag.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
