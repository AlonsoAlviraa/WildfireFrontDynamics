#!/usr/bin/env python3
"""S1 inventory of real IF packs vs artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIRES = {
    "tobarra_20240802": {"hint": "tobarra", "priority": "anchor"},
    "cardoso_2025": {"hint": "cardoso", "priority": "anchor_needed"},
    "hellin_2024": {"hint": "hellin", "priority": "anchor_needed"},
    "la_estrella_acom1_2024": {"hint": "la_estrella_acom1", "priority": "anchor_needed"},
    "la_estrella_acom2_2024": {"hint": "la_estrella_acom2", "priority": "pack"},
    "retuerta_2025": {"hint": "retuerta", "priority": "qa_flag"},
    "brazatortas_2025": {"hint": "brazatortas", "priority": "pack"},
    "polan_2025": {"hint": "polan", "priority": "pack"},
}


def _has_dir(artifacts: Path, hint: str, keyword: str) -> bool:
    if not artifacts.is_dir():
        return False
    hint_l = hint.lower()
    for p in artifacts.iterdir():
        if not p.is_dir():
            continue
        name = p.name.lower()
        if hint_l in name and keyword in name:
            return True
    return False


def main() -> int:
    artifacts = ROOT / "artifacts"
    obs = ROOT / "outputs" / "observatorio"
    rows = []
    for fid, meta in FIRES.items():
        hint = meta["hint"]
        pack = obs / fid
        ops_path = pack / "operational_metrics.json"
        grade = ros = area = None
        qa = None
        if ops_path.is_file():
            ops = json.loads(ops_path.read_text(encoding="utf-8"))
            grade = ops.get("quality_grade")
            ros = ops.get("speed_median_m_min")
            area = ops.get("area_ha_max")
            if fid == "retuerta_2025" and isinstance(area, (int, float)) and area > 500:
                qa = "AREA_ANOMALOUS_LIKELY_MASK_OR_FOV"
        rows.append(
            {
                "fire_id": fid,
                "has_pack": ops_path.is_file(),
                "has_reprojected_dir": _has_dir(artifacts, hint, "reprojected"),
                "has_masks_dir": _has_dir(artifacts, hint, "masks"),
                "quality_grade": grade,
                "ros_m_min": ros,
                "area_ha_max": area,
                "qa_flag": qa,
                "priority": meta["priority"],
                "usable_for_o1": grade == "A" or (meta["priority"] == "anchor_needed"),
            }
        )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol": "if_inventory_s1_v1",
        "fires": rows,
        "summary": {
            "n_listed": len(rows),
            "n_packs": sum(1 for r in rows if r["has_pack"]),
            "n_grade_a": sum(1 for r in rows if r["quality_grade"] == "A"),
            "n_qa_flag": sum(1 for r in rows if r["qa_flag"]),
            "missing_packs": [r["fire_id"] for r in rows if not r["has_pack"]],
        },
        "retuerta_note": (
            "area_ha_max >> realistic IF size → do not use for ROS validation until mask QA. "
            "Likely FOV / component merge / wrong threshold, not front_dynamics math."
        ),
    }

    out_docs = ROOT / "docs" / "IF_INVENTORY_S1.json"
    out_docs.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_obs = obs / "if_inventory_s1.json"
    out_obs.parent.mkdir(parents=True, exist_ok=True)
    out_obs.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for r in rows:
        print(
            f"  {r['fire_id']}: pack={r['has_pack']} grade={r['quality_grade']} "
            f"area={r['area_ha_max']} qa={r['qa_flag']}"
        )
    print("Wrote", out_docs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
