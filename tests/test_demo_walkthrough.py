"""Walkthrough recorder: shipped CLI list + honesty rails."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.product.decide_service import REPO_ROOT
from wildfire_front.product.demo_walkthrough import (
    _forbidden_hits,
    command_lines,
    run_chapter,
    storyboard_markdown,
    walkthrough_spec,
)


def test_walkthrough_spec_uses_shipped_entry_and_three_surfaces() -> None:
    spec = walkthrough_spec()
    assert spec["go_q"] == "partial"
    assert spec["go_q_complete"] is False
    assert spec["not_tactical_dispatch"] is True
    assert spec["signed_acta"] is False
    surfaces = {ch["surface"] for ch in spec["chapters"]}
    assert {"cli", "app", "fire_e2e"} <= surfaces
    ids = [ch["id"] for ch in spec["chapters"]]
    assert "cli_flags" in ids
    assert "cli_snapshot" in ids
    assert "cli_compare" in ids
    assert "app_build" in ids
    assert "fire_decide" in ids
    assert "fire_status" in ids
    for ch in spec["chapters"]:
        assert ch["entry"] == "python -m wildfire_front"
        assert ch["argv"]
        assert ch["argv"][0] != "python"
    blob = json.dumps(spec).lower()
    assert '"go_q_complete": true' not in blob
    assert "go_q complete" not in blob
    assert "hellín" not in blob and "hellin" not in blob
    assert "rcda" not in blob and "caldor" not in blob
    assert "0.308" not in blob
    assert "cardoso" not in blob
    lines = command_lines(spec)
    assert lines
    for argv in lines:
        assert argv[1:3] == ["-m", "wildfire_front"]


def test_storyboard_names_surfaces_and_keeps_rails() -> None:
    spec = walkthrough_spec()
    fake_run = {
        "spec": spec,
        "results": [
            {
                "title": ch["title"],
                "surface": ch["surface"],
                "cmd": "python -m wildfire_front " + " ".join(ch["argv"]),
                "decision": "ABSTAIN" if ch["id"] == "fire_decide" else None,
            }
            for ch in spec["chapters"]
        ],
    }
    md = storyboard_markdown(fake_run)
    assert "CLI" in md and "app" in md.lower()
    assert "e2e" in md.lower() or "fire" in md.lower()
    assert "GO_Q **partial**" in md or "GO_Q partial" in md
    assert "not tactical dispatch" in md.lower() or "not_tactical_dispatch" in md.lower()
    hits = _forbidden_hits(md)
    assert hits == []
    assert "go_q complete" not in md.lower()
    assert "0.308" not in md


def test_cinema_title_and_chapter_are_1080p(tmp_path: Path) -> None:
    from PIL import Image

    from wildfire_front.product.walkthrough_cinema import (
        render_chapter,
        render_lesson,
        render_three_words,
        render_title,
        write_cinema_frames,
    )

    title = render_title()
    assert title.size == (1920, 1080)
    lesson = render_lesson("La palabra grande", "SEGUIR no es una orden de despacho.")
    assert lesson.size == (1920, 1080)
    words = render_three_words()
    assert words.size == (1920, 1080)
    row = {
        "id": "cli_flags",
        "surface": "cli",
        "title": "CLI — flags",
        "cmd": "python -m wildfire_front flags --json",
        "stdout": '{"GO_Q":"partial","field_ops_fusion":"ON","not_tactical_dispatch":true}',
        "returncode": 0,
        "elapsed_ms": 12,
        "decision": None,
    }
    card = render_chapter(row, index=1, total=3)
    assert card.size == (1920, 1080)
    fake = {
        "results": [row],
        "go_q": "partial",
        "not_tactical_dispatch": True,
    }
    paths, concat = write_cinema_frames(fake, tmp_path / "frames")
    assert paths
    assert len(paths) >= 8
    assert concat.is_file()
    assert "duration" in concat.read_text(encoding="utf-8")
    with Image.open(paths[0]) as im:
        assert im.size == (1920, 1080)
    names = " ".join(p.name for p in paths)
    assert names
    # This cut stays on the sala de mando — no CLI chapter dump.
    blob = " ".join(p.read_bytes().decode("latin-1", errors="ignore") for p in paths[:3])
    assert "flags --json" not in blob


def test_run_chapter_flags_is_real_cli() -> None:
    spec = walkthrough_spec()
    flags = next(ch for ch in spec["chapters"] if ch["id"] == "cli_flags")
    row = run_chapter(flags, repo=REPO_ROOT)
    assert row["ok"] is True
    assert row["returncode"] == 0
    payload = json.loads(row["stdout"])
    assert str(payload.get("GO_Q")).lower() == "partial"
    assert payload.get("field_ops_fusion") == "ON"
    card_ch = next(ch for ch in spec["chapters"] if ch["id"] == "cli_card")
    sla = REPO_ROOT / "outputs" / "incidents" / "_sla_measure"
    if sla.is_dir():
        card_row = run_chapter(card_ch, repo=REPO_ROOT)
        assert card_row["ok"] is True
        body = json.loads(card_row["stdout"])
        dec = (body.get("summary") or {}).get("decision") or body.get("decision")
        assert dec in {"GO", "HOLD", "ABSTAIN"}
