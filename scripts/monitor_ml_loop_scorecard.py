#!/usr/bin/env python3
"""Print a line whenever ML_LOOP_3WAY_SCORECARD.json changes."""
from __future__ import annotations

import json
import time
from pathlib import Path

SCORE = Path("docs/ML_LOOP_3WAY_SCORECARD.json")


def snapshot() -> str:
    if not SCORE.is_file():
        return "missing scorecard"
    sc = json.loads(SCORE.read_text(encoding="utf-8"))
    n = len(sc.get("rounds") or [])
    c = sc.get("champion") or {}
    return (
        f"rounds={n} updated={sc.get('updated_at_utc')} "
        f"champion={c.get('name')} iou={c.get('model_iou')} "
        f"delta={c.get('improvement_vs_copy_iou')}"
    )


def main() -> None:
    last = ""
    while True:
        try:
            line = snapshot()
        except Exception as exc:  # noqa: BLE001
            line = f"error:{exc}"
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(90)


if __name__ == "__main__":
    main()
