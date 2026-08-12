"""Tests for lab loop iter4 generalization collector (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_lab_ml_loop_v34_generalization import collect_lofo_rows, summarize_rows


def test_collect_lofo_rows_from_repo():
    root = Path(__file__).resolve().parents[1]
    rows = collect_lofo_rows(root / "outputs" / "ml_eval" / "lofo_v1")
    # Repo may or may not have LOFO; if present, rows are well-formed
    for r in rows:
        assert "fold" in r
        if r.get("model_iou") is not None:
            assert 0.0 <= float(r["model_iou"]) <= 1.0


def test_summarize_rows_empty():
    assert summarize_rows([])["n_folds"] == 0


def test_summarize_rows_stats():
    rows = [
        {"model_iou": 0.7, "improvement_vs_copy_iou": 0.1},
        {"model_iou": 0.8, "improvement_vs_copy_iou": 0.2},
    ]
    s = summarize_rows(rows)
    assert s["n_folds"] == 2
    assert abs(s["model_iou_mean"] - 0.75) < 1e-9
    assert abs(s["spread_max_minus_min"] - 0.1) < 1e-9


def test_generalization_script_main(tmp_path, monkeypatch):
    # Minimal fake LOFO tree
    fold = tmp_path / "lofo" / "FAKE_FIRE"
    fold.mkdir(parents=True)
    (fold / "evaluation_metrics.json").write_text(
        json.dumps(
            {
                "model_iou": 0.7,
                "copy_baseline_iou": 0.5,
                "improvement_vs_copy_iou": 0.2,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    score = tmp_path / "score.json"
    score.write_text(
        json.dumps(
            {
                "primary": {"model_iou": 0.85},
                "uncertainty": {"ece_patch_conf": 0.15},
                "provenance": {"catalog_holdout_test_reference": {"test_iou": 0.89}},
            }
        ),
        encoding="utf-8",
    )
    # write reject stub for lock
    out.mkdir(parents=True)
    (out / "lab_loop_v34_reject_latest.json").write_text(
        json.dumps(
            {
                "tuned": {
                    "abstain_threshold": 0.8,
                    "test_metrics_tuned": {
                        "abstain_rate": 0.5,
                        "mean_iou_accepted": 0.95,
                    },
                },
                "verdict": {"lab_reject_surface_improved": True},
            }
        ),
        encoding="utf-8",
    )
    from scripts import run_lab_ml_loop_v34_generalization as mod

    rc = mod.main(
        [
            "--lofo-root",
            str(tmp_path / "lofo"),
            "--out-dir",
            str(out),
            "--scorecard",
            str(score),
            "--no-md",  # never clobber repo docs/ML_LOOP_ITERATIONS from unit tests
        ]
    )
    assert rc == 0
    gen = json.loads((out / "lab_loop_v34_generalization_latest.json").read_text(encoding="utf-8"))
    assert gen["lofo"]["summary"]["n_folds"] == 1
    assert gen["rails"]["ml_product_go"] is True
    assert gen["verdict"]["recommended_lab_surface"] == "iter1_reject_only"
    latest = json.loads((out / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "4_generalization" in latest["iterations"]
