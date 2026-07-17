#!/usr/bin/env python3
"""Aggregate ALL project metrics into one hub (JSON + MD + HTML dashboard)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.product.confidence import (  # noqa: E402
    build_decision_card,
    content_hash,
)


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _git_head() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
            ).strip()
            or None
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def collect() -> dict[str, Any]:
    clm = _load(ROOT / "models" / "clm_ensemble" / "manifest.json") or {}
    ml_loop = _load(ROOT / "docs" / "ML_LOOP_3WAY_SCORECARD.json") or {}
    industrial = _load(ROOT / "docs" / "INDUSTRIAL_READINESS_STATUS.json") or {}
    compare = _load(ROOT / "docs" / "COMPARE_CLM_VS_OPEN_SCORECARD.json") or {}
    pista_b = _load(ROOT / "docs" / "PISTA_B_SCORECARD_SNAPSHOT.json") or {}

    open_packs = []
    open_dir = ROOT / "outputs" / "open_if"
    if open_dir.is_dir():
        for d in sorted(open_dir.iterdir()):
            sc = _load(d / "scorecard_pista_b.json")
            man = _load(d / "manifest.json")
            if sc:
                open_packs.append(
                    {
                        "id": d.name,
                        **{k: sc.get(k) for k in sc},
                        "ros_proxy_n": len((man or {}).get("ros_proxy_rows") or []),
                        "hausdorff_series": [
                            r.get("hausdorff_m")
                            for r in ((man or {}).get("ros_proxy_rows") or [])
                        ],
                        "growth_ha_h": [
                            r.get("growth_ha_per_hour")
                            for r in ((man or {}).get("ros_proxy_rows") or [])
                        ],
                    }
                )

    # best open pack for fusion demo
    best_open = None
    if open_packs:
        best_open = max(open_packs, key=lambda p: float(p.get("max_area_ha") or 0))

    champ = (ml_loop.get("champion") or {}) if isinstance(ml_loop, dict) else {}
    ml_metrics = clm.get("metrics") or {
        "test_iou": champ.get("model_iou"),
        "improvement_vs_copy_iou": champ.get("improvement_vs_copy_iou"),
        "model_iou_growth": champ.get("model_iou_growth"),
    }

    # representative ops: Tobarra anchor known
    anchors = _load(ROOT / "data" / "infocam_anchors.json") or {}
    tob = (anchors.get("anchors") or {}).get("tobarra_20240802") or {}
    ops_metrics = {
        "quality_grade": "A" if tob.get("status") == "confirmed" else "C",
        "primary_ros_m_min": 5.71,  # documented historical pack
        "n_frames_staged": 35,
        "area_ha_max": tob.get("area_ha"),
        "speed_vs_ref_ratio": (5.71 / float(tob["vp_m_min"]))
        if tob.get("vp_m_min")
        else None,
        "anchor_status": tob.get("status"),
    }

    open_metrics = None
    if best_open:
        open_metrics = {
            "max_area_ha": best_open.get("max_area_ha"),
            "n_timeline_steps": best_open.get("n_timeline_steps"),
            "activation": best_open.get("activation"),
            "O2_cems_delineation": best_open.get("O2_cems_delineation"),
        }

    card = build_decision_card(
        "hub_aggregate",
        ml_metrics=ml_metrics,
        ops_metrics=ops_metrics,
        open_metrics=open_metrics,
        git_commit=_git_head(),
    )

    hub = {
        "schema": "metrics_hub_v1",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(),
        "content_hash": "",
        "ml": {
            "product": clm.get("version") or "clm_ensemble_v34",
            "metrics": ml_metrics,
            "member_weights": clm.get("member_weights"),
            "member_temperatures": clm.get("member_temperatures"),
            "protocol": clm.get("protocol"),
            "loop_status": ml_loop.get("status"),
            "champion_name": champ.get("name"),
        },
        "ops": {
            "product": "incident_runtime_v1 / front_dynamics_v1",
            "tobarra_anchor": tob,
            "representative_metrics": ops_metrics,
        },
        "open_cems": {
            "n_packs": len(open_packs),
            "packs": open_packs,
            "best": best_open,
        },
        "gates": industrial.get("gates") or {},
        "industrial": {
            "GO_MES": industrial.get("GO_MES"),
            "GO_ENG": industrial.get("GO_ENG"),
            "GO_MES_reason": industrial.get("GO_MES_reason"),
        },
        "commercial_compare": {
            "score_dual": compare.get("score_dual_weighted"),
            "score_clm_only": compare.get("score_clm_only_weighted"),
            "VENTA_GO": compare.get("VENTA_GO"),
            "axes_win": compare.get("axes_where_dual_wins"),
        },
        "decision_card": card.to_dict(),
        "reliability_note": (
            "system_reliability five-nines bound applies to silent-GO prevention "
            "under tests, NOT to fire-spread forecast accuracy."
        ),
    }
    hub["content_hash"] = content_hash(
        {k: hub[k] for k in hub if k not in ("built_at_utc", "content_hash")}
    )
    return hub


def render_md(hub: dict[str, Any]) -> str:
    ml = hub.get("ml") or {}
    mm = ml.get("metrics") or {}
    ops = (hub.get("ops") or {}).get("representative_metrics") or {}
    card = hub.get("decision_card") or {}
    lines = [
        "# Metrics Hub — todas las métricas",
        "",
        f"_UTC: {hub.get('built_at_utc')}_ · git `{hub.get('git_commit')}` · "
        f"hash `{str(hub.get('content_hash'))[:12]}…`",
        "",
        "## Decision Card (fusión)",
        "",
        f"- **decision:** `{card.get('decision')}`",
        f"- **confidence_pred:** {card.get('confidence_pred')} ({card.get('confidence_pred_label')})",
        f"- **system_reliability_pass:** {card.get('system_reliability_pass')}",
        f"- **reasons:** {', '.join(card.get('reasons') or [])}",
        "",
        "> Fire prediction is **not** 99.9999% accurate. "
        "Five-nines bound = no silent GO without gates under automation.",
        "",
        "## ML (CLM ensemble)",
        "",
        f"| Métrica | Valor |",
        f"|---------|------:|",
        f"| product | {ml.get('product')} |",
        f"| test_iou | {mm.get('test_iou')} |",
        f"| improvement_vs_copy_iou | {mm.get('improvement_vs_copy_iou')} |",
        f"| model_iou_growth | {mm.get('model_iou_growth')} |",
        f"| temps | {ml.get('member_temperatures')} |",
        f"| mix | {ml.get('member_weights')} |",
        "",
        "## Ops (Tobarra representativo)",
        "",
        f"| Métrica | Valor |",
        f"|---------|------:|",
        f"| grade | {ops.get('quality_grade')} |",
        f"| ROS m/min | {ops.get('primary_ros_m_min')} |",
        f"| frames | {ops.get('n_frames_staged')} |",
        f"| area_ha | {ops.get('area_ha_max')} |",
        f"| ratio vs Vp | {ops.get('speed_vs_ref_ratio')} |",
        "",
        "## Open CEMS packs",
        "",
        f"n_packs = **{(hub.get('open_cems') or {}).get('n_packs')}**",
        "",
        "| Pack | max_ha | steps | O2_cems |",
        "|------|-------:|------:|---------|",
    ]
    for p in (hub.get("open_cems") or {}).get("packs") or []:
        lines.append(
            f"| {p.get('activation') or p.get('id')} | {float(p.get('max_area_ha') or 0):.1f} | "
            f"{p.get('n_timeline_steps')} | {p.get('O2_cems_delineation')} |"
        )
    lines.extend(
        [
            "",
            "## Gates industriales",
            "",
            "```json",
            json.dumps(hub.get("gates") or {}, indent=2),
            "```",
            "",
            "## Comercial (dual vs CLM-solo)",
            "",
            f"- score_dual: {(hub.get('commercial_compare') or {}).get('score_dual')}",
            f"- score_clm_only: {(hub.get('commercial_compare') or {}).get('score_clm_only')}",
            f"- VENTA_GO: {(hub.get('commercial_compare') or {}).get('VENTA_GO')}",
            "",
            "## Audit",
            "",
            f"- decision audit: `{(card.get('audit') or {}).get('output_hash', '')[:16]}…`",
            f"- hub hash: `{hub.get('content_hash')}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(hub: dict[str, Any]) -> str:
    card = hub.get("decision_card") or {}
    dec = card.get("decision")
    color = {"GO": "#0a7", "HOLD": "#c80", "ABSTAIN": "#a33"}.get(str(dec), "#333")
    mm = (hub.get("ml") or {}).get("metrics") or {}
    packs = (hub.get("open_cems") or {}).get("packs") or []
    rows = "".join(
        f"<tr><td>{p.get('activation') or p.get('id')}</td>"
        f"<td>{float(p.get('max_area_ha') or 0):.0f}</td>"
        f"<td>{p.get('n_timeline_steps')}</td>"
        f"<td>{p.get('O2_cems_delineation')}</td></tr>"
        for p in packs
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Metrics Hub</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#0f1419;color:#e7ecf1}}
.wrap{{max-width:960px;margin:0 auto;padding:1.5rem}}
.card{{background:#1a2332;border-radius:12px;padding:1.2rem;margin:1rem 0}}
.badge{{display:inline-block;padding:.4rem .8rem;border-radius:8px;background:{color};font-weight:700}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:.4rem;border-bottom:1px solid #334;text-align:left}}
.muted{{color:#9ab;font-size:.9rem}}
h1{{margin-top:0}}
</style></head><body><div class="wrap">
<h1>Metrics Hub</h1>
<p class="muted">{hub.get('built_at_utc')} · {hub.get('git_commit')} · hash {str(hub.get('content_hash'))[:16]}…</p>
<div class="card">
  <span class="badge">{dec}</span>
  <p>confidence_pred = <b>{card.get('confidence_pred')}</b> ({card.get('confidence_pred_label')})
  · system_reliability = <b>{card.get('system_reliability_pass')}</b></p>
  <p class="muted">99.9999% applies only to silent-GO prevention under tests — NOT fire accuracy.</p>
</div>
<div class="card">
  <h2>ML v34</h2>
  <ul>
    <li>IoU {mm.get('test_iou')}</li>
    <li>Δ copy {mm.get('improvement_vs_copy_iou')}</li>
    <li>growth {mm.get('model_iou_growth')}</li>
  </ul>
</div>
<div class="card">
  <h2>Open CEMS packs</h2>
  <table><thead><tr><th>Pack</th><th>ha</th><th>steps</th><th>O2</th></tr></thead>
  <tbody>{rows}</tbody></table>
</div>
<div class="card">
  <h2>Commercial</h2>
  <pre>{json.dumps(hub.get('commercial_compare'), indent=2)}</pre>
</div>
<div class="card">
  <h2>Gates</h2>
  <pre>{json.dumps(hub.get('gates'), indent=2)}</pre>
</div>
</div></body></html>
"""


def main() -> int:
    hub = collect()
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "METRICS_HUB.json").write_text(
        json.dumps(hub, indent=2, default=str), encoding="utf-8"
    )
    (docs / "METRICS_HUB.md").write_text(render_md(hub), encoding="utf-8")
    (docs / "METRICS_DASHBOARD.html").write_text(render_html(hub), encoding="utf-8")
    # also decision card standalone
    (docs / "FIRE_DECISION_CARD.json").write_text(
        json.dumps(hub["decision_card"], indent=2, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "decision": hub["decision_card"]["decision"],
                "confidence_pred": hub["decision_card"]["confidence_pred"],
                "n_open_packs": hub["open_cems"]["n_packs"],
                "ml_iou": (hub.get("ml") or {}).get("metrics", {}).get("test_iou"),
                "hash": hub["content_hash"][:16],
                "files": [
                    "docs/METRICS_HUB.json",
                    "docs/METRICS_HUB.md",
                    "docs/METRICS_DASHBOARD.html",
                    "docs/FIRE_DECISION_CARD.json",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
