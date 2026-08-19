"""VAL-only event-bootstrap scorecard tests."""

from __future__ import annotations

import json

import pytest

from scripts.summarize_rcda_validation import build_validation_scorecard


def _report(name: str, first: float, second: float) -> dict:
    return {
        "config": {"run_name": name},
        "best_epoch": 3,
        "selected_threshold": 0.5,
        "threshold_selected_on": "val",
        "test_used_for_selection": False,
        "test_evaluated": False,
        "val": {
            "selected": {
                "per_event": {
                    "fire-a": {"iou": first},
                    "fire-b": {"iou": second},
                }
            }
        },
    }


def test_validation_scorecard_uses_paired_events_and_keeps_test_sealed(tmp_path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "reports": [_report("leader", 0.4, 0.5), _report("other", 0.2, 0.3)],
            }
        ),
        encoding="utf-8",
    )
    result = build_validation_scorecard(
        [source], tmp_path / "scorecard.json", n_resamples=1_000
    )
    assert result["leader"] == "leader"
    assert result["events"] == 2
    assert result["test_evaluated"] is False
    assert result["ranking"][1]["leader_minus_candidate_paired_delta"] == pytest.approx(0.2)
    assert result["ranking"][1]["leader_wins_event_fraction"] == 1.0


def test_validation_scorecard_rejects_any_test_evaluation(tmp_path) -> None:
    leaky = _report("leaky", 0.9, 0.9)
    leaky["test_evaluated"] = True
    source = tmp_path / "summary.json"
    source.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_paper_tune_v1",
                "selection_split": "val",
                "test_evaluated": False,
                "reports": [leaky, _report("clean", 0.2, 0.3)],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="TEST isolation"):
        build_validation_scorecard([source], tmp_path / "scorecard.json")
