#!/usr/bin/env python3
"""Record written CONAF cession → lab_ok_conaf=true (evidence required).

Does NOT invent cession. Requires a local evidence file (PDF/MD/TXT/image)
plus signer metadata. Updates send_status.json rails.lab_ok_conaf and rights docs.

  python scripts/record_conaf_cession.py \\
    --evidence docs/data_campaigns/conaf_send/CESSION/oficio.pdf \\
    --signer "CONAF OIRS" --by AlonsoAlviraa \\
    --summary "Cesión de perímetros 2023-2024 uso lab"

  python scripts/record_conaf_cession.py --revoke --by AlonsoAlviraa

Exit codes:
  0 — recorded (or revoked)
  1 — missing evidence / invalid
  2 — usage
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "docs" / "data_campaigns" / "conaf_send"
STATUS_SCHEMA = "wfd_conaf_send_status_v1"
CESSION_SCHEMA = "wfd_conaf_cession_v1"
ALLOWED_EVIDENCE_SUFFIX = {".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".json"}


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_status(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "send_status.json"
    if not path.is_file():
        raise FileNotFoundError(f"send_status.json missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_status(package_dir: Path, doc: dict[str, Any]) -> None:
    (package_dir / "send_status.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )


def patch_rights_lab_ok(lab_ok: bool) -> None:
    """Best-effort update of CONAF row notes in RIGHTS.md (non-fatal)."""
    rights = ROOT / "docs" / "data_campaigns" / "LATAM_AU_RIGHTS.md"
    if not rights.is_file():
        return
    text = rights.read_text(encoding="utf-8")
    marker = "<!-- CONAF_LAB_OK_AUTO -->"
    block = (
        f"{marker}\n"
        f"- **lab_ok_conaf:** `{'true' if lab_ok else 'false'}` "
        f"(auto from `scripts/record_conaf_cession.py`, {utc_now()})\n"
    )
    if marker in text:
        # replace from marker to next blank line or end of auto block
        pre, rest = text.split(marker, 1)
        # drop old auto line(s) until blank or non-list after
        lines = rest.splitlines()
        # first line may be empty after marker on same section
        drop = 0
        for i, ln in enumerate(lines):
            if i == 0 and ln.strip() == "":
                drop = 1
                continue
            if ln.startswith("- **lab_ok_conaf:**"):
                drop = i + 1
                continue
            break
        rest2 = "\n".join(lines[drop:])
        text = pre + block + rest2
        if not text.endswith("\n"):
            text += "\n"
    else:
        text = text.rstrip() + "\n\n## CONAF cession gate\n\n" + block + "\n"
    rights.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record CONAF written cession → lab_ok_conaf")
    ap.add_argument("--package-dir", type=Path, default=PACKAGE_DIR)
    ap.add_argument("--evidence", type=Path, default=None, help="Path to written cession evidence")
    ap.add_argument("--signer", default="", help="Who signed/issued the cession (e.g. CONAF OIRS)")
    ap.add_argument("--by", default="", help="Who recorded this in the repo")
    ap.add_argument("--summary", default="", help="Short cession summary")
    ap.add_argument("--ref", default="", help="Oficio / ticket / folio reference")
    ap.add_argument("--revoke", action="store_true", help="Revoke lab_ok_conaf")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    package_dir = Path(args.package_dir)
    if not package_dir.is_dir():
        print(f"error: package dir missing: {package_dir}", file=sys.stderr)
        return 1

    try:
        status = load_status(package_dir)
    except (OSError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if status.get("schema") != STATUS_SCHEMA:
        print(f"error: bad status schema {status.get('schema')}", file=sys.stderr)
        return 1

    if args.revoke:
        by = (args.by or "").strip()
        if not by:
            print("error: --revoke requires --by", file=sys.stderr)
            return 2
        status["cession"] = {
            "schema": CESSION_SCHEMA,
            "revoked": True,
            "revoked_utc": utc_now(),
            "revoked_by": by,
            "prior": status.get("cession"),
        }
        rails = dict(status.get("rails") or {})
        rails["lab_ok_conaf"] = False
        status["rails"] = rails
        status["as_of_utc"] = utc_now()
        notes = list(status.get("notes") or [])
        notes.append(f"lab_ok_conaf revoked by {by} at {utc_now()}")
        status["notes"] = notes
        if not args.dry_run:
            write_status(package_dir, status)
            patch_rights_lab_ok(False)
        print(json.dumps({"ok": True, "lab_ok_conaf": False, "revoked": True}, indent=2))
        return 0

    evidence = Path(args.evidence) if args.evidence else None
    signer = (args.signer or "").strip()
    by = (args.by or "").strip()
    if evidence is None or not signer or not by:
        print(
            "error: --evidence, --signer, and --by are required (or use --revoke)",
            file=sys.stderr,
        )
        return 2
    if not evidence.is_file():
        print(f"error: evidence file missing: {evidence}", file=sys.stderr)
        return 1
    if evidence.suffix.lower() not in ALLOWED_EVIDENCE_SUFFIX:
        print(
            f"error: evidence suffix not allowed: {evidence.suffix} "
            f"(allowed: {sorted(ALLOWED_EVIDENCE_SUFFIX)})",
            file=sys.stderr,
        )
        return 1
    if evidence.stat().st_size < 16:
        print("error: evidence file too small", file=sys.stderr)
        return 1

    # Prefer storing a copy under package CESSION/
    cession_dir = package_dir / "CESSION"
    cession_dir.mkdir(parents=True, exist_ok=True)
    dest = cession_dir / evidence.name
    if evidence.resolve() != dest.resolve():
        dest.write_bytes(evidence.read_bytes())
    digest = sha256_file(dest)
    rel = (
        str(dest.relative_to(ROOT)).replace("\\", "/")
        if dest.is_relative_to(ROOT)
        else str(dest)
    )

    cession = {
        "schema": CESSION_SCHEMA,
        "recorded_utc": utc_now(),
        "recorded_by": by,
        "signer": signer,
        "ref": (args.ref or "").strip() or None,
        "summary": (args.summary or "").strip()
        or "Written CONAF cession for lab use of perimeter geometries",
        "evidence_rel": rel,
        "evidence_sha256": digest,
        "evidence_bytes": dest.stat().st_size,
        "revoked": False,
        "lab_ok_conaf": True,
        "not_claims": [
            "not automatic product GO",
            "not field_ops fusion change",
            "not FREEZE lift",
            "lab use only as stated in request",
        ],
    }

    status["cession"] = cession
    rails = dict(status.get("rails") or {})
    rails["lab_ok_conaf"] = True
    rails.setdefault("go_q", "partial")
    rails.setdefault("freeze_intact", True)
    status["rails"] = rails
    status["as_of_utc"] = utc_now()
    notes = list(status.get("notes") or [])
    notes.append(
        f"lab_ok_conaf=true after written cession recorded by {by} "
        f"(signer={signer}, sha256={digest[:12]}…)"
    )
    status["notes"] = notes

    if not args.dry_run:
        write_status(package_dir, status)
        # sidecar cession record
        (cession_dir / "cession_record.json").write_text(
            json.dumps(cession, indent=2) + "\n", encoding="utf-8"
        )
        patch_rights_lab_ok(True)

    print(
        json.dumps(
            {
                "ok": True,
                "lab_ok_conaf": True,
                "evidence_rel": rel,
                "evidence_sha256": digest,
                "signer": signer,
                "recorded_by": by,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
