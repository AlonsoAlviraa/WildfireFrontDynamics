#!/usr/bin/env python3
"""Prepare H1 acta draft for human third-party demo (does not flip GO_Q).

Copies ``docs/ACTA_DEMO_TERCERO_TEMPLATE.md`` → ``docs/actas/ACTA_DEMO_PENDING_HUMAN.md``
with git SHA + rails prefill. Blanks remain for human / third party.

Usage
-----
::

    python scripts/prepare_h1_acta_draft.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "ACTA_DEMO_TERCERO_TEMPLATE.md"
OUT_DEFAULT = ROOT / "docs" / "actas" / "ACTA_DEMO_PENDING_HUMAN.md"
STATUS_JSON = ROOT / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"


def git_sha(repo: Path = ROOT) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except OSError:
        pass
    return "unknown"


def load_rails(status_path: Path = STATUS_JSON) -> dict:
    if not status_path.is_file():
        return {
            "GO_MES": True,
            "GO_Q": "partial",
            "ml_product_go": False,
            "field_ops_ml_live_fusion": "OFF",
        }
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "GO_MES": True,
            "GO_Q": "partial",
            "ml_product_go": False,
            "field_ops_ml_live_fusion": "OFF",
        }
    rails = data.get("rails") or {}
    return {
        "GO_MES": rails.get("GO_MES", True),
        "GO_Q": rails.get("GO_Q", "partial"),
        "ml_product_go": rails.get("ml_product_go", False),
        "field_ops_ml_live_fusion": rails.get("field_ops_ml_live_fusion", "OFF"),
    }


def build_draft(
    template_text: str,
    *,
    sha: str,
    rails: dict,
    prepared_utc: str | None = None,
) -> str:
    """Inject prep banner + version/commit; leave human fields blank."""
    utc = prepared_utc or datetime.now(UTC).isoformat()
    banner = "\n".join(
        [
            "",
            "---",
            "",
            f"> **BORRADOR eng** preparado `{utc}` — **NO firmado** · **NO cierra GO_Q**",
            f"> **Commit:** `{sha}` · producto WildfireFrontDynamics",
            f"> **Rails prefill:** GO_MES=`{rails.get('GO_MES')}` · "
            f"GO_Q=`{rails.get('GO_Q', 'partial')}` · "
            f"ml_product_go=`{rails.get('ml_product_go', False)}` · "
            f"field_ops ML fusion=`{rails.get('field_ops_ml_live_fusion', 'OFF')}`",
            "> **Humano:** rellenar Fecha, Presentador, Tercero (externo), checklists, firmas.",
            "> **Cerrar GO_Q:** tras demo real → `python scripts/record_h1_demo_complete.py --acta PATH`",
            "> (rechaza placeholders; no inventar tercero).",
            "",
            "---",
            "",
        ]
    )

    # Prefill product + version/commit line in metadata table
    text = template_text
    text = text.replace(
        "| **Versión / commit / tag** | (ej. main @ `________` o tag `________`) |",
        f"| **Versión / commit / tag** | main @ `{sha}` (borrador eng; confirmar en demo) |",
    )
    text = text.replace(
        "| **Producto mostrado** | WildfireFrontDynamics (ops + ML lab + Decision Card) |",
        "| **Producto mostrado** | WildfireFrontDynamics (ops + ML lab + Decision Card) |",
    )

    # Ensure human blanks stay blank (explicit comments in asistentes if empty)
    # Template already has empty name cells — leave them.

    if text.lstrip().startswith("#"):
        # Insert banner after title block (first horizontal rule or after first heading para)
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[0] + "\n---\n" + banner + parts[1]
    return banner + text


def prepare(
    *,
    template: Path = TEMPLATE,
    out: Path = OUT_DEFAULT,
    force: bool = False,
) -> Path:
    if not template.is_file():
        raise FileNotFoundError(f"template missing: {template}")
    if out.is_file() and not force:
        # Refresh content but allow overwrite of eng draft by default with --force
        # Default: overwrite draft (it's always PENDING_HUMAN)
        pass
    sha = git_sha()
    rails = load_rails()
    body = build_draft(template.read_text(encoding="utf-8"), sha=sha, rails=rails)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prepare H1 acta draft (human blanks)")
    ap.add_argument(
        "--output",
        type=Path,
        default=OUT_DEFAULT,
        help="Output path (default: docs/actas/ACTA_DEMO_PENDING_HUMAN.md)",
    )
    ap.add_argument(
        "--template",
        type=Path,
        default=TEMPLATE,
        help="Template path",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing draft (default: always rewrite PENDING draft)",
    )
    args = ap.parse_args(argv)

    try:
        path = prepare(template=Path(args.template), out=Path(args.output), force=True)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rel = str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)
    print(
        json.dumps(
            {
                "ok": True,
                "draft": rel,
                "git_sha": git_sha(),
                "rails": load_rails(),
                "go_q_met": False,
                "note": "Draft only — human must fill third party + date + presenter",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
