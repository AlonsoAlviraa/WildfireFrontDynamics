#!/usr/bin/env python3
"""Audit an assembled WFIGS ML tensor dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_dataset_audit import (  # noqa: E402
    audit_wfigs_tensor_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()
    report = audit_wfigs_tensor_dataset(args.dataset_root)
    print(json.dumps(report, indent=2))
    return 1 if args.fail_on_issues and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
