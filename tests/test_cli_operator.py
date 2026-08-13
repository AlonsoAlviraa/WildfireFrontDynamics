"""Operator hub / checklist / teach / show — H1 cheatsheet surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from wildfire_front.cli_operator import build_checklist, rails_snapshot
from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wildfire_front", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
    )


STALE_FUSION_BAN = "No field_ops ML live fusion ON"


def test_rails_go_q_not_met():
    r = rails_snapshot()
    assert r["go_q_met"] is False
    assert r["GO_Q"] == "partial"
    assert r["GO_Q_semaforo"] == "AMARILLO"
    assert r["field_ops_fusion"] == field_ops_ml_live_fusion_rail()


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
    assert data["rails"]["field_ops_fusion"] == field_ops_ml_live_fusion_rail()


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
    assert r["field_ops_fusion"] == field_ops_ml_live_fusion_rail()


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
    assert data["field_ops_fusion"] == field_ops_ml_live_fusion_rail()
    readme = ROOT / "outputs" / "demo_third_party" / "README.md"
    assert readme.is_file()
    readme_txt = readme.read_text(encoding="utf-8")
    rail = field_ops_ml_live_fusion_rail()
    assert f"field_ops fusion: **{rail}**" in readme_txt
    if rail == "ON":
        assert "field_ops fusion: **OFF**" not in readme_txt


def test_build_checklist_structure():
    data = build_checklist(root=ROOT)
    assert data["go_q_met"] is False
    assert len(data["checks"]) == 7


def test_kill_list_honest_vs_fusion_rail():
    data = build_checklist(root=ROOT)
    rail = field_ops_ml_live_fusion_rail()
    assert data["rails"]["field_ops_fusion"] == rail
    assert data["go_q_met"] is False
    kills = list(data["kill_list"])
    blob = "\n".join(kills)
    if rail == "ON":
        assert STALE_FUSION_BAN not in kills
        assert STALE_FUSION_BAN not in blob
        assert any("despacho" in k.lower() for k in kills)
        assert any("GO_Q" in k for k in kills)
        assert any("0.20" in k and "0.45" in k for k in kills)
    else:
        assert any(STALE_FUSION_BAN in k for k in kills)
    assert any("GO_Q" in k for k in kills)
    assert any("IoU" in k and "ROS" in k for k in kills)
    assert any("ROS" in k for k in kills)


def test_operator_hub_json_kill_list_honest():
    p = _run(["operator", "--json"])
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    rail = field_ops_ml_live_fusion_rail()
    assert data["go_q_met"] is False
    assert data["rails"]["field_ops_fusion"] == rail
    kills = list(data["kill_list"])
    if rail == "ON":
        assert STALE_FUSION_BAN not in kills
        assert not any(k.strip() == STALE_FUSION_BAN for k in kills)
        assert any("despacho" in k.lower() for k in kills)
    assert any("GO_Q" in k for k in kills)


def test_prepare_h1_demo_session_snapshots_fusion_to_temp(tmp_path: Path):
    script = ROOT / "scripts" / "prepare_h1_demo_session.py"
    out = tmp_path / "h1_prep"
    p = subprocess.run(
        [
            sys.executable,
            str(script),
            "--skip-dry-run",
            "--out-dir",
            str(out),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
    )
    assert p.returncode in (0, 1), p.stderr + p.stdout
    session = out / "H1_DEMO_SESSION_READY.json"
    invite = out / "H1_CALENDAR_INVITE.md"
    assert session.is_file(), p.stdout
    assert invite.is_file(), p.stdout
    payload = json.loads(session.read_text(encoding="utf-8"))
    rail = field_ops_ml_live_fusion_rail()
    assert payload["go_q_met"] is False
    assert payload["rails"]["field_ops_fusion"] == rail
    invite_txt = invite.read_text(encoding="utf-8")
    if rail == "ON":
        assert STALE_FUSION_BAN not in invite_txt
        assert "fusion **OFF**" not in invite_txt
        assert "fusion OFF" not in invite_txt
