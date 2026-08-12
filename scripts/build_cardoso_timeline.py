#!/usr/bin/env python3
"""Cardoso multi-day KMZ Δha timeline (polygon proxy — NOT front ROS)."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ops_perimeter import parse_ops_perimeter  # noqa: E402

CARD = ROOT / "data" / "real_if" / "pablo_geacam_20260803_drop" / "cardoso"
MANUAL_HA = {
    "Perimetro_Cardoso De La Sierra_20250927_1300.kmz": 2153.0,
}


def _ts_from_name(name: str) -> str | None:
    m = re.search(r"(20\d{6})_(\d{4})", name)
    if m:
        d, hm = m.group(1), m.group(2)
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}T{hm[0:2]}:{hm[2:4]}:00"
    m2 = re.search(r"(\d{2})(\d{2})(\d{2})\s*(\d{4})", name)
    if m2:
        dd, mo, yy, hm = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
        return f"20{yy}-{mo}-{dd}T{hm[0:2]}:{hm[2:4]}:00"
    return None


def main() -> int:
    rows: list[dict] = []
    for kmz in sorted(CARD.glob("*.kmz")):
        name = kmz.name
        kind = "thermal" if "termico" in name.lower() or "térmico" in name.lower() else "ops_active"
        ts = _ts_from_name(name)
        sup = None
        err = None
        try:
            per = parse_ops_perimeter(kmz)
            sup = per.sup_ha
            # Prefer explicit Spanish thousands: 2,153.00 ha or 2.153,00 ha
            blob = f"{per.name or ''} {name}"
            mha = re.search(
                r"([0-9]{1,3}(?:[.,][0-9]{3})+(?:[.,][0-9]+)?)\s*ha",
                blob,
                re.I,
            )
            if mha:
                token = mha.group(1)
                if "," in token and "." in token:
                    # 2,153.00 → thousands comma
                    raw = token.replace(",", "")
                elif "," in token:
                    parts = token.split(",")
                    if len(parts[-1]) == 3 and len(parts) == 2:
                        raw = "".join(parts)  # 2,153
                    else:
                        raw = token.replace(",", ".")
                else:
                    raw = token
                try:
                    parsed = float(raw)
                    if sup is None or parsed > 100:  # prefer real ha over misparse
                        sup = parsed
                except ValueError:
                    pass
        except Exception as exc:
            err = str(exc)
        # Force known Sup.Activa label (parser may yield 2.153)
        if name in MANUAL_HA and (
            sup is None or (sup is not None and sup < 10 and MANUAL_HA[name] > 100)
        ):
            sup = MANUAL_HA[name]
        rows.append(
            {
                "file": name,
                "timestamp": ts,
                "kind": kind,
                "sup_ha": sup,
                "error": err,
            }
        )

    ops = [
        r for r in rows if r["kind"] == "ops_active" and r["timestamp"] and r["sup_ha"] is not None
    ]
    ops.sort(key=lambda x: x["timestamp"])
    timeline: list[dict] = []
    prev = None
    for r in ops:
        t = datetime.fromisoformat(r["timestamp"])
        item = {
            "timestamp": r["timestamp"],
            "file": r["file"],
            "sup_ha": r["sup_ha"],
            "delta_ha": None,
            "delta_hours": None,
            "ha_per_hour_polygon_proxy": None,
            "note": "polygon area growth proxy — NOT front ROS / NOT Vp",
        }
        if prev is not None:
            dt = (t - datetime.fromisoformat(prev["timestamp"])).total_seconds() / 3600.0
            dha = float(r["sup_ha"]) - float(prev["sup_ha"])
            item["delta_ha"] = round(dha, 2)
            item["delta_hours"] = round(dt, 3)
            if dt > 0:
                item["ha_per_hour_polygon_proxy"] = round(dha / dt, 3)
        timeline.append(item)
        prev = r

    doc = {
        "schema": "wfd_cardoso_timeline_delta_ha_v1",
        "fire_id": "cardoso_2025",
        "honesty": [
            "Delta ha / hour is polygon expansion proxy only",
            "Not head ROS m/min",
            "Not official EGIF ha",
            "No Vp from this drop",
        ],
        "all_kmz": rows,
        "timeline_ops_with_ha": timeline,
        "n_thermal_kmz": sum(1 for r in rows if r["kind"] == "thermal"),
    }
    out_json = CARD / "timeline_delta_ha.json"
    out_json.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Cardoso timeline Δha (proxy, no Vp)",
        "",
        "| timestamp | sup_ha | Δha | Δh | ha/h proxy |",
        "|-----------|-------:|----:|---:|----------:|",
    ]
    for t in timeline:
        lines.append(
            "| {ts} | {ha} | {dha} | {dh} | {r} |".format(
                ts=t["timestamp"],
                ha=t["sup_ha"],
                dha=t["delta_ha"] if t["delta_ha"] is not None else "—",
                dh=t["delta_hours"] if t["delta_hours"] is not None else "—",
                r=(
                    t["ha_per_hour_polygon_proxy"]
                    if t["ha_per_hour_polygon_proxy"] is not None
                    else "—"
                ),
            )
        )
    lines += [
        "",
        "**Not front ROS.** Source: ops KMZ from Pablo 2026-08-03 drop.",
    ]
    (CARD / "timeline_delta_ha.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"wrote": str(out_json), "n_timeline": len(timeline)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
