"""Tests for post-freeze lab smoke gate."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.ml.lab_smoke import format_lab_smoke_human, run_lab_smoke

ROOT = Path(__file__).resolve().parents[1]


def test_run_lab_smoke_offline_no_pytest():
    payload = run_lab_smoke(ROOT, run_pytest=False)
    assert payload["schema"] == "wfd_ml_lab_smoke_v1"
    assert payload["rails"]["ml_product_go"] is True
    assert payload["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert payload["rails"]["iou_is_not_ros"] is True
    assert payload["summary"]["n_steps"] >= 5
    # Real repo should pass smoke after freeze
    if payload["freeze"]["lab_usable_freeze"]:
        assert payload["verdict"]["smoke_pass"] is True
    text = format_lab_smoke_human(payload)
    assert "smoke_pass" in text
    assert "OFF" in text


def test_smoke_script_writes(tmp_path, monkeypatch):
    # Use real repo for freeze inputs; write artifacts to tmp
    from scripts import run_lab_ml_loop_v34_smoke as mod

    rc = mod.main(
        [
            "--repo",
            str(ROOT),
            "--out-dir",
            str(tmp_path),
            "--no-md",
        ]
    )
    data = json.loads((tmp_path / "lab_loop_v34_smoke_latest.json").read_text(encoding="utf-8"))
    assert data["iteration"] == 8
    assert data["rails"]["ml_product_go"] is True
    latest = json.loads((tmp_path / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "8_smoke" in latest["iterations"]
    if data["smoke"]["verdict"]["smoke_pass"]:
        assert rc == 0
    else:
        assert rc == 2
