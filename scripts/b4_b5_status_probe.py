#!/usr/bin/env python3
"""B4/B5 status probe — calendar facts only, no grade invention.

Writes docs/B4_B5_STATUS.json from existing scorecards + outreach report when present.
Missing sources → null/unknown (not hardcoded grades).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "B4_B5_STATUS.json"

HELLIN_MD = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.md"
HELLIN_JSON = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.json"
TOBARRA_CANDIDATES = (
    ROOT / "docs" / "TOBARRA_TRACK_A_SCORECARD.json",
    ROOT / "docs" / "TOBARRA_SCORECARD.json",
    ROOT / "docs" / "GOLD_IF_E2E_VERIFICATION.json",
)
OUTREACH_CANDIDATES = (
    ROOT / "docs" / "OUTREACH_SEND_REPORT_20260810.md",
    ROOT / "docs" / "OUTREACH_SEND_REPORT.md",
)


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _hellin_grade() -> tuple[str | None, list[str]]:
    sources_missing: list[str] = []
    hellin_j: dict = {}
    if HELLIN_JSON.is_file():
        try:
            hellin_j = json.loads(HELLIN_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hellin_j = {}
    else:
        sources_missing.append("docs/HELLIN_TRACK_A_SCORECARD.json")

    grade = hellin_j.get("structural_grade") or hellin_j.get("grade")
    hellin_md = _read(HELLIN_MD)
    if not hellin_md:
        sources_missing.append("docs/HELLIN_TRACK_A_SCORECARD.md")
    elif not grade and "Structural grade" in hellin_md:
        m = re.search(r"Structural grade\s*\|\s*\*\*([A-Z])\*\*", hellin_md)
        if m:
            grade = m.group(1)
    if grade is not None:
        grade = str(grade).strip().upper() or None
    return grade, sources_missing


def _tobarra_grade() -> tuple[str | None, list[str]]:
    """Only emit Tobarra grade if an in-repo scorecard/evidence file exists."""
    missing: list[str] = []
    for path in TOBARRA_CANDIDATES:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Prefer explicit structural grade keys
        for key in ("structural_grade", "grade", "tobarra_grade", "tobarra_structural_grade"):
            if key in data and data[key]:
                return str(data[key]).strip().upper(), []
        # GOLD_IF style nested
        if isinstance(data.get("tobarra"), dict):
            g = data["tobarra"].get("structural_grade") or data["tobarra"].get("grade")
            if g:
                return str(g).strip().upper(), []
        if data.get("incident") == "tobarra" or "tobarra" in path.name.lower():
            g = data.get("structural_grade") or data.get("grade")
            if g:
                return str(g).strip().upper(), []
    missing.append("docs/*tobarra*scorecard* (none found with grade)")
    return None, missing


def _outreach_sent() -> tuple[dict | None, list[str]]:
    for path in OUTREACH_CANDIDATES:
        text = _read(path)
        if not text:
            continue
        m = re.search(r"(\d+)/(\d+)\s+SENT", text)
        if m:
            return {"sent": int(m.group(1)), "total": int(m.group(2)), "source": path.name}, []
    return None, ["docs/OUTREACH_SEND_REPORT*.md (no SENT line found)"]


def main() -> int:
    hellin_grade, hellin_missing = _hellin_grade()
    tobarra_grade, tobarra_missing = _tobarra_grade()
    sent, outreach_missing = _outreach_sent()

    sources_missing = sorted(set(hellin_missing + tobarra_missing + outreach_missing))

    # Count grade-A ops only from measured grades present in-repo
    n_grade_a = 0
    if tobarra_grade == "A":
        n_grade_a += 1
    if hellin_grade == "A":
        n_grade_a += 1

    hellin_eligible = hellin_grade == "A" if hellin_grade is not None else False

    payload = {
        "schema": "wfd_b4_b5_status_v1",
        "as_of_utc": datetime.now(UTC).isoformat(),
        "product_flags_touched": False,
        "sources_missing": sources_missing,
        "B4": {
            "id": "second_grade_A_ops",
            "status": "OPEN",
            "tobarra": tobarra_grade,  # null if no in-repo evidence
            "hellin_structural_grade": hellin_grade,  # null if scorecard missing
            "hellin_grade_a_eligible": hellin_eligible,
            "n_grade_a_ops": n_grade_a,
            "n_grade_a_ops_note": "count only from in-repo scorecards; not historical memory",
            "need": "second IF with grade A + in-band ROS/Vp without silent k-fit",
            "calendar": "docs/B4_B5_UNBLOCK_CALENDAR.md",
            "scorecard": "docs/HELLIN_TRACK_A_SCORECARD.md",
        },
        "B5": {
            "id": "o2_national_perimeter",
            "status": "BLOCKED_EXTERNAL",
            "official_national": False,
            "open_proxy_note": "CEMS/EFFIS dual-track only — not official cadastre",
            "outreach_batch": sent,  # null if send report not in tree
            "silence": ["CyL 4082 until ~2026-08-17 (calendar reminder; verify FOI log)"],
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
            "After new media: re-run score_hellin_track_a.py when pack exists",
            "Re-run this probe after scorecards are committed",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
