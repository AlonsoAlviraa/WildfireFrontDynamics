from __future__ import annotations

import pytest

from scripts.run_wfigs_scaleup_paper_nightwatch import (
    _validate_preregistered_inventory,
    _validation_score,
)


def test_scaleup_score_accepts_only_val_isolated_single_seed() -> None:
    report = {
        "test_used_for_selection": False,
        "wfigs_test_loaded": False,
        "reports": [
            {
                "test_evaluated": False,
                "threshold_selected_on": "wfigs_validation",
                "validation": {"selected": {"event_macro_iou": 0.123}},
            }
        ],
    }

    assert _validation_score(report) == 0.123
    report["wfigs_test_loaded"] = True
    with pytest.raises(ValueError, match="validation-only"):
        _validation_score(report)


def test_prospective_inventory_must_match_preregistered_hashes() -> None:
    inventory = {
        "rows": [
            {
                "event_id": "event-a",
                "pair_id": "pair-a",
                "training_ready": True,
            },
            {
                "event_id": "event-b",
                "pair_id": "pair-b",
                "training_ready": False,
            },
        ]
    }
    preregistration = {
        "event_ids_sha256": "327331555e1384aa22c4cb6c9b2da411039ec7387ec326c6b3f8ef850ea25643",
        "pair_ids_sha256": "89aa56a1f1b2aa12bef51d8dc327e4212dcc1a785a06d18d1a0a333b96e50cde",
    }

    cohort = _validate_preregistered_inventory(preregistration, inventory)

    assert cohort["events_selected"] == 2
    assert cohort["events_materialized"] == 1
    inventory["rows"][1]["event_id"] = "changed"
    with pytest.raises(ValueError, match="differs from preregistration"):
        _validate_preregistered_inventory(preregistration, inventory)
