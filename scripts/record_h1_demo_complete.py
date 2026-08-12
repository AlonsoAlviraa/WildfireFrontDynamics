#!/usr/bin/env python3
"""Record H1 / M3.2 demo complete — strict validation of real third-party acta.

Requires ``--acta PATH``. Validates non-empty, non-placeholder:
  - fecha (YYYY-MM-DD)
  - presentador
  - tercero (externo)

Only then updates ``docs/PLAN_1_MES_GRAPH_V6_STATUS.json`` for M3.2 / H1 / GO_Q.
Empty or placeholder fields → exit **2** (no status mutation).

Usage
-----
::

    python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_20260810_org.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (str(ROOT), str(_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATUS_DEFAULT = ROOT / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"

# Reuse strict validators from H3 path script
from run_h3_dry_run_path import validate_acta_fields  # noqa: E402


def load_status(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_h1_complete(
    status: dict[str, Any],
    *,
    acta_rel: str,
    fields: dict[str, Any],
    utc: str | None = None,
) -> dict[str, Any]:
    """Mutate a copy of status JSON for M3.2 / H1 / GO_Q after valid acta."""
    out = json.loads(json.dumps(status))  # deep copy via JSON
    now = utc or datetime.now(UTC).isoformat()

    gates = out.setdefault("gates", {})
    gates["M3.2"] = {
        **(gates.get("M3.2") or {}),
        "met": True,
        "status": "DONE",
        "templates_ready": True,
        "acta": acta_rel,
        "fecha": fields.get("fecha"),
        "presentador": fields.get("presentador"),
        "tercero": fields.get("tercero"),
        "recorded_at_utc": now,
    }
    gates["GO_Q"] = {
        **(gates.get("GO_Q") or {}),
        "met": True,
        "status": "complete",
        "note": "M3.2 human demo+acta recorded; M3.4 eng-filled",
        "recorded_at_utc": now,
    }

    rails = out.setdefault("rails", {})
    rails["GO_Q"] = True

    tracks = out.setdefault("tracks", {})
    h = tracks.setdefault("H", {})
    items = h.setdefault("items", {})
    items["H1_demo_acta"] = "DONE"
    evidence = h.setdefault("evidence", {})
    evidence["H1"] = (
        f"{acta_rel} (tercero={fields.get('tercero')}; "
        f"fecha={fields.get('fecha')}; presentador={fields.get('presentador')})"
    )

    out["as_of"] = now[:10] if len(now) >= 10 else now
    note = out.setdefault("h1_record", {})
    note.update(
        {
            "recorded_at_utc": now,
            "acta": acta_rel,
            "fields": {
                "fecha": fields.get("fecha"),
                "presentador": fields.get("presentador"),
                "tercero": fields.get("tercero"),
            },
        }
    )
    return out


def record(
    *,
    acta_path: Path,
    status_path: Path,
    dry_run: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Validate acta and optionally write status. Returns (exit_code, payload)."""
    if not acta_path.is_file():
        return 2, {
            "ok": False,
            "error": f"acta not found: {acta_path}",
            "exit_code": 2,
        }

    text = acta_path.read_text(encoding="utf-8")
    # Refuse obvious eng drafts by name
    if "PENDING_HUMAN" in acta_path.name.upper():
        return 2, {
            "ok": False,
            "error": "refusing PENDING_HUMAN draft — use a filled signed acta path",
            "exit_code": 2,
        }

    fields = validate_acta_fields(text)
    if not fields.get("ok"):
        return 2, {
            "ok": False,
            "error": "acta validation failed",
            "problems": fields.get("problems"),
            "fields": {
                "fecha": fields.get("fecha"),
                "presentador": fields.get("presentador"),
                "tercero": fields.get("tercero"),
            },
            "exit_code": 2,
            "go_q_met": False,
            "note": "Status NOT updated — fill fecha, presentador, tercero (no placeholders)",
        }

    if not status_path.is_file():
        return 1, {
            "ok": False,
            "error": f"status JSON missing: {status_path}",
            "exit_code": 1,
        }

    try:
        status = load_status(status_path)
    except (OSError, json.JSONDecodeError) as exc:
        return 1, {"ok": False, "error": str(exc), "exit_code": 1}

    try:
        rel = str(acta_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        rel = str(acta_path)

    new_status = apply_h1_complete(status, acta_rel=rel, fields=fields)

    if not dry_run:
        status_path.write_text(
            json.dumps(new_status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return 0, {
        "ok": True,
        "dry_run": dry_run,
        "acta": rel,
        "fields": {
            "fecha": fields.get("fecha"),
            "presentador": fields.get("presentador"),
            "tercero": fields.get("tercero"),
        },
        "updated": {
            "M3.2": new_status["gates"]["M3.2"]["status"],
            "H1_demo_acta": new_status["tracks"]["H"]["items"]["H1_demo_acta"],
            "GO_Q": new_status["rails"]["GO_Q"],
            "GO_Q_gate_met": new_status["gates"]["GO_Q"]["met"],
        },
        "status_path": str(status_path),
        "exit_code": 0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Record H1 demo complete (strict acta validation → M3.2/H1/GO_Q)"
    )
    ap.add_argument(
        "--acta",
        type=Path,
        required=True,
        help="Path to filled human acta (not PENDING_HUMAN draft)",
    )
    ap.add_argument(
        "--status",
        type=Path,
        default=STATUS_DEFAULT,
        help="Plan status JSON to update",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show planned update without writing status",
    )
    args = ap.parse_args(argv)

    code, payload = record(
        acta_path=Path(args.acta),
        status_path=Path(args.status),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
