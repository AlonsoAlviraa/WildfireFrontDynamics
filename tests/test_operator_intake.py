"""Operator intake: folder + geotiff only + Spanish, no GO_Q invent."""

from __future__ import annotations

import base64
from pathlib import Path

from wildfire_front.product.app_spa import build_product_app_payload, render_product_app_html
from wildfire_front.product.live_ops import (
    LIVE_PATH_INTAKE,
    LIVE_PATH_INTAKE_OPEN,
    LIVE_PATH_INTAKE_PROCESS,
    dispatch_live,
)
from wildfire_front.product.operator_intake import (
    ensure_named_work_dir,
    intake_guide,
    intake_status,
    need_to_know,
    receive_files,
    sanitize_fire_id,
)


def test_sanitize_and_ensure_under_incidents(tmp_path: Path) -> None:
    assert sanitize_fire_id("Tobarra Norte!") == "Tobarra_Norte"
    wd = ensure_named_work_dir("prueba 1", base=tmp_path)
    assert (wd / "inbox").is_dir()
    assert "incidents" in str(wd).replace("\\", "/")
    assert wd.name == "prueba_1"


def test_jpg_rejected_tif_saved(tmp_path: Path) -> None:
    wd = ensure_named_work_dir("drop", base=tmp_path)
    out = receive_files(
        wd,
        [
            {"name": "movil.jpg", "content_b64": base64.b64encode(b"not-a-tif").decode("ascii")},
            {
                "name": "20260817_153000_frente.tif",
                "content_b64": base64.b64encode(b"II*\x00fake-tiff").decode("ascii"),
            },
        ],
    )
    assert out["saved"] == ["20260817_153000_frente.tif"]
    assert out["rejected"]
    assert "JPG" in out["rejected"][0]["why"] or "tif" in out["rejected"][0]["why"].lower()
    assert (wd / "inbox" / "20260817_153000_frente.tif").is_file()
    st = intake_status(wd)
    assert st["n_photos"] == 1
    assert st["n_with_date"] == 1
    assert st["go_q_met"] is not True


def test_need_to_know_spanish_and_not_dispatch() -> None:
    brief = need_to_know(
        card={"decision": "ABSTAIN", "sources": [{"id": "open_cems", "available": False}]},
        ops=None,
        snapshot=None,
        inbox_n=0,
    )
    assert "calla" in brief["action"].lower() or "fotos" in brief["action"].lower()
    assert brief["not_tactical_dispatch"] is True
    assert any("Copernicus" in m or "copernicus" in m.lower() for m in brief["missing"])


def test_guide_and_payload_markers() -> None:
    g = intake_guide(work_dir=None, fire_id="demo")
    assert g["need_geotiff"] is True
    assert g["jpg_not_enough"] is True
    assert len(g["steps"]) == 3
    payload = build_product_app_payload(work_dir=None, live=False, scan=False)
    assert payload["need_to_know"]["not_tactical_dispatch"] is True
    assert payload["intake_guide"]["steps"]
    html = render_product_app_html(payload)
    assert "Meter fotos" in html
    assert "btn-intake-open" in html
    assert "need-to-know" in html
    assert "Un JPG" in html or "JPG del móvil" in html


def test_dispatch_intake_status_and_process_empty(tmp_path: Path) -> None:
    wd = ensure_named_work_dir("vacio", base=tmp_path)
    rel = wd.relative_to(tmp_path)
    st, payload = dispatch_live(
        LIVE_PATH_INTAKE,
        {"work_dir": str(rel).replace("\\", "/"), "fire_id": "vacio"},
        base=tmp_path,
        method="GET",
    )
    assert st == 200
    assert payload["n_photos"] == 0
    assert payload["honesty_rails"]["go_q_met"] is False
    st2, proc = dispatch_live(
        LIVE_PATH_INTAKE_PROCESS,
        {"work_dir": str(rel).replace("\\", "/")},
        base=tmp_path,
        method="POST",
    )
    assert st2 == 200
    assert proc["ok"] is False
    assert proc["go_q_met"] is False
    assert "tif" in (proc.get("hint") or "").lower()
    st3, opened = dispatch_live(
        LIVE_PATH_INTAKE_OPEN,
        {"work_dir": str(rel).replace("\\", "/")},
        base=tmp_path,
        method="POST",
    )
    assert st3 == 200
    assert opened["ok"] is True
    assert opened["inbox"]
