"""CLI registration and dispatch for regional fire adapters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .open_if.regional import ADAPTERS, CWFIS_LAYERS, RegionalQuery, build_adapter


def _bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox values must be numeric") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be west,south,east,north")
    west, south, east, north = parts
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise argparse.ArgumentTypeError("bbox must be valid EPSG:4326 west,south,east,north")
    return west, south, east, north


def register_regional_ingest_command(commands, *, add_global_flags) -> None:
    parser = commands.add_parser(
        "ingest-regional",
        help="Ingest WFIGS, CWFIS, or INPE fire observations into an auditable index",
        description=(
            "Fetch a bounded regional fire-data snapshot, retain the raw payload, normalize "
            "geometry/time semantics, and update a deduplicated GeoJSON index."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front ingest-regional --provider wfigs --bbox=-125,32,-114,42 "
            "--start 2026-08-01 --limit 500\n"
            "  wildfire-front ingest-regional --provider cwfis --cwfis-layer activefires "
            "--limit 1000\n"
            "  wildfire-front ingest-regional --provider inpe --inpe-status active "
            "--bbox=-74,-34,-34,6 --limit 2000\n"
            "  wildfire-front ingest-regional --provider wfigs --fixture sample.geojson --json"
        ),
    )
    parser.add_argument("--provider", required=True, choices=sorted(ADAPTERS))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/open_if/regional"),
        help="Root containing one durable directory per provider",
    )
    parser.add_argument("--bbox", type=_bbox, help="EPSG:4326 west,south,east,north")
    parser.add_argument("--start", help="Inclusive observed date/time")
    parser.add_argument("--end", help="Inclusive observed date/time")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum normalized records")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=64 * 1024 * 1024,
        help="Maximum bytes per upstream response (default: 64 MiB)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        default=[],
        help="Offline payload; repeat for multiple pages/statuses",
    )
    parser.add_argument(
        "--cwfis-layer",
        choices=sorted(CWFIS_LAYERS),
        default="activefires",
    )
    parser.add_argument(
        "--inpe-status",
        choices=("active", "observation", "both"),
        default="active",
    )
    add_global_flags(parser)


def run_regional_ingest(args) -> dict[str, Any]:
    query = RegionalQuery(
        bbox=args.bbox,
        start=args.start,
        end=args.end,
        limit=args.limit,
        cwfis_layer=args.cwfis_layer,
        inpe_status=args.inpe_status,
    )
    adapter = build_adapter(args.provider, timeout=args.timeout, max_bytes=args.max_bytes)
    return adapter.ingest(
        output_root=args.output_root,
        query=query,
        fixtures=list(args.fixture or []) or None,
    )


def format_regional_result(result: dict[str, Any]) -> str:
    counts = result.get("counts") or {}
    return "\n".join(
        [
            f"source: {result.get('source_id')}",
            f"normalized: {counts.get('normalized')} (events={counts.get('events')})",
            f"candidate_progression_labels: {counts.get('candidate_progression_labels')}",
            f"index_total: {counts.get('index_total')}",
            f"manifest: {result.get('manifest')}",
            f"index: {result.get('index')}",
            "honesty: " + json.dumps(result.get("honesty") or {}, ensure_ascii=False),
        ]
    )
