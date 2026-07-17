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
