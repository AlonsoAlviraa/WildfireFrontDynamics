"""Operator hub / checklist / teach / show — H1 cheatsheet surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from wildfire_front.cli_operator import build_checklist, rails_snapshot

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wildfire_front", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
    )


def test_rails_go_q_not_met():
    r = rails_snapshot()
    assert r["go_q_met"] is False
    assert r["GO_Q"] == "partial"
    assert r["GO_Q_semaforo"] == "AMARILLO"
    assert r["field_ops_fusion"] == "OFF"


def test_operator_hub_exit_0():
    p = _run(["operator"])
    assert p.returncode == 0, p.stderr
    out = p.stdout
    assert "AMARILLO" in out
    # Stable print_hub rails (#18): go_q_met False · field_ops fusion OFF
    assert "go_q_met" in out
    assert "go_q_met          False" in out or "go_q_met False" in out.replace(" ", "")
    assert "field_ops fusion" in out
    assert "OFF" in out
    # Guard against accidental GO_Q flip / fusion ON in hub text
    assert "go_q_met          True" not in out
    assert "fusion  ON" not in out and "fusion ON" not in out


def test_operator_checklist_exit_0_and_no_go_q_claim():
    p = _run(["operator", "checklist", "--json"])
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["go_q_met"] is False
    assert data["semaforo"] == "AMARILLO"
    assert "GO_Q complete" not in p.stdout.lower()
    assert data["rails"]["GO_Q"] == "partial"


def test_teach_and_show_exit_0():
    t = _run(["teach"])
    assert t.returncode == 0, t.stderr
    assert "AMARILLO" in t.stdout
    s = _run(["show", "--json"])
    assert s.returncode == 0, s.stderr
    data = json.loads(s.stdout)
    assert data["go_q_met"] is False


def test_operator_do_missing_act_exit_2():
    p = _run(["operator", "do"])
    assert p.returncode == 2
    assert "operator do requires" in p.stderr or "hint:" in p.stderr


def test_operator_do_act_1_smoke():
    """Act 1 (Ver) dispatches build_demo_multi_ccaa — local fixtures only, no network."""
    p = _run(["operator", "do", "--act", "1"])
    assert p.returncode == 0, p.stderr + p.stdout
    combined = p.stdout + p.stderr
    assert "build_demo_multi_ccaa" in combined
    assert "[demo-multi-ccaa]" in combined or (
        ROOT / "outputs" / "demo_multi_ccaa" / "index.html"
    ).is_file()
    # #18 rails unchanged by act 1 (hub helpers stay honest)
    r = rails_snapshot()
    assert r["go_q_met"] is False
    assert r["GO_Q_semaforo"] == "AMARILLO"
    assert r["field_ops_fusion"] == "OFF"


def test_demo_third_party_rehearsal_keeps_go_q_false():
    p = _run(["demo-third-party", "--skip-build"])
    assert p.returncode == 0, p.stderr + p.stdout
    assert "go_q_met: False" in p.stdout or "go_q_met:False" in p.stdout.replace(" ", "")
    summary = ROOT / "outputs" / "demo_third_party" / "REHEARSAL_SUMMARY.json"
    assert summary.is_file()
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["go_q_met"] is False
    assert data["semaforo"] == "AMARILLO"
    assert data["field_ops_fusion"] == "OFF"


def test_build_checklist_structure():
    data = build_checklist(root=ROOT)
    assert data["go_q_met"] is False
    assert len(data["checks"]) == 7
