#!/usr/bin/env python3
"""Copy an official cite file into a gitignored data/real_if/<fire_id>/cite/ dest.

Does **not** promote anchors. Missing cite / missing fire-id / unknown fire → exit 1.

python scripts/copy_cite_to_real_if.py --cite PATH --fire-id hellin_2024
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import score_if_weakness_board as board  # noqa: E402

from wildfire_front.console import configure_console_output  # noqa: E402

DEST_PARENT = ROOT / "data" / "real_if"


def known_fire_ids(root: Path) -> set[str]:
    ids: set[str] = set(board.TREE_MAP) | set(board.OPEN_PROXY_IDS) | set(
        board.PROCESS_ONE_FIRE_FALLBACK
    )
    ids.update(board.process_one_fire_ids())
    ids.update(board.NO_USE_REASONS)
    anchors = root / "data" / "infocam_anchors.json"
    if anchors.is_file():
        with contextlib.suppress(OSError, ValueError):
            ids.update(board.load_anchors(anchors)["anchors"].keys())
    return ids


def copy_cite(
    *,
    cite: Path,
    fire_id: str,
    dest_parent: Path,
    known: set[str],
) -> tuple[int, str]:
    if not fire_id or not str(fire_id).strip():
        return 1, "error: missing --fire-id"
    fid = str(fire_id).strip()
    if fid not in known:
        return 1, f"error: unknown fire_id {fid!r}"
    if not cite.is_file():
        return 1, f"error: missing cite file: {cite}"
    dest_dir = dest_parent / fid / "cite"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / cite.name
    shutil.copy2(cite, dest)
    return 0, f"copied; promote still requires H1–H7 + Alonso → {dest}"


def main(argv: list[str] | None = None) -> int:
    configure_console_output()
    parser = argparse.ArgumentParser(
        description="Copy cite bytes into gitignored data/real_if/<fire_id>/cite/ (no promote)."
    )
    parser.add_argument("--cite", default=None, help="Existing cite file (PDF/KMZ/…)")
    parser.add_argument("--fire-id", default=None, dest="fire_id")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dest-parent", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.cite:
        print("error: missing --cite PATH", file=sys.stderr)
        return 1
    if not args.fire_id:
        print("error: missing --fire-id", file=sys.stderr)
        return 1

    root = args.root.resolve()
    dest_parent = (args.dest_parent or (root / "data" / "real_if")).resolve()
    known = known_fire_ids(root)
    code, msg = copy_cite(
        cite=Path(args.cite),
        fire_id=str(args.fire_id),
        dest_parent=dest_parent,
        known=known,
    )
    if code != 0:
        print(msg, file=sys.stderr)
        return code
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
