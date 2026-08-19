#!/usr/bin/env python3
"""Apply the WFIGS internal-research policy to existing audit artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.wfigs_rights import (  # noqa: E402
    refresh_wfigs_rights_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = refresh_wfigs_rights_artifacts(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"WFIGS rights refreshed: events={report['event_count']} "
            f"files={len(report['updated'])} recomputed=False"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
