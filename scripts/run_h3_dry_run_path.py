#!/usr/bin/env python3
"""H3 full path dry-run: teach → show → cheatsheet → demo-third-party → report.

Engineering path only. Does **not** complete H3 human attestation or flip GO_Q.

Usage
-----
::

    python scripts/run_h3_dry_run_path.py
    make h3-dry-run
    wildfire-front dry-run-h3
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DEFAULT = ROOT / "outputs" / "demo_third_party"
CHEATSHEET = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
ACTAS_DIR = ROOT / "docs" / "actas"
PENDING_ACTA_NAME = "ACTA_DEMO_PENDING_HUMAN.md"
SCHEMA = "wfd_h3_dry_run_v1"

# Placeholders that never count as a real human-signed third-party acta.
_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"|yyyy-mm-dd"
    r"|________+"
    r"|todo|tbd|n/?a|pending|placeholder|nombre|name|org"
    r"|externo|third.?party"
    r")$",
    re.IGNORECASE,
)


def resolve_repo_root() -> Path:
    return ROOT


def human_signed_acta_exists(actas_dir: Path | None = None) -> bool:
    """True only if a non-draft acta under docs/actas/ has non-placeholder fields."""
    d = actas_dir if actas_dir is not None else ACTAS_DIR
    if not d.is_dir():
        return False
    for path in sorted(d.glob("ACTA_DEMO_*.md")):
        if path.name == PENDING_ACTA_NAME:
            continue
        if path.name.upper().endswith("_PENDING_HUMAN.MD"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if validate_acta_fields(text).get("ok"):
            return True
    return False


def validate_acta_fields(text: str) -> dict[str, Any]:
    """Strict field check for H1 acta (also used by record_h1_demo_complete)."""
    date = _table_value(text, "Fecha")
    presenter = _role_name(text, "Presentador")
    third = _role_name(text, "Tercero")

    problems: list[str] = []
    if not _is_real_value(date) or not _looks_like_date(date or ""):
        problems.append("fecha missing or placeholder (need YYYY-MM-DD)")
    if not _is_real_value(presenter):
        problems.append("presentador missing or placeholder")
    if not _is_real_value(third):
        problems.append("tercero (externo) missing or placeholder")

    return {
        "ok": len(problems) == 0,
        "fecha": date,
        "presentador": presenter,
        "tercero": third,
        "problems": problems,
    }


def _table_value(text: str, label: str) -> str | None:
    """Extract markdown table cell after **Label**."""
    # | **Fecha** | YYYY-MM-DD |
    pat = re.compile(
        rf"\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*([^|]+?)\s*\|",
        re.IGNORECASE,
    )
    m = pat.search(text)
    if not m:
        # also allow without bold
        pat2 = re.compile(
            rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|",
            re.IGNORECASE,
        )
        m = pat2.search(text)
    if not m:
        return None
    return m.group(1).strip()


def _role_name(text: str, role: str) -> str | None:
    """Extract Nombre from asistentes table row starting with role."""
    # | **Presentador** | Alice | Org | |
    # | **Tercero (externo)** | Bob | Org | |
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        head = re.sub(r"\*+", "", cells[0]).strip().lower()
        role_l = role.lower()
        if role_l == "tercero":
            if not head.startswith("tercero"):
                continue
        elif role_l not in head:
            continue
        if len(cells) < 2:
            return None
        return cells[1].strip() or None
    return None


def _is_real_value(value: str | None) -> bool:
    if value is None:
        return False
    v = value.strip()
    if not v:
        return False
    # strip common fill hints
    v_clean = re.sub(r"[_\s.]+$", "", v).strip()
    if not v_clean:
        return False
    if _PLACEHOLDER_RE.match(v_clean):
        return False
    if set(v_clean) <= {"_", "-", ".", " "}:
        return False
    return not ("____" in v or "ej." in v.lower() or "ejemplo" in v.lower())


def _looks_like_date(value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()))


def run_teach_step(
    *,
    quiet: bool = True,
    runner: Callable[[], tuple[int, str]] | None = None,
) -> dict[str, Any]:
    """Step 1: teach path; ok if exit 0 and stdout has Acto / acts 1-4."""
    if runner is not None:
        rc, stdout = runner()
    else:
        from wildfire_front.cli_teach import run_teach

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run_teach(SimpleNamespace(act=None, json=False, verbose=False, quiet=quiet))
        stdout = buf.getvalue()

    has_acto = bool(re.search(r"Acto\s*[1-4]", stdout, re.IGNORECASE))
    has_acts = (
        all(re.search(rf"(?:Acto\s*{n}|act\s*{n})", stdout, re.IGNORECASE) for n in (1, 2, 3, 4))
        or has_acto
    )
    ok = rc == 0 and (has_acto or has_acts)
    return {
        "id": "teach",
        "ok": ok,
        "rc": rc,
        "detail": "Acto/acts present" if has_acto or has_acts else "missing Acto markers",
        "stdout_tail": stdout[-2000:],
    }


def run_show_step(
    *,
    runner: Callable[[], tuple[int, dict[str, Any] | None, str]] | None = None,
) -> dict[str, Any]:
    """Step 2: show --json; assert GO_Q not true, fusion OFF."""
    if runner is not None:
        rc, data, raw = runner()
    else:
        from wildfire_front.cli_teach import run_show

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run_show(SimpleNamespace(json=True, verbose=False, quiet=False, open=False))
        raw = buf.getvalue()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None

    gates = (data or {}).get("gates") or {}
    go_q = gates.get("GO_Q")
    fusion = gates.get("field_ops_ml_live_fusion")
    go_q_not_true = go_q is not True and str(go_q).lower() not in ("true", "complete", "1")
    fusion_off = str(fusion).upper() in ("OFF", "FALSE", "0") or fusion is False
    ok = rc == 0 and data is not None and go_q_not_true and fusion_off
    return {
        "id": "show",
        "ok": ok,
        "rc": rc,
        "detail": {
            "GO_Q": go_q,
            "field_ops_ml_live_fusion": fusion,
            "go_q_not_true": go_q_not_true,
            "fusion_off": fusion_off,
        },
        "gates": {
            "GO_MES": gates.get("GO_MES"),
            "GO_Q": go_q if go_q is not None else "partial",
            "field_ops_ml_live_fusion": fusion if fusion is not None else "OFF",
        },
        "stdout_tail": raw[-1500:] if isinstance(raw, str) else "",
    }


def run_cheatsheet_step(path: Path | None = None) -> dict[str, Any]:
    """Step 3: cheatsheet file must exist."""
    p = path if path is not None else CHEATSHEET
    ok = p.is_file()
    rel = str(p.relative_to(ROOT)).replace("\\", "/") if p.is_relative_to(ROOT) else str(p)
    return {
        "id": "cheatsheet",
        "ok": ok,
        "rc": 0 if ok else 1,
        "detail": rel,
        "path": rel,
    }


def run_demo_third_party_step(
    *,
    no_zip: bool = False,
    skip_build: bool = False,
    do_replay: bool = True,
    out: Path | None = None,
    runner: Callable[[], tuple[int, dict[str, Any] | None]] | None = None,
) -> dict[str, Any]:
    """Step 4: demo-third-party (default: full build + replay)."""
    if runner is not None:
        rc, payload = runner()
    else:
        from wildfire_front.cli_teach import run_demo_third_party

        out_dir = out if out is not None else OUT_DEFAULT
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run_demo_third_party(
                SimpleNamespace(
                    json=True,
                    quiet=False,
                    verbose=False,
                    skip_build=skip_build,
                    replay=do_replay,
                    no_zip=no_zip,
                    output=out_dir,
                    dist=ROOT / "dist",
                )
            )
        raw = buf.getvalue()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw_tail": raw[-1500:]}

    ok = rc == 0
    return {
        "id": "demo_third_party",
        "ok": ok,
        "rc": rc,
        "detail": {
            "build": (payload or {}).get("build"),
            "replay_ok": (payload or {}).get("replay_ok"),
            "decision": (payload or {}).get("decision"),
            "out": (payload or {}).get("out"),
        },
        "payload": payload,
    }


def aggregate_report(
    steps: list[dict[str, Any]],
    *,
    gates: dict[str, Any] | None = None,
    human_attestation_pending: bool = True,
    h1_status: str = "NOT_STARTED",
    utc: str | None = None,
) -> dict[str, Any]:
    """Build wfd_h3_dry_run_v1 report from step results (pure / testable)."""
    by_id = {s["id"]: s for s in steps}
    eng_ok = all(bool(s.get("ok")) for s in steps)
    g = gates or {}
    if not g and "show" in by_id:
        g = (by_id["show"].get("gates") or {}).copy()
    g.setdefault("GO_MES", True)
    g.setdefault("GO_Q", "partial")
    g.setdefault("field_ops_ml_live_fusion", "OFF")

    # Honesty rails absolute: never claim GO_Q met from eng path
    go_q_met = False
    pending = True if human_attestation_pending else human_attestation_pending
    # Always true until real human file exists — caller must pass human_attestation_pending
    if human_attestation_pending:
        pending = True

    return {
        "schema": SCHEMA,
        "utc": utc or datetime.now(UTC).isoformat(),
        "steps": [
            {
                "id": s["id"],
                "ok": bool(s.get("ok")),
                "rc": s.get("rc"),
                "detail": s.get("detail"),
            }
            for s in steps
        ],
        "gates": {
            "GO_MES": g.get("GO_MES"),
            "GO_Q": g.get("GO_Q", "partial"),
            "field_ops_ml_live_fusion": g.get("field_ops_ml_live_fusion", "OFF"),
        },
        "h3_eng_path_ok": eng_ok,
        "h3_human_attestation_pending": pending,
        "h1_status": h1_status,
        "go_q_met": go_q_met,
        "next": (
            "Human: walk cheatsheet 12 min + fill acta with real third party"
            if pending
            else "Human attestation on file; still verify GO_Q checklist before claim"
        ),
        "rails": {
            "field_ops_ml_live_fusion": "OFF",
            "no_invented_third_party": True,
            "no_GO_Q_claim_from_eng": True,
        },
    }


def render_md(report: dict[str, Any]) -> str:
    steps = report.get("steps") or []
    lines = [
        "# H3 dry-run path — eng report",
        "",
        f"_UTC: {report.get('utc')}_",
        f"_Schema: `{report.get('schema')}`_",
        "",
        f"- **h3_eng_path_ok:** `{report.get('h3_eng_path_ok')}`",
        f"- **h3_human_attestation_pending:** `{report.get('h3_human_attestation_pending')}`",
        f"- **h1_status:** `{report.get('h1_status')}`",
        f"- **go_q_met:** `{report.get('go_q_met')}`  ← eng path **never** flips this",
        "",
        "## Gates (from show)",
        "",
        "```json",
        json.dumps(report.get("gates") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Steps",
        "",
        "| id | ok | rc | detail |",
        "|----|:--:|:--:|--------|",
    ]
    for s in steps:
        detail = s.get("detail")
        if isinstance(detail, dict):
            detail_s = json.dumps(detail, ensure_ascii=False)[:120]
        else:
            detail_s = str(detail)[:120]
        lines.append(f"| `{s.get('id')}` | `{s.get('ok')}` | `{s.get('rc')}` | {detail_s} |")
    lines.extend(
        [
            "",
            "## Next",
            "",
            str(report.get("next") or ""),
            "",
            "## Honesty",
            "",
            "- H3 eng path green ≠ H3 human attestation.",
            "- H1 / M3.2 / GO_Q require real third-party demo + signed acta.",
            "- field_ops ML fusion remains **OFF**.",
            "",
            "```json",
            json.dumps(report.get("rails") or {}, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "H3_DRY_RUN_REPORT.md"
    json_path = out_dir / "H3_DRY_RUN_REPORT.json"
    json_path.write_text(
        json.dumps(report, indent=2, default=str, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_md(report), encoding="utf-8")
    return md_path, json_path


def run_path(
    *,
    no_zip: bool = False,
    skip_build: bool = False,
    full_demo: bool = False,
    out_dir: Path | None = None,
    teach_runner: Callable[[], tuple[int, str]] | None = None,
    show_runner: Callable[[], tuple[int, dict[str, Any] | None, str]] | None = None,
    demo_runner: Callable[[], tuple[int, dict[str, Any] | None]] | None = None,
) -> tuple[dict[str, Any], int]:
    """Execute ordered H3 path; return (report, exit_code)."""
    out = out_dir if out_dir is not None else OUT_DEFAULT
    steps: list[dict[str, Any]] = []

    teach = run_teach_step(quiet=True, runner=teach_runner)
    steps.append(teach)

    show = run_show_step(runner=show_runner)
    steps.append(show)

    cheat = run_cheatsheet_step()
    steps.append(cheat)

    demo = run_demo_third_party_step(
        no_zip=no_zip,
        skip_build=skip_build,
        do_replay=True,
        out=out,
        runner=demo_runner,
    )
    steps.append(demo)

    if full_demo:
        # Optional heavier steps — non-fatal for eng_path if missing tooling
        full_step = _run_full_demo_optional()
        steps.append(full_step)

    # Human attestation: always pending unless a real signed acta exists
    signed = human_signed_acta_exists()
    pending = not signed  # design: true until human file exists

    h1 = "NOT_STARTED"
    if signed:
        h1 = "ACTA_ON_FILE"
    elif (ACTAS_DIR / PENDING_ACTA_NAME).is_file():
        h1 = "DRAFT_PENDING_HUMAN"

    report = aggregate_report(
        steps,
        gates=show.get("gates"),
        human_attestation_pending=pending,
        h1_status=h1,
    )
    # Absolute honesty: force these even if someone mutates aggregation
    report["h3_human_attestation_pending"] = bool(pending)
    if pending:
        report["h3_human_attestation_pending"] = True
    report["go_q_met"] = False

    write_report(report, out)
    exit_code = 0 if report.get("h3_eng_path_ok") else 2
    return report, exit_code


def _run_full_demo_optional() -> dict[str, Any]:
    """Optional multi-ccaa / pilot honesty presence check (no rebuild by default)."""
    multi = ROOT / "outputs" / "demo_multi_ccaa" / "index.html"
    pilot = ROOT / "outputs" / "pilot_honesty_card" / "index.html"
    ok = multi.is_file() or pilot.is_file()
    return {
        "id": "full_demo_artifacts",
        "ok": ok,
        "rc": 0 if ok else 1,
        "detail": {
            "demo_multi_ccaa": multi.is_file(),
            "pilot_honesty": pilot.is_file(),
            "note": "optional --full-demo presence only (no rebuild)",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="H3 full path dry-run: teach → show → cheatsheet → demo-third-party"
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DEFAULT,
        help="Report + pack directory (default: outputs/demo_third_party)",
    )
    ap.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip zip when building pack (faster; still full replay)",
    )
    ap.add_argument(
        "--skip-build",
        action="store_true",
        help="Replay existing pack only (skip rebuild)",
    )
    ap.add_argument(
        "--full-demo",
        action="store_true",
        help="Also check multi-CCAA / pilot honesty artifacts (default OFF)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print full report JSON to stdout",
    )
    args = ap.parse_args(argv)

    report, code = run_path(
        no_zip=bool(args.no_zip),
        skip_build=bool(args.skip_build),
        full_demo=bool(args.full_demo),
        out_dir=Path(args.out_dir),
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    else:
        print(
            json.dumps(
                {
                    "schema": report.get("schema"),
                    "h3_eng_path_ok": report.get("h3_eng_path_ok"),
                    "h3_human_attestation_pending": report.get("h3_human_attestation_pending"),
                    "go_q_met": report.get("go_q_met"),
                    "h1_status": report.get("h1_status"),
                    "gates": report.get("gates"),
                    "report_md": "outputs/demo_third_party/H3_DRY_RUN_REPORT.md",
                    "report_json": "outputs/demo_third_party/H3_DRY_RUN_REPORT.json",
                    "next": report.get("next"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
