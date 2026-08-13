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
    assert r["field_ops_fusion"] == "ON"


def test_operator_hub_exit_0():
    p = _run(["operator"])
    assert p.returncode == 0, p.stderr
    out = p.stdout
    assert "AMARILLO" in out
    # Stable print_hub rails (#18): go_q_met False · field_ops fusion ON
    assert "go_q_met" in out
    assert "go_q_met          False" in out or "go_q_met False" in out.replace(" ", "")
    assert "field_ops fusion" in out
    assert "ON" in out
    # Guard against accidental GO_Q flip
    assert "go_q_met          True" not in out
    assert "go_q complete" not in out.lower()


def test_operator_checklist_exit_0_and_no_go_q_claim():
    p = _run(["operator", "checklist", "--json"])
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["go_q_met"] is False
    assert data["semaforo"] == "AMARILLO"
    assert "GO_Q complete" not in p.stdout.lower()
    assert data["rails"]["GO_Q"] == "partial"
    assert data["rails"]["field_ops_fusion"] == "ON"


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
    assert (
        "[demo-multi-ccaa]" in combined
        or (ROOT / "outputs" / "demo_multi_ccaa" / "index.html").is_file()
    )
    # #18 rails unchanged by act 1 (hub helpers stay honest)
    r = rails_snapshot()
    assert r["go_q_met"] is False
    assert r["GO_Q_semaforo"] == "AMARILLO"
    assert r["field_ops_fusion"] == "ON"


def test_operator_unknown_subcommand_exits_2():
    """Unknown operator subcommand must fail closed (argparse exit 2), not silent 0."""
    p = _run(["operator", "not-a-real-act"])
    assert p.returncode == 2
    combined = (p.stderr + p.stdout).lower()
    assert "invalid choice" in combined or "choose from" in combined or "error" in combined


def test_demo_third_party_rehearsal_keeps_go_q_false():
    p = _run(["demo-third-party", "--skip-build"])
    assert p.returncode == 0, p.stderr + p.stdout
    assert "go_q_met: False" in p.stdout or "go_q_met:False" in p.stdout.replace(" ", "")
    summary = ROOT / "outputs" / "demo_third_party" / "REHEARSAL_SUMMARY.json"
    assert summary.is_file()
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["go_q_met"] is False
    assert data["semaforo"] == "AMARILLO"
    assert data["field_ops_fusion"] == "ON"


def test_build_checklist_structure():
    data = build_checklist(root=ROOT)
    assert data["go_q_met"] is False
    assert len(data["checks"]) == 7


def _stamp_fusion() -> str | None:
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    if not stamp_path.is_file():
        return None
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
        return "ON"
    rails = stamp.get("rails") or {}
    raw = rails.get("field_ops_fusion")
    if raw is None:
        return "OFF"
    return str(raw).upper()


def test_operator_kill_list_does_not_contradict_stamp():
    """kill_list[0] must follow stamp. Fusion ON ≠ GO_Q ≠ despacho."""
    fusion = _stamp_fusion()
    if fusion is None:
        import pytest

        pytest.skip("ML product stamp missing — cannot assert kill_list vs stamp")
    data = build_checklist(root=ROOT)
    assert data["go_q_met"] is False
    assert data["rails"]["field_ops_fusion"] == fusion
    first = data["kill_list"][0]
    assert first != "No field_ops ML live fusion ON"
    if fusion == "ON":
        blob = first.lower()
        assert "go_q" in blob or "despacho" in blob
        assert "no field_ops ml live fusion on" not in blob
    p = _run(["operator", "checklist", "--json"])
    assert p.returncode == 0, p.stderr
    listed = json.loads(p.stdout)["kill_list"]
    assert listed[0] == first
