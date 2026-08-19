"""Operator walkthrough: real CLI/app/fire run + storyboard + video frames.

Records the product path (not scripts/ ML/campaign). Does not close GO_Q.
Not tactical dispatch. Not a signed H1 acta.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from wildfire_front.product.decide_service import REPO_ROOT

WALKTHROUGH_SCHEMA = "wfd_operator_walkthrough_v1"
DEFAULT_FIRE = "_sla_measure"
DEFAULT_WORK = Path("outputs") / "incidents" / DEFAULT_FIRE
FORBIDDEN_CLAIMS = (
    "go_q complete",
    "acta firmada",
    "hellín",
    "hellin",
    "cardoso",
    "rcda",
    "caldor",
    "0.308",
    "es despacho táctico",
    "tactical dispatch order",
)

# Chaptered operator path — CLI + app + one fire e2e.
_CHAPTERS: tuple[dict[str, Any], ...] = (
    {
        "id": "cli_commands",
        "surface": "cli",
        "title": "CLI — mapa de comandos",
        "argv": ["commands", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_flags",
        "surface": "cli",
        "title": "CLI — flags (GO_Q partial, fusion ON)",
        "argv": ["flags", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_catalog",
        "surface": "cli",
        "title": "CLI — catálogo (holdout_only no es producto)",
        "argv": ["catalog", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_policies",
        "surface": "cli",
        "title": "CLI — políticas de decisión",
        "argv": ["decide", "--list-policies", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "fire_doctor",
        "surface": "fire_e2e",
        "title": "Fuego e2e — incident doctor",
        "argv": [
            "incident",
            "doctor",
            "--inbox",
            "{work_dir}/inbox",
            "--work-dir",
            "{work_dir}",
            "--json",
        ],
        "timeout_s": 60,
    },
    {
        "id": "fire_status",
        "surface": "fire_e2e",
        "title": "Fuego e2e — incident status",
        "argv": ["incident", "status", "--work-dir", "{work_dir}", "--json"],
        "timeout_s": 60,
    },
    {
        "id": "fire_decide",
        "surface": "fire_e2e",
        "title": "Fuego e2e — decide field_ops",
        "argv": [
            "decide",
            "--work-dir",
            "{work_dir}",
            "--policy",
            "field_ops",
            "--event-id",
            "WALKTHROUGH_SLA",
            "--json",
        ],
        "timeout_s": 90,
    },
    {
        "id": "cli_card",
        "surface": "cli",
        "title": "CLI — última Decision Card",
        "argv": ["card", "--work-dir", "{work_dir}", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_snapshot",
        "surface": "cli",
        "title": "CLI — snapshot (cifras citadas, no save)",
        "argv": ["snapshot", "--work-dir", "{work_dir}", "--no-save", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_compare",
        "surface": "cli",
        "title": "CLI — compare (alerta local, no SMS)",
        "argv": ["compare", "--work-dir", "{work_dir}", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "cli_export_acta",
        "surface": "cli",
        "title": "CLI — export-acta (forense, no acta H1)",
        "argv": ["export-acta", "--work-dir", "{work_dir}", "--json"],
        "timeout_s": 60,
    },
    {
        "id": "cli_replay",
        "surface": "cli",
        "title": "CLI — replay-decide (consistencia, no crypto)",
        "argv": ["replay-decide", "--work-dir", "{work_dir}", "--json"],
        "timeout_s": 60,
    },
    {
        "id": "cli_operator",
        "surface": "cli",
        "title": "CLI — operator hub (GO_Q sigue partial)",
        "argv": ["operator", "--json"],
        "timeout_s": 30,
    },
    {
        "id": "app_list",
        "surface": "app",
        "title": "App — listar fuegos",
        "argv": ["app", "--list-fires", "--json"],
        "timeout_s": 60,
    },
    {
        "id": "app_build",
        "surface": "app",
        "title": "App — SPA _sla_measure (Estado/Decidir/Acta)",
        "argv": [
            "app",
            "--fire",
            DEFAULT_FIRE,
            "--output",
            "{out_dir}/spa",
            "--json",
        ],
        "timeout_s": 90,
    },
)


def walkthrough_spec(*, work_dir: Path | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    """Declarative chapter list. All product argv are ``python -m wildfire_front``."""
    wd = Path(work_dir or DEFAULT_WORK)
    out = Path(out_dir or (Path("outputs") / "walkthrough"))
    chapters: list[dict[str, Any]] = []
    for raw in _CHAPTERS:
        argv = [str(wd) if token == "{work_dir}" else str(out) if token == "{out_dir}" else token
                for token in raw["argv"]]
        argv = [
            part.replace("{work_dir}", str(wd)).replace("{out_dir}", str(out))
            for part in argv
        ]
        chapters.append(
            {
                "id": raw["id"],
                "surface": raw["surface"],
                "title": raw["title"],
                "entry": "python -m wildfire_front",
                "argv": argv,
                "timeout_s": int(raw["timeout_s"]),
            }
        )
    return {
        "schema": WALKTHROUGH_SCHEMA,
        "title": "WFD operator walkthrough — CLI + app + fire e2e",
        "fire_id": DEFAULT_FIRE,
        "work_dir": str(wd),
        "not_tactical_dispatch": True,
        "go_q": "partial",
        "go_q_complete": False,
        "signed_acta": False,
        "not_h1_acta": True,
        "note": (
            "Operator product path only. Not every scripts/ job. "
            "fusion ON ≠ despacho. GO_Q stays partial."
        ),
        "chapters": chapters,
        "surfaces": ["cli", "app", "fire_e2e"],
    }


def _expand(token: str, *, work_dir: Path, out_dir: Path) -> str:
    return token.replace("{work_dir}", str(work_dir)).replace("{out_dir}", str(out_dir))


def command_lines(spec: dict[str, Any] | None = None) -> list[list[str]]:
    data = spec or walkthrough_spec()
    lines: list[list[str]] = []
    for ch in data["chapters"]:
        lines.append([sys.executable, "-m", "wildfire_front", *list(ch["argv"])])
    return lines


def _extract_decision(text: str) -> str | None:
    blob = text.strip()
    if not blob:
        return None
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        for token in ("ABSTAIN", "HOLD", "GO"):
            if f'"decision": "{token}"' in blob or f"decision: {token}" in blob:
                return token
        return None
    if isinstance(data, dict):
        dec = data.get("decision")
        if dec in {"GO", "HOLD", "ABSTAIN"}:
            return str(dec)
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        dec2 = summary.get("decision")
        if dec2 in {"GO", "HOLD", "ABSTAIN"}:
            return str(dec2)
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        dec3 = result.get("decision")
        if dec3 in {"GO", "HOLD", "ABSTAIN"}:
            return str(dec3)
    return None


def _forbidden_hits(text: str) -> list[str]:
    low = text.lower()
    return [item for item in FORBIDDEN_CLAIMS if item in low]


def run_chapter(
    chapter: dict[str, Any],
    *,
    repo: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    argv = [sys.executable, "-m", "wildfire_front", *list(chapter["argv"])]
    run_env = dict(os.environ if env is None else env)
    run_env["PYTHONPATH"] = str(repo)
    started = time.perf_counter()
    proc = subprocess.run(
        argv,
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=run_env,
        timeout=int(chapter.get("timeout_s") or 60),
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return {
        "id": chapter["id"],
        "surface": chapter["surface"],
        "title": chapter["title"],
        "cmd": " ".join(["python", "-m", "wildfire_front", *chapter["argv"]]),
        "argv": argv,
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": stdout,
        "stderr": stderr[-4000:],
        "decision": _extract_decision(stdout),
        "ok": proc.returncode == 0,
    }


def run_walkthrough(
    *,
    repo: Path | None = None,
    work_dir: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo or REPO_ROOT)
    spec = walkthrough_spec(work_dir=work_dir, out_dir=out_dir)
    results: list[dict[str, Any]] = []
    for chapter in spec["chapters"]:
        results.append(run_chapter(chapter, repo=root))
    decisions = [row["decision"] for row in results if row.get("decision")]
    joined = "\n".join(row.get("stdout") or "" for row in results)
    return {
        "schema": WALKTHROUGH_SCHEMA,
        "ok": all(row["ok"] for row in results),
        "spec": spec,
        "results": results,
        "decisions": decisions,
        "not_tactical_dispatch": True,
        "go_q": "partial",
        "go_q_complete": False,
        "forbidden_hits": _forbidden_hits(joined + json.dumps(spec, default=str)),
    }


def storyboard_markdown(run: dict[str, Any]) -> str:
    spec = run.get("spec") or walkthrough_spec()
    lines = [
        "# WFD operator walkthrough — CLI + app + fire e2e",
        "",
        "Not tactical dispatch. GO_Q **partial**. Not a signed H1 acta.",
        "fusion ON ≠ despacho. Instantánea/compare are local (no SMS).",
        "Film 1080p: sala de mando (SEGUIR / ESPERAR / SE CALLA) + CLI real.",
        "Flujo operario: abrir app --serve · leer qué hay/falta · Meter fotos · Decidir/Acta.",
        "",
        f"Fire: `{spec.get('fire_id')}` · work_dir `{spec.get('work_dir')}`",
        "",
        "| # | Surface | Chapter | Command | Decision |",
        "|---|---------|---------|---------|----------|",
    ]
    for i, row in enumerate(run.get("results") or spec.get("chapters") or [], start=1):
        title = row.get("title") or ""
        surface = row.get("surface") or ""
        cmd = row.get("cmd") or (
            "python -m wildfire_front " + " ".join(row.get("argv") or [])
        )
        dec = row.get("decision") or "—"
        lines.append(f"| {i} | {surface} | {title} | `{cmd}` | {dec} |")
    lines.extend(
        [
            "",
            "## Rails",
            "",
            "- GO_Q partial (not complete)",
            "- not_tactical_dispatch: true",
            "- field_ops fusion ON ≠ dispatch",
            "- export-acta is forensic bundle, not a third-party signed acta",
            "- catalog holdout_only is not a product score",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int, limit: int = 28) -> list[str]:
    out: list[str] = []
    for raw in text.replace("\r", "").splitlines() or [""]:
        line = raw if raw else " "
        while len(line) > width:
            out.append(line[:width])
            line = line[width:]
            if len(out) >= limit:
                return out
        out.append(line)
        if len(out) >= limit:
            break
    return out[:limit]


def render_chapter_frame(
    row: dict[str, Any],
    *,
    index: int,
    total: int,
    size: tuple[int, int] = (1280, 720),
) -> Any:
    from PIL import Image, ImageDraw, ImageFont

    w, h = size
    img = Image.new("RGB", (w, h), (11, 18, 32))
    draw = ImageDraw.Draw(img)
    try:
        font_lg = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 28)
        font_md = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)
        font_sm = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 15)
    except OSError:
        font_lg = ImageFont.load_default()
        font_md = font_lg
        font_sm = font_lg
    draw.rectangle((0, 0, w, 56), fill=(15, 23, 42))
    header = f"WFD walkthrough  {index}/{total}  ·  CLI + app + fire e2e"
    draw.text((24, 16), header, fill=(14, 165, 233), font=font_md)
    title = str(row.get("title") or row.get("id") or "")
    draw.text((24, 76), title, fill=(249, 250, 251), font=font_lg)
    cmd = str(row.get("cmd") or "")
    y = 122
    for line in _wrap(cmd, 92, 3):
        draw.text((24, y), line, fill=(56, 189, 248), font=font_sm)
        y += 22
    dec = row.get("decision")
    rc = row.get("returncode")
    meta = f"decision={dec or '—'}   exit={rc}   surface={row.get('surface')}"
    draw.text((24, y + 8), meta, fill=(34, 197, 94) if dec else (156, 163, 175), font=font_md)
    y += 44
    excerpt = (row.get("stdout") or "")[:1800]
    for line in _wrap(excerpt, 108, 22):
        draw.text((24, y), line, fill=(209, 213, 219), font=font_sm)
        y += 18
        if y > h - 70:
            break
    draw.rectangle((0, h - 48, w, h), fill=(15, 23, 42))
    footer = "GO_Q partial  ·  not tactical dispatch  ·  fusion ON ≠ despacho  ·  not H1 acta"
    draw.text((24, h - 32), footer, fill=(156, 163, 175), font=font_sm)
    return img


def write_frames(run: dict[str, Any], frames_dir: Path, *, hold: int = 6) -> list[Path]:
    """Write cinematic 1080p stills (concat list) plus a fallback numbered sequence."""
    from wildfire_front.product.walkthrough_cinema import capture_spa_shots, write_cinema_frames

    frames_dir.mkdir(parents=True, exist_ok=True)
    spa_dir = frames_dir.parent / "spa"
    shot_dir = frames_dir.parent / "shots"
    spa_shots: list[Path] = []
    if (spa_dir / "index.html").is_file():
        try:
            spa_shots = capture_spa_shots(spa_dir, shot_dir)
        except OSError:
            spa_shots = []
    paths, _concat = write_cinema_frames(run, frames_dir, spa_shots=spa_shots)
    if paths:
        return paths
    # Fallback: original JSON-card frames if cinema cannot write.
    rows = list(run.get("results") or [])
    out: list[Path] = []
    n = max(len(rows), 1)
    idx = 0
    for i, row in enumerate(rows, start=1):
        img = render_chapter_frame(row, index=i, total=n)
        for _ in range(max(1, hold)):
            dest = frames_dir / f"frame_{idx:04d}.png"
            img.save(dest)
            out.append(dest)
            idx += 1
    return out


def encode_video(frames_dir: Path, dest: Path, *, fps: int = 2) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    concat = frames_dir / "concat.txt"
    if concat.is_file():
        from wildfire_front.product.walkthrough_cinema import encode_concat

        return encode_concat(concat, dest)
    pattern = str(frames_dir / "frame_%04d.png")
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        pattern,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-3000:],
        "path": str(dest),
        "bytes": dest.stat().st_size if dest.is_file() else 0,
    }


def probe_video(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    data: dict[str, Any] = {}
    if proc.returncode == 0 and proc.stdout:
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {"raw": proc.stdout}
    st = path.stat() if path.is_file() else None
    fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
    duration = None
    try:
        duration = float(fmt.get("duration")) if fmt.get("duration") is not None else None
    except (TypeError, ValueError):
        duration = None
    return {
        "ok": proc.returncode == 0 and path.is_file(),
        "path": str(path),
        "bytes": st.st_size if st else 0,
        "duration_s": duration,
        "format_name": fmt.get("format_name"),
        "ffprobe_returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-800:],
    }
