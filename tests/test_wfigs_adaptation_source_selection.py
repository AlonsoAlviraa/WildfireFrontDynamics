from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.select_wfigs_adaptation_source import SCHEMA, freeze_wfigs_source


def _adaptation(path: Path, values: dict[str, float], train_events: int = 87) -> Path:
    path.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "counts": {
                    "train_events": train_events,
                    "validation_events": len(values),
                },
                "reports": [{"test_evaluated": False}] * 3,
                "ensemble": {
                    "members": 3,
                    "selected_threshold": 0.1,
                    "threshold_selected_on": "wfigs_validation",
                    "test_used_for_selection": False,
                    "test_evaluated": False,
                    "validation": {
                        "selected": {
                            "event_macro_iou": sum(values.values()) / len(values),
                            "per_event": {
                                event: {"iou": score}
                                for event, score in values.items()
                            },
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_wfigs_source_freeze_uses_only_paired_val_events(tmp_path: Path) -> None:
    frozen = freeze_wfigs_source(
        {
            "old": _adaptation(tmp_path / "old.json", {"a": 0.1, "b": 0.2}),
            "front": _adaptation(tmp_path / "front.json", {"a": 0.3, "b": 0.25}),
        },
        bootstrap_resamples=100,
        bootstrap_seed=3,
    )

    assert frozen["schema"] == SCHEMA
    assert frozen["winner"]["name"] == "front"
    assert frozen["selection_split"] == "wfigs_validation"
    assert frozen["prospective_test_evaluated"] is False
    comparison = frozen["paired_comparisons"][0]
    assert comparison["winner_minus_candidate_paired_delta"] == pytest.approx(0.125)
    assert comparison["events"] == 2


def test_wfigs_source_freeze_rejects_dataset_drift(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dataset counts"):
        freeze_wfigs_source(
            {
                "old": _adaptation(tmp_path / "old.json", {"a": 0.1}, 87),
                "front": _adaptation(tmp_path / "front.json", {"a": 0.2}, 88),
            },
            bootstrap_resamples=10,
        )
