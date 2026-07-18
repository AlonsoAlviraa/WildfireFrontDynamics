#!/usr/bin/env python3
"""Build multi-pack open_if index + CLM-vs-Open comparison scorecard (Pista B sellable)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "open_if"
DOCS = ROOT / "docs"


def _load(p: Path) -> dict | None:
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    packs = []
    if OUT.is_dir():
        for d in sorted(OUT.iterdir()):
            if not d.is_dir():
                continue
            sc = _load(d / "scorecard_pista_b.json")
            man = _load(d / "manifest.json")
            if not sc:
                continue
            packs.append(
                {
                    "id": d.name,
                    "activation": sc.get("activation") or (man or {}).get("activation"),
                    "max_area_ha": sc.get("max_area_ha") or (man or {}).get("max_area_ha"),
                    "n_timeline_steps": sc.get("n_timeline_steps"),
                    "n_ros_proxy_steps": sc.get("n_ros_proxy_steps"),
                    "status": sc.get("status"),
                    "O2_cems": sc.get("O2_cems_delineation"),
                    "map": str((d / "map.html").relative_to(ROOT))
                    if (d / "map.html").is_file()
                    else None,
                    "brief": str((d / "operator_brief_open_if.md").relative_to(ROOT))
                    if (d / "operator_brief_open_if.md").is_file()
                    else None,
                    "activation_url": (man or {}).get("activation_url"),
                    "ros_proxy_rows": (man or {}).get("ros_proxy_rows") or [],
                }
            )

    clm = _load(ROOT / "models" / "clm_ensemble" / "manifest.json") or {}
    clm_m = clm.get("metrics") or {}

    # multi-eje score 0-100 (honest, documented)
    e1 = 95 if packs else 20  # reproducibility open
    e2 = min(100, 30 * len(packs))  # multi-fire open
    e3 = 0
    if packs:
        mx = max(float(p.get("max_area_ha") or 0) for p in packs)
        e3 = 90 if mx >= 1000 else 60 if mx >= 100 else 30
    e4 = 85 if any(p.get("O2_cems") == "GO" for p in packs) else 20
    e5 = 70  # will bump if one-pager + demo exist
    if (DOCS / "ONEPAGER_COMERCIAL_ES.md").is_file():
        e5 += 15
    if (ROOT / "scripts" / "demo_sellable_product.py").is_file():
        e5 += 15
    e5 = min(100, e5)
    e6 = 95 if float(clm_m.get("test_iou") or 0) >= 0.89 else 50  # hold ML

    # CLM-only baseline scores (solo pista A)
    clm_only = {
        "E1_reproducibilidad_demo": 35,
        "E2_multi_incendio_publico": 10,
        "E3_escala_evento": 25,
        "E4_validacion_geometrica": 15,
        "E5_producto_empaquetado": 55,
        "E6_ml_transfer": e6,
    }
    dual = {
        "E1_reproducibilidad_demo": e1,
        "E2_multi_incendio_publico": e2,
        "E3_escala_evento": e3,
        "E4_validacion_geometrica": e4,
        "E5_producto_empaquetado": e5,
        "E6_ml_transfer": e6,
    }
    weights = {
        "E1_reproducibilidad_demo": 0.20,
        "E2_multi_incendio_publico": 0.20,
        "E3_escala_evento": 0.10,
        "E4_validacion_geometrica": 0.15,
        "E5_producto_empaquetado": 0.20,
        "E6_ml_transfer": 0.15,
    }
    score_clm = sum(clm_only[k] * weights[k] for k in weights)
    score_dual = sum(dual[k] * weights[k] for k in weights)
    axes_win = sum(1 for k in weights if dual[k] > clm_only[k] + 1e-6)
    venta_go = (
        e1 >= 80
        and e2 >= 50
        and e5 >= 80
        and e6 >= 90
        and score_dual > score_clm
        and axes_win >= 4
    )

    comparison = {
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "definition": "docs/PLAN_COMERCIAL_SUPERA_CLM.md",
        "clm_product": {
            "id": clm.get("version") or "clm_ensemble_v34",
            "metrics": clm_m,
            "strength": "LWIR front + ML holdout; weak on public multi-fire perimeter",
        },
        "open_packs": packs,
        "scores_clm_only": clm_only,
        "scores_dual_product": dual,
        "weights": weights,
        "score_clm_only_weighted": round(score_clm, 2),
        "score_dual_weighted": round(score_dual, 2),
        "axes_where_dual_wins": axes_win,
        "VENTA_GO": venta_go,
        "claims_allowed": [
            "Dual product: thermal front when drone data exists + open CEMS perimeter intelligence",
            "Public multi-fire packs without NDA",
            f"Open packs max area ~{max((p.get('max_area_ha') or 0) for p in packs):.0f} ha"
            if packs
            else "no packs",
        ],
        "claims_forbidden": [
            "Open CEMS IoU better than CLM ensemble on Cardoso holdout",
            "CEMS perimeter is Spanish national official cadastre",
            "ROS proxy is tactical dispatch rate",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(
        json.dumps({"packs": packs, "n": len(packs)}, indent=2), encoding="utf-8"
    )
    (DOCS / "COMPARE_CLM_VS_OPEN_SCORECARD.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )

    # human MD
    lines = [
        "# Comparativa vendible: CLM-solo vs producto dual (CLM + open CEMS)",
        "",
        f"_Actualizado: {comparison['updated_at_utc']}_",
        "",
        f"**Score ponderado CLM-solo:** {score_clm:.1f}/100",
        f"**Score ponderado dual:** {score_dual:.1f}/100",
        f"**Ejes donde dual gana:** {axes_win}/6",
        f"**VENTA_GO:** {'**SÍ**' if venta_go else '**NO** (faltan empaque/demo o packs)'}",
        "",
        "| Eje | CLM-solo | Dual |",
        "|-----|---------:|-----:|",
    ]
    for k in weights:
        lines.append(f"| {k} | {clm_only[k]} | {dual[k]} |")
    lines.extend(["", "## Packs open", ""])
    for p in packs:
        lines.append(
            f"- **{p['activation']}** · {p.get('max_area_ha', 0):.0f} ha · "
            f"steps={p.get('n_timeline_steps')} · [map]({p.get('map')})"
        )
    lines.extend(
        [
            "",
            "## Claims permitidos / prohibidos",
            "",
            "Ver JSON `claims_allowed` / `claims_forbidden`.",
            "",
            "Plan: `docs/PLAN_COMERCIAL_SUPERA_CLM.md`",
            "",
        ]
    )
    (DOCS / "COMPARE_CLM_VS_OPEN.md").write_text("\n".join(lines), encoding="utf-8")

    # index html
    cards = []
    for p in packs:
        cards.append(
            f"<li><b>{p['activation']}</b> — {p.get('max_area_ha', 0):.0f} ha — "
            f"<a href='../{p.get('map')}'>map</a> — "
            f"<a href='{p.get('activation_url')}'>CEMS</a></li>"
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Open IF index</title>
<style>body{{font-family:system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}}
.score{{font-size:1.4rem;padding:1rem;background:#0b1;color:#fff;border-radius:8px}}
.no{{background:#a30}}</style></head><body>
<h1>Open IF index (Pista B)</h1>
<div class="score {'no' if not venta_go else ''}">
Dual score {score_dual:.1f} vs CLM-only {score_clm:.1f} · VENTA_GO={'YES' if venta_go else 'NO'}
</div>
<ul>{''.join(cards) or '<li>No packs — run build_open_if_pack.py</li>'}</ul>
<p><a href="../../docs/COMPARE_CLM_VS_OPEN.md">Comparativa</a> ·
<a href="../../docs/ONEPAGER_COMERCIAL_ES.md">One-pager</a></p>
</body></html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"n_packs": len(packs), "score_dual": score_dual, "score_clm": score_clm, "VENTA_GO": venta_go}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
