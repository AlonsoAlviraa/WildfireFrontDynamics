#!/usr/bin/env python3
"""E5 — Open pack freshness_score + content checksum/version.

Adds or reports:

* ``freshness_score`` ∈ [0, 1] from ``built_at_utc`` age (and optional
  product timestamps)
* ``content_checksum`` SHA-256 over stable pack files
* ``pack_version`` / ``freshness_audited_at_utc``

Usage::

    python scripts/audit_open_pack_freshness.py --pack outputs/open_if/emsr578
    python scripts/audit_open_pack_freshness.py --pack outputs/open_if/emsr578 --write
    python scripts/audit_open_pack_freshness.py --all-under outputs/open_if --write

Does not invent areas or activation dates. Fails soft if built_at missing
(freshness_score=null, reason recorded).
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

# Product files hashed when present (stable surface; skip huge raw zips).
# Intentional: do NOT include manifest.json — apply_to_manifest writes
# freshness_* / content_checksum into it, which would invalidate the checksum
# (self-referential). Checksum lives in freshness_audit.json + manifest pointer.
HASH_CANDIDATES = (
    "scorecard_pista_b.json",
    "scorecard_and_industrial.json",
    "scorecard_ext_industrial.json",
    "metrics_o2.json",
    "timeline_perimeters.geojson",
    "firms_metrics.json",
    "dnbr_summary.json",
    "operator_brief_open_if.md",
)

# Half-life days: score = 0.5 ** (age_days / half_life)
DEFAULT_HALF_LIFE_DAYS = 30.0
# Soft floor: packs older than this get score capped discussion only
STALE_DAYS = 90.0


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def freshness_score_from_age(
    age_days: float,
    *,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Exponential decay in [0, 1]; age 0 → 1.0."""
    if age_days < 0:
        age_days = 0.0
    if half_life_days <= 0:
        return 0.0
    score = 0.5 ** (age_days / half_life_days)
    return max(0.0, min(1.0, float(score)))


def audit_pack(
    pack_dir: Path,
    *,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    pack_dir = Path(pack_dir)
    now = now or datetime.now(UTC)
    man_path = pack_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if man_path.is_file():
        try:
            raw = json.loads(man_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                manifest = raw
        except (OSError, json.JSONDecodeError):
            manifest = {}

    built = _parse_iso(manifest.get("built_at_utc") or manifest.get("built_at"))
    age_days: float | None
    score: float | None
    reason: str
    if built is None:
        age_days = None
        score = None
        reason = "missing_built_at_utc"
    else:
        age_days = max(0.0, (now - built).total_seconds() / 86400.0)
        score = freshness_score_from_age(age_days, half_life_days=half_life_days)
        reason = "ok"
        if age_days >= STALE_DAYS:
            reason = "stale_over_90d"

    file_hashes: dict[str, str] = {}
    for name in HASH_CANDIDATES:
        p = pack_dir / name
        if p.is_file():
            file_hashes[name] = _sha256_file(p)
    # Also hash a few vectors if small set
    vectors = pack_dir / "vectors"
    if vectors.is_dir():
        geojsons = sorted(vectors.glob("*.geojson"))[:12]
        for g in geojsons:
            rel = f"vectors/{g.name}"
            file_hashes[rel] = _sha256_file(g)

    content_checksum = hashlib.sha256(
        json.dumps(file_hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()

    pack_version = manifest.get("pack_version") or manifest.get("product") or "open_if_pack_v1"
    activation = manifest.get("activation") or pack_dir.name

    report = {
        "schema": "open_pack_freshness_audit_v1",
        "pack_dir": str(pack_dir).replace("\\", "/"),
        "pack_id": pack_dir.name,
        "activation": activation,
        "audited_at_utc": now.isoformat(),
        "built_at_utc": built.isoformat() if built else None,
        "age_days": round(age_days, 3) if age_days is not None else None,
        "freshness_score": round(score, 4) if score is not None else None,
        "freshness_half_life_days": half_life_days,
        "freshness_reason": reason,
        "pack_version": pack_version,
        "content_checksum": content_checksum,
        "files_sha256": file_hashes,
        "n_files_hashed": len(file_hashes),
        "stale_threshold_days": STALE_DAYS,
    }
    return report


def apply_to_manifest(pack_dir: Path, report: dict[str, Any]) -> Path:
    """Write freshness fields into manifest.json (+ sidecar audit).

    ``content_checksum`` covers product files only (not this manifest). Re-running
    ``audit_pack`` after ``--write`` must yield the same checksum.
    """
    pack_dir = Path(pack_dir)
    man_path = pack_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if man_path.is_file():
        try:
            raw = json.loads(man_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                manifest = raw
        except (OSError, json.JSONDecodeError):
            manifest = {}

    manifest["freshness_score"] = report.get("freshness_score")
    manifest["freshness_reason"] = report.get("freshness_reason")
    manifest["freshness_audited_at_utc"] = report.get("audited_at_utc")
    # Pointer only — integrity truth is files_sha256 in freshness_audit.json
    manifest["content_checksum"] = report.get("content_checksum")
    manifest["content_checksum_scope"] = "product_files_excluding_manifest"
    if "pack_version" not in manifest or not manifest.get("pack_version"):
        manifest["pack_version"] = report.get("pack_version")
    manifest["age_days_at_audit"] = report.get("age_days")

    man_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    # Sidecar is the authoritative audit record (includes files_sha256 map).
    audit_path = pack_dir / "freshness_audit.json"
    sidecar = dict(report)
    sidecar["content_checksum_scope"] = "product_files_excluding_manifest"
    audit_path.write_text(json.dumps(sidecar, indent=2, default=str), encoding="utf-8")
    return man_path


def _discover_packs(root: Path) -> list[Path]:
    root = Path(root)
    if not root.is_dir():
        return []
    packs: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "manifest.json").is_file():
            packs.append(child)
    return packs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit open pack freshness + checksum (E5).")
    parser.add_argument("--pack", type=Path, default=None, help="Single open pack directory")
    parser.add_argument(
        "--all-under",
        type=Path,
        default=None,
        help="Audit every child dir with manifest.json",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write freshness_* fields into manifest.json + freshness_audit.json",
    )
    parser.add_argument(
        "--half-life-days",
        type=float,
        default=DEFAULT_HALF_LIFE_DAYS,
        help="Exponential half-life for freshness_score (default 30)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write combined report JSON",
    )
    args = parser.parse_args(argv)

    packs: list[Path] = []
    if args.pack:
        packs.append(Path(args.pack))
    if args.all_under:
        packs.extend(_discover_packs(args.all_under))
    if not packs:
        # Default: one well-known pack if present
        default = ROOT / "outputs" / "open_if" / "emsr578"
        if default.is_dir():
            packs = [default]
        else:
            print("error: provide --pack or --all-under", file=sys.stderr)
            return 1

    reports: list[dict[str, Any]] = []
    for p in packs:
        if not p.is_dir():
            print(f"skip (missing): {p}", file=sys.stderr)
            continue
        rep = audit_pack(p, half_life_days=float(args.half_life_days))
        if args.write:
            apply_to_manifest(p, rep)
            print(f"wrote freshness → {p / 'manifest.json'}")
        score = rep.get("freshness_score")
        score_s = f"{score:.4f}" if isinstance(score, float) else "null"
        print(
            f"{rep['pack_id']}: freshness_score={score_s} "
            f"age_days={rep.get('age_days')} reason={rep.get('freshness_reason')} "
            f"checksum={str(rep.get('content_checksum'))[:12]}…"
        )
        reports.append(rep)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "open_pack_freshness_batch_v1",
            "n": len(reports),
            "reports": reports,
        }
        args.json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"wrote {args.json_out}")

    return 0 if reports else 1


if __name__ == "__main__":
    raise SystemExit(main())
