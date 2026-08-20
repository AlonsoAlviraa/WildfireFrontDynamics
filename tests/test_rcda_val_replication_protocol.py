from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.register_rcda_val_replications import (
    SCHEMA,
    build_replication_protocol,
)
from scripts.run_rcda_kaggle_alt_continuation import single_seed_run_source


def test_val_replication_protocol_is_test_free_and_seed_fixed(tmp_path: Path) -> None:
    checkpoint = tmp_path / "source.pt"
    checkpoint.write_bytes(b"validation checkpoint")
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": [
                    {
                        "run_name": "resunet_multitask_front_ring_v1",
                        "val_event_macro_iou": 0.22,
                        "selected_threshold": 0.7,
                    }
                ],
                "reports": [
                    {
                        "checkpoint": str(checkpoint),
                        "config": {
                            "run_name": "resunet_multitask_front_ring_v1",
                            "seed": 0,
                        },
                        "test_evaluated": False,
                        "test_used_for_selection": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner_paths = {}
    for seed in (11, 29, 47):
        runner = tmp_path / f"seed{seed}.py"
        runner.write_text(
            single_seed_run_source("resunet_multitask_front_ring_v1", seed),
            encoding="utf-8",
        )
        runner_paths[seed] = runner

    protocol = build_replication_protocol(
        summary,
        run_name="resunet_multitask_front_ring_v1",
        seeds=(11, 29, 47),
        kernel_template="owner/front-ring-seed{seed}",
        runner_paths=runner_paths,
    )

    assert protocol["schema"] == SCHEMA
    assert protocol["selection_split"] == "val"
    assert protocol["test_evaluated"] is False
    assert [row["seed"] for row in protocol["replications"]] == [11, 29, 47]
    assert len({row["runner_sha256"] for row in protocol["replications"]}) == 3
    assert protocol["claims"]["does_not_restore_historical_test_sealing"] is True


def test_val_replication_protocol_requires_three_unique_seeds(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="three unique"):
        build_replication_protocol(
            tmp_path / "unused.json",
            run_name="candidate",
            seeds=(11, 11, 29),
            kernel_template="owner/seed{seed}",
            runner_paths={},
        )
