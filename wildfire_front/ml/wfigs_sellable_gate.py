"""Internal sellable-gate for WFIGS DEV event-macro growth IoU."""

from __future__ import annotations

from typing import Any

DILATED_COPY_EVENT_MACRO = 0.09915459429085662
SELLABLE_DELTA = 0.05
HISTORICAL_GATE = 0.1411784859726811
MIN_RECALL = 0.28


def wfigs_dev_is_sellable(
    selected: dict[str, Any],
    *,
    dilated_copy: float = DILATED_COPY_EVENT_MACRO,
) -> bool:
    """Return True when DEV growth skill is demo-grade and still TEST-sealed."""

    iou = float(selected["event_macro_iou"])
    recall = float(selected["recall"])
    vs_copy = iou - float(dilated_copy)
    return vs_copy >= SELLABLE_DELTA or (
        iou >= HISTORICAL_GATE and recall >= MIN_RECALL and vs_copy > 0.0
    )
