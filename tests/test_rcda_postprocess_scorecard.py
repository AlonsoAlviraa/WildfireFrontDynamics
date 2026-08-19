from __future__ import annotations

import json
from pathlib import Path

from scripts.summarize_rcda_postprocess import build_postprocess_scorecard


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_postprocess_scorecard_uses_paired_val_events(tmp_path: Path) -> None:
    raw = tmp_path / "raw.json"
    decoded = tmp_path / "decoded.json"
    output = tmp_path / "scorecard.json"
    report = {
        "config": {"run_name": "candidate"},
        "threshold_selected_on": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "val": {
            "selected": {
                "per_event": {"A": {"iou": 0.1}, "B": {"iou": 0.3}}
            }
        },
    }
    _write(
        raw,
        {
            "selection_split": "val",
            "test_evaluated": False,
            "reports": [report],
        },
    )
    _write(
        decoded,
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "checkpoint_sha256": "abc",
            "best": {
                "threshold": 0.8,
                "dilation_radius_px": 1,
                "require_t0_connection": True,
                "per_event": {"A": {"iou": 0.2}, "B": {"iou": 0.4}},
            },
        },
    )

    result = build_postprocess_scorecard(
        raw,
        decoded,
        output,
        run_name="candidate",
        n_resamples=100,
    )

    assert result["events"] == 2
    assert round(result["paired_delta"], 6) == 0.1
    assert result["decoded_wins_event_fraction"] == 1.0
    assert result["test_evaluated"] is False
    assert output.is_file()
