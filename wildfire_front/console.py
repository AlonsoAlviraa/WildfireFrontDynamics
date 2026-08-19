"""Small cross-platform helpers for robust human CLI output."""

from __future__ import annotations

import sys
from typing import TextIO


def configure_console_output(*streams: TextIO) -> None:
    """Prevent legacy Windows charmaps from crashing on Unicode reports.

    The active encoding is preserved so subprocess callers decode with the
    same locale. Unsupported decorative glyphs are replaced instead of
    aborting an otherwise successful command.
    """
    selected = streams or (sys.stdout, sys.stderr)
    for stream in selected:
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")
