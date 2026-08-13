"""W4-A: H1 dry-run never sets GO_Q / go_q_met true."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dry_run_h1.py"
sys.path.insert(0, str(ROOT / "scripts"))

import dry_run_h1 as dry  # noqa: E402


def test_stamp_pins_exact_flags() -> None:
    stamp = dry.build_dry_run_stamp()
    assert stamp["go_q_met"] is False
    assert stamp["GO_Q"] == "partial"
    assert stamp["not_third_party_acta"] is True
    assert stamp["not_signed_acta"] is True
    assert stamp["product_unlock"] is False
    assert stamp["calls_record_h1_demo_complete"] is False
    assert stamp["field_ops_fusion"] == "ON"
    assert stamp["schema"] == "wfd_h1_dry_run_v1"


def test_cli_writes_stamp_without_go_q(tmp_path: Path) -> None:
    out = tmp_path / "H1_DRY_RUN.json"
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["go_q_met"] is False
    assert payload["GO_Q"] == "partial"
    assert payload["not_third_party_acta"] is True
    assert payload["not_signed_acta"] is True
    assert payload["calls_record_h1_demo_complete"] is False
    printed = json.loads(p.stdout)
    assert printed["go_q_met"] is False
    assert printed["GO_Q"] == "partial"
    # Live GO_Q stamp must stay partial (dry-run does not touch it).
    live = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    assert live.get("GO_Q") == "partial"
