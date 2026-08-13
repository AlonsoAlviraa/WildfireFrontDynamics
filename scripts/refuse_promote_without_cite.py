#!/usr/bin/env python3
"""W3-B: no cite = no promote.

Reads data/infocam_anchors.json. Exit 0 when no pending fire is marked
confirmed without cite. Exit 1 with ``error: no cite = no promote`` otherwise.

``--attempt-promote --fire-id hellin_2024`` always refuses on current SSOT.
Never writes anchors.

python scripts/refuse_promote_without_cite.py
python scripts/refuse_promote_without_cite.py --attempt-promote --fire-id hellin_2024
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.anchor_guard import can_promote_to_confirmed  # noqa: E402

TOBARRA_ID = "tobarra_20240802"
ERR = "error: no cite = no promote"


def _h1_zero(row: dict[str, Any]) -> bool:
    h1 = row.get("H1")
    if h1 is None:
        return False
    try:
        return int(h1) == 0
    except (TypeError, ValueError):
        return True


def _has_cite(row: dict[str, Any]) -> bool:
    ok, _reasons = can_promote_to_confirmed(row)
    if not ok:
        return False
    if _h1_zero(row):
        return False
    return True


def evaluate_anchors(doc: dict[str, Any]) -> tuple[int, str]:
    anchors = doc.get("anchors")
    if not isinstance(anchors, dict) or not anchors:
        return 1, "error: no usable anchors"
    for fid, row in anchors.items():
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").lower() != "confirmed":
            continue
        if fid == TOBARRA_ID:
            if not _has_cite(row):
                return 1, f"{ERR} ({fid})"
            continue
        return 1, ERR
    return 0, "ok: no pending fire marked confirmed without cite"


def evaluate_anchors_file(path: Path) -> tuple[int, str]:
    if not path.is_file():
        return 1, f"error: missing anchors file: {path}"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 1, f"error: {exc}"
    if not isinstance(doc, dict):
        return 1, "error: anchors file must be a JSON object"
    return evaluate_anchors(doc)


def attempt_promote(doc: dict[str, Any], fire_id: str) -> tuple[int, str]:
    if not fire_id or not str(fire_id).strip():
        return 1, "error: missing --fire-id"
    fid = str(fire_id).strip()
    anchors = doc.get("anchors") if isinstance(doc.get("anchors"), dict) else {}
    row = anchors.get(fid)
    if not isinstance(row, dict):
        return 1, f"error: unknown fire_id {fid!r}"
    # Never write. Hellín (and any non-cited pending fire) must refuse.
    if fid != TOBARRA_ID or not _has_cite(row):
        return 1, ERR
    return 1, ERR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse promote without official cite (no write)."
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        default=ROOT / "data" / "infocam_anchors.json",
    )
    parser.add_argument("--attempt-promote", action="store_true")
    parser.add_argument("--fire-id", default=None, dest="fire_id")
    args = parser.parse_args(argv)

    if not args.anchors.is_file():
        print(f"error: missing anchors file: {args.anchors}", file=sys.stderr)
        return 1
    try:
        doc = json.loads(args.anchors.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not isinstance(doc, dict):
        print("error: anchors file must be a JSON object", file=sys.stderr)
        return 1

    if args.attempt_promote:
        if not args.fire_id:
            print("error: missing --fire-id", file=sys.stderr)
            return 1
        code, msg = attempt_promote(doc, str(args.fire_id))
        print(msg, file=sys.stderr if code else sys.stdout)
        return code

    code, msg = evaluate_anchors(doc)
    if code != 0:
        print(msg, file=sys.stderr)
        return code
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
