"""T0 industrial product gate script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "industrial_product_gate.py"


def test_industrial_product_gate_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["schema"] == "wfd_industrial_product_gate_v1"
    assert report["status"] == "PASS"
    assert all(row["ok"] for row in report["checks"])
