#!/usr/bin/env python3
"""Write a single HTML index for all Observatory packs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / "outputs" / "observatorio"


def main() -> int:
    scorecard_path = OBS / "observatory_scorecard.json"
    scorecard = (
        json.loads(scorecard_path.read_text(encoding="utf-8")) if scorecard_path.is_file() else {}
    )
    rows = []
    for fire in scorecard.get("fires", []):
        fid = fire.get("fire_id", "")
        m = fire.get("metrics") or {}
        ops = m.get("operational") if isinstance(m.get("operational"), dict) else {}
        href = f"{fid}/operational_report.html"
        href_tech = f"{fid}/report.html"
        rows.append(
            "<tr>"
            f"<td><a href='{href}'>{fid}</a> "
            f"(<a href='{href_tech}'>técnico</a>)</td>"
            f"<td>{fire.get('status')}</td>"
            f"<td>{ops.get('quality_grade') or fire.get('quality_grade') or '—'}</td>"
            f"<td>{m.get('num_observations', '—')}</td>"
            f"<td>{ops.get('speed_median_m_min', m.get('speed_median_m_min', '—'))}</td>"
            f"<td>{ops.get('area_ha_max', '—')}</td>"
            f"<td>{ops.get('speed_n_observable', m.get('num_observable', '—'))}</td>"
            f"<td>{fire.get('speed_vs_infocam_ratio') or ops.get('speed_vs_ref_ratio') or '—'}</td>"
            "</tr>"
        )
    gates = scorecard.get("gates", {})
    gate_cards = "".join(
        f"<article><span>{k}</span><strong>{'PASS' if v.get('pass') else 'FAIL'}</strong>"
        f"<small>{v.get('notes', v.get('n_ok', ''))}</small></article>"
        for k, v in gates.items()
    )
    html = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Entrega Observatorio — WildfireFrontDynamics</title>
<style>
body{{margin:0;background:#08131c;color:#f5f1e8;font:16px system-ui;max-width:1100px;padding:40px;margin:auto}}
h1{{font-size:36px}} p,small{{color:#9eb1bd}} a{{color:#f5b942}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:24px 0}}
article{{background:#112532;border:1px solid #26404f;border-radius:12px;padding:16px}}
span{{display:block;color:#9eb1bd;font-size:12px}} strong{{font-size:22px;color:#f5b942}}
table{{width:100%;border-collapse:collapse;background:#112532}} th,td{{padding:10px;border-bottom:1px solid #26404f;text-align:left}}
</style>
<h1>Entrega Observatorio</h1>
<p>{scorecard.get("observatory_message_es", "")}</p>
<section class="grid">{gate_cards}</section>
<table>
<thead><tr><th>Incendio</th><th>Estado</th><th>Grado</th><th>Frames</th><th>Vp med m/min</th><th>Área máx ha</th><th>N vel</th><th>vs INFOCAM</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<p><strong>Limitación:</strong> reconstrucción de dinámica observada desde máscaras LWIR.
No es predicción operacional 24h. Velocidades con alta abstención deben interpretarse con
perímetros oficiales cuando existan.</p>
</html>"""
    out = OBS / "index.html"
    out.write_text(html, encoding="utf-8")
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
