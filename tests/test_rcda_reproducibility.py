from __future__ import annotations

import json
from pathlib import Path

from scripts.summarize_rcda_reproducibility import compare_reproducibility


def _summary(run_name: str, event_iou: float) -> dict:
    return {
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "ranking": [{"run_name": run_name}],
        "reports": [
            {
                "config": {"run_name": run_name},
                "test_evaluated": False,
                "test_used_for_selection": False,
                "val": {
                    "selected": {
                        "event_macro_iou": event_iou,
                        "threshold": 0.2,
                        "per_event": {"fire-1": {"iou": event_iou}},
                    }
                },
            }
        ],
    }


def test_compare_reproducibility_requires_exact_checkpoint_and_metrics(
    tmp_path: Path,
) -> None:
    first_summary = tmp_path / "first.json"
    rerun_summary = tmp_path / "rerun.json"
    first_summary.write_text(json.dumps(_summary("candidate", 0.3)), encoding="utf-8")
    rerun_summary.write_text(json.dumps(_summary("candidate", 0.3)), encoding="utf-8")
    first_checkpoint = tmp_path / "first.pt"
    rerun_checkpoint = tmp_path / "rerun.pt"
    first_checkpoint.write_bytes(b"same-checkpoint")
    rerun_checkpoint.write_bytes(b"same-checkpoint")

    report = compare_reproducibility(
        first_summary,
        rerun_summary,
        first_checkpoint,
        rerun_checkpoint,
        run_name="candidate",
    )

    assert report["reproducible"] is True
    assert report["checkpoint_exact"] is True
    assert report["metrics_exact"] is True
    assert report["test_evaluated"] is False
