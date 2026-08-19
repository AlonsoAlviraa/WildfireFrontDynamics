#!/usr/bin/env python3
"""Audit every local data file, logical dataset, and enriched WFIGS pair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.repo_data_audit import RepositoryDataAuditor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "docs/audits/mega_data_2026_08_18"
    )
    parser.add_argument("--hash-mode", choices=("none", "small", "all"), default="small")
    parser.add_argument(
        "--refresh-derived-only",
        action="store_true",
        help="refresh WFIGS/RCDA result sections while preserving the file inventory",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="reclassify the saved file inventory and refresh all derived sections",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    auditor = RepositoryDataAuditor(
        repo_root=ROOT,
        output_root=args.output_root,
        hash_mode=args.hash_mode,
    )
    if args.refresh_existing:
        report = auditor.refresh_existing()
    elif args.refresh_derived_only:
        report = auditor.refresh_derived()
    else:
        report = auditor.build()
    summary = {
        "files": report["files"],
        "dataset_count": len(report["datasets"]),
        "wfigs_pairs": report["wfigs_pairs"],
        "rcda_sealed_results": report["rcda_sealed_results"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
