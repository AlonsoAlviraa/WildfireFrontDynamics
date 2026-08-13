"""Fail-closed IF weakness board: missing data, R/H rails, no invented metrics."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "score_if_weakness_board.py"
sys.path.insert(0, str(ROOT / "scripts"))

import score_if_weakness_board as board  # noqa: E402

R_KEYS = ("R1", "R2", "R3", "R4", "R5", "R6")
H_KEYS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
HONESTY = {"ml_strong", "ml_weak", "proxy", "context_only", "discard"}
REQUIRED_ROW_KEYS = {
    "fire_id",
    "status",
    "honesty_class",
    "on_disk_tif_count",
    "dated_scene_count",
    "usable_dated_scene_count",
    "blocking_gap",
    "owner",
    *R_KEYS,
    *H_KEYS,
}


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
    )


def _write_anchors(path: Path, extra: dict | None = None) -> None:
    anchors = {
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
    }
    if extra:
        anchors.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"protocol": "infocam_anchors_v1", "anchors": anchors}, indent=2),
        encoding="utf-8",
    )


def _touch_dated_tifs(folder: Path, stamps: list[str], *, masks: bool = False) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for stamp in stamps:
        (folder / f"{stamp}_LWIR.tif").write_bytes(b"II*\x00fake")
        if masks:
            (folder / f"{stamp}_LWIR_mask.tif").write_bytes(b"II*\x00mask")


def _mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    anchors = root / "data" / "infocam_anchors.json"
    _write_anchors(anchors)
    _touch_dated_tifs(
        root / "artifacts" / "aligned_spatial_v1" / "tobarra_20240802" / "chains" / "chain_00" / "lwir",
        [
            "2024-08-02_16-08-21-553",
            "2024-08-02_16-15-07-320",
            "2024-08-02_16-19-14-281",
        ],
        masks=False,
    )
    manifest = {
        "schema": "w3_align_fire_chains_v1",
        "chains": [
            {
                "ok": True,
                "n_frames": 3,
                "grid": {
                    "crs": "EPSG:32630",
                    "left": 1.0,
                    "bottom": 2.0,
                    "right": 3.0,
                    "top": 4.0,
                },
                "images": [{"destination": "a"}, {"destination": "b"}, {"destination": "c"}],
            }
        ],
    }
    man_path = root / "artifacts" / "aligned_spatial_v1" / "tobarra_20240802" / "align_manifest.json"
    man_path.write_text(json.dumps(manifest), encoding="utf-8")
    _touch_dated_tifs(
        root / "artifacts" / "aligned_spatial_v1" / "hellin_2024" / "chains" / "chain_00" / "lwir",
        [
            "2024-07-19_12-00-00-000",
            "2024-07-19_12-10-00-000",
            "2024-07-19_12-20-00-000",
        ],
    )
    _touch_dated_tifs(
        root / "artifacts" / "polan_2025_reprojected_lwir",
        ["2025-09-13_17-41-59-513"],
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "V29_LOFO_TOBARRA_VERDICT.json").write_text(
        json.dumps(
            {
                "held_out": "tobarra_20240802",
                "test_iou": 0.4938,
                "copy_baseline_iou": 0.3284,
                "improvement_vs_copy_iou": 0.1654,
                "n_test": 300,
                "verdict": "GO_TRANSFER_LOFO",
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "CLM_LOFO_ALL_FOLDS_REPORT.json").write_text(
        json.dumps(
            {
                "folds": [
                    {"held": "CARDOSO", "test_iou": 0.7978106779815259, "copy_baseline_iou": 0.64},
                    {"held": "tobarra_20240802", "test_iou": 0.4938, "copy_baseline_iou": 0.3284},
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def _assert_row_rails(row: dict) -> None:
    missing = REQUIRED_ROW_KEYS - set(row)
    assert not missing, missing
    for key in (*R_KEYS, *H_KEYS):
        assert row[key] in (0, 1), (row["fire_id"], key, row[key])
    assert row["honesty_class"] in HONESTY
    assert row["status"] in {"confirmed", "pending_external", "inventory_only", "NO_USE"}
    assert isinstance(row["on_disk_tif_count"], int)
    assert isinstance(row["dated_scene_count"], int)
    assert row["on_disk_tif_count"] >= 0
    assert row["dated_scene_count"] >= 0
    assert row["owner"] in {"human", "eng"}
    assert row["invented_vp_ha"] is False
    if row["H1"] == 0:
        assert row["status"] != "confirmed", row
    if row["H1"] == 0 or row["R1"] == 0:
        assert row["honesty_class"] != "ml_strong", row


def test_missing_anchors_exits_1(tmp_path: Path) -> None:
    missing = tmp_path / "no_anchors.json"
    out = tmp_path / "board.json"
    p = _run(
        [
            "--root",
            str(tmp_path),
            "--anchors",
            str(missing),
            "--out-json",
            str(out),
            "--out-md",
            str(tmp_path / "board.md"),
            "--inventory-json",
            str(tmp_path / "inv.json"),
            "--inventory-csv",
            str(tmp_path / "inv.csv"),
        ]
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "error:" in p.stderr
    assert "anchors" in p.stderr.lower()
    assert not out.is_file()


def test_unreadable_anchors_exits_1(tmp_path: Path) -> None:
    bad = tmp_path / "anchors.json"
    bad.write_text("{not-json", encoding="utf-8")
    p = _run(
        [
            "--root",
            str(tmp_path),
            "--anchors",
            str(bad),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )
    assert p.returncode == 1
    assert "error:" in p.stderr


def test_empty_anchors_object_exits_1(tmp_path: Path) -> None:
    empty = tmp_path / "anchors.json"
    empty.write_text(json.dumps({"protocol": "infocam_anchors_v1", "anchors": {}}), encoding="utf-8")
    p = _run(["--root", str(tmp_path), "--anchors", str(empty)])
    assert p.returncode == 1
    assert "error:" in p.stderr
    assert "no usable anchors" in p.stderr


def test_unknown_fire_id_exits_1(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    p = _run(
        [
            "--root",
            str(root),
            "--anchors",
            str(root / "data" / "infocam_anchors.json"),
            "--fire-id",
            "not_a_real_fire_xyz",
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "error:" in p.stderr
    assert "unknown fire_id" in p.stderr
    assert "not_a_real_fire_xyz" in p.stderr
    assert not (tmp_path / "board.json").is_file()


def test_board_rails_never_confirmed_or_ml_strong_without_h1_r1(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    out_json = tmp_path / "board.json"
    p = _run(
        [
            "--root",
            str(root),
            "--anchors",
            str(root / "data" / "infocam_anchors.json"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(tmp_path / "board.md"),
            "--inventory-json",
            str(tmp_path / "inv.json"),
            "--inventory-csv",
            str(tmp_path / "inv.csv"),
        ]
    )
    assert p.returncode == 0, p.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["schema"] == "wfd_if_weakness_board_v1"
    assert payload["rails"]["tobarra_keep_reopen"] is False
    assert payload["rails"]["go_q"] == "partial"
    assert payload["rails"]["field_ops_ml_fusion"] == "ON"
    assert payload["rails"]["invented_vp_ha"] is False
    assert payload["rails"]["new_iou_invented"] is False
    assert payload["rails"]["retrained_clm_ensemble_v34"] is False
    assert payload["rails"]["anchors_written"] is False
    assert payload["tobarra_lofo"]["new_iou_invented"] is False
    assert payload["tobarra_lofo"]["keep_reopened"] is False
    assert payload["tobarra_lofo"]["sealed_v29"]["test_iou"] == 0.4938
    assert payload["tobarra_lofo"]["sealed_v29"]["held_out"] == "tobarra_20240802"
    assert "0.857" not in json.dumps(payload)
    fires = {row["fire_id"]: row for row in payload["fires"]}
    assert "tobarra_20240802" in fires
    assert "hellin_2024" in fires
    assert "polan_2025" in fires
    for row in payload["fires"]:
        _assert_row_rails(row)
    hellin = fires["hellin_2024"]
    assert hellin["status"] == "pending_external"
    assert hellin["H1"] == 0
    assert hellin["H2"] == 0
    assert hellin["H4"] == 0
    assert hellin["H5"] == 0
    assert hellin["H6"] == 0
    assert hellin["H7"] == 1
    assert hellin["R1"] == 1
    assert hellin["honesty_class"] != "ml_strong"
    assert hellin["blocking_gap"] == "cite"
    assert hellin["owner"] == "human"
    assert hellin["dated_scene_count"] == 3
    polan = fires["polan_2025"]
    assert polan["status"] == "NO_USE"
    assert polan["honesty_class"] == "discard"
    assert polan["R1"] == 0
    assert polan["dated_scene_count"] == 1
    assert polan["on_disk_tif_count"] == 1
    assert polan["blocking_gap"] == ">=3 frames"
    tobarra = fires["tobarra_20240802"]
    assert tobarra["status"] == "confirmed"
    assert tobarra["H1"] == 1
    assert tobarra["H2"] == 1
    assert tobarra["R1"] == 1
    assert tobarra["dated_scene_count"] == 3
    assert tobarra["vp_m_min_cited"] == 7.0
    assert tobarra["area_ha_cited"] == 39.0
    assert tobarra["anchors_written"] is False
    # R4 rights are fail-closed for CLM (no cession file) → not ml_strong.
    assert tobarra["R4"] == 0
    assert tobarra["honesty_class"] != "ml_strong"
    md = (tmp_path / "board.md").read_text(encoding="utf-8")
    assert "| `hellin_2024` | `pending_external` |" in md
    assert "ml_strong" in md
    assert "does not write" in md.lower() or "Does not write" in md


def test_does_not_write_infocam_anchors(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    anchors = root / "data" / "infocam_anchors.json"
    before = anchors.read_text(encoding="utf-8")
    mtime = anchors.stat().st_mtime_ns
    p = _run(
        [
            "--root",
            str(root),
            "--anchors",
            str(anchors),
            "--fire-id",
            "hellin_2024",
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-md",
            str(tmp_path / "board.md"),
        ]
    )
    assert p.returncode == 0, p.stderr
    after = anchors.read_text(encoding="utf-8")
    assert after == before
    assert anchors.stat().st_mtime_ns == mtime
    payload = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))
    assert payload["rails"]["anchors_written"] is False
    assert payload["fires"][0]["fire_id"] == "hellin_2024"
    assert payload["fires"][0]["status"] == "pending_external"


def test_h1_zero_cannot_emit_confirmed() -> None:
    r = {k: 1 for k in R_KEYS}
    h = {k: 1 for k in H_KEYS}
    h["H1"] = 0
    inv = {
        "on_disk_tif_count": 10,
        "dated_scene_count": 5,
        "aligned_tif_count": 8,
        "mask_tif_count": 8,
        "pack_kind": "clm",
        "has_geometry": True,
        "has_weather": False,
    }
    honesty, status, gap, owner = board.classify_row(
        "hellin_2024",
        r=r,
        h=h,
        inv=inv,
        anchor={"status": "confirmed", "source": ""},
    )
    assert status != "confirmed"
    assert honesty != "ml_strong"
    assert gap == "cite"
    assert owner == "human"


def test_r1_zero_cannot_emit_ml_strong() -> None:
    r = {k: 1 for k in R_KEYS}
    r["R1"] = 0
    h = {k: 1 for k in H_KEYS}
    inv = {
        "on_disk_tif_count": 1,
        "dated_scene_count": 1,
        "aligned_tif_count": 1,
        "mask_tif_count": 0,
        "pack_kind": "clm",
        "has_geometry": True,
        "has_weather": False,
    }
    honesty, status, _gap, _owner = board.classify_row(
        "polan_2025",
        r=r,
        h=h,
        inv=inv,
        anchor=None,
    )
    assert honesty != "ml_strong"
    assert honesty == "discard"
    assert status == "NO_USE"


def test_score_h_pending_is_zeros_except_h3_h7() -> None:
    bits = board.score_h_bits(
        "hellin_2024",
        {
            "fire_id": "hellin_2024",
            "status": "pending_external",
            "vp_m_min": None,
            "area_ha": None,
            "source": None,
        },
        {"hellin_2024"},
    )
    assert bits["H1"] == 0
    assert bits["H2"] == 0
    assert bits["H3"] == 1
    assert bits["H4"] == 0
    assert bits["H5"] == 0
    assert bits["H6"] == 0
    assert bits["H7"] == 1


def test_score_r1_requires_three_dated_scenes() -> None:
    low = board.score_r_bits(
        {
            "dated_scene_count": 2,
            "has_geometry": True,
            "has_crs_bbox_dates": True,
            "has_documented_rights": True,
            "tree_fingerprint": "abc",
            "inventory_file_count": 2,
        }
    )
    assert low["R1"] == 0
    high = board.score_r_bits(
        {
            "dated_scene_count": 3,
            "has_geometry": True,
            "has_crs_bbox_dates": True,
            "has_documented_rights": True,
            "tree_fingerprint": "abc",
            "inventory_file_count": 3,
        }
    )
    assert high["R1"] == 1


def test_live_repo_board_does_not_flip_hellin_or_invent_u1() -> None:
    """Live SSOT path: Hellín stays pending; sealed LOFO cited; no U1 vanity."""
    if not (ROOT / "data" / "infocam_anchors.json").is_file():
        pytest.skip("anchors missing")
    payload = board.build_board(
        root=ROOT,
        anchors_path=ROOT / "data" / "infocam_anchors.json",
        fire_ids=["tobarra_20240802", "hellin_2024", "retuerta_2025", "polan_2025"],
    )
    board._assert_fail_closed(payload)
    by_id = {row["fire_id"]: row for row in payload["fires"]}
    for row in payload["fires"]:
        _assert_row_rails(row)
    assert by_id["hellin_2024"]["status"] == "pending_external"
    assert by_id["hellin_2024"]["H1"] == 0
    assert by_id["hellin_2024"]["honesty_class"] != "ml_strong"
    assert by_id["retuerta_2025"]["honesty_class"] == "discard"
    assert by_id["retuerta_2025"]["status"] == "NO_USE"
    assert by_id["retuerta_2025"]["blocking_gap"] == "FOV"
    assert by_id["polan_2025"]["honesty_class"] == "discard"
    assert by_id["tobarra_20240802"]["status"] == "confirmed"
    assert by_id["tobarra_20240802"]["H1"] == 1
    assert by_id["tobarra_20240802"]["vp_m_min_cited"] == 7.0
    assert by_id["tobarra_20240802"]["area_ha_cited"] == 39.0
    dumped = json.dumps(payload)
    assert "0.857" not in dumped
    assert payload["tobarra_lofo"]["new_iou_invented"] is False
    assert payload["tobarra_lofo"]["sealed_v29"]["test_iou"] == 0.4938
    assert payload["rails"]["field_ops_ml_fusion"] == "ON"
    assert payload["summary"]["n_confirmed"] == 1


def test_open_proxy_pack_is_not_second_grade_a(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    pack = root / "data" / "open_if" / "latam_au" / "au" / "AU_EMSR500_PERTH"
    _touch_dated_tifs(
        pack / "labels",
        ["2021-02-05_20-32-25", "2021-02-11_17-03-24", "2021-02-13_02-23-04"],
    )
    (pack / "meta.json").write_text(
        json.dumps(
            {
                "event_id": "AU_EMSR500_PERTH",
                "class": "ml_weak",
                "license_id": "copernicus_ems_reg_2021_696_open",
                "crs": "EPSG:32750",
                "bbox_wgs84": [1.0, 2.0, 3.0, 4.0],
                "dates": ["2021-02-05", "2021-02-11", "2021-02-13"],
            }
        ),
        encoding="utf-8",
    )
    payload = board.build_board(
        root=root,
        anchors_path=root / "data" / "infocam_anchors.json",
        fire_ids=["AU_EMSR500_PERTH"],
    )
    row = payload["fires"][0]
    _assert_row_rails(row)
    assert row["fire_id"] == "AU_EMSR500_PERTH"
    assert row["status"] != "confirmed"
    assert row["H1"] == 0
    assert row["honesty_class"] in {"ml_weak", "proxy"}
    assert row["honesty_class"] != "ml_strong"
    assert row["R1"] == 1
    assert row["R4"] == 1


def test_open_proxy_without_tifs_is_proxy_not_discard(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    pack = root / "data" / "external" / "pt_firesprd"
    pack.mkdir(parents=True)
    (pack / "inventory.json").write_text(
        json.dumps({"license_id": "cc-by-4.0", "n_shp": 12}),
        encoding="utf-8",
    )
    (pack / "sample.shp").write_bytes(b"shp")
    payload = board.build_board(
        root=root,
        anchors_path=root / "data" / "infocam_anchors.json",
        fire_ids=["pt_firesprd"],
    )
    row = payload["fires"][0]
    _assert_row_rails(row)
    assert row["fire_id"] == "pt_firesprd"
    assert row["on_disk_tif_count"] == 0
    assert row["R1"] == 0
    assert row["honesty_class"] == "proxy"
    assert row["status"] == "inventory_only"
    assert row["honesty_class"] != "ml_strong"
    assert row["status"] != "confirmed"
