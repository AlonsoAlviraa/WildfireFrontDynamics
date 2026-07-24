#!/usr/bin/env python3
"""Finalize current loop tranche: O3 GO, multi-IF v5, promote, scorecard."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "observatorio_v5"
DST = ROOT / "outputs" / "observatorio"
O3 = ROOT / "outputs" / "temporal_windows" / "tobarra_20240802" / "temporal_windows_report.json"
M2 = ROOT / "outputs" / "ml_eval" / "clm_transfer_report.json"


def main() -> int:
    o3 = json.loads(O3.read_text(encoding="utf-8")) if O3.is_file() else {}
    m2 = json.loads(M2.read_text(encoding="utf-8")) if M2.is_file() else {}
    fires = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        ops = json.loads((d / "operational_metrics.json").read_text(encoding="utf-8"))
        o4 = all(
            (d / f).is_file()
            for f in ("main_front.geojson", "ros_timeline.csv", "brief_operativo.md")
        )
        fires.append(
            {
                "fire_id": d.name,
                "grade": ops.get("quality_grade"),
                "ros": ops.get("speed_median_m_min"),
                "ratio": ops.get("speed_vs_ref_ratio"),
                "methods": ops.get("primary_methods_used"),
                "area_ha_max": ops.get("area_ha_max"),
                "o4": o4,
            }
        )

    tob = next((f for f in fires if "tobarra" in f["fire_id"]), {})
    n_a = sum(1 for f in fires if f.get("grade") == "A")
    score = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "tranche": "close_O3_multiIF_v24_prep",
        "leaps": {
            "O3": {
                "verdict": o3.get("verdict"),
                "n_pass_strict": o3.get("n_pass_ratio_band"),
                "n_pass_wide": o3.get("n_pass_wide"),
                "windows": o3.get("windows"),
            },
            "O4": {"verdict": "GO" if all(f.get("o4") for f in fires) else "PARTIAL"},
            "multi_IF": {"n_fires": len(fires), "n_grade_A": n_a, "fires": fires},
            "O1_tobarra": {
                "ros": tob.get("ros"),
                "ratio": tob.get("ratio"),
                "verdict": "GO"
                if tob.get("ratio") and 0.5 <= float(tob["ratio"]) <= 2.0
                else "CHECK",
            },
            "M2": {
                "verdict": m2.get("status"),
                "delta": m2.get("improvement_vs_copy_iou"),
                "split": m2.get("clm_split"),
            },
            "M1_v24": {"status": "queued_or_running", "kernel": "wildfire-front-training-v24"},
        },
        "session_es": (
            f"O3={o3.get('verdict')} · multi-IF n={len(fires)} (A={n_a}) · "
            f"Tobarra ROS={tob.get('ros')} ratio={tob.get('ratio')} · "
            f"M2={m2.get('status')}"
        ),
    }

    DST.mkdir(parents=True, exist_ok=True)
    for f in fires:
        s, d = SRC / f["fire_id"], DST / f["fire_id"]
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(s, d)
    (SRC / "loop_tranche_scorecard.json").write_text(
        json.dumps(score, indent=2, default=str), encoding="utf-8"
    )
    shutil.copy2(SRC / "loop_tranche_scorecard.json", DST / "loop_tranche_scorecard.json")

    rows = "".join(
        f"<tr><td><a href='{f['fire_id']}/brief_operativo.md'>{f['fire_id']}</a></td>"
        f"<td>{f.get('grade')}</td><td>{f.get('ros')}</td><td>{f.get('ratio')}</td>"
        f"<td>{', '.join(f.get('methods') or [])}</td></tr>"
        for f in fires
    )
    html = f"""<!doctype html><html lang=es><meta charset=utf-8>
<title>Loop tranche — O3 + multi-IF</title>
<style>body{{background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1100px;margin:auto;padding:40px}}
a{{color:#f5b942}}table{{width:100%;border-collapse:collapse;background:#112532}}
th,td{{padding:10px;border-bottom:1px solid #26404f;text-align:left}}.ok{{color:#3d9a5f}}</style>
<h1>Tramo loop: O3 + multi-IF</h1>
<p class="ok">{score["session_es"]}</p>
<table><thead><tr><th>IF</th><th>Grado</th><th>ROS</th><th>vs INFOCAM</th><th>Métodos</th></tr></thead>
<tbody>{rows}</tbody></table>
<p>O3: early/mid/late en <code>outputs/temporal_windows/tobarra_20240802/</code></p>
</html>"""
    (DST / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps(score["leaps"], indent=2, default=str)[:2500])
    print("Promoted v5 -> outputs/observatorio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
