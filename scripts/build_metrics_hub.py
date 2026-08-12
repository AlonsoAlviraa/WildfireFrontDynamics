#!/usr/bin/env python3
"""Aggregate ALL project metrics into one hub (JSON + MD + HTML dashboard)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
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


def _iter_decision_card_paths() -> list[tuple[str, Path]]:
    """Known Decision Card JSON locations (no invent)."""
    candidates: list[tuple[str, Path]] = [
        ("demo_third_party", ROOT / "outputs" / "demo_third_party" / "fire_decision_card.json"),
        ("forensic_demo", ROOT / "outputs" / "forensic_demo" / "fire_decision_card.json"),
        ("gold_e2e", ROOT / "outputs" / "gold_e2e" / "fire_decision_card.json"),
        ("gold_e2e_empty", ROOT / "outputs" / "gold_e2e" / "fire_decision_card_empty.json"),
        (
            "fuel_envelope",
            ROOT / "outputs" / "fuel_stack" / "tobarra" / "fire_decision_card_with_envelope.json",
        ),
        ("ml_live_card_demo", ROOT / "outputs" / "ml_live_card_demo" / "decision_card.json"),
        (
            "ml_live_card_demo_abstain",
            ROOT / "outputs" / "ml_live_card_demo_abstain" / "decision_card.json",
        ),
        (
            "ml_live_card_demo_live",
            ROOT / "outputs" / "ml_live_card_demo_live" / "decision_card.json",
        ),
        ("docs_hub_card", ROOT / "docs" / "FIRE_DECISION_CARD.json"),
    ]
    # pilot honesty site cards if present
    pilot_sites = ROOT / "outputs" / "pilot_honesty_card" / "sites"
    if pilot_sites.is_dir():
        for p in sorted(pilot_sites.glob("**/fire_decision_card*.json")):
            candidates.append((f"pilot:{p.parent.name}", p))
        for p in sorted(pilot_sites.glob("**/*decision_card*.json")):
            key = f"pilot:{p.parent.name}/{p.name}"
            if not any(c[1] == p for c in candidates):
                candidates.append((key, p))
    return [(k, p) for k, p in candidates if p.is_file()]


def collect_abstention_slice() -> dict[str, Any]:
    """E7 — honest abstention / source-coverage slice from existing artifacts.

    Rules
    -----
    * Prefer decision cards + reliability suite samples already on disk.
    * If no cards found, rates are **0** with ``unknown=true`` (do not invent).
    * Suite samples are labeled suite_only; never claim field_ops fleet rate.
    * ABSTAIN rate is product-decision rate, **not** fire-spread accuracy.
    """
    samples: list[dict[str, Any]] = []

    # Reliability suite samples (design-bound, not fleet telemetry)
    for rel_path in (
        ROOT / "outputs" / "reliability_gate_report.json",
        ROOT / "outputs" / "demo_third_party" / "reliability_gate_report.json",
    ):
        rel = _load(rel_path)
        if not isinstance(rel, dict):
            continue
        suite_samples = rel.get("samples") or {}
        if not isinstance(suite_samples, dict):
            continue
        for name, card in suite_samples.items():
            if not isinstance(card, dict):
                continue
            samples.append(
                {
                    "id": f"reliability:{rel_path.name}:{name}",
                    "path": str(rel_path.relative_to(ROOT)).replace("\\", "/"),
                    "kind": "suite_sample",
                    "decision": card.get("decision"),
                    "sources": card.get("sources") or [],
                    "confidence_pred": card.get("confidence_pred"),
                    "system_reliability_pass": card.get("system_reliability_pass"),
                }
            )
        # Prefer first report that actually has samples
        if suite_samples:
            break

    # On-disk Decision Cards
    for label, path in _iter_decision_card_paths():
        card = _load(path)
        if not isinstance(card, dict) or not card.get("decision"):
            continue
        # Skip docs hub card if it is purely aggregate mirror (still count once)
        samples.append(
            {
                "id": label,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "kind": "artifact_card",
                "decision": card.get("decision"),
                "sources": card.get("sources") or [],
                "confidence_pred": card.get("confidence_pred"),
                "system_reliability_pass": card.get("system_reliability_pass"),
            }
        )

    n_cards = len(samples)
    if n_cards == 0:
        return {
            "schema": "metrics_hub_abstention_v1",
            "graph_id": "E7",
            "unknown": True,
            "n_cards": 0,
            "n_abstain": 0,
            "n_hold": 0,
            "n_go": 0,
            "abstain_rate": 0.0,
            "hold_rate": 0.0,
            "go_rate": 0.0,
            "source_coverage_mean": 0.0,
            "source_coverage_by_id": {},
            "ml_live_fusion": "OFF",
            "note": (
                "No decision cards found under outputs/; rates set to 0 (unknown). "
                "Do not invent fleet abstain_rate."
            ),
            "samples": [],
        }

    n_abstain = sum(1 for s in samples if str(s.get("decision") or "").upper() == "ABSTAIN")
    n_hold = sum(1 for s in samples if str(s.get("decision") or "").upper() == "HOLD")
    n_go = sum(1 for s in samples if str(s.get("decision") or "").upper() == "GO")

    # Per-source availability across cards that expose sources[]
    coverage_hits: dict[str, int] = {}
    coverage_n: dict[str, int] = {}
    card_coverages: list[float] = []
    for s in samples:
        sources = s.get("sources") or []
        if not isinstance(sources, list) or not sources:
            continue
        available = 0
        for src in sources:
            if not isinstance(src, dict):
                continue
            sid = str(src.get("id") or "unknown")
            coverage_n[sid] = coverage_n.get(sid, 0) + 1
            is_avail = bool(src.get("available"))
            if is_avail:
                coverage_hits[sid] = coverage_hits.get(sid, 0) + 1
                available += 1
            else:
                coverage_hits.setdefault(sid, coverage_hits.get(sid, 0))
        card_coverages.append(available / len(sources))

    source_coverage_by_id = {
        sid: {
            "n_seen": coverage_n[sid],
            "n_available": coverage_hits.get(sid, 0),
            "available_rate": (
                (coverage_hits.get(sid, 0) / coverage_n[sid]) if coverage_n[sid] else 0.0
            ),
        }
        for sid in sorted(coverage_n)
    }
    source_coverage_mean = sum(card_coverages) / len(card_coverages) if card_coverages else 0.0

    # Orion-style R3 check from reliability report if present
    rel = _load(ROOT / "outputs" / "reliability_gate_report.json") or {}
    r3 = None
    if isinstance(rel, dict):
        checks = (rel.get("system_reliability") or {}).get("checks") or {}
        r3 = checks.get("R3_abstention_enforced")

    return {
        "schema": "metrics_hub_abstention_v1",
        "graph_id": "E7",
        "unknown": False,
        "n_cards": n_cards,
        "n_abstain": n_abstain,
        "n_hold": n_hold,
        "n_go": n_go,
        "abstain_rate": n_abstain / n_cards,
        "hold_rate": n_hold / n_cards,
        "go_rate": n_go / n_cards,
        "source_coverage_mean": source_coverage_mean,
        "source_coverage_by_id": source_coverage_by_id,
        "r3_abstention_enforced": r3,
        "ml_live_fusion": "OFF",
        "population": "artifact_cards_plus_suite_samples_not_fleet_telemetry",
        "note": (
            "abstain_rate = fraction of sampled Decision Cards with decision=ABSTAIN "
            "(suite + on-disk artifacts). NOT live fire accuracy, NOT field fleet rate. "
            "source_coverage_mean = mean fraction of sources[] marked available per card. "
            "ml_live fusion remains OFF (weight 0 / not fused)."
        ),
        "samples": [
            {
                "id": s["id"],
                "path": s["path"],
                "kind": s["kind"],
                "decision": s["decision"],
                "confidence_pred": s.get("confidence_pred"),
            }
            for s in samples
        ],
    }


def collect() -> dict[str, Any]:
    clm = _load(ROOT / "models" / "clm_ensemble" / "manifest.json") or {}
    ml_loop = _load(ROOT / "docs" / "ML_LOOP_3WAY_SCORECARD.json") or {}
    industrial = _load(ROOT / "docs" / "INDUSTRIAL_READINESS_STATUS.json") or {}
    compare = _load(ROOT / "docs" / "COMPARE_CLM_VS_OPEN_SCORECARD.json") or {}
    _load(ROOT / "docs" / "PISTA_B_SCORECARD_SNAPSHOT.json") or {}

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
                            r.get("hausdorff_m") for r in ((man or {}).get("ros_proxy_rows") or [])
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
    # Catalog holdout metrics (provenance only — not live certainty / not U1 pitch)
    catalog_metrics = dict(
        clm.get("metrics")
        or {
            "test_iou": champ.get("model_iou"),
            "improvement_vs_copy_iou": champ.get("improvement_vs_copy_iou"),
            "model_iou_growth": champ.get("model_iou_growth"),
        }
    )
    # Hub fusion still uses catalog holdout quality (capped at 0.75 in confidence.py)
    ml_metrics = catalog_metrics

    scorecard = _load(ROOT / "docs" / "ML_PRODUCT_SCORECARD.json") or {}
    sc_primary = scorecard.get("primary") or {}
    sc_unc = scorecard.get("uncertainty") or {}
    sc_gates = scorecard.get("gates") or {}
    u1_lab = {
        "u1_test_honest_mean_iou": sc_primary.get("model_iou"),
        "ece_patch_conf": sc_unc.get("ece_patch_conf"),
        "selective_iou_at_80pct_coverage": sc_unc.get("selective_iou_at_80pct_coverage"),
        "u1_test_honest": sc_gates.get("u1_test_honest"),
        "ml_product_go": sc_gates.get("ml_product_go"),
        "note": (
            "Lab pitch: U1 TEST honest mean IoU + ECE. "
            "Catalog holdout test_iou 0.8963 is provenance only — not live certainty, not ROS."
        ),
    }
    catalog_provenance = {
        "test_iou": catalog_metrics.get("test_iou"),
        "improvement_vs_copy_iou": catalog_metrics.get("improvement_vs_copy_iou"),
        "model_iou_growth": catalog_metrics.get("model_iou_growth"),
        "label": "provenance_only",
        "note": "Do not treat as U1 eval mean IoU or live fire certainty.",
    }

    # representative ops: Tobarra anchor known
    anchors = _load(ROOT / "data" / "infocam_anchors.json") or {}
    tob = (anchors.get("anchors") or {}).get("tobarra_20240802") or {}
    ops_metrics = {
        "quality_grade": "A" if tob.get("status") == "confirmed" else "C",
        "primary_ros_m_min": 5.71,  # documented historical pack
        "n_frames_staged": 35,
        "area_ha_max": tob.get("area_ha"),
        "speed_vs_ref_ratio": (5.71 / float(tob["vp_m_min"])) if tob.get("vp_m_min") else None,
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
        "built_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_head(),
        "content_hash": "",
        "ml": {
            "product": clm.get("version") or "clm_ensemble_v34",
            "pitch": "u1_test_honest",
            "u1_lab": u1_lab,
            "catalog_holdout_provenance": catalog_provenance,
            "metrics": ml_metrics,
            "metrics_note": (
                "metrics.test_iou is catalog holdout (provenance). "
                "Prefer u1_lab for public lab pitch."
            ),
            "member_weights": clm.get("member_weights"),
            "member_temperatures": clm.get("member_temperatures"),
            "protocol": clm.get("protocol"),
            "loop_status": ml_loop.get("status"),
            "champion_name": champ.get("name"),
            "manifest_verdict": clm.get("verdict") or "GO_RESEARCH_HOLDOUT",
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
        "abstention": collect_abstention_slice(),
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
        "| Métrica | Valor |",
        "|---------|------:|",
        f"| product | {ml.get('product')} |",
        f"| **U1 TEST honest mean IoU (lab pitch)** | {(ml.get('u1_lab') or {}).get('u1_test_honest_mean_iou')} |",
        f"| **ECE patch conf (lab)** | {(ml.get('u1_lab') or {}).get('ece_patch_conf')} |",
        f"| selective@80 IoU | {(ml.get('u1_lab') or {}).get('selective_iou_at_80pct_coverage')} |",
        f"| u1_test_honest | {(ml.get('u1_lab') or {}).get('u1_test_honest')} |",
        f"| ml_product_go | {(ml.get('u1_lab') or {}).get('ml_product_go')} |",
        f"| catalog holdout test_iou (provenance only) | {(ml.get('catalog_holdout_provenance') or {}).get('test_iou')} |",
        f"| catalog Δ copy (provenance) | {(ml.get('catalog_holdout_provenance') or {}).get('improvement_vs_copy_iou')} |",
        f"| catalog growth (provenance) | {(ml.get('catalog_holdout_provenance') or {}).get('model_iou_growth')} |",
        f"| manifest_verdict | {ml.get('manifest_verdict')} |",
        f"| temps | {ml.get('member_temperatures')} |",
        f"| mix | {ml.get('member_weights')} |",
        "",
        "> Catalog holdout IoU is **provenance only** — not live certainty, not ROS, not `ml_product_go`.",
        "",
        "## Ops (Tobarra representativo)",
        "",
        "| Métrica | Valor |",
        "|---------|------:|",
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
    ab = hub.get("abstention") or {}
    lines.extend(
        [
            "",
            "## Abstention slice (E7)",
            "",
            f"- **n_cards:** {ab.get('n_cards')} · unknown={ab.get('unknown')}",
            f"- **abstain_rate:** {ab.get('abstain_rate')} "
            f"(ABSTAIN={ab.get('n_abstain')} · HOLD={ab.get('n_hold')} · GO={ab.get('n_go')})",
            f"- **source_coverage_mean:** {ab.get('source_coverage_mean')}",
            f"- **R3_abstention_enforced:** {ab.get('r3_abstention_enforced')}",
            f"- **ml_live_fusion:** {ab.get('ml_live_fusion')}",
            f"- population: `{ab.get('population') or 'none'}`",
            "",
            f"> {ab.get('note') or 'No abstention note.'}",
            "",
            "### Source coverage by id",
            "",
            "| Source | n_seen | n_available | available_rate |",
            "|--------|-------:|------------:|---------------:|",
        ]
    )
    for sid, row in (ab.get("source_coverage_by_id") or {}).items():
        lines.append(
            f"| {sid} | {row.get('n_seen')} | {row.get('n_available')} | "
            f"{row.get('available_rate')} |"
        )
    if not (ab.get("source_coverage_by_id") or {}):
        lines.append("| _(none)_ | 0 | 0 | 0 |")

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
    ml = hub.get("ml") or {}
    u1 = ml.get("u1_lab") or {}
    cat = ml.get("catalog_holdout_provenance") or {}
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
<p class="muted">{hub.get("built_at_utc")} · {hub.get("git_commit")} · hash {str(hub.get("content_hash"))[:16]}…</p>
<div class="card">
  <span class="badge">{dec}</span>
  <p>confidence_pred = <b>{card.get("confidence_pred")}</b> ({card.get("confidence_pred_label")})
  · system_reliability = <b>{card.get("system_reliability_pass")}</b></p>
  <p class="muted">99.9999% applies only to silent-GO prevention under tests — NOT fire accuracy.</p>
</div>
<div class="card">
  <h2>ML v34 — lab pitch (U1 TEST honest)</h2>
  <ul>
    <li><b>U1 mean IoU</b> {u1.get("u1_test_honest_mean_iou")}</li>
    <li><b>ECE</b> {u1.get("ece_patch_conf")}</li>
    <li>selective@80 {u1.get("selective_iou_at_80pct_coverage")}</li>
    <li>u1_test_honest={u1.get("u1_test_honest")} · ml_product_go={u1.get("ml_product_go")}</li>
  </ul>
  <p class="muted">Catalog holdout IoU {cat.get("test_iou")} = <b>provenance only</b> — not live certainty, not ROS.</p>
</div>
<div class="card">
  <h2>Open CEMS packs</h2>
  <table><thead><tr><th>Pack</th><th>ha</th><th>steps</th><th>O2</th></tr></thead>
  <tbody>{rows}</tbody></table>
</div>
<div class="card">
  <h2>Abstention (E7)</h2>
  <ul>
    <li>abstain_rate = <b>{(hub.get("abstention") or {}).get("abstain_rate")}</b>
      (n_cards={(hub.get("abstention") or {}).get("n_cards")})</li>
    <li>source_coverage_mean = {(hub.get("abstention") or {}).get("source_coverage_mean")}</li>
    <li>R3 = {(hub.get("abstention") or {}).get("r3_abstention_enforced")} · ml_live = {(hub.get("abstention") or {}).get("ml_live_fusion")}</li>
  </ul>
  <p class="muted">{(hub.get("abstention") or {}).get("note")}</p>
</div>
<div class="card">
  <h2>Commercial</h2>
  <pre>{json.dumps(hub.get("commercial_compare"), indent=2)}</pre>
</div>
<div class="card">
  <h2>Gates</h2>
  <pre>{json.dumps(hub.get("gates"), indent=2)}</pre>
</div>
</div></body></html>
"""


def main() -> int:
    hub = collect()
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "METRICS_HUB.json").write_text(json.dumps(hub, indent=2, default=str), encoding="utf-8")
    (docs / "METRICS_HUB.md").write_text(render_md(hub), encoding="utf-8")
    (docs / "METRICS_DASHBOARD.html").write_text(render_html(hub), encoding="utf-8")
    # also decision card standalone
    (docs / "FIRE_DECISION_CARD.json").write_text(
        json.dumps(hub["decision_card"], indent=2, default=str), encoding="utf-8"
    )
    ab = hub.get("abstention") or {}
    print(
        json.dumps(
            {
                "ok": True,
                "decision": hub["decision_card"]["decision"],
                "confidence_pred": hub["decision_card"]["confidence_pred"],
                "n_open_packs": hub["open_cems"]["n_packs"],
                "ml_iou": (hub.get("ml") or {}).get("metrics", {}).get("test_iou"),
                "abstain_rate": ab.get("abstain_rate"),
                "n_cards_abstention": ab.get("n_cards"),
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
