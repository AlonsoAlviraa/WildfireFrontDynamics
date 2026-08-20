from __future__ import annotations

import json
from pathlib import Path

from scripts.run_wfigs_front_ring_source_pilot import localized_source_summary


def test_front_ring_source_is_localized_without_test(tmp_path: Path) -> None:
    checkpoint = tmp_path / "front_seed0_best.pt"
    checkpoint.write_bytes(b"checkpoint")
    summary = tmp_path / "TUNING_SUMMARY.json"
    summary.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": [{"run_name": "front"}],
                "reports": [
                    {
                        "checkpoint": "/kaggle/working/front_seed0_best.pt",
                        "config": {"run_name": "front", "seed": 0},
                        "test_used_for_selection": False,
                        "test_evaluated": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    localized = localized_source_summary(summary, run_name="front")

    assert localized["selection_split"] == "val"
    assert localized["test_evaluated"] is False
    assert localized["reports"][0]["local_checkpoint"] == str(checkpoint.resolve())
