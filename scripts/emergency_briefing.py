#!/usr/bin/env python3
"""One-command emergency briefing for an observatorio pack (default Tobarra).

Writes a human-readable markdown brief with grade, ROS, sectors, envelope,
and explicit blocked items (anchors / official perimeter).
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
)


def _ensure_enriched(pack: Path) -> dict:
    ops_path = pack / "operational_metrics.json"
    if not ops_path.is_file():
        raise FileNotFoundError(f"missing {ops_path}")
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    need = "sector_ros" not in ops or not (
        ops.get("short_horizon_envelope") or {}
    ).get("sector_aware")
    if need:
        bearing = None
        mf = pack / "main_front.geojson"
        if mf.is_file():
            bearing = expansion_bearing_deg_from_centroids(load_main_front_centroids(mf))
        ops = enrich_ops_dict(ops, expansion_bearing_deg=bearing)
        ops_path.write_text(json.dumps(ops, indent=2), encoding="utf-8")
        write_emergency_envelope_file(
            ops.get("short_horizon_envelope") or {},
            pack / "emergency_envelope.json",
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

    # Reference / blocked
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
    lines.append(
        "- **15/30/60 envelope is NOT validated tactical dispatch**"
    )
    lines.append("- **NDWS global ML is research-only** (G1 features+temporal KILL)")

    lines += [
        "",
        "## Artifacts",
        "",
        f"- `{pack / 'operational_metrics.json'}`",
        f"- `{pack / 'emergency_envelope.json'}`",
        f"- `{pack / 'main_front.geojson'}`",
        f"- `{pack / 'operational_report.html'}`",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Emergency briefing (one command)")
    ap.add_argument("--fire", default="tobarra_20240802")
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT / "outputs" / "observatorio",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: pack/emergency_briefing.md",
    )
    args = ap.parse_args()
    pack = args.root / args.fire
    ops = _ensure_enriched(pack)
    md = build_briefing_md(args.fire, ops, pack)
    out = args.output or (pack / "emergency_briefing.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(str(out.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
