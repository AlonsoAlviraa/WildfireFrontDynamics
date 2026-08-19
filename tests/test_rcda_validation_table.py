from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.export_rcda_validation_table import export_validation_table


def test_export_validation_table_refuses_test_and_preserves_paired_ci(
    tmp_path: Path,
) -> None:
    scorecard = tmp_path / "scorecard.json"
    scorecard.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": [
                    {
                        "rank": 1,
                        "run_name": "leader",
                        "event_macro_iou": 0.2,
                        "event_bootstrap_95_ci": [0.1, 0.3],
                        "event_median_iou": 0.19,
                        "selected_threshold": 0.5,
                        "best_epoch": 3,
                    },
                    {
                        "rank": 2,
                        "run_name": "runner",
                        "event_macro_iou": 0.18,
                        "event_bootstrap_95_ci": [0.08, 0.28],
                        "event_median_iou": 0.17,
                        "selected_threshold": 0.4,
                        "best_epoch": 2,
                        "leader_minus_candidate_paired_delta": 0.02,
                        "leader_minus_candidate_bootstrap_95_ci": [0.01, 0.03],
                        "leader_wins_event_fraction": 0.6,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    csv_path, markdown_path = export_validation_table(scorecard, tmp_path / "out")

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[1]["leader_minus_candidate_ci_low"] == "0.01"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "TEST remains sealed" in markdown
    assert "+0.02000 [+0.01000, +0.03000]" in markdown
