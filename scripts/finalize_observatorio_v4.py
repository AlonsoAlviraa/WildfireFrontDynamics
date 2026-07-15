#!/usr/bin/env python3
"""Promote observatorio_v4 + merge O3/O4/M2 experiment results."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "observatorio_v4"
DST = ROOT / "outputs" / "observatorio"
O3 = ROOT / "outputs" / "temporal_windows" / "tobarra_20240802" / "temporal_windows_report.json"
M2 = ROOT / "outputs" / "ml_eval" / "clm_transfer_report.json"


def main() -> int:
    results = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        ops = json.loads((d / "operational_metrics.json").read_text(encoding="utf-8"))
        o4 = all(
            (d / f).is_file()
            for f in (
                "main_front.geojson",
                "ros_timeline.csv",
                "brief_operativo.md",
                "operational_report.html",
            )
        )
        results.append(
            {
                "fire_id": d.name,
                "quality_grade": ops.get("quality_grade"),
                "primary_ros_m_min": ops.get("speed_median_m_min"),
                "ratio_infocam": ops.get("speed_vs_ref_ratio"),
                "methods": ops.get("primary_methods_used"),
                "o4_operator_products": o4,
            }
        )
        print(d.name, results[-1])

    o3 = json.loads(O3.read_text(encoding="utf-8")) if O3.is_file() else {}
    m2 = json.loads(M2.read_text(encoding="utf-8")) if M2.is_file() else {}
    tob = next((r for r in results if "tobarra" in r["fire_id"]), {})

    scorecard = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "observatorio_v4_loop_execution",
        "engine": "front_dynamics_v1+operator_export",
        "leaps": {
            "O3_temporal_windows": {
                "verdict": o3.get("verdict"),
                "n_pass": o3.get("n_pass_ratio_band"),
                "n_ok": o3.get("n_ok"),
                "windows": [
                    {
                        "window": w.get("window"),
                        "ros": w.get("primary_ros_m_min"),
                        "ratio": w.get("ratio_infocam"),
                        "pass": w.get("pass_ratio_band"),
                    }
                    for w in o3.get("windows") or []
                ],
            },
            "O4_operator_products": {
                "verdict": "GO" if all(r.get("o4_operator_products") for r in results) else "PARTIAL",
                "products": [
                    "main_front.geojson",
                    "ros_timeline.csv",
                    "brief_operativo.md",
                    "operational_report.html",
                ],
            },
            "O1_tobarra_anchor": {
                "verdict": "GO"
                if tob.get("ratio_infocam") and 0.5 <= float(tob["ratio_infocam"]) <= 2.0
                else "NO_GO",
                "ros": tob.get("primary_ros_m_min"),
                "ratio": tob.get("ratio_infocam"),
            },
            "M2_clm_transfer": {
                "verdict": m2.get("status"),
                "model_iou": m2.get("model_iou"),
                "copy_iou": m2.get("copy_iou"),
                "delta": m2.get("improvement_vs_copy_iou"),
            },
        },
        "fires": results,
        "session_summary_es": (
            f"Loop ejecución: O3={o3.get('verdict')} (ventanas), "
            f"Tobarra ROS={tob.get('primary_ros_m_min')} ratio={tob.get('ratio_infocam')}, "
            f"O4 productos operador en 3 IF, M2 CLM={m2.get('status')}."
        ),
    }

    DST.mkdir(parents=True, exist_ok=True)
    for r in results:
        s, d = SRC / r["fire_id"], DST / r["fire_id"]
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(s, d)
    (SRC / "loop_execution_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, default=str), encoding="utf-8"
    )
    shutil.copy2(SRC / "loop_execution_scorecard.json", DST / "loop_execution_scorecard.json")

    rows = "".join(
        f"<tr><td><a href='{r['fire_id']}/brief_operativo.md'>{r['fire_id']}</a></td>"
        f"<td>{r.get('quality_grade')}</td><td>{r.get('primary_ros_m_min')}</td>"
        f"<td>{r.get('ratio_infocam')}</td><td>{r.get('o4_operator_products')}</td></tr>"
        for r in results
    )
    html = f"""<!doctype html><html lang=es><meta charset=utf-8>
<title>Observatorio v4 — loop execution</title>
<style>body{{background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1000px;margin:auto;padding:40px}}
a{{color:#f5b942}} table{{width:100%;border-collapse:collapse;background:#112532}}
th,td{{padding:10px;border-bottom:1px solid #26404f;text-align:left}} .ok{{color:#3d9a5f}}</style>
<h1>Observatorio v4 — ejecución loop</h1>
<p class="ok">{scorecard['session_summary_es']}</p>
<table><thead><tr><th>IF</th><th>Grado</th><th>ROS</th><th>vs INFOCAM</th><th>O4</th></tr></thead>
<tbody>{rows}</tbody></table>
<p>Brief: <code>brief_operativo.md</code> · Capa: <code>main_front.geojson</code> · Timeline: <code>ros_timeline.csv</code></p>
<p>O3 report: <code>outputs/temporal_windows/tobarra_20240802/temporal_windows_report.json</code></p>
</html>"""
    (DST / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps(scorecard["leaps"], indent=2, default=str))
    print("Promoted v4 -> outputs/observatorio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
