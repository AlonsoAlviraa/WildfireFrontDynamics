#!/usr/bin/env python3
"""Validate ml_scorecard_v1 JSON (protocol rails + no ROS leakage)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.scorecard_schema import scorecard_gates_pass  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path, help="Path to scorecard JSON")
    args = p.parse_args(argv)
    doc = json.loads(args.path.read_text(encoding="utf-8"))
    rep = scorecard_gates_pass(doc)
    print(json.dumps(rep, indent=2))
    return 0 if rep["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
