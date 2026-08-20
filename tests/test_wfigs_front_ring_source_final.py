from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_wfigs_front_ring_source_final import validate_replication_source


def _source(tmp_path: Path) -> Path:
    reports = []
    for seed in (11, 29, 47):
        checkpoint = tmp_path / f"seed{seed}.pt"
        checkpoint.write_bytes(b"checkpoint")
        reports.append(
            {
                "config": {"seed": seed},
                "local_checkpoint": str(checkpoint),
                "threshold_selected_on": "val",
                "test_used_for_selection": False,
                "test_evaluated": False,
            }
        )
    path = tmp_path / "replications.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wfd_rcda_val_replication_summary_v1",
                "selection_split": "val",
                "test_used_for_selection": False,
                "test_evaluated": False,
                "claims": {"ready_as_test_free_wfigs_adaptation_source": True},
                "reports": reports,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_accepts_three_registered_test_free_replications(tmp_path: Path) -> None:
    source, seeds = validate_replication_source(_source(tmp_path))

    assert seeds == (11, 29, 47)
    assert source["selection_split"] == "val"


def test_rejects_replication_that_evaluated_test(tmp_path: Path) -> None:
    path = _source(tmp_path)
    source = json.loads(path.read_text(encoding="utf-8"))
    source["reports"][1]["test_evaluated"] = True
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="VAL/TEST boundary"):
        validate_replication_source(path)
