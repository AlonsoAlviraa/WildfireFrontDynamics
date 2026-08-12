"""Tests for lab teach-cases pack + loop iter5 runner (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.ml.lab_teach_cases import (
    build_teach_cases_pack,
    filter_fail_rows,
    format_teach_cases_human,
    summarize_fail_cases,
)

ROOT = Path(__file__).resolve().parents[1]


def test_summarize_fail_cases_buckets():
    fail = {
        "threshold": 0.8,
        "rows": [
            {"bucket": "accepted_low_iou", "index": 1, "conf": 0.8, "iou": 0.4},
            {"bucket": "rejected_high_iou", "index": 2, "conf": 0.7, "iou": 0.99},
            {"bucket": "accepted_low_iou", "index": 3, "conf": 0.81, "iou": 0.5},
        ],
    }
    s = summarize_fail_cases(fail)
    assert s["present"] is True
    assert s["n_rows"] == 3
    assert s["buckets"]["accepted_low_iou"] == 2
    assert s["buckets"]["rejected_high_iou"] == 1
    assert len(s["examples"]) == 2


def test_summarize_empty():
    assert summarize_fail_cases(None)["present"] is False
    assert summarize_fail_cases({})["n_rows"] == 0


def test_build_pack_from_repo():
    pack = build_teach_cases_pack(ROOT)
    assert pack["schema"] == "wfd_ml_teach_cases_v1"
    assert pack["rails"]["ml_product_go"] is True
    assert pack["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert pack["rails"]["iou_is_not_ros"] is True
    # Repo has fail cases from prior loop
    assert pack["fail_cases"]["present"] is True
    assert pack["fail_cases"]["n_rows"] >= 1
    text = format_teach_cases_human(pack)
    assert "ml_product_go" in text
    assert "OFF" in text
    assert "Fail-case" in text or "fail" in text.lower()


def test_filter_fail_rows():
    fail = {
        "rows": [
            {"bucket": "a", "index": 1},
            {"bucket": "b", "index": 2},
            {"bucket": "a", "index": 3},
        ]
    }
    assert len(filter_fail_rows(fail, bucket="a", limit=10)) == 2
    assert len(filter_fail_rows(fail, bucket="a", limit=1)) == 1


def test_teach_cases_script_isolated(tmp_path):
    # Minimal repo-like tree
    loop = tmp_path / "outputs" / "ml_eval" / "lab_loop"
    loop.mkdir(parents=True)
    (loop / "lab_loop_v34_fail_cases_test.json").write_text(
        json.dumps(
            {
                "threshold": 0.8,
                "rows": [
                    {
                        "bucket": "accepted_low_iou",
                        "index": 1,
                        "conf": 0.8,
                        "iou": 0.4,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (loop / "lab_loop_v34_latest.json").write_text(
        json.dumps(
            {
                "iterations": {"4_generalization": "x"},
                "summary": {
                    "iter1_reject_improved": True,
                    "iter4_generalization_table": True,
                    "recommended_lab_surface": "iter1_reject_only",
                    "reject": {
                        "thr": 0.8,
                        "test_abstain_rate": 0.5,
                        "test_iou_accepted": 0.95,
                    },
                    "lofo": {"n_folds": 3, "model_iou_mean": 0.75},
                    "holdout_u1_iou": 0.85,
                    "holdout_u1_ece": 0.15,
                    "stop_ece_thrash_on_same_test": True,
                },
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    from scripts import run_lab_ml_loop_v34_teach_cases as mod

    rc = mod.main(
        [
            "--repo",
            str(tmp_path),
            "--out-dir",
            str(out),
            "--no-md",
        ]
    )
    assert rc == 0
    teach = json.loads((out / "lab_loop_v34_teach_cases_latest.json").read_text(encoding="utf-8"))
    assert teach["iteration"] == 5
    assert teach["rails"]["ml_product_go"] is True
    assert teach["verdict"]["fail_cases_productized"] is True
    latest = json.loads((out / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "5_teach_cases" in latest["iterations"]
    assert latest["summary"]["iter5_teach_cases_productized"] is True
