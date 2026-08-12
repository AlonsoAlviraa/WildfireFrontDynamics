#!/usr/bin/env python3
"""Poll Kaggle metrics-lift E3a kernel until complete; download outputs."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNELS = [
    "alonsoalviraaaa/wfd-metrics-lift-lofo-e3a-hellin-train-pool",
    "alonsoalviraaaa/wfd-metrics-lift-lofo-e3a",
]
OUT = ROOT / "outputs" / "kaggle_metrics_lift_e3a"


def status(slug: str) -> str:
    r = subprocess.run(
        ["kaggle", "kernels", "status", slug],
        capture_output=True,
        text=True,
    )
    text = (r.stdout or "") + (r.stderr or "")
    return text.strip()


def main() -> int:
    slug = None
    for s in KERNELS:
        t = status(s)
        print(s, "→", t[:200])
        if "403" not in t and "404" not in t.lower() and t:
            slug = s
            break
    if not slug:
        print("no kernel slug reachable", file=sys.stderr)
        return 2

    for i in range(180):  # up to ~3h at 60s
        t = status(slug)
        print(f"[{i}] {t}", flush=True)
        low = t.lower()
        if "complete" in low or "success" in low:
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["kaggle", "kernels", "output", slug, "-p", str(OUT)],
                check=False,
            )
            print("downloaded to", OUT)
            return 0
        if "error" in low or "cancel" in low or "failed" in low:
            print("FAILED", t, file=sys.stderr)
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["kaggle", "kernels", "output", slug, "-p", str(OUT)],
                check=False,
            )
            return 1
        time.sleep(60)
    print("timeout", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
