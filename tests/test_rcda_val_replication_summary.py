from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.summarize_rcda_val_replications import (
    SCHEMA,
    summarize_replications,
)


def _summary(root: Path, seed: int, values: dict[str, float]) -> Path:
    checkpoint = root / f"candidate_seed{seed}_best.pt"
    checkpoint.write_bytes(f"seed={seed}".encode())
    path = root / f"summary_seed{seed}.json"
    path.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": [{"run_name": "candidate"}],
                "reports": [
                    {
                        "checkpoint": str(checkpoint),
                        "config": {"run_name": "candidate", "seed": seed},
                        "val": {
                            "selected": {
                                "per_event": {
                                    event: {"iou": value}
                                    for event, value in values.items()
                                }
                            }
                        },
                        "test_evaluated": False,
                        "test_used_for_selection": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_replication_summary_is_val_only_and_wfigs_ready(tmp_path: Path) -> None:
    paths = [
        _summary(tmp_path, 11, {"a": 0.1, "b": 0.3}),
        _summary(tmp_path, 29, {"a": 0.2, "b": 0.4}),
        _summary(tmp_path, 47, {"a": 0.3, "b": 0.5}),
    ]

    report = summarize_replications(
        paths,
        run_name="candidate",
        expected_seeds=(11, 29, 47),
        bootstrap_resamples=100,
        bootstrap_seed=7,
    )

    assert report["schema"] == SCHEMA
    assert report["selection_split"] == "val"
    assert report["test_evaluated"] is False
    assert report["validation"]["event_macro_iou_seed_mean"] == pytest.approx(0.3)
    assert report["counts"] == {"seeds": 3, "validation_events": 2}
    assert all(Path(row["local_checkpoint"]).is_file() for row in report["reports"])
    assert report["claims"]["ready_as_test_free_wfigs_adaptation_source"] is True


def test_replication_summary_rejects_unregistered_seed_order(tmp_path: Path) -> None:
    paths = [
        _summary(tmp_path, 29, {"a": 0.2}),
        _summary(tmp_path, 11, {"a": 0.1}),
        _summary(tmp_path, 47, {"a": 0.3}),
    ]
    with pytest.raises(ValueError, match="registered order"):
        summarize_replications(
            paths,
            run_name="candidate",
            expected_seeds=(11, 29, 47),
            bootstrap_resamples=10,
        )


def test_replication_summary_rejects_recipe_drift(tmp_path: Path) -> None:
    paths = [
        _summary(tmp_path, 11, {"a": 0.1}),
        _summary(tmp_path, 29, {"a": 0.2}),
        _summary(tmp_path, 47, {"a": 0.3}),
    ]
    changed = json.loads(paths[1].read_text(encoding="utf-8"))
    changed["reports"][0]["config"]["lr"] = 9e-4
    paths[1].write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="configurations differ"):
        summarize_replications(
            paths,
            run_name="candidate",
            expected_seeds=(11, 29, 47),
            bootstrap_resamples=10,
        )
