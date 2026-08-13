"""W2-B: auditable CLM packs — missing trees honest; NO_USE never usable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_clm_audit_packs.py"
sys.path.insert(0, str(ROOT / "scripts"))

import export_clm_audit_packs as packs  # noqa: E402


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
    )


def _write_anchors(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "protocol": "infocam_anchors_v1",
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
                        "status": "pending_external",
                    },
                    "cardoso_2025": {
                        "fire_id": "cardoso_2025",
                        "vp_m_min": None,
                        "area_ha": None,
                        "source": None,
                        "status": "pending_external",
                    },
                    "retuerta_2025": {
                        "fire_id": "retuerta_2025",
                        "status": "pending_external",
                    },
                    "polan_2025": {"fire_id": "polan_2025", "status": "pending_external"},
                    "la_estrella_acom1_2024": {
                        "fire_id": "la_estrella_acom1_2024",
                        "status": "pending_external",
                    },
                    "la_estrella_acom2_2024": {
                        "fire_id": "la_estrella_acom2_2024",
                        "status": "pending_external",
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_missing_tree_pack_honest_zero_counts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write_anchors(root / "data" / "infocam_anchors.json")
    out = tmp_path / "packs"
    p = _run(
        [
            "--root",
            str(root),
            "--anchors",
            str(root / "data" / "infocam_anchors.json"),
            "--out",
            str(out),
            "--fire-id",
            "hellin_2024",
            "--fire-id",
            "cardoso_2025",
        ]
    )
    assert p.returncode == 0, p.stderr
    hellin = json.loads((out / "hellin_2024.json").read_text(encoding="utf-8"))
    assert hellin["on_disk_tif_count"] == 0
    assert hellin["on_disk_kmz_count"] == 0
    assert hellin["invented_vp_ha"] is False
    assert hellin["status"] != "confirmed"
    assert hellin["honesty_class"] != "ml_strong"
    assert hellin["ml_strong"] is False
    cardoso = json.loads((out / "cardoso_2025.json").read_text(encoding="utf-8"))
    assert cardoso["invented_vp_ha"] is False
    assert cardoso["status"] != "confirmed"
    assert cardoso["honesty_class"] != "ml_strong"


def test_retuerta_polan_never_usable() -> None:
    ret = packs.pack_from_row(
        {
            "fire_id": "retuerta_2025",
            "honesty_class": "discard",
            "use_flag": "NO_USE",
            "status": "NO_USE",
            "blocking_gap": "FOV",
            "on_disk_tif_count": 48,
            "on_disk_kmz_count": 16,
            "aligned_tif_count": 14,
            "mask_tif_count": 15,
            "trees_present": ["artifacts/aligned_spatial_v1/retuerta_2025"],
            "tree_fingerprint": "abc",
            "manifest_sha256": {},
        },
        usable=True,
    )
    assert ret["usable_pack"] is False
    assert ret["use_flag"] == "NO_USE"
    assert ret["honesty_class"] == "discard"
    polan = packs.pack_from_row(
        {
            "fire_id": "polan_2025",
            "honesty_class": "discard",
            "use_flag": "NO_USE",
            "status": "NO_USE",
            "blocking_gap": ">=3 frames",
            "on_disk_tif_count": 1,
            "on_disk_kmz_count": 0,
            "aligned_tif_count": 0,
            "mask_tif_count": 0,
            "trees_present": [],
            "tree_fingerprint": "",
            "manifest_sha256": {},
        },
        usable=True,
    )
    assert polan["usable_pack"] is False
    assert polan["use_flag"] == "NO_USE"


def test_unknown_fire_id_exits_1(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write_anchors(root / "data" / "infocam_anchors.json")
    p = _run(
        [
            "--root",
            str(root),
            "--anchors",
            str(root / "data" / "infocam_anchors.json"),
            "--out",
            str(tmp_path / "packs"),
            "--fire-id",
            "not_a_real_fire_xyz",
        ]
    )
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "unknown fire_id" in p.stderr


def test_missing_anchors_without_board_exits_1(tmp_path: Path) -> None:
    p = _run(
        [
            "--root",
            str(tmp_path),
            "--anchors",
            str(tmp_path / "missing.json"),
            "--out",
            str(tmp_path / "packs"),
            "--fire-id",
            "hellin_2024",
        ]
    )
    assert p.returncode == 1
    assert "error:" in p.stderr


@pytest.mark.parametrize("fid", ["hellin_2024", "cardoso_2025"])
def test_hellin_cardoso_pack_not_confirmed_or_ml_strong(fid: str) -> None:
    pack = packs.pack_from_row(
        {
            "fire_id": fid,
            "honesty_class": "ml_weak",
            "use_flag": "review",
            "status": "pending_external",
            "blocking_gap": "cite",
            "on_disk_tif_count": 0,
            "H1": 0,
        },
        usable=True,
    )
    assert pack["status"] != "confirmed"
    assert pack["honesty_class"] != "ml_strong"
    assert pack["confirmed"] is False
    assert pack["ml_strong"] is False
    assert pack["invented_vp_ha"] is False
