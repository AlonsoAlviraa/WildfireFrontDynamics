"""Minimal V&V scorecard sidecar — real allowlisted paths (Agent B PR2)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from wildfire_front.product.decide_service import PathNotAllowedError
from wildfire_front.product.vv_sidecar import (
    DEFAULT_RAILS,
    NON_CLAIMS,
    VV_SCORECARD_FILENAME,
    VV_SCORECARD_SCHEMA,
    VV_STATUS_ENG_STUB,
    load_vv_scorecard,
    run_vv_sidecar,
    scorecard_path,
    write_vv_scorecard,
)

ROOT = Path(__file__).resolve().parents[1]


def test_write_read_stub_round_trip(tmp_path: Path):
    work = tmp_path / "incident_vv"
    work.mkdir()
    card = run_vv_sidecar(
        work,
        base=tmp_path,
        include_repo_root=False,
        event_id="IF_VV_1",
    )
    assert card["schema"] == VV_SCORECARD_SCHEMA
    assert card["status"] == VV_STATUS_ENG_STUB
    assert card["eng_stub"] is True
    assert card["event_id"] == "IF_VV_1"
    assert card["rails"]["GO_Q"] == "partial"
    assert card["rails"]["field_ops_fusion"] == "OFF"

    path = scorecard_path(work)
    assert path.is_file()
    assert path.name == VV_SCORECARD_FILENAME
    assert path.stat().st_size > 0
    assert path.resolve().is_relative_to(work.resolve())

    loaded = load_vv_scorecard(work, base=tmp_path, include_repo_root=False)
    assert loaded["schema"] == VV_SCORECARD_SCHEMA
    assert loaded["eng_stub"] is True
    assert loaded["status"] == VV_STATUS_ENG_STUB
    assert loaded["rails"]["GO_Q"] == DEFAULT_RAILS["GO_Q"]


def test_non_claims_and_no_field_metrics(tmp_path: Path):
    work = tmp_path / "nc"
    work.mkdir()
    card = write_vv_scorecard(work, base=tmp_path, include_repo_root=False)
    for claim in NON_CLAIMS:
        assert claim in card["non_claims"], claim
    metrics = card["metrics"]
    assert metrics.get("field_iou") is None
    assert metrics.get("field_ros") is None
    assert metrics.get("field_grade") is None
    raw = (work / VV_SCORECARD_FILENAME).read_text(encoding="utf-8").lower()
    assert "go_q complete" not in raw
    assert '"field_ops_fusion": "on"' not in raw
    assert "tactical dispatch" not in raw or "not" in raw
    # Must not claim field-validated true
    assert "field-validated" not in raw or "not" in raw
    assert card["rails"]["field_ops_fusion"] == "OFF"
    assert card["rails"]["GO_Q"] != "true"


def test_path_outside_allowlist_rejected(tmp_path: Path):
    work = tmp_path / "ok"
    work.mkdir()
    outside = tmp_path.parent / f"outside_vv_{tmp_path.name}"
    outside.mkdir(exist_ok=True)
    with pytest.raises(PathNotAllowedError):
        run_vv_sidecar(outside, base=tmp_path, include_repo_root=False)
    with pytest.raises(PathNotAllowedError):
        load_vv_scorecard(outside, base=tmp_path, include_repo_root=False)
    evil = work / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathNotAllowedError):
        run_vv_sidecar(evil, base=tmp_path, include_repo_root=False)


def test_script_entry_writes_scorecard(tmp_path: Path):
    """Drive documented eng command path (scripts/run_vv_sidecar.py)."""
    work = tmp_path / "cli_incident"
    work.mkdir()
    script = ROOT / "scripts" / "run_vv_sidecar.py"
    assert script.is_file()
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--work-dir",
            str(work),
            "--base-dir",
            str(tmp_path),
            "--no-repo-root",
            "--event-id",
            "script_path",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "eng_stub" in proc.stdout or "status=eng_stub" in proc.stdout
    out = work / VV_SCORECARD_FILENAME
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == VV_SCORECARD_SCHEMA
    assert data["eng_stub"] is True
    assert data["event_id"] == "script_path"
    assert data["rails"]["GO_Q"] == "partial"
    assert data["rails"]["field_ops_fusion"] == "OFF"


def test_script_rejects_outside_path(tmp_path: Path):
    outside = tmp_path.parent / f"outside_script_{tmp_path.name}"
    outside.mkdir(exist_ok=True)
    script = ROOT / "scripts" / "run_vv_sidecar.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--work-dir",
            str(outside),
            "--base-dir",
            str(tmp_path),
            "--no-repo-root",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "path_not_allowed" in proc.stderr.lower() or "error" in proc.stderr.lower()
