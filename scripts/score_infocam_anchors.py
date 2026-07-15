#!/usr/bin/env python3
"""O1/O5 — score observatorio packs against data/infocam_anchors.json.

Confirmed anchors only count for multi-A / ratio band GO.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    anchors_path = ROOT / "data" / "infocam_anchors.json"
    packs_root = ROOT / "outputs" / "observatorio"
    if len(sys.argv) > 1:
        packs_root = Path(sys.argv[1])

    anchors_doc = json.loads(anchors_path.read_text(encoding="utf-8"))
    anchors = anchors_doc.get("anchors") or {}
    band = anchors_doc.get("ratio_band") or [0.5, 2.0]
    lo, hi = float(band[0]), float(band[1])

    rows = []
    n_confirmed = 0
    n_in_band = 0
    n_grade_a = 0

    for fire_id, anc in sorted(anchors.items()):
        pack = packs_root / fire_id
        ops_path = pack / "operational_metrics.json"
        ops = {}
        if ops_path.is_file():
            ops = json.loads(ops_path.read_text(encoding="utf-8"))
        # Prefer fused primary ROS when pack wrote it; else speed_median (ops estimate).
        ros = ops.get("primary_ros_m_min")
        if ros is None:
            ros = ops.get("speed_median_m_min")
        grade = ops.get("quality_grade")
        status = anc.get("status")
        vp = anc.get("vp_m_min")
        area_ref = anc.get("area_ha")
        area_obs = ops.get("area_ha_max")
        if area_obs is None and isinstance(ops.get("area_ha_series"), list) and ops["area_ha_series"]:
            try:
                area_obs = max(float(x.get("area_ha") or 0) for x in ops["area_ha_series"])
            except (TypeError, ValueError):
                area_obs = None
        ratio = None
        in_band = None
        if status == "confirmed" and isinstance(vp, (int, float)) and vp > 0 and isinstance(ros, (int, float)):
            n_confirmed += 1
            ratio = float(ros) / float(vp)
            in_band = lo <= ratio <= hi
            if in_band:
                n_in_band += 1
        if grade == "A":
            n_grade_a += 1
        area_ratio = None
        if isinstance(area_ref, (int, float)) and area_ref > 0 and isinstance(area_obs, (int, float)):
            area_ratio = float(area_obs) / float(area_ref)

        rows.append(
            {
                "fire_id": fire_id,
                "anchor_status": status,
                "vp_ref": vp,
                "area_ref_ha": area_ref,
                "ros_primary": ros,
                "area_obs_ha": area_obs,
                "ratio_ros": ratio,
                "ratio_in_band": in_band,
                "area_ratio": area_ratio,
                "quality_grade": grade,
                "source": anc.get("source"),
            }
        )

    o1 = n_confirmed >= 2 and n_in_band >= 2
    o1_partial = n_confirmed >= 1 and n_in_band >= 1
    o5 = n_grade_a >= 2

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "packs_root": str(packs_root),
        "ratio_band": [lo, hi],
        "n_confirmed_anchors": n_confirmed,
        "n_in_band": n_in_band,
        "n_grade_a": n_grade_a,
        "O1_multi_anchor": {
            "pass": o1,
            "partial": o1_partial,
            "verdict": "GO" if o1 else ("PARTIAL" if o1_partial else "BLOCKED"),
            "need": ">=2 confirmed anchors with ratio in band",
        },
        "O5_second_grade_A": {
            "pass": o5,
            "verdict": "GO" if o5 else "NO_GO",
            "need": ">=2 packs with quality_grade A",
        },
        "fires": rows,
        "blocked_reason": None
        if o1
        else "Only confirmed INFOCAM anchor in-repo is Tobarra; Cardoso/Hellín/Estrella pending_external",
    }

    out = ROOT / "outputs" / "observatorio" / "anchor_scorecard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "fires"}, indent=2))
    for r in rows:
        print(
            f"  {r['fire_id']}: anchor={r['anchor_status']} ros={r['ros_primary']} "
            f"ratio={r['ratio_ros']} grade={r['quality_grade']}"
        )
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
