#!/usr/bin/env python3
"""Write a briefing KML 2.2 with TimeSpan for Earth Pro (Tobarra + envelopes).

Reads the Pablo/GEACAM drop (18:30 and 21:43 CEST on 2024-08-02) and optional
WFD envelope GeoJSON. Does **not** overwrite source KMZ/KML or official MET JSON.

  python scripts/export_tobarra_timespan_kml.py
  python scripts/export_tobarra_timespan_kml.py --out outputs/tobarra_pablo_perimeters/tobarra_earth_pro_timespan.kml

Filename HHMM is CEST (UTC+2). KML TimeSpan is UTC Z.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.kml_timespan import (  # noqa: E402
    NOT_CLAIMS,
    ROLE_ENVELOPE,
    ROLE_PERIMETER,
    TIMEZONE_CONVENTION,
    build_briefing_kml,
    iter_placemarks,
    load_envelope_geojson,
    timed_rings_from_ops,
)
from wildfire_front.ops_perimeter import parse_ops_perimeter  # noqa: E402

DEFAULT_DROP = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
DEFAULT_KMZ = (
    "2024020124_TOBARRA_20240802_1830.kmz",
    "2024020124_TOBARRA_20240802_2143.kmz",
)
DEFAULT_ENVELOPE = ROOT / "outputs" / "fuel_stack" / "tobarra" / "envelope_v3_hybrid.geojson"
DEFAULT_OUT = ROOT / "outputs" / "tobarra_pablo_perimeters" / "tobarra_earth_pro_timespan.kml"
OFFICIAL_MET_JSON = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MISSING = 3
EXIT_REFUSED = 4


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dest_refused(path: Path) -> str | None:
    try:
        resolved = path.resolve()
    except OSError:
        return "unresolvable_out"
    if resolved == OFFICIAL_MET_JSON.resolve():
        return "refuses_official_met_json"
    try:
        resolved.relative_to(DEFAULT_DROP.resolve())
    except ValueError:
        return None
    return "refuses_overwrite_source_drop"


def resolve_perimeter_paths(drop: Path) -> list[Path]:
    found: list[Path] = []
    for name in DEFAULT_KMZ:
        kmz = drop / name
        kml = drop / name.replace(".kmz", ".kml")
        if kmz.is_file():
            found.append(kmz)
        elif kml.is_file():
            found.append(kml)
    return found


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Tobarra Earth Pro TimeSpan KML (briefing only)")
    ap.add_argument("--drop", type=Path, default=DEFAULT_DROP)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--envelope",
        type=Path,
        default=None,
        help="Envelope FeatureCollection GeoJSON (WGS84 or UTM). Default: hybrid on disk if present.",
    )
    ap.add_argument("--no-envelope", action="store_true", help="Perímetros only")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    drop = Path(args.drop)
    out = Path(args.out)
    reason = dest_refused(out)
    if reason:
        print(f"error: {reason} ({out})", file=sys.stderr)
        return EXIT_REFUSED

    paths = resolve_perimeter_paths(drop)
    if len(paths) < 2:
        print(f"error: need two perímetro files under {drop}", file=sys.stderr)
        return EXIT_MISSING

    perims = [parse_ops_perimeter(p, root=ROOT) for p in paths]
    rings = timed_rings_from_ops(perims)
    if len(rings) != 2:
        print(f"error: expected 2 timed perímetros, got {len(rings)}", file=sys.stderr)
        return EXIT_MISSING

    envelope_fc: dict[str, Any] | None = None
    envelope_path: Path | None = None
    if not args.no_envelope:
        envelope_path = Path(args.envelope) if args.envelope is not None else DEFAULT_ENVELOPE
        if envelope_path.is_file():
            envelope_fc = load_envelope_geojson(envelope_path)
        elif args.envelope is not None:
            print(f"error: missing envelope {envelope_path}", file=sys.stderr)
            return EXIT_MISSING

    kml = build_briefing_kml(rings, envelope_fc)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(kml, encoding="utf-8")

    n_peri = len(iter_placemarks(kml, role=ROLE_PERIMETER))
    n_env = len(iter_placemarks(kml, role=ROLE_ENVELOPE))
    rec = {
        "ok": True,
        "wrote": str(out).replace("\\", "/"),
        "n_perimeter_features": n_peri,
        "n_envelope_features": n_env,
        "timezone_convention": TIMEZONE_CONVENTION,
        "source_perimeters": [str(p).replace("\\", "/") for p in paths],
        "envelope": str(envelope_path).replace("\\", "/") if envelope_fc is not None else None,
        "briefing_only": True,
        "wrote_official_met_json": False,
        "rewrote_source_drop": False,
        "not_claims": list(NOT_CLAIMS),
    }
    print(json.dumps(rec, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
