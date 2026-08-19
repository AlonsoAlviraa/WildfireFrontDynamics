#!/usr/bin/env python3
"""Inventory and probe open-if agency/event URLs (LATAM + AU campaign F0).

Reads a source catalog (JSON) or candidate CSV, optionally checks HTTP reachability,
and writes a git-friendly inventory CSV (+ optional JSON). Does not download
multi-GB rasters. Does not invent metrics, licenses, or GO gates.

Exit codes:
  0 — inventory written; if --check, at least one URL is reachable
  1 — hard failure (missing input, bad path, unreadable catalog, write error)
  2 — --check requested and zero URLs reachable (or no checkable URLs)
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "docs" / "data_campaigns" / "LATAM_AU_SOURCE_CATALOG.json"
DEFAULT_OUT = ROOT / "docs" / "data_campaigns" / "LATAM_AU_URL_INVENTORY.csv"

USER_AGENT = "WildfireFrontDynamics-open-if-inventory/1.0 (+research; no bulk scrape)"
BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "metadata.google.internal",
    }
)
ALLOWED_SCHEMES = frozenset({"http", "https"})

INVENTORY_FIELDS = [
    "source_id",
    "name",
    "country_or_region",
    "role",
    "url",
    "license_class",
    "access",
    "lab_ok_provisional",
    "status",
    "http_code",
    "final_url",
    "elapsed_ms",
    "error",
    "checked_at_utc",
    "notes",
]


@dataclass
class UrlRecord:
    source_id: str
    name: str
    country_or_region: str
    role: str
    url: str
    license_class: str
    access: str
    lab_ok_provisional: str
    notes: str


def is_safe_public_url(url: str) -> tuple[bool, str]:
    """Reject non-http(s), empty hosts, loopback/private IPs, and blocked hostnames.

    Uses parsed hostname equality (not naive startswith) so spoofed names like
    127.0.0.1.attacker.example are not treated as loopback, and real loopback is blocked.
    """
    raw = (url or "").strip()
    if not raw:
        return False, "empty_url"
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"bad_scheme:{parsed.scheme or 'none'}"
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False, "missing_host"
    if host in BLOCKED_HOSTS:
        return False, f"blocked_host:{host}"
    if host.endswith(".localhost") or host.endswith(".local"):
        return False, f"blocked_suffix:{host}"
    # Exact IP forms only (hostname that merely starts with 127. is not an IP)
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True, ""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False, f"blocked_ip:{host}"
    return True, ""


def load_catalog_json(path: Path) -> list[UrlRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError(f"catalog missing sources list: {path}")
    out: list[UrlRecord] = []
    for i, row in enumerate(sources):
        if not isinstance(row, dict):
            raise ValueError(f"sources[{i}] is not an object")
        url = str(row.get("url") or "").strip()
        sid = str(row.get("source_id") or f"row_{i}").strip()
        out.append(
            UrlRecord(
                source_id=sid,
                name=str(row.get("name") or sid),
                country_or_region=str(row.get("country_or_region") or ""),
                role=str(row.get("role") or ""),
                url=url,
                license_class=str(row.get("license_class") or ""),
                access=str(row.get("access") or ""),
                lab_ok_provisional=str(row.get("lab_ok_provisional", "")),
                notes=str(row.get("notes") or ""),
            )
        )
    return out


def load_candidates_csv(path: Path) -> list[UrlRecord]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        rows = list(reader)
    out: list[UrlRecord] = []
    for _i, row in enumerate(rows):
        # Skip comment-like rows
        eid = (row.get("event_id") or "").strip()
        if not eid or eid.startswith("#"):
            continue
        url = (row.get("url") or "").strip()
        out.append(
            UrlRecord(
                source_id=eid,
                name=eid,
                country_or_region=str(row.get("country") or ""),
                role=str(row.get("source_index") or row.get("class") or ""),
                url=url,
                license_class=str(row.get("license") or ""),
                access="",
                lab_ok_provisional="",
                notes=str(row.get("notes") or ""),
            )
        )
    return out


def load_records(path: Path) -> list[UrlRecord]:
    if not path.is_file():
        raise FileNotFoundError(f"catalog not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_catalog_json(path)
    if suffix == ".csv":
        return load_candidates_csv(path)
    raise ValueError(f"unsupported catalog type (use .json or .csv): {path}")


def probe_url(url: str, timeout: float) -> dict[str, Any]:
    """HEAD then GET fallback. Returns status fields; never raises for network."""
    safe, reason = is_safe_public_url(url)
    if not safe:
        return {
            "status": "rejected",
            "http_code": "",
            "final_url": "",
            "elapsed_ms": 0,
            "error": reason,
        }

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    t0 = time.perf_counter()
    last_error = ""
    for method in ("HEAD", "GET"):
        req = Request(url, method=method, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — host validated above
                code = int(getattr(resp, "status", None) or resp.getcode() or 0)
                final = str(resp.geturl() or url)
                # Drain a tiny body on GET to complete response without bulk download
                if method == "GET":
                    resp.read(4096)
                elapsed = int((time.perf_counter() - t0) * 1000)
                if 200 <= code < 400:
                    return {
                        "status": "reachable",
                        "http_code": str(code),
                        "final_url": final,
                        "elapsed_ms": elapsed,
                        "error": "",
                    }
                return {
                    "status": "unreachable",
                    "http_code": str(code),
                    "final_url": final,
                    "elapsed_ms": elapsed,
                    "error": f"http_{code}",
                }
        except HTTPError as exc:
            code = int(exc.code or 0)
            elapsed = int((time.perf_counter() - t0) * 1000)
            # Some servers reject HEAD; try GET
            if method == "HEAD" and code in {403, 405, 501}:
                last_error = f"HEAD_http_{code}"
                continue
            if 200 <= code < 400:
                return {
                    "status": "reachable",
                    "http_code": str(code),
                    "final_url": url,
                    "elapsed_ms": elapsed,
                    "error": "",
                }
            return {
                "status": "unreachable",
                "http_code": str(code),
                "final_url": url,
                "elapsed_ms": elapsed,
                "error": f"http_{code}",
            }
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}:{exc}"
            if method == "HEAD":
                continue
            elapsed = int((time.perf_counter() - t0) * 1000)
            return {
                "status": "unreachable",
                "http_code": "",
                "final_url": "",
                "elapsed_ms": elapsed,
                "error": last_error[:500],
            }
    elapsed = int((time.perf_counter() - t0) * 1000)
    return {
        "status": "unreachable",
        "http_code": "",
        "final_url": "",
        "elapsed_ms": elapsed,
        "error": last_error[:500] or "probe_failed",
    }


def inventory_rows(
    records: list[UrlRecord],
    *,
    check: bool,
    timeout: float,
) -> list[dict[str, str]]:
    checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rows: list[dict[str, str]] = []
    for rec in records:
        base = {
            "source_id": rec.source_id,
            "name": rec.name,
            "country_or_region": rec.country_or_region,
            "role": rec.role,
            "url": rec.url,
            "license_class": rec.license_class,
            "access": rec.access,
            "lab_ok_provisional": rec.lab_ok_provisional,
            "notes": rec.notes,
            "checked_at_utc": checked_at if check else "",
        }
        if not check:
            rows.append(
                {
                    **base,
                    "status": "not_checked",
                    "http_code": "",
                    "final_url": "",
                    "elapsed_ms": "",
                    "error": "",
                }
            )
            continue
        result = probe_url(rec.url, timeout=timeout)
        rows.append(
            {
                **base,
                "status": str(result["status"]),
                "http_code": str(result["http_code"]),
                "final_url": str(result["final_url"]),
                "elapsed_ms": str(result["elapsed_ms"]),
                "error": str(result["error"]),
            }
        )
    return rows


def write_inventory_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in INVENTORY_FIELDS})


def write_inventory_json(rows: list[dict[str, str]], path: Path, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "wfd_open_if_url_inventory_v1",
        "meta": meta,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def summarize(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        st = row.get("status") or "unknown"
        counts[st] = counts.get(st, 0) + 1
    return counts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Inventory open-if source URLs and optionally probe reachability."
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"JSON catalog or candidates CSV (default: {DEFAULT_CATALOG})",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output inventory CSV (default: {DEFAULT_OUT})",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON inventory path",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Probe each URL (HEAD/GET). Without this, status=not_checked.",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Per-request timeout seconds (default 15)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, only process first N records (debug)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog: Path = args.catalog
    try:
        records = load_records(catalog)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: failed to load catalog: {exc}", file=sys.stderr)
        return 1

    if args.limit and args.limit > 0:
        records = records[: args.limit]

    if not records:
        print("error: catalog has zero usable URL records", file=sys.stderr)
        return 1

    try:
        rows = inventory_rows(records, check=bool(args.check), timeout=float(args.timeout))
        write_inventory_csv(rows, args.output)
        counts = summarize(rows)
        meta = {
            "catalog": str(catalog),
            "output": str(args.output),
            "check": bool(args.check),
            "n_records": len(rows),
            "status_counts": counts,
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "honesty": "status from live probe or not_checked; no IoU/grade invented",
        }
        if args.json_out:
            write_inventory_json(rows, args.json_out, meta)
    except OSError as exc:
        print(f"error: write failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"wrote {args.output} n={len(rows)} check={bool(args.check)} counts={counts}",
        flush=True,
    )

    if args.check:
        reachable = counts.get("reachable", 0)
        if reachable < 1:
            print(
                "error: --check requested but zero URLs reachable "
                f"(counts={counts})",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
