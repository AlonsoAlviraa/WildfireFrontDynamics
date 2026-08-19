#!/usr/bin/env python3
"""Bridge LATAM/AU EMSR source packs → product open_if (scorecard_pista_b).

Reads data/open_if/latam_au/<region>/<event_id>/ and writes
outputs/open_if/<slug>/ with scorecard_pista_b.json so:

  python -m wildfire_front decide --open-pack outputs/open_if/emsr500_perth

Exit codes:
  0 — all requested packs bridged
  1 — one or more packs failed (missing source, bad meta)
  2 — usage / no packs selected

  python scripts/bridge_latam_au_to_open_if.py
  python scripts/bridge_latam_au_to_open_if.py --event-id AU_EMSR500_PERTH
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    bridge_source_pack_to_open_if,
    default_product_out_dir,
    default_source_pack_dir,
    source_pack_ready,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bridge LATAM/AU packs to product open_if")
    ap.add_argument(
        "--event-id",
        action="append",
        dest="event_ids",
        default=None,
        help="Event id (repeatable). Default: both AU + CL packs.",
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
        help="Source root containing <region>/<event_id>/",
    )
    ap.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "outputs" / "open_if",
        help="Product open_if root (default: outputs/open_if)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary to stdout",
    )
    args = ap.parse_args(argv)

    event_ids = list(args.event_ids) if args.event_ids else list(EMSR_PACK_SPECS.keys())
    if not event_ids:
        print("error: no event ids", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    any_fail = False
    for eid in event_ids:
        if eid not in EMSR_PACK_SPECS:
            results.append({"event_id": eid, "ok": False, "error": "unknown_event_id"})
            any_fail = True
            continue
        src = default_source_pack_dir(ROOT, eid)
        # allow override data-root
        if args.data_root is not None:
            from wildfire_front.open_if.latam_au import pack_dir_for

            src = pack_dir_for(Path(args.data_root), EMSR_PACK_SPECS[eid])
        ready, reason = source_pack_ready(src)
        if not ready:
            results.append(
                {
                    "event_id": eid,
                    "ok": False,
                    "error": reason,
                    "source_pack": str(src),
                }
            )
            any_fail = True
            print(f"FAIL {eid}: {reason}", file=sys.stderr)
            continue
        out = Path(args.out_root) / (
            default_product_out_dir(ROOT, eid).name
        )
        try:
            info = bridge_source_pack_to_open_if(src, out, repo_root=ROOT)
            results.append({"event_id": eid, **info})
            print(f"OK {eid} → {info.get('out_pack')}")
        except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            results.append({"event_id": eid, "ok": False, "error": str(exc)})
            any_fail = True
            print(f"FAIL {eid}: {exc}", file=sys.stderr)

    summary = {
        "n": len(results),
        "ok": not any_fail,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
