#!/usr/bin/env python3
"""Record H1 / M3.2 demo complete — strict validation of real third-party acta.

Requires ``--acta PATH``. Validates non-empty, non-placeholder:
  - fecha (YYYY-MM-DD)
  - presentador
  - tercero (externo)

Only then updates ``docs/PLAN_1_MES_GRAPH_V6_STATUS.json`` for M3.2 / H1 / GO_Q
when that file exists. Empty or placeholder fields → exit **2** (no status mutation).
PENDING_HUMAN draft paths always exit **2**.

Usage
-----
::

    python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_20260810_org.md
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_DEFAULT = ROOT / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"
STAMP_DEFAULT = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
CURRENT_STATE_DEFAULT = ROOT / "docs" / "CURRENT_STATE.md"
SESSION_DEFAULT = ROOT / "docs" / "H1_DEMO_SESSION_READY.json"
GO_TOTAL_DEFAULT = ROOT / "docs" / "GO_TOTAL_STATUS.json"

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


def _table_value(text: str, label: str) -> str | None:
    pat = re.compile(
        rf"\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*([^|]+?)\s*\|",
        re.IGNORECASE,
    )
    m = pat.search(text)
    if not m:
        pat2 = re.compile(
            rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|",
            re.IGNORECASE,
        )
        m = pat2.search(text)
    if not m:
        return None
    return m.group(1).strip()


def _role_name(text: str, role: str) -> str | None:
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
    v_clean = re.sub(r"[_\s.]+$", "", v).strip()
    if not v_clean:
        return False
    if _PLACEHOLDER_RE.match(v_clean):
        return False
    return v_clean.lower() not in {"_", "-", "—", "–", "...", "…"}


def _looks_like_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))


def validate_acta_fields(text: str) -> dict[str, Any]:
    """Strict field check for H1 acta (self-contained; no external import)."""
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
    stamp_path: Path | None = None,
    current_state_path: Path | None = None,
    session_path: Path | None = None,
    go_total_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    """Validate acta and optionally write status. Returns (exit_code, payload)."""
    if not acta_path.is_file():
        return 2, {
            "ok": False,
            "error": f"acta not found: {acta_path}",
            "exit_code": 2,
            "go_q_met": False,
        }

    # Refuse obvious eng drafts by name (before field parse / status load)
    if "PENDING_HUMAN" in acta_path.name.upper():
        return 2, {
            "ok": False,
            "error": "refusing PENDING_HUMAN draft — use a filled signed acta path",
            "exit_code": 2,
            "go_q_met": False,
            "note": "Status NOT updated",
        }

    text = acta_path.read_text(encoding="utf-8")
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

    stamp_path = Path(stamp_path) if stamp_path is not None else STAMP_DEFAULT
    current_state_path = (
        Path(current_state_path) if current_state_path is not None else CURRENT_STATE_DEFAULT
    )
    session_path = Path(session_path) if session_path is not None else SESSION_DEFAULT
    go_total_path = Path(go_total_path) if go_total_path is not None else GO_TOTAL_DEFAULT

    if not status_path.is_file() and not stamp_path.is_file():
        return 1, {
            "ok": False,
            "error": f"status and product stamp missing: {status_path}; {stamp_path}",
            "exit_code": 1,
            "go_q_met": False,
            "note": "Acta validated but cannot record without plan status JSON",
        }

    status: dict[str, Any] | None = None
    if status_path.is_file():
        try:
            status = load_status(status_path)
        except (OSError, json.JSONDecodeError) as exc:
            return 1, {"ok": False, "error": str(exc), "exit_code": 1, "go_q_met": False}

    try:
        rel = str(acta_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        rel = str(acta_path)

    new_status = (
        apply_h1_complete(status, acta_rel=rel, fields=fields) if status is not None else None
    )

    try:
        stamp: dict[str, Any] = load_status(stamp_path) if stamp_path.is_file() else {}
        stamp["GO_Q"] = "complete"
        stamp["h1_acta"] = {
            "path": rel,
            "fecha": fields.get("fecha"),
            "presentador": fields.get("presentador"),
            "tercero": fields.get("tercero"),
        }
    except (OSError, json.JSONDecodeError) as exc:
        return 1, {"ok": False, "error": str(exc), "exit_code": 1, "go_q_met": False}

    go_mes = bool(stamp.get("GO_MES"))
    go_total_met = go_mes
    session: dict[str, Any] = load_status(session_path) if session_path.is_file() else {}
    session.update(
        {
            "go_q_met": True,
            "product_unlock": False,
            "go_total_met": go_total_met,
        }
    )
    go_total: dict[str, Any] = (
        load_status(go_total_path)
        if go_total_path.is_file()
        else {"schema": "wfd_go_total_status_v1"}
    )
    go_total.update({"met": go_total_met, "go_total": go_total_met})
    go_total["gates"] = {
        **(go_total.get("gates") or {}),
        "GO_MES": go_mes,
        "GO_Q": "complete",
    }
    go_total["go_q"] = {
        **(go_total.get("go_q") or {}),
        "met": True,
        "status": "complete",
        "h1_acta": stamp["h1_acta"],
    }
    go_total["remaining_human_steps"] = (
        []
        if go_total_met
        else [
            {
                "id": "go_mes",
                "owner": "human",
                "detail": "GO_MES remains false; GO_Q completion alone cannot close GO_TOTAL.",
            }
        ]
    )

    if not dry_run:
        if new_status is not None:
            status_path.write_text(
                json.dumps(new_status, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        stamp_path.write_text(
            json.dumps(stamp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if current_state_path.is_file():
            current = current_state_path.read_text(encoding="utf-8")
            current = re.sub(
                r"\|\s*\*\*GO_Q\*\*\s*\|[^\n]*",
                "| **GO_Q** | **complete** | H1 third-party acta registrada |",
                current,
                count=1,
            )
            current_state_path.write_text(current, encoding="utf-8")
        session_path.write_text(
            json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        go_total_path.write_text(
            json.dumps(go_total, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
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
        "go_q_met": True,
        "go_total_met": go_total_met,
        "updated": {
            "M3.2": new_status["gates"]["M3.2"]["status"] if new_status else None,
            "H1_demo_acta": (
                new_status["tracks"]["H"]["items"]["H1_demo_acta"]
                if new_status
                else None
            ),
            "GO_Q": "complete",
            "GO_Q_gate_met": True,
        },
        "status_path": str(status_path).replace("\\", "/"),
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
