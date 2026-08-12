#!/usr/bin/env python3
"""Watch Kaggle spatial_v1 estrella LOFO kernel; download board when complete."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = "alonsoalviraaaa/wfd-spatial-v1-estrella-lofo"
OUT = ROOT / "outputs" / "kaggle_spatial_v1_estrella"


def status() -> str:
    r = subprocess.run(
        ["kaggle", "kernels", "status", KERNEL],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    poll = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(f"watching {KERNEL} every {poll}s → {OUT}", flush=True)
    while True:
        s = status()
        print(datetime.now(UTC).isoformat(), s.strip(), flush=True)
        low = s.lower()
        if "complete" in low or "error" in low or "cancel" in low:
            subprocess.run(
                ["kaggle", "kernels", "output", KERNEL, "-p", str(OUT)],
                check=False,
                timeout=600,
            )
            board = list(OUT.rglob("spatial_v1_estrella_lofo_board.json"))
            meta = {
                "kernel": KERNEL,
                "finished_utc": datetime.now(UTC).isoformat(),
                "status_line": s.strip(),
                "board_paths": [str(p) for p in board],
                "out": str(OUT),
            }
            (OUT / "watch_result.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            print(json.dumps(meta, indent=2), flush=True)
            return 0 if board else 1
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())
