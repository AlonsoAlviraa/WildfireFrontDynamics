"""CLI surface for fire-status map (local layers + optional FIRMS NRT)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .cli_report import print_error, print_json
from .map_status import build_fire_status_map_payload, write_fire_status_map


def register_map_commands(commands: Any, *, add_global_flags) -> None:
    """Register ``map`` top-level command on the root parser."""
    m = commands.add_parser(
        "map",
        help="Fire-status map (local fronts/envelopes + optional FIRMS NRT hotspots)",
        description=(
            "Build an interactive Leaflet map of fire-status geometry.\n"
            "  · Local: incident outbox / GeoJSON (main_front, fronts, envelopes)\n"
            "  · External NRT: NASA FIRMS (MAP_KEY area API or public Europe 24h CSV)\n"
            "Offline works without keys; connectivity status is always explicit.\n"
            "Honesty: hotspots ≠ official burned area; NOT tactical dispatch; "
            "field_ops ML fusion OFF."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front map --work-dir outputs/incidents/_sla_measure --no-live\n"
            "  wildfire-front map --geojson outputs/demo_v2/fronts.geojson --no-live\n"
            "  wildfire-front map --bbox=-3.5,40.7,-2.7,41.4 --output outputs/maps/mierla\n"
            "  wildfire-front map --west -3.5 --south 40.7 --east -2.7 --north 41.4\n"
            "  wildfire-front map --lat 40.9 --lon -3.1 --radius-km 40\n"
            "  set FIRMS_MAP_KEY=...  # optional free key from NASA FIRMS\n"
        ),
    )
    m.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Incident work-dir (reads outbox/*.geojson when present)",
    )
    m.add_argument(
        "--geojson",
        type=Path,
        action="append",
        default=None,
        metavar="PATH",
        help="Extra local GeoJSON layer (repeatable)",
    )
    m.add_argument(
        "--bbox",
        default=None,
        metavar="W,S,E,N",
        help=(
            "FIRMS bbox west,south,east,north (degrees). "
            "Use equals form when west is negative: --bbox=-3.5,40.7,-2.7,41.4"
        ),
    )
    m.add_argument("--west", type=float, default=None, help="BBox west (alt to --bbox)")
    m.add_argument("--south", type=float, default=None, help="BBox south")
    m.add_argument("--east", type=float, default=None, help="BBox east")
    m.add_argument("--north", type=float, default=None, help="BBox north")
    m.add_argument("--lat", type=float, default=None, help="Center latitude (with --lon)")
    m.add_argument("--lon", type=float, default=None, help="Center longitude (with --lat)")
    m.add_argument(
        "--radius-km",
        type=float,
        default=50.0,
        help="Half-size of bbox when using --lat/--lon (default 50 km approx)",
    )
    m.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/maps/fire_status"),
        help="Output directory for HTML+JSON (default: outputs/maps/fire_status)",
    )
    m.add_argument(
        "--no-live",
        action="store_true",
        help="Skip network FIRMS fetch (local layers only; connectivity=skipped)",
    )
    m.add_argument(
        "--fixture-csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="Load FIRMS CSV from disk instead of network (tests/offline demos)",
    )
    m.add_argument(
        "--day-range",
        type=int,
        default=1,
        help="FIRMS area API day range 1–10 (default 1; ignored for public Europe CSV)",
    )
    m.add_argument(
        "--open",
        action="store_true",
        help="Attempt to open HTML in the default browser",
    )
    m.add_argument(
        "--title",
        default="WFD · estado del incendio (mapa)",
        help="HTML title",
    )
    add_global_flags(m)


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be W,S,E,N (4 comma-separated floats)")
    w, s, e, n = (float(x) for x in parts)
    return (w, s, e, n)


def _bbox_from_center(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    # rough degrees: 1 deg lat ~ 111 km; lon scales with cos(lat)
    import math

    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def run_map(args: argparse.Namespace) -> int:
    """Build map payload, write HTML/JSON, print human or JSON summary."""
    try:
        bbox = _parse_bbox(args.bbox)
    except ValueError as exc:
        print_error(str(exc), hint="example: --bbox=-3.5,40.7,-2.7,41.4  or  --west -3.5 --south 40.7 --east -2.7 --north 41.4")
        return 2

    if bbox is None and all(
        getattr(args, k, None) is not None for k in ("west", "south", "east", "north")
    ):
        bbox = (float(args.west), float(args.south), float(args.east), float(args.north))
    elif any(getattr(args, k, None) is not None for k in ("west", "south", "east", "north")):
        print_error(
            "partial bbox corners: provide all of --west --south --east --north",
            hint="--west -3.5 --south 40.7 --east -2.7 --north 41.4",
        )
        return 2

    lat = args.lat
    lon = args.lon
    center = None
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            print_error("both --lat and --lon are required together", hint="--lat 40.9 --lon -3.1")
            return 2
        center = (float(lon), float(lat))
        if bbox is None:
            bbox = _bbox_from_center(float(lat), float(lon), float(args.radius_km or 50.0))

    work_dir = args.work_dir
    geojson = list(args.geojson or [])
    live = not bool(args.no_live)
    fixture = args.fixture_csv

    # Usage guidance when nothing local and no live intent / center
    if work_dir is None and not geojson and bbox is None and center is None and fixture is None:
        print_error(
            "map needs local geometry and/or a bbox/center for FIRMS",
            hint=(
                "wildfire-front map --work-dir outputs/incidents/_sla_measure --no-live\n"
                "  or: wildfire-front map --geojson path/to/fronts.geojson --no-live\n"
                "  or: wildfire-front map --lat 40.9 --lon -3.1 --radius-km 40"
            ),
        )
        return 2

    payload = build_fire_status_map_payload(
        work_dir=work_dir,
        geojson_paths=geojson or None,
        bbox=bbox,
        center=center,
        live=live,
        day_range=int(args.day_range or 1),
        fixture_csv=fixture,
        title=str(args.title or "WFD · estado del incendio (mapa)"),
    )

    out_dir = Path(args.output or "outputs/maps/fire_status")
    paths = write_fire_status_map(payload, out_dir)
    payload = dict(payload)
    payload["artifacts"] = {"html": str(paths["html"]), "json": str(paths["json"])}

    if bool(args.json):
        print_json(payload)
    else:
        conn = (payload.get("connectivity") or {}).get("status")
        firms = payload.get("firms") or {}
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  WFD · MAPA estado del incendio  (no despacho táctico)   ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print("")
        print(f"  connectivity:  {conn}")
        print(f"  firms mode:    {firms.get('source_mode')}  ·  hotspots={firms.get('n_hotspots')}")
        print(f"  local layers:  {(payload.get('connectivity') or {}).get('local_layers')}")
        print(f"  rails:         field_ops fusion={(payload.get('rails') or {}).get('field_ops_ml_live_fusion')}")
        print(f"  HTML:          {paths['html']}")
        print(f"  JSON:          {paths['json']}")
        print("")
        for row in payload.get("layer_summary") or []:
            print(
                f"  · {row.get('name')}: n={row.get('n_features')} "
                f"source={row.get('source')}"
            )
        print("")
        print(f"  ⚠  {payload.get('disclaimer')}")
        if firms.get("reasons"):
            print(f"  notes: {', '.join(str(r) for r in firms.get('reasons')[:4])}")
        print("")

    if bool(args.open):
        try:
            import webbrowser

            webbrowser.open(paths["html"].resolve().as_uri())
        except Exception as exc:  # pragma: no cover - platform dependent
            if not bool(args.quiet):
                print_error(f"could not open browser: {exc}", hint=str(paths["html"]))

    return 0
