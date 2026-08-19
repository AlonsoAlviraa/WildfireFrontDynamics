"""Relator — live fire dossier (constellation desk, no LLM).

Satellites + source board + regex fiscal + sealed ``decide`` judge.
No language-model tokens. ``wildfire_front`` is disclosed prior art.

Not tactical dispatch. GO_Q stays partial. FIRMS ≠ official burned area.
"""

from __future__ import annotations

__all__ = [
    "SCHEMA",
    "empty_board",
    "handle_event",
    "prosecute",
    "run_clock",
]

SCHEMA = "relator_source_board_v1"
TRACK = "The Taskmaster"
NOT_CLAIMS = (
    "not_tactical_dispatch",
    "firms_neq_official_burned",
    "go_q_partial",
    "no_llm",
    "iou_neq_ros",
)


def empty_board(*args, **kwargs):  # lazy re-export
    from .board import empty_board as _empty

    return _empty(*args, **kwargs)


def handle_event(*args, **kwargs):
    from .agent import handle_event as _handle

    return _handle(*args, **kwargs)


def prosecute(*args, **kwargs):
    from .fiscal import prosecute as _prosecute

    return _prosecute(*args, **kwargs)


def run_clock(*args, **kwargs):
    from .agent import run_clock as _clock

    return _clock(*args, **kwargs)
