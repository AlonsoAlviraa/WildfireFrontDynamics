from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_wfigs_source_pilot import compare_pilot_sources


def _adaptation(path: Path, seed: int, scores: dict[str, float]) -> None:
    path.write_text(
        json.dumps(
            {
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "reports": [
                    {
                        "config": {"seed": seed},
                        "threshold_selected_on": "wfigs_validation",
                        "test_evaluated": False,
                        "validation": {
                            "selected": {
                                "event_macro_iou": sum(scores.values()) / len(scores),
                                "per_event": {
                                    event: {"iou": score}
                                    for event, score in scores.items()
                                },
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_comparison_is_paired_stratified_and_identifier_free(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    reference = tmp_path / "reference.json"
    manifest = tmp_path / "validation.json"
    scores = {
        "secret-fire-alpha": 0.2,
        "secret-fire-bravo": 0.4,
        "secret-fire-charlie": 0.6,
    }
    _adaptation(candidate, 0, scores)
    _adaptation(reference, 47, {key: value - 0.1 for key, value in scores.items()})
    manifest.write_text(
        json.dumps(
            {
                "split": "validation",
                "samples": [
                    {
                        "event_id": event,
                        "horizon_hours": horizon,
                        "growth_pixels": growth,
                        "extent_pixels": 10,
                    }
                    for event, horizon, growth in (
                    ("secret-fire-alpha", 10, 1),
                    ("secret-fire-bravo", 20, 3),
                    ("secret-fire-charlie", 30, 8),
                    )
                ],
            }
        ),
        encoding="utf-8",
    )

    report = compare_pilot_sources(
        candidate,
        reference,
        manifest,
        candidate_seed=0,
        reference_seed=47,
        bootstrap_resamples=100,
    )

    assert report["paired"]["mean_delta"] > 0.09
    assert [row["events"] for row in report["by_horizon"]] == [1, 1, 1]
    assert report["claims"]["event_identifiers_exposed"] is False
    serialized = json.dumps(report)
    assert all(event not in serialized for event in scores)
