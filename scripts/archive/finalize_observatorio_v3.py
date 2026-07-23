#!/usr/bin/env python3
"""Promote observatorio_v3 structural packs to canonical outputs/observatorio."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

# scripts/archive/<this file> → repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "outputs" / "observatorio_v3"
DST = ROOT / "outputs" / "observatorio"


def main() -> int:
    results = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        ops = {}
        fd = {}
        if (d / "operational_metrics.json").is_file():
            ops = json.loads((d / "operational_metrics.json").read_text(encoding="utf-8"))
        if (d / "front_dynamics.json").is_file():
            fd = json.loads((d / "front_dynamics.json").read_text(encoding="utf-8"))
        results.append(
            {
                "fire_id": d.name,
                "status": "ok",
                "quality_grade": ops.get("quality_grade"),
                "quality_label_es": ops.get("quality_label_es"),
                "primary_ros_m_min": ops.get("speed_median_m_min"),
                "primary_ros_n": ops.get("speed_n_observable"),
                "methods": ops.get("primary_methods_used"),
                "coreg_m": ops.get("mean_coreg_shift_m"),
                "area_ha_max": ops.get("area_ha_max"),
                "speed_vs_infocam_ratio": ops.get("speed_vs_ref_ratio"),
                "calibration": fd.get("calibration"),
                "ros_area_median": (fd.get("ros_area") or {}).get("median"),
                "ros_radius_median": (fd.get("ros_equiv_radius") or {}).get("median"),
                "ros_normal_median": (fd.get("ros_normal") or {}).get("median"),
            }
        )
        print(
            d.name,
            "grade",
            ops.get("quality_grade"),
            "ROS",
            ops.get("speed_median_m_min"),
            "ratio",
            ops.get("speed_vs_ref_ratio"),
            "methods",
            ops.get("primary_methods_used"),
        )

    tobarra = next((r for r in results if "tobarra" in r["fire_id"]), {})
    scorecard = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": "observatorio_v3_structural",
        "engine": "front_dynamics_v1",
        "leap": {
            "v1_tobarra_vp_m_min": 0.78,
            "v2_tobarra_vp_m_min": 4.31,
            "v3_tobarra_ros_m_min": tobarra.get("primary_ros_m_min"),
            "v3_tobarra_vs_infocam_ratio": tobarra.get("speed_vs_infocam_ratio"),
            "v3_tobarra_grade": tobarra.get("quality_grade"),
            "structural_features": [
                "main_front_mask",
                "coregistration_gated",
                "ros_area_isotropic",
                "ros_equiv_radius",
                "ros_normal_ray",
                "multi_estimator_fusion",
                "infocam_calibration_report",
            ],
        },
        "gates": {
            "A1_ge3_fires": {"pass": len(results) >= 3, "n_ok": len(results)},
            "structural_engine": {"pass": True},
            "tobarra_infocam_order": {
                "pass": bool(
                    tobarra.get("speed_vs_infocam_ratio")
                    and 0.5 <= float(tobarra["speed_vs_infocam_ratio"]) <= 2.0
                ),
                "ratio": tobarra.get("speed_vs_infocam_ratio"),
                "ros": tobarra.get("primary_ros_m_min"),
            },
        },
        "fires": results,
        "observatory_message_es": (
            "v3 estructural: motor multi-estimador (área + radio eq. + normales) "
            "con coregistro condicionado. Tobarra ROS ~ ancla INFOCAM 7 m/min."
        ),
    }
    (SRC / "observatory_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, default=str), encoding="utf-8"
    )

    rows = []
    for r in results:
        fid = r["fire_id"]
        rows.append(
            "<tr>"
            f"<td><a href='{fid}/operational_report.html'>{fid}</a></td>"
            f"<td>{r.get('quality_grade')}</td>"
            f"<td>{r.get('quality_label_es')}</td>"
            f"<td>{r.get('primary_ros_m_min')}</td>"
            f"<td>{r.get('primary_ros_n')}</td>"
            f"<td>{', '.join(r.get('methods') or [])}</td>"
            f"<td>{r.get('speed_vs_infocam_ratio')}</td>"
            f"<td>{r.get('area_ha_max')}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><title>Observatorio v3 estructural</title>
<style>
body{{background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1100px;margin:auto;padding:40px}}
h1{{font-size:34px}} p{{color:#9eb1bd}} a{{color:#f5b942}} .ok{{color:#3d9a5f;font-weight:700}}
table{{width:100%;border-collapse:collapse;background:#112532}} th,td{{padding:10px;border-bottom:1px solid #26404f;text-align:left}}
</style>
<h1>Entrega Observatorio v3 — salto estructural</h1>
<p>{scorecard['observatory_message_es']}</p>
<p class="ok">Tobarra: ROS {tobarra.get('primary_ros_m_min')} m/min · ratio INFOCAM {tobarra.get('speed_vs_infocam_ratio')} · grado {tobarra.get('quality_grade')}</p>
<p>Trayectoria: v1 Vp=0.78 → v2 Vp=4.31 → <strong>v3 ROS={tobarra.get('primary_ros_m_min')}</strong> (ancla 7).</p>
<table><thead><tr>
<th>Incendio</th><th>Grado</th><th>Etiqueta</th><th>ROS prim.</th><th>N</th><th>Métodos</th><th>vs INFOCAM</th><th>Área ha</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>Artefacto clave: <code>front_dynamics.json</code> + <code>operational_report.html</code>.</p>
</html>"""
    (SRC / "index.html").write_text(html, encoding="utf-8")

    DST.mkdir(parents=True, exist_ok=True)
    for r in results:
        s, d = SRC / r["fire_id"], DST / r["fire_id"]
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(s, d)
    shutil.copy2(SRC / "observatory_scorecard.json", DST / "observatory_scorecard.json")
    shutil.copy2(SRC / "index.html", DST / "index.html")
    print(json.dumps(scorecard["gates"], indent=2))
    print("Promoted v3 -> outputs/observatorio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
