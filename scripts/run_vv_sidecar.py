#!/usr/bin/env python3
"""Eng command: write minimal V&V scorecard stub under allowlisted work_dir.

Usage:
  python scripts/run_vv_sidecar.py --work-dir outputs/incidents/IF1
  python scripts/run_vv_sidecar.py --work-dir /abs/path --base-dir /abs/sandbox

Produces ``<work_dir>/vv_scorecard.json`` with schema ``wfd_vv_scorecard_stub_v1``.
Eng-only: does not claim field validation, GO_Q complete, or fusion ON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.product.decide_service import PathNotAllowedError  # noqa: E402
from wildfire_front.product.vv_sidecar import (  # noqa: E402
    VV_SCORECARD_FILENAME,
    run_vv_sidecar,
    scorecard_path,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write eng-only V&V scorecard stub (no field claims)")
    ap.add_argument(
        "--work-dir",
        required=True,
        type=Path,
        help="Incident / eng work directory (must be under allowlist)",
    )
    ap.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Allowlist base (untrusted sandbox root). Default: include repo root.",
    )
    ap.add_argument(
        "--event-id",
        default=None,
        help="Optional event id label on the stub",
    )
    ap.add_argument(
        "--notes",
        default=None,
        help="Optional free-text eng notes",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print full scorecard JSON to stdout",
    )
    ap.add_argument(
        "--no-repo-root",
        action="store_true",
        help="Fail closed: only paths under --base-dir (require --base-dir)",
    )
    args = ap.parse_args(argv)

    include_repo = not args.no_repo_root
    if args.no_repo_root and args.base_dir is None:
        print(
            "error: --no-repo-root requires --base-dir",
            file=sys.stderr,
        )
        return 2

    try:
        card = run_vv_sidecar(
            args.work_dir,
            base=args.base_dir,
            include_repo_root=include_repo,
            event_id=args.event_id,
            notes=args.notes,
        )
    except PathNotAllowedError as exc:
        print(f"error: path_not_allowed: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out = scorecard_path(Path(card["work_dir"]))
    if args.json:
        print(json.dumps(card, indent=2, ensure_ascii=False))
    else:
        print(f"status={card.get('status')} schema={card.get('schema')}")
        print(f"wrote={out}")
        print(f"file={VV_SCORECARD_FILENAME}")
        print("rails GO_Q=partial field_ops_fusion=OFF eng_stub=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
