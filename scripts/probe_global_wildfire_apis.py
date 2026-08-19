#!/usr/bin/env python3
"""Safely smoke-probe the public endpoints in the global wildfire API registry.

The probe is deliberately small and sequential.  It never bulk-downloads datasets,
follows a fixed allow-list from the registry, caps sampled response bytes, and skips
credentialed endpoints unless the named environment variable is present.

Examples:
    python scripts/probe_global_wildfire_apis.py
    python scripts/probe_global_wildfire_apis.py --priority P0 --priority P1
    python scripts/probe_global_wildfire_apis.py --source global_nasa_eonet_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "research" / "global_wildfire_api_registry_2026.json"
DEFAULT_OUTPUT = ROOT / "docs" / "GLOBAL_WILDFIRE_API_PROBE_2026-08-18.json"
USER_AGENT = "WildfireFrontDynamics-api-audit/1.0 (+research; bounded-smoke-probe)"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_summary(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8", "replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"json_valid": False}
    summary: dict[str, Any] = {"json_valid": True, "json_type": type(value).__name__}
    if isinstance(value, dict):
        summary["top_level_keys"] = sorted(str(k) for k in value)[:30]
        for key in ("features", "collections", "events", "results", "items"):
            if isinstance(value.get(key), list):
                summary[f"n_{key}_sample"] = len(value[key])
    elif isinstance(value, list):
        summary["n_items_sample"] = len(value)
    return summary


def _build_request(probe: dict[str, Any]) -> tuple[urllib.request.Request | None, str | None]:
    url = str(probe["url"])
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    auth_env = probe.get("auth_env")
    if probe.get("auth_required") and auth_env:
        token = os.environ.get(str(auth_env))
        if not token:
            return None, f"missing_env:{auth_env}"
        header = str(probe.get("auth_header") or "Authorization")
        headers[header] = token if header != "Authorization" else f"Bearer {token}"
    elif probe.get("auth_required"):
        return None, "credentialed_probe_not_configured"
    method = str(probe.get("method") or "GET").upper()
    return urllib.request.Request(url, headers=headers, method=method), None


def probe_source(source: dict[str, Any], *, timeout: float, max_bytes: int) -> dict[str, Any]:
    started = time.perf_counter()
    base: dict[str, Any] = {
        "id": source["id"],
        "name": source["name"],
        "priority": source["priority"],
        "checked_at_utc": _utc_now(),
    }

    def done(result: dict[str, Any]) -> dict[str, Any]:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result

    probe = source.get("probe")
    if not isinstance(probe, dict):
        return done({**base, "status": "SKIP", "reason": "no_safe_probe_declared"})
    request, skip_reason = _build_request(probe)
    if request is None:
        return done({**base, "status": "SKIP", "reason": skip_reason, "url": probe["url"]})

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            sample = raw[:max_bytes]
            content_type = response.headers.get("Content-Type", "")
            result = {
                **base,
                "status": "PASS",
                "url": probe["url"],
                "http_status": int(response.status),
                "final_url": response.geturl(),
                "content_type": content_type,
                "bytes_sampled": len(sample),
                "sample_truncated": truncated,
                "sample_sha256": hashlib.sha256(sample).hexdigest(),
            }
            if "json" in content_type.lower() or probe.get("expected") == "json":
                result.update(_json_summary(sample))
            return done(result)
    except urllib.error.HTTPError as exc:
        sample = exc.read(min(max_bytes, 8192))
        return done({
            **base,
            "status": "FAIL",
            "url": probe["url"],
            "http_status": int(exc.code),
            "reason": str(exc.reason),
            "error_sample_sha256": hashlib.sha256(sample).hexdigest(),
        })
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return done({**base, "status": "FAIL", "url": probe["url"], "reason": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--priority", action="append", choices=["P0", "P1", "P2", "P3"])
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-bytes", type=int, default=262_144)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    wanted_priorities = set(args.priority or [])
    wanted_sources = set(args.source or [])
    selected = []
    for source in registry["sources"]:
        if wanted_priorities and source["priority"] not in wanted_priorities:
            continue
        if wanted_sources and source["id"] not in wanted_sources:
            continue
        selected.append(source)

    rows: list[dict[str, Any]] = []
    for index, source in enumerate(selected):
        row = probe_source(source, timeout=args.timeout, max_bytes=args.max_bytes)
        rows.append(row)
        print(
            f"{row['status']:4} {source['id']}"
            + (f" HTTP {row['http_status']}" if "http_status" in row else "")
            + (f" ({row['reason']})" if row.get("reason") else ""),
            flush=True,
        )
        if index + 1 < len(selected):
            time.sleep(max(0.0, args.interval))

    counts = {state: sum(row["status"] == state for row in rows) for state in ("PASS", "FAIL", "SKIP")}
    report = {
        "schema": "wfd_global_wildfire_api_probe_v1",
        "generated_at_utc": _utc_now(),
        "registry": str(args.registry.relative_to(ROOT)),
        "selection": {
            "priorities": sorted(wanted_priorities),
            "sources": sorted(wanted_sources),
            "n_selected": len(selected),
        },
        "safety": {
            "sequential": True,
            "interval_seconds": args.interval,
            "timeout_seconds": args.timeout,
            "max_response_bytes": args.max_bytes,
            "bulk_downloads": False,
            "secrets_persisted": False,
        },
        "counts": counts,
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0 if counts["FAIL"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
