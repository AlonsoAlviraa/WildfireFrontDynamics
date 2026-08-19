#!/usr/bin/env python3
"""Gate for CEMS commercial rehost / product packaging.

Fails closed when packaging claims commercial rehost without human sign-off.

  python scripts/check_cems_commercial_rehost.py
  python scripts/check_cems_commercial_rehost.py --require-commercial-rehost
  python scripts/check_cems_commercial_rehost.py --attempt-cdn-rehost

Exit codes:
  0 — gate honest; no blocked rehost path requested (or flag true + signed)
  1 — missing gate / commercial path without OK / silent claim refused
  2 — usage
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = ROOT / "docs" / "data_campaigns" / "cems_commercial_rehost_gate.json"
GATE_SCHEMA = "wfd_cems_commercial_rehost_gate_v1"


def load_gate(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, f"missing_gate:{path}"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"bad_gate_json:{exc}"
    if doc.get("schema") != GATE_SCHEMA:
        return None, f"bad_schema:{doc.get('schema')}"
    if "commercial_rehost_ok" not in doc:
        return None, "missing_commercial_rehost_ok"
    return doc, "ok"


def commercial_ok(doc: dict[str, Any]) -> bool:
    return doc.get("commercial_rehost_ok") is True


def validate_signoff(doc: dict[str, Any]) -> list[str]:
    """If flag true, require human sign fields (no silent true)."""
    errs: list[str] = []
    if commercial_ok(doc):
        if not doc.get("signer"):
            errs.append("commercial_rehost_ok_true_requires_signer")
        if not doc.get("signed_utc"):
            errs.append("commercial_rehost_ok_true_requires_signed_utc")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CEMS commercial rehost gate")
    ap.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    ap.add_argument(
        "--require-commercial-rehost",
        action="store_true",
        help="Product packaging path: exit 1 unless commercial_rehost_ok=true",
    )
    ap.add_argument(
        "--attempt-cdn-rehost",
        action="store_true",
        help="Simulate CDN rehost attempt; fail closed if flag false",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print gate snapshot JSON",
    )
    args = ap.parse_args(argv)

    doc, reason = load_gate(Path(args.gate))
    if doc is None:
        print(f"error: {reason}", file=sys.stderr)
        return 1

    sign_errs = validate_signoff(doc)
    if sign_errs:
        for e in sign_errs:
            print(f"error: {e}", file=sys.stderr)
        return 1

    ok_flag = commercial_ok(doc)
    snapshot = {
        "ok": True,
        "gate": str(
            Path(args.gate).relative_to(ROOT)
            if Path(args.gate).is_relative_to(ROOT)
            else args.gate
        ).replace("\\", "/"),
        "commercial_rehost_ok": ok_flag,
        "lab_ok_provisional": bool(doc.get("lab_ok_provisional")),
        "signer": doc.get("signer"),
        "require_commercial_rehost": bool(args.require_commercial_rehost),
        "attempt_cdn_rehost": bool(args.attempt_cdn_rehost),
        "message": (
            "commercial rehost allowed"
            if ok_flag
            else "commercial_rehost_ok=false; lab only; no silent commercial claim"
        ),
    }

    # Packaging / CDN paths fail closed without flag.
    if args.require_commercial_rehost and not ok_flag:
        snapshot["ok"] = False
        snapshot["error"] = "commercial_rehost_blocked"
        print(json.dumps(snapshot, indent=2))
        print(
            "error: product packaging requires commercial_rehost_ok=true "
            "(human/legal sign-off in gate JSON)",
            file=sys.stderr,
        )
        return 1

    if args.attempt_cdn_rehost and not ok_flag:
        snapshot["ok"] = False
        snapshot["error"] = "cdn_rehost_blocked"
        print(json.dumps(snapshot, indent=2))
        print(
            "error: refusing CDN rehost while commercial_rehost_ok=false",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
