#!/usr/bin/env python3
"""Poll Kaggle LOFO metrics grid kernel; download outputs."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUGS = [
    "alonsoalviraaaa/wfd-metrics-lift-lofo-grid-sealed",
    "alonsoalviraaaa/wfd-metrics-lift-lofo-grid",
]
OUT = ROOT / "outputs" / "kaggle_metrics_lift_grid"


def status(slug: str) -> str:
    r = subprocess.run(
        ["kaggle", "kernels", "status", slug],
        capture_output=True,
        text=True,
    )
    return ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    slug = None
    for s in SLUGS:
        t = status(s)
        print(s, "→", t[:160], flush=True)
        if "403" not in t and "404" not in t.lower() and "Cannot access" not in t:
            slug = s
            break
    if not slug:
        # try list recent
        print("no slug", file=sys.stderr)
        return 2
    for i in range(240):  # up to ~6h @ 90s
        t = status(slug)
        print(f"[{i}] {t}", flush=True)
        low = t.lower()
        if "complete" in low:
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run(["kaggle", "kernels", "output", slug, "-p", str(OUT)], check=False)
            print("downloaded", OUT)
            return 0
        if "error" in low or "failed" in low or "cancel" in low:
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run(["kaggle", "kernels", "output", slug, "-p", str(OUT)], check=False)
            return 1
        time.sleep(90)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
