from __future__ import annotations

import numpy as np

from scripts.audit_rcda_caldor_results import confusion, metrics, size_bin


def test_confusion_and_metrics() -> None:
    prediction = np.array([[1, 1], [0, 0]], dtype=bool)
    target = np.array([[1, 0], [1, 0]], dtype=bool)
    row = confusion(prediction, target)
    assert row.tolist() == [1, 1, 1, 1]
    result = metrics(row)
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["iou"] == 1 / 3


def test_size_bin_edges() -> None:
    assert size_bin(0) == "empty"
    assert size_bin(1) == "1_to_99"
    assert size_bin(99) == "1_to_99"
    assert size_bin(100) == "100_to_499"
    assert size_bin(500) == "500_to_1999"
    assert size_bin(2000) == "2000_plus"
