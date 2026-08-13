"""W3-B: no cite = no promote (SSOT + attempt-promote refuse)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from wildfire_front.open_if.anchor_guard import (
    can_promote_to_confirmed,
    promote_anchor_to_confirmed,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refuse_promote_without_cite.py"
sys.path.insert(0, str(ROOT / "scripts"))

import refuse_promote_without_cite as refuse  # noqa: E402


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def test_live_ssot_exits_0_only_tobarra_confirmed() -> None:
    p = _run([])
    assert p.returncode == 0, p.stderr
    assert "no pending fire marked confirmed" in p.stdout.lower() or "ok:" in p.stdout.lower()


def test_attempt_promote_hellin_refuses() -> None:
    p = _run(["--attempt-promote", "--fire-id", "hellin_2024"])
    assert p.returncode == 1
    assert "error: no cite = no promote" in p.stderr


def test_attempt_promote_missing_fire_id_exits_1() -> None:
    p = _run(["--attempt-promote"])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "fire-id" in p.stderr.lower()


def test_missing_anchors_exits_1(tmp_path: Path) -> None:
    p = _run(["--anchors", str(tmp_path / "missing.json")])
    assert p.returncode == 1
    assert "error:" in p.stderr


def test_non_tobarra_confirmed_without_cite_fails(tmp_path: Path) -> None:
    path = tmp_path / "anchors.json"
    path.write_text(
        json.dumps(
            {
                "anchors": {
                    "tobarra_20240802": {
                        "fire_id": "tobarra_20240802",
                        "vp_m_min": 7.0,
                        "area_ha": 39.0,
                        "source": "INFOCAM 2024 parte operativo",
                        "status": "confirmed",
                    },
                    "hellin_2024": {
                        "fire_id": "hellin_2024",
                        "vp_m_min": None,
                        "area_ha": None,
                        "source": None,
                        "status": "confirmed",
                        "H1": 0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    code, msg = refuse.evaluate_anchors_file(path)
    assert code == 1
    assert "error: no cite = no promote" in msg


def test_confirmed_h1_zero_or_null_vp_fails_guard() -> None:
    ok, reasons = can_promote_to_confirmed(
        {
            "fire_id": "hellin_2024",
            "vp_m_min": 50.0,
            "area_ha": 100.0,
            "source": "INFOCAM 2024 parte operativo",
            "H1": 0,
        }
    )
    assert ok is False
    assert any("h1_zero_no_cite" in r for r in reasons)

    ok2, reasons2 = can_promote_to_confirmed(
        {
            "fire_id": "hellin_2024",
            "vp_m_min": None,
            "area_ha": None,
            "source": None,
            "status": "confirmed",
        }
    )
    assert ok2 is False
    assert any("missing_vp_m_min" in r for r in reasons2)
    assert any("missing_area_ha" in r for r in reasons2)
    assert any("missing_source" in r for r in reasons2)

    with pytest.raises(ValueError):
        promote_anchor_to_confirmed(
            {
                "fire_id": "hellin_2024",
                "vp_m_min": None,
                "area_ha": None,
                "source": None,
                "H1": 0,
            },
            force=True,
        )
