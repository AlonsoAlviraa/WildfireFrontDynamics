#!/usr/bin/env python3
"""W3 fire inventory: in-pack sources + external READY/PARTIAL/BLOCKED.

Usage::

    $env:PYTHONPATH = "."
    python scripts/inventory_w3_new_signal.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.w3_signal import inventory_w3_fires  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lab_loop" / "w3_fire_inventory.json",
    )
    args = p.parse_args(argv)
    inv = inventory_w3_fires(args.repo.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "summary": inv["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
