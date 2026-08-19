"""Smoke test for wildfire-front decide command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_decide_empty_abstains():
    p = subprocess.run(
        [sys.executable, "-m", "wildfire_front", "decide", "--event-id", "t", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["decision"] == "ABSTAIN"


def test_cli_flags_and_catalog_and_card(tmp_path: Path):
    import os

    env = {**dict(os.environ), "PYTHONPATH": str(ROOT)}
    flags = subprocess.run(
        [sys.executable, "-m", "wildfire_front", "flags", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert flags.returncode == 0, flags.stderr
    payload = json.loads(flags.stdout)
    assert str(payload["GO_Q"]).lower() == "partial"
    catalog = subprocess.run(
        [sys.executable, "-m", "wildfire_front", "catalog", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert catalog.returncode == 0, catalog.stderr
    cat = json.loads(catalog.stdout)
    assert "rcda_net" in cat["not_ready_ids"]
    work = tmp_path / "inc"
    (work / "outbox").mkdir(parents=True)
    (work / "outbox" / "fire_decision_card.json").write_text(
        json.dumps({"event_id": "cli", "decision": "ABSTAIN", "confidence_pred": 0.1}),
        encoding="utf-8",
    )
    card = subprocess.run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "card",
            "--work-dir",
            str(work),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert card.returncode == 0, card.stderr
    shown = json.loads(card.stdout)
    assert shown["summary"]["decision"] == "ABSTAIN"
    snap = subprocess.run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "snapshot",
            "--work-dir",
            str(work),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert snap.returncode == 0, snap.stderr
    snap_body = json.loads(snap.stdout)
    assert snap_body["decision"] == "ABSTAIN"
    assert "source_board" in snap_body
    assert snap_body["rails"]["go_q_complete"] is False
    assert snap_body.get("saved") is True
    assert (work / "outbox" / "incident_snapshot.json").is_file()
    cmp = subprocess.run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "compare",
            "--work-dir",
            str(work),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert cmp.returncode == 0, cmp.stderr
    cmp_body = json.loads(cmp.stdout)
    assert cmp_body["flipped"] is False
    assert cmp_body["alert"]["kind"] == "identity"
