#!/usr/bin/env python3
"""Write a single HTML index for all Observatory packs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / "outputs" / "observatorio"


def main() -> int:
    scorecard_path = OBS / "observatory_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8")) if scorecard_path.is_file() else {}
    rows = []
    for fire in scorecard.get("fires", []):
        fid = fire.get("fire_id", "")
        m = fire.get("metrics") or {}
        href = f"{fid}/report.html"
        rows.append(
            "<tr>"
            f"<td><a href='{href}'>{fid}</a></td>"
            f"<td>{fire.get('status')}</td>"
            f"<td>{m.get('num_observations', '—')}</td>"
            f"<td>{m.get('speed_status', '—')}</td>"
            f"<td>{m.get('speed_median_m_min', '—')}</td>"
            f"<td>{m.get('observable_ratio', '—')}</td>"
            f"<td>{fire.get('speed_vs_infocam_ratio', '—')}</td>"
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
<p>{scorecard.get('observatory_message_es', '')}</p>
<section class="grid">{gate_cards}</section>
<table>
<thead><tr><th>Incendio</th><th>Estado</th><th>Obs</th><th>Speed</th><th>Mediana m/min</th><th>Obs. ratio</th><th>vs INFOCAM</th></tr></thead>
<tbody>
{''.join(rows)}
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
