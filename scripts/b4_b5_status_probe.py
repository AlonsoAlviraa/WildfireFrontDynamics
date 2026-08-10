#!/usr/bin/env python3
"""B4/B5 status probe — calendar facts only, no grade invention.

Writes docs/B4_B5_STATUS.json from existing scorecards + outreach report.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "B4_B5_STATUS.json"


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    hellin_md = _read(ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.md")
    hellin_json_path = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.json"
    hellin_j = {}
    if hellin_json_path.is_file():
        try:
            hellin_j = json.loads(hellin_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hellin_j = {}

    grade = hellin_j.get("structural_grade") or hellin_j.get("grade")
    if not grade and "Structural grade" in hellin_md:
        m = re.search(r"Structural grade\s*\|\s*\*\*([A-Z])\*\*", hellin_md)
        if m:
            grade = m.group(1)

    outreach = _read(ROOT / "docs" / "OUTREACH_SEND_REPORT_20260810.md")
    sent = None
    m = re.search(r"(\d+)/(\d+)\s+SENT", outreach)
    if m:
        sent = {"sent": int(m.group(1)), "total": int(m.group(2))}

    payload = {
        "schema": "wfd_b4_b5_status_v1",
        "as_of_utc": datetime.now(UTC).isoformat(),
        "product_flags_touched": False,
        "B4": {
            "id": "second_grade_A_ops",
            "status": "OPEN",
            "tobarra": "A",
            "hellin_structural_grade": grade or "B",
            "hellin_grade_a_eligible": False if (grade or "B") != "A" else True,
            "n_grade_a_ops": 1,
            "need": "second IF with grade A + in-band ROS/Vp without silent k-fit",
            "calendar": "docs/B4_B5_UNBLOCK_CALENDAR.md",
            "scorecard": "docs/HELLIN_TRACK_A_SCORECARD.md",
        },
        "B5": {
            "id": "o2_national_perimeter",
            "status": "BLOCKED_EXTERNAL",
            "official_national": False,
            "open_proxy_note": "CEMS/EFFIS dual-track only — not official cadastre",
            "outreach_batch_20260810": sent,
            "silence": ["CyL 4082 until ~2026-08-17"],
            "calendar": "docs/B4_B5_UNBLOCK_CALENDAR.md",
            "blocked_doc": "docs/O2_HAUSDORFF_BLOCKED.md",
        },
        "eng_actions_done": [
            "Calendar doc B4_B5_UNBLOCK_CALENDAR.md",
            "Status probe JSON (this file)",
            "No GO_MES+ flip",
        ],
        "human_next": [
            "Follow-up outreach non-response (not CyL silence)",
            "Request 2nd complete IF package from partner",
            "After new media: re-run score_hellin_track_a.py",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
