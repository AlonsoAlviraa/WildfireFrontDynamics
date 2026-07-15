#!/usr/bin/env python3
"""Merge observatorio_v2 packs + write index + sync to outputs/observatorio."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "observatorio_v2"
DST = ROOT / "outputs" / "observatorio"
REQUIRED = (
    "report.html",
    "operational_report.html",
    "operational_metrics.json",
    "fronts.geojson",
    "local_speeds.csv",
    "summary.json",
    "ingest_manifest.csv",
    "observations_manifest.csv",
)


def main() -> int:
    results = []
    for d in sorted(SRC.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        missing = [n for n in REQUIRED if not (d / n).is_file()]
        metrics = {}
        ops = {}
        if (d / "summary.json").is_file():
            metrics = json.loads((d / "summary.json").read_text(encoding="utf-8")).get(
                "metrics", {}
            )
        if (d / "operational_metrics.json").is_file():
            ops = json.loads((d / "operational_metrics.json").read_text(encoding="utf-8"))
        entry = {
            "fire_id": d.name,
            "status": "ok" if not missing else "partial",
            "output_dir": str(d),
            "missing_artifacts": missing,
            "metrics": metrics,
            "operational": ops,
            "quality_grade": ops.get("quality_grade"),
            "quality_label_es": ops.get("quality_label_es"),
            "speed_vs_infocam_ratio": ops.get("speed_vs_ref_ratio"),
        }
        results.append(entry)
        print(
            d.name,
            entry["status"],
            "grade",
            ops.get("quality_grade"),
            "Vp",
            ops.get("speed_median_m_min"),
            "area",
            ops.get("area_ha_max"),
            "n_vel",
            ops.get("speed_n_observable"),
            "comps",
            ops.get("component_count_median"),
        )

    ok = [r for r in results if r["status"] == "ok"]
    tobarra = next((r for r in results if "tobarra" in r["fire_id"]), None)
    ops_t = (tobarra or {}).get("operational") or {}
    scorecard = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "observatorio_v2_scientific",
        "gates": {
            "A1_ge3_fires": {"pass": len(ok) >= 3, "n_ok": len(ok)},
            "A2_artifacts_present": {"pass": bool(ok) and all(not r["missing_artifacts"] for r in ok)},
            "A5_tobarra_anchor": {
                "pass": ops_t.get("speed_vs_ref_ratio") is not None,
                "notes": ops_t.get("speed_vs_ref_interpretation_es", ""),
                "grade": ops_t.get("quality_grade"),
                "vp_median": ops_t.get("speed_median_m_min"),
                "ratio": ops_t.get("speed_vs_ref_ratio"),
            },
        },
        "fires": results,
        "observatory_message_es": (
            "Pack científico v2: limpieza de máscara (frente principal), "
            "Vp con IQR y grado A/B/C, comparación INFOCAM cuando existe. "
            "Producto = dinámica observada (no predicción ML)."
        ),
        "before_after_tobarra": {
            "v1_vp_median_m_min": 0.78,
            "v1_components_max": 1264,
            "v1_observable_ratio": 0.005,
            "v2_vp_median_m_min": ops_t.get("speed_median_m_min"),
            "v2_components_median": ops_t.get("component_count_median"),
            "v2_speed_n_observable": ops_t.get("speed_n_observable"),
            "v2_infocam_ratio": ops_t.get("speed_vs_ref_ratio"),
            "v2_quality_grade": ops_t.get("quality_grade"),
        },
    }
    (SRC / "observatory_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, default=str), encoding="utf-8"
    )

    rows = []
    for fire in results:
        fid = fire["fire_id"]
        ops = fire.get("operational") or {}
        rows.append(
            "<tr>"
            f"<td><a href='{fid}/operational_report.html'>{fid}</a></td>"
            f"<td>{fire.get('status')}</td>"
            f"<td>{ops.get('quality_grade')}</td>"
            f"<td>{ops.get('quality_label_es')}</td>"
            f"<td>{ops.get('speed_median_m_min')}</td>"
            f"<td>{ops.get('area_ha_max')}</td>"
            f"<td>{ops.get('speed_n_observable')}</td>"
            f"<td>{ops.get('component_count_median')}</td>"
            f"<td>{ops.get('speed_vs_ref_ratio')}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Observatorio v2 — entrega científica</title>
<style>
body{{margin:0;background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1100px;padding:40px;margin:auto}}
h1{{font-size:34px}} p{{color:#9eb1bd}} a{{color:#f5b942}}
table{{width:100%;border-collapse:collapse;background:#112532;margin-top:18px}}
th,td{{padding:10px;border-bottom:1px solid #26404f;text-align:left}}
.ok{{color:#3d9a5f;font-weight:700}}
</style>
<h1>Entrega Observatorio v2 (científica)</h1>
<p>{scorecard['observatory_message_es']}</p>
<p class="ok">Tobarra: Vp mediana {ops_t.get('speed_median_m_min')} m/min vs INFOCAM 7
(ratio {ops_t.get('speed_vs_ref_ratio')}) · grado {ops_t.get('quality_grade')}</p>
<table>
<thead><tr>
<th>Incendio</th><th>Estado</th><th>Grado</th><th>Etiqueta</th>
<th>Vp med</th><th>Área ha</th><th>N vel</th><th>Comp. med</th><th>vs INFOCAM</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p>Documento principal por incendio: <code>operational_report.html</code>.</p>
</html>"""
    (SRC / "index.html").write_text(html, encoding="utf-8")

    # Promote v2 as canonical observatorio deliverable
    DST.mkdir(parents=True, exist_ok=True)
    for fire in results:
        src_dir = SRC / fire["fire_id"]
        dst_dir = DST / fire["fire_id"]
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
    shutil.copy2(SRC / "observatory_scorecard.json", DST / "observatory_scorecard.json")
    shutil.copy2(SRC / "index.html", DST / "index.html")
    print("Promoted v2 -> outputs/observatorio")
    print(json.dumps(scorecard["gates"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
