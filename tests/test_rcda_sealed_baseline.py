from __future__ import annotations

import numpy as np

from scripts.eval_rcda_sealed_baseline import _confusion, _metrics, evaluate


def test_sealed_baseline_confusion() -> None:
    prediction = np.array([[1, 1], [0, 0]], dtype=bool)
    target = np.array([[1, 0], [1, 0]], dtype=bool)
    row = _confusion(prediction, target)
    assert row.tolist() == [1, 1, 1, 1]
    assert _metrics(row)["iou"] == 1 / 3


def test_baseline_selects_radius_on_event_macro_not_pooled_iou(tmp_path) -> None:
    # Two VAL events: pooled pixels prefer radius 1, but equal event weighting
    # prefers radius 2. The paper baseline must follow the latter.
    full = tmp_path / "full"
    dataset = full / "dataset"
    protocol = full / "protocol"
    for split in ("val", "test"):
        (dataset / split / "inputs").mkdir(parents=True)
        (dataset / split / "labels").mkdir(parents=True)
    samples = []
    for split in ("val", "test"):
        split_samples = []
        for uid, size in (("A", 32), ("B", 8)):
            inputs = np.zeros((12, size, size), dtype=np.float32)
            inputs[0, size // 2, size // 2] = 1.0
            label = inputs[0].copy()
            radius = 1 if uid == "A" else 2
            yy, xx = np.ogrid[:size, :size]
            label[(yy - size // 2) ** 2 + (xx - size // 2) ** 2 <= radius**2] = 1.0
            name = f"UID_FIRE_{uid}_2018-08-01.npy"
            np.save(dataset / split / "inputs" / name, inputs)
            np.save(dataset / split / "labels" / name, label)
            split_samples.append(
                {
                    "name": name,
                    "uid": f"UID_FIRE_{uid}",
                    "input": f"{split}/inputs/{name}",
                    "label": f"{split}/labels/{name}",
                }
            )
        (protocol).mkdir(parents=True, exist_ok=True)
        (protocol / f"{split}.json").write_text(
            __import__("json").dumps(
                {
                    "split": split,
                    "samples": split_samples,
                    "n_samples": len(split_samples),
                    "n_events": 2,
                }
            ),
            encoding="utf-8",
        )
        samples.extend(split_samples)
    result = evaluate(full, tmp_path / "baseline.json")
    assert result["validation"]["selection_metric"] == "event_macro_growth_iou"
    assert result["validation"]["test_used_for_selection"] is False
    rows = result["validation"]["results"]
    pooled_winner = max(rows, key=lambda radius: float(rows[radius]["iou"]))
    macro_winner = max(rows, key=lambda radius: float(rows[radius]["event_macro_iou"]))
    assert str(result["validation"]["selected_radius_pixels"]) == macro_winner
    assert macro_winner != pooled_winner
