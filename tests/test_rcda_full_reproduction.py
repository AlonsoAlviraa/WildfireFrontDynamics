from __future__ import annotations

import numpy as np

from scripts.reproduce_rcda_full import _confusion, _metrics, _uid


def test_rcda_confusion_and_metrics_match_growth_task() -> None:
    probability = np.array([[0.9, 0.6], [0.4, 0.1]], dtype=np.float32)
    target = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    confusion = _confusion(probability, target, 0.5)
    assert confusion.tolist() == [1, 1, 1, 1]
    metrics = _metrics(confusion)
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["iou"] == 1 / 3


def test_rcda_threshold_matches_upstream_greater_or_equal() -> None:
    probability = np.array([[0.5]], dtype=np.float32)
    target = np.array([[1]], dtype=np.uint8)
    assert _confusion(probability, target, 0.5).tolist() == [1, 0, 0, 0]


def test_uid_parser_keeps_full_event_identifier() -> None:
    assert _uid("UID_FIRE_656_2018-09-01.npy") == "UID_FIRE_656"
