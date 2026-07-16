#!/usr/bin/env python3
"""Emergency briefing + GIS envelope export (single entry, multi-IF capable).

Examples:
  python scripts/emergency_briefing.py
  python scripts/emergency_briefing.py --fires tobarra_20240802,cardoso_2025
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.emergency_products import (  # noqa: E402
    enrich_ops_dict,
    expansion_bearing_deg_from_centroids,
    load_main_front_centroids,
    write_emergency_envelope_file,
    write_envelope_geojson,
)


def _ensure_enriched(pack: Path, fire_id: str) -> dict:
    ops_path = pack / "operational_metrics.json"
    if not ops_path.is_file():
        raise FileNotFoundError(f"missing {ops_path}")
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    env = ops.get("short_horizon_envelope") or {}
    need = "sector_ros" not in ops or not env.get("sector_aware")
    bearing = None
    cents: list[tuple[float, float]] = []
    mf = pack / "main_front.geojson"
    if mf.is_file():
        cents = load_main_front_centroids(mf)
        bearing = expansion_bearing_deg_from_centroids(cents)
    if need:
        ops = enrich_ops_dict(ops, expansion_bearing_deg=bearing)
        ops_path.write_text(json.dumps(ops, indent=2), encoding="utf-8")
        write_emergency_envelope_file(
            ops.get("short_horizon_envelope") or {},
            pack / "emergency_envelope.json",
        )
    # Always refresh GIS from current envelope numbers (single ROS source)
    env = ops.get("short_horizon_envelope") or {}
    center = cents[-1] if cents else None
    if center is None and bearing is None:
        # last chance from envelope bearing only
        pass
    write_envelope_geojson(
        env,
        pack / "emergency_envelope_guidance.geojson",
        center_xy=center,
        fire_id=fire_id,
        expansion_bearing_deg=bearing
        or (ops.get("sector_ros") or {}).get("expansion_bearing_deg"),
    )
    return ops


def build_briefing_md(fire_id: str, ops: dict, pack: Path) -> str:
    sector = ops.get("sector_ros") or {}
    secs = sector.get("sectors") or {}
    env = ops.get("short_horizon_envelope") or {}
    envelopes = env.get("envelopes") or []
    lines = [
        f"# Emergency briefing — {fire_id}",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Status",
        "",
        f"- **Quality grade:** {ops.get('quality_grade') or 'n/a'}",
        f"- **Speed status:** {ops.get('speed_status') or 'n/a'}",
        f"- **Primary ROS:** {ops.get('speed_median_m_min')} m/min",
        f"- **Engine:** {ops.get('engine') or 'front_dynamics_v1'}",
        "",
        "## Sector ROS (observed guidance)",
        "",
    ]
    if secs:
        lines += [
            f"- **Head:** {secs.get('head_m_min')} m/min",
            f"- **Flank:** {secs.get('flank_m_min')} m/min",
            f"- **Rear:** {secs.get('rear_m_min')} m/min",
        ]
        if secs.get("head_bearing_deg") is not None:
            lines.append(f"- **Head bearing:** {secs.get('head_bearing_deg')}°")
        lines.append(f"- _{sector.get('label_es') or ''}_")
    else:
        lines.append(f"- **Abstained:** {sector.get('reason') or 'no sectors'}")

    lines += ["", "## Short-horizon envelope (extrapolated)", ""]
    lines.append(f"- _{env.get('label_es') or env.get('label_en') or ''}_")
    if envelopes:
        for e in envelopes:
            h = e.get("horizon_min")
            lines.append(
                f"- **{h} min:** head {e.get('head_radius_m')} m · "
                f"flank {e.get('flank_radius_m')} m · rear {e.get('rear_radius_m')} m "
                f"(isotropic {e.get('radius_m')} m)"
            )
    else:
        lines.append(f"- Abstained: {env.get('reason')}")

    lines += ["", "## Blocked / not claimed", ""]
    if ops.get("has_reference") or ops.get("reference_vp_m_min"):
        lines.append(
            f"- INFOCAM-style ref present: Vp={ops.get('reference_vp_m_min')} "
            f"ratio={ops.get('speed_vs_ref_ratio')}"
        )
    else:
        lines.append("- **Multi-IF anchors (O1/O5):** BLOCKED without external Vp/ha")
    lines.append(
        "- **Official perimeter Hausdorff (O2):** BLOCKED without official GeoJSON "
        "(KMZ image footprint is not a fire perimeter)"
    )
    lines.append("- **15/30/60 envelope is NOT validated tactical dispatch**")
    lines.append("- **NDWS global ML is research-only** (G1 features+temporal KILL)")
    lines.append(
        "- **GIS layer emergency_envelope_guidance.geojson is extrapolated guidance, "
        "NOT an official perimeter**"
    )

    lines += [
        "",
        "## Artifacts",
        "",
        f"- `{pack / 'operational_metrics.json'}`",
        f"- `{pack / 'emergency_envelope.json'}`",
        f"- `{pack / 'emergency_envelope_guidance.geojson'}`",
        f"- `{pack / 'main_front.geojson'}`",
        f"- `{pack / 'operational_report.html'}`",
        "",
    ]
    return "\n".join(lines) + "\n"


def process_fire(root: Path, fire_id: str) -> Path:
    pack = root / fire_id
    ops = _ensure_enriched(pack, fire_id)
    md = build_briefing_md(fire_id, ops, pack)
    out = pack / "emergency_briefing.md"
    out.write_text(md, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Emergency briefing multi-IF + GIS")
    ap.add_argument(
        "--fires",
        default="tobarra_20240802,cardoso_2025",
        help="Comma-separated fire pack ids under outputs/observatorio",
    )
    ap.add_argument(
        "--fire",
        default=None,
        help="Single fire (overrides --fires if set)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT / "outputs" / "observatorio",
    )
    args = ap.parse_args()
    if args.fire:
        fires = [args.fire.strip()]
    else:
        fires = [x.strip() for x in args.fires.split(",") if x.strip()]

    written: list[Path] = []
    for fid in fires:
        pack = args.root / fid
        if not pack.is_dir():
            print(f"SKIP missing pack {fid}", file=sys.stderr)
            continue
        try:
            written.append(process_fire(args.root, fid))
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {fid}: {exc}", file=sys.stderr)
            return 1

    if not written:
        print("No briefings written", file=sys.stderr)
        return 1
    for p in written:
        print(str(p.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
