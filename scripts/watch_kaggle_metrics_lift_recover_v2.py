#!/usr/bin/env python3
"""Poll Kaggle E_recover_v2 kernel until complete; download outputs."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNELS = [
    "alonsoalviraaaa/wfd-metrics-lift-lofo-recover-v2",
    "alonsoalviraaaa/wfd-metrics-lift-lofo-recover-v2-sealed",
]
OUT = ROOT / "outputs" / "kaggle_metrics_lift_recover_v2"


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
        print(s, "->", t[:200], flush=True)
        low = t.lower()
        if "403" not in t and "404" not in low and t:
            slug = s
            break
    if not slug:
        print("no kernel slug reachable", file=sys.stderr)
        return 2

    # up to ~5h at 60s (28 epochs x 3 folds on T4 can be long)
    for i in range(300):
        t = status(slug)
        print(f"[{i}] {t}", flush=True)
        low = t.lower()
        if "complete" in low or "success" in low:
            OUT.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["kaggle", "kernels", "output", slug, "-p", str(OUT)],
                check=False,
            )
            print("downloaded to", OUT, flush=True)
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
