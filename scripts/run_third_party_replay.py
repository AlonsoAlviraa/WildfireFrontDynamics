#!/usr/bin/env python3
"""E3 — One-command forensic replay for third-party validation.

Exit codes
----------
0  — ``replay_ok`` is True (hashes + decision match)
2  — ``replay_ok`` is False (mismatch / tamper)
1  — usage / missing inputs / unexpected error

Limits (honesty)
----------------
Exit 0 means **internal forensic consistency** of a bundle (rebuild Decision
Card from ``replay_sources`` and match decision/output_hash). It is **not**
cryptographic authenticity or anti-pack-forgery: a fully controlled offline
bundle can rewrite metrics + expected_* + embedded reliability_gate together.
Live HTTP still rejects untrusted inline gates; live publish re-runs this-run
quality floor. See pack README and Reliability Report §7.

Usage (repo root, PYTHONPATH=.)
-------------------------------
::

    # From a forensic bundle (export-acta output or demo pack)
    python scripts/run_third_party_replay.py --bundle outputs/demo_third_party
    python scripts/run_third_party_replay.py --bundle outputs/forensic_demo

    # Explicit sources file
    python scripts/run_third_party_replay.py --sources path/to/replay_sources.json

    # Incident work-dir (uses work-dir/outbox)
    python scripts/run_third_party_replay.py --work-dir outputs/incidents/IF_x

Wraps ``wildfire_front.product.forensics`` (same logic as
``python -m wildfire_front replay-decide``).
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


def _run_replay(
    *,
    bundle: Path | None,
    sources: Path | None,
    work_dir: Path | None,
) -> dict[str, Any]:
    from wildfire_front.product.forensics import load_and_replay_bundle, replay_decision

    if sources is not None:
        src_path = Path(sources)
        if not src_path.is_file():
            raise FileNotFoundError(f"sources not found: {src_path}")
        src = json.loads(src_path.read_text(encoding="utf-8"))
        return replay_decision(src, base=ROOT)

    target = bundle
    if target is None and work_dir is not None:
        target = Path(work_dir) / "outbox"
    if target is None:
        raise SystemExit(
            "usage: run_third_party_replay.py requires --bundle, --sources, or --work-dir"
        )
    target = Path(target)
    if not target.is_dir():
        raise FileNotFoundError(f"bundle directory not found: {target}")
    return load_and_replay_bundle(target, base=ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forensic replay one-command (exit 0 iff replay_ok).",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Directory with replay_sources.json or fire_decision_card.json",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=None,
        help="Explicit replay_sources.json path",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Incident work-dir (uses outbox/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full forensic_replay_result_v1 JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print replay_ok: True/False",
    )
    args = parser.parse_args(argv)

    try:
        result = _run_replay(
            bundle=args.bundle,
            sources=args.sources,
            work_dir=args.work_dir,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except SystemExit as exc:
        msg = str(exc) if exc.args else "usage error"
        if msg and msg != "0":
            print(f"error: {msg}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    ok = bool(result.get("replay_ok"))
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif args.quiet:
        print(f"replay_ok: {ok}")
    else:
        print(f"replay_ok: {ok}")
        print(
            f"decision: expected={result.get('expected_decision')} "
            f"got={result.get('got_decision')} match={result.get('match_decision')}"
        )
        print(f"output_hash match: {result.get('match_output_hash')}")
        event_id = result.get("event_id")
        if event_id is None:
            card = result.get("card")
            if isinstance(card, dict):
                event_id = card.get("event_id")
        if event_id:
            print(f"event_id: {event_id}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
