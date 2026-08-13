"""W2-Alonso: cite copy CLI is fail-closed (missing data → exit 1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "copy_cite_to_real_if.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def test_missing_cite_flag_exits_1() -> None:
    p = _run(["--fire-id", "hellin_2024"])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "cite" in p.stderr.lower()


def test_missing_fire_id_flag_exits_1(tmp_path: Path) -> None:
    cite = tmp_path / "parte.pdf"
    cite.write_bytes(b"%PDF-1.4 fake")
    p = _run(["--cite", str(cite)])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "fire-id" in p.stderr.lower()


def test_missing_cite_file_exits_1() -> None:
    p = _run(["--cite", str(ROOT / "no_such_cite_xyz.pdf"), "--fire-id", "hellin_2024"])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "cite" in p.stderr.lower()


def test_unknown_fire_id_exits_1(tmp_path: Path) -> None:
    cite = tmp_path / "parte.pdf"
    cite.write_bytes(b"%PDF-1.4 fake")
    p = _run(["--cite", str(cite), "--fire-id", "not_a_real_fire_xyz"])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "unknown fire_id" in p.stderr


def test_copy_does_not_promote(tmp_path: Path) -> None:
    cite = tmp_path / "hellin_parte.pdf"
    cite.write_bytes(b"%PDF-1.4 cite")
    dest = tmp_path / "real_if"
    p = _run(
        [
            "--cite",
            str(cite),
            "--fire-id",
            "hellin_2024",
            "--dest-parent",
            str(dest),
        ]
    )
    assert p.returncode == 0, p.stderr
    copied = dest / "hellin_2024" / "cite" / "hellin_parte.pdf"
    assert copied.is_file()
    assert copied.read_bytes() == b"%PDF-1.4 cite"
    assert "promote still requires H1" in p.stdout
    assert "H7" in p.stdout
    # Anchors SSOT untouched
    anchors = (ROOT / "data" / "infocam_anchors.json").read_text(encoding="utf-8")
    assert '"hellin_2024"' in anchors
    assert '"status": "pending_external"' in anchors
