#!/usr/bin/env python3
"""Poll Kaggle kernel status until COMPLETE/ERROR. Prints DONE or FAILED."""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

SLUG = sys.argv[1] if len(sys.argv) > 1 else "alonsoalviraaaa/wildfire-front-training-v21"
HOURS = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
POLL_S = int(sys.argv[3]) if len(sys.argv) > 3 else 120


def status(slug: str) -> str:
    r = subprocess.run(
        ["kaggle", "kernels", "status", slug],
        capture_output=True,
        text=True,
        timeout=90,
    )
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if r.returncode != 0 and not out:
        raise RuntimeError(f"kaggle status rc={r.returncode}")
    return out


def main() -> int:
    deadline = datetime.now(UTC) + timedelta(hours=HOURS)
    transient = 0
    while datetime.now(UTC) < deadline:
        try:
            out = status(SLUG)
            transient = 0
        except Exception as exc:
            # Network blips (SSL/timeout) must not kill the watch.
            transient += 1
            if transient >= 30:
                print(f"FAILED: too many network errors: {exc}", flush=True)
                return 1
            time.sleep(min(POLL_S, 60))
            continue
        upper = out.upper()
        # Only emit terminal lines for the monitor tool
        if "COMPLETE" in upper and "ERROR" not in upper:
            print("DONE", flush=True)
            return 0
        if any(x in upper for x in ("CANCELLED", "CANCELED")):
            print(f"FAILED: {out}", flush=True)
            return 1
        # ERROR can appear in stack traces; only fail on status enum
        if "KERNELWORKERSTATUS.ERROR" in upper or 'STATUS "ERROR"' in upper:
            print(f"FAILED: {out}", flush=True)
            return 1
        time.sleep(POLL_S)
    print("FAILED: timeout waiting for kernel", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
