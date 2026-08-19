"""Tests for the immutable pre-TEST RCDA decision record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.register_rcda_pretest_decisions import register_pretest_decisions

CODE_PATHS = (
    "wildfire_front/ml/rcda_sealed.py",
    "scripts/salvage_rcda_numeric_failure.py",
    "scripts/gcp_salvage_rcda_numeric_failure.sh",
    "scripts/run_rcda_kaggle_alt_continuation.py",
    "scripts/push_rcda_paper_stage2_kaggle.py",
    "scripts/run_rcda_gcp_paper_continuation.py",
    "scripts/analyze_rcda_paper_tuning.py",
    "scripts/tune_rcda_val_ensembles.py",
    "scripts/tune_rcda_val_postprocess.py",
    "scripts/summarize_rcda_postprocess.py",
    "scripts/push_rcda_paper_final_kaggle.py",
    "wildfire_front/ml/wfigs_domain_adapt.py",
    "wildfire_front/ml/wfigs_external_eval.py",
)


def _write(path: Path, value: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value) if isinstance(value, dict) else value,
        encoding="utf-8",
    )


def test_pretest_log_requires_isolated_evidence_and_absent_final(tmp_path: Path) -> None:
    work = tmp_path / "work"
    _write(
        work / "phase1/TUNING_SUMMARY.json",
        {
            "test_evaluated": False,
            "ranking": [{"run_name": "res", "val_event_macro_iou": 0.18}],
        },
    )
    _write(
        work / "PHASE1_VAL_ENSEMBLES.json",
        {
            "selection_split": "val",
            "test_evaluated": False,
            "test_used_for_selection": False,
            "decision": {"preregister_multi_model_ensemble": False},
        },
    )
    _write(
        work / "TRAIN_SAMPLER_AUDIT.json",
        {
            "analysis_split": "train",
            "validation_evaluated": False,
            "test_evaluated": False,
            "transition_geometry": {"samples_with_any_t0_loss": 0},
            "strategies": [
                {
                    "name": "default_size_event_half",
                    "event_probability_mass_cv": 0.647,
                },
                {"name": "uniform_events", "event_probability_mass_cv": 0.0},
            ],
        },
    )
    for path in CODE_PATHS:
        _write(tmp_path / path, f"source for {path}\n")
    output = work / "PRETEST_DECISION_LOG.json"
    report = register_pretest_decisions(
        work_root=work,
        output_path=output,
        repository_root=tmp_path,
    )
    assert report["new_candidate_test_evaluated"] is False
    assert report["evidence"]["uniform_event_mass_cv"] == 0.0
    assert len(report["code_sha256"]) == len(CODE_PATHS)
    assert output.is_file()

    _write(work / "FINAL_SUMMARY.json", {})
    with pytest.raises(ValueError, match="after final artifacts"):
        register_pretest_decisions(
            work_root=work,
            output_path=output,
            repository_root=tmp_path,
        )
