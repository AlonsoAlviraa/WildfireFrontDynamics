from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.assemble_wfigs_adaptation_replications import (
    validate_adaptation_replications,
)


def _summary(tmp_path: Path, seed: int, *, test_evaluated: bool = False) -> Path:
    checkpoint = tmp_path / f"seed{seed}.pt"
    checkpoint.write_bytes(b"checkpoint")
    path = tmp_path / f"summary{seed}.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_wfigs_domain_adaptation_v1",
                "configuration": {
                    "epochs": 12,
                    "batch_size": 4,
                    "num_workers": 0,
                    "source_seeds": [seed],
                },
                "counts": {"train_events": 87, "validation_events": 27, "reports": 1},
                "test_used_for_selection": False,
                "wfigs_test_loaded": False,
                "reports": [
                    {
                        "config": {"seed": seed, "model_name": "m"},
                        "checkpoint": str(checkpoint),
                        "threshold_selected_on": "wfigs_validation",
                        "test_evaluated": test_evaluated,
                        "validation": {
                            "selected": {"per_event": {"fire-a": {"iou": 0.2}}}
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_accepts_same_recipe_cohort_and_registered_seed_order(tmp_path: Path) -> None:
    paths = [_summary(tmp_path, seed) for seed in (11, 29, 47)]

    reports, adaptation, counts = validate_adaptation_replications(
        paths,
        expected_seeds=(11, 29, 47),
    )

    assert [row["config"]["seed"] for row in reports] == [11, 29, 47]
    assert "source_seeds" not in adaptation
    assert counts == {"train_events": 87, "validation_events": 27}


def test_rejects_any_replication_that_evaluated_test(tmp_path: Path) -> None:
    paths = [
        _summary(tmp_path, 11),
        _summary(tmp_path, 29, test_evaluated=True),
        _summary(tmp_path, 47),
    ]

    with pytest.raises(ValueError, match="VAL-only"):
        validate_adaptation_replications(paths, expected_seeds=(11, 29, 47))
