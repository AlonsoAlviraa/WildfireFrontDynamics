from __future__ import annotations

import json
from pathlib import Path

from scripts.plot_rcda_validation_evidence import build_figure


def _report(name: str, values: tuple[float, float]) -> dict:
    return {
        "config": {"run_name": name},
        "val": {
            "selected": {
                "per_event": {
                    "A": {"iou": values[0]},
                    "B": {"iou": values[1]},
                }
            }
        },
    }


def test_validation_figure_uses_only_paired_val_evidence(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    combined = tmp_path / "combined.json"
    output = tmp_path / "figure.svg"
    scorecard.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "ranking": [
                    {
                        "run_name": "leader",
                        "event_macro_iou": 0.3,
                        "event_bootstrap_95_ci": [0.2, 0.4],
                    },
                    {
                        "run_name": "runner",
                        "event_macro_iou": 0.2,
                        "event_bootstrap_95_ci": [0.1, 0.3],
                        "leader_minus_candidate_paired_delta": 0.1,
                        "leader_minus_candidate_bootstrap_95_ci": [0.05, 0.15],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    combined.write_text(
        json.dumps(
            {
                "selection_split": "val",
                "test_evaluated": False,
                "test_used_for_selection": False,
                "reports": [
                    _report("leader", (0.2, 0.4)),
                    _report("runner", (0.1, 0.3)),
                ],
            }
        ),
        encoding="utf-8",
    )

    assert build_figure(scorecard, combined, output) == output
    svg = output.read_text(encoding="utf-8")
    assert "TEST remains sealed" in svg
    assert "Paired validation fires" in svg
