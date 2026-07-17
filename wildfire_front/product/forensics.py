"""Forensic acta, radio-bridge text, and decision replay.

Dream slice (M2.9): auditor can re-build a Decision Card from stored sources
and a mando can read a short radio line. MD acta — no PDF dependency.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .confidence import content_hash
from .decide_service import API_VERSION, decide_from_request

FORENSIC_SCHEMA = "forensic_bundle_v1"
REPLAY_SOURCES_SCHEMA = "forensic_replay_sources_v1"
RADIO_MAX_CHARS = 280

RADIO_FILENAME = "fire_decision_radio.txt"
ACTA_FILENAME = "fire_decision_acta.md"
MANIFEST_FILENAME = "forensic_manifest.json"
REPLAY_SOURCES_FILENAME = "replay_sources.json"
CARD_FILENAME = "fire_decision_card.json"


def render_radio_bridge(card: Mapping[str, Any], *, lang: str = "es") -> str:
    """Short plain-text line for tablet / radio / SMS-style channel."""
    dec = str(card.get("decision") or "ABSTAIN")
    conf = card.get("confidence_pred")
    conf_s = f"{float(conf):.2f}" if isinstance(conf, (int, float)) else "?"
    label = str(card.get("confidence_pred_label") or "")
    event = str(card.get("event_id") or "IF")
    audit = card.get("audit") if isinstance(card.get("audit"), Mapping) else {}
    oh = str(audit.get("output_hash") or "")[:10]

    if lang == "en":
        base = (
            f"WFD {event}: {dec} conf={conf_s} ({label}). "
            f"NOT dispatch order. hash={oh}…"
        )
    else:
        base = (
            f"WFD {event}: {dec} conf={conf_s} ({label}). "
            f"NO es orden táctica. hash={oh}…"
        )

    # Optional one-line source hint
    avail = []
    for s in card.get("sources") or []:
        if isinstance(s, Mapping) and s.get("available"):
            sid = str(s.get("id") or "")
            if "ops" in sid:
                avail.append("ops")
            elif "open" in sid or "cems" in sid:
                avail.append("cems")
            elif "ml" in sid:
                avail.append("ml")
    if avail:
        src = "+".join(avail)
        extra = f" src={src}"
        if len(base) + len(extra) <= RADIO_MAX_CHARS:
            base = base + extra

    if len(base) > RADIO_MAX_CHARS:
        base = base[: RADIO_MAX_CHARS - 1] + "…"
    return base


def render_acta_md(
    card: Mapping[str, Any],
    *,
    title: str | None = None,
    operator: str | None = None,
) -> str:
    """One-page audit acta (Markdown) for crisis room / legal trail."""
    event = card.get("event_id") or "—"
    dec = card.get("decision") or "—"
    conf = card.get("confidence_pred")
    conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
    label = card.get("confidence_pred_label") or "—"
    audit = card.get("audit") if isinstance(card.get("audit"), Mapping) else {}
    built = card.get("built_at_utc") or datetime.now(timezone.utc).isoformat()
    hdr = title or f"Acta de decisión — {event}"

    lines = [
        f"# {hdr}",
        "",
        f"_Generado: {built} · product: fire_decision_card · api: {API_VERSION}_",
        "",
        "## Decisión",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| **Decisión** | **{dec}** |",
        f"| Confianza (fenómeno) | {conf_s} ({label}) |",
        f"| System reliability | "
        f"{'PASS' if card.get('system_reliability_pass') else 'FAIL'} |",
        f"| Evento | `{event}` |",
    ]
    if operator:
        lines.append(f"| Operador / sala | {operator} |")
    lines += [
        "",
        "## Fuentes",
        "",
        "| Fuente | Disponible | Conf | Peso |",
        "|--------|------------|------|------|",
    ]
    for s in card.get("sources") or []:
        if not isinstance(s, Mapping):
            continue
        avail = "sí" if s.get("available") else "no"
        c = s.get("confidence")
        c_s = f"{float(c):.3f}" if isinstance(c, (int, float)) else "—"
        w = s.get("weight")
        w_s = f"{float(w):.2f}" if isinstance(w, (int, float)) else "—"
        lines.append(f"| {s.get('id')} | {avail} | {c_s} | {w_s} |")

    lines += ["", "## Motivos (resumen)", ""]
    for r in (card.get("reasons") or [])[:20]:
        lines.append(f"- {r}")

    lines += [
        "",
        "## Auditoría (hashes)",
        "",
        f"- **schema:** `{audit.get('schema') or 'fire_decision_card_v1'}`",
        f"- **input_hash:** `{audit.get('input_hash') or '—'}`",
        f"- **output_hash:** `{audit.get('output_hash') or '—'}`",
        f"- **git_commit:** `{audit.get('git_commit') or 'n/a'}`",
        "",
        "## Avisos (siempre)",
        "",
    ]
    for d in card.get("disclaimers") or []:
        lines.append(f"- {d}")
    lines += [
        "",
        "---",
        "",
        "*Esta acta no es una orden de despacho táctico. "
        "ABSTAIN significa que el producto se niega a recomendar acción.*",
        "",
        "Replay: `python -m wildfire_front replay-decide --bundle <dir>`",
        "",
    ]
    return "\n".join(lines)


def extract_replay_sources(
    card: Mapping[str, Any],
    *,
    ml_metrics: Mapping[str, Any] | None = None,
    ops_metrics: Mapping[str, Any] | None = None,
    open_metrics: Mapping[str, Any] | None = None,
    require_ops_for_go: bool = False,
) -> dict[str, Any]:
    """Build replay snapshot. Prefer explicit metrics; else reconstruct hints from card."""
    # Prefer caller-provided raw metrics (exact replay)
    if ml_metrics is None:
        ml_metrics = _metrics_from_card_source(card, "ml_clm_ensemble")
    if ops_metrics is None:
        ops_metrics = _metrics_from_card_source(card, "ops_thermal_front")
    if open_metrics is None:
        open_metrics = _metrics_from_card_source(card, "open_cems_perimeter")

    audit = card.get("audit") if isinstance(card.get("audit"), Mapping) else {}
    metrics = card.get("metrics") if isinstance(card.get("metrics"), Mapping) else {}
    policy_id = (
        audit.get("policy_id")
        or metrics.get("policy_id")
        or "default"
    )
    return {
        "schema": REPLAY_SOURCES_SCHEMA,
        "event_id": card.get("event_id") or "decision",
        "require_ops_for_go": require_ops_for_go,
        "policy_id": policy_id,
        "ml_metrics": dict(ml_metrics) if ml_metrics else None,
        "ops_metrics": dict(ops_metrics) if ops_metrics else None,
        "open_metrics": dict(open_metrics) if open_metrics else None,
        "expected_decision": card.get("decision"),
        "expected_output_hash": audit.get("output_hash"),
        "expected_input_hash": audit.get("input_hash"),
        "expected_confidence_pred": card.get("confidence_pred"),
    }


def _metrics_from_card_source(
    card: Mapping[str, Any], source_id: str
) -> dict[str, Any] | None:
    for s in card.get("sources") or []:
        if isinstance(s, Mapping) and s.get("id") == source_id and s.get("available"):
            m = s.get("metrics")
            if isinstance(m, dict) and m:
                return dict(m)
    # fallback nested metrics block
    metrics = card.get("metrics") if isinstance(card.get("metrics"), Mapping) else {}
    key = {
        "ml_clm_ensemble": "ml",
        "ops_thermal_front": "ops",
        "open_cems_perimeter": "open_cems",
    }.get(source_id)
    if key and isinstance(metrics.get(key), dict):
        return dict(metrics[key])
    return None


def replay_decision(
    sources: Mapping[str, Any],
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Rebuild Decision Card from stored sources and verify hashes/decision."""
    req = {
        "event_id": sources.get("event_id") or "replay",
        "ml_metrics": sources.get("ml_metrics"),
        "ops_metrics": sources.get("ops_metrics"),
        "open_metrics": sources.get("open_metrics"),
        "require_ops_for_go": bool(sources.get("require_ops_for_go", False)),
        "policy_id": sources.get("policy_id") or sources.get("policy") or "default",
        "channel": "forensic_replay",
    }
    card = decide_from_request(req, base=base)
    expected_out = sources.get("expected_output_hash")
    expected_dec = sources.get("expected_decision")
    audit = card.get("audit") if isinstance(card.get("audit"), dict) else {}
    got_out = audit.get("output_hash")
    match_hash = (expected_out is None) or (got_out == expected_out)
    match_dec = (expected_dec is None) or (card.get("decision") == expected_dec)
    conf_ok = True
    exp_c = sources.get("expected_confidence_pred")
    if isinstance(exp_c, (int, float)) and isinstance(card.get("confidence_pred"), (int, float)):
        conf_ok = abs(float(card["confidence_pred"]) - float(exp_c)) < 1e-9

    return {
        "schema": "forensic_replay_result_v1",
        "replay_ok": bool(match_hash and match_dec and conf_ok),
        "match_output_hash": match_hash,
        "match_decision": match_dec,
        "match_confidence": conf_ok,
        "expected_decision": expected_dec,
        "got_decision": card.get("decision"),
        "expected_output_hash": expected_out,
        "got_output_hash": got_out,
        "card": card,
    }


def write_forensic_bundle(
    out_dir: Path | str,
    card: Mapping[str, Any],
    *,
    ml_metrics: Mapping[str, Any] | None = None,
    ops_metrics: Mapping[str, Any] | None = None,
    open_metrics: Mapping[str, Any] | None = None,
    require_ops_for_go: bool = False,
    operator: str | None = None,
    lang: str = "es",
) -> dict[str, str]:
    """Write acta + radio + card + replay sources + manifest. Returns paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    card_dict = dict(card)
    radio = render_radio_bridge(card_dict, lang=lang)
    acta = render_acta_md(card_dict, operator=operator)
    replay_src = extract_replay_sources(
        card_dict,
        ml_metrics=ml_metrics,
        ops_metrics=ops_metrics,
        open_metrics=open_metrics,
        require_ops_for_go=require_ops_for_go,
    )

    paths: dict[str, str] = {}
    card_path = out / CARD_FILENAME
    card_path.write_text(
        json.dumps(card_dict, indent=2, default=str), encoding="utf-8"
    )
    paths["card"] = str(card_path)

    radio_path = out / RADIO_FILENAME
    radio_path.write_text(radio + "\n", encoding="utf-8")
    paths["radio"] = str(radio_path)

    acta_path = out / ACTA_FILENAME
    acta_path.write_text(acta, encoding="utf-8")
    paths["acta"] = str(acta_path)

    replay_path = out / REPLAY_SOURCES_FILENAME
    replay_path.write_text(
        json.dumps(replay_src, indent=2, default=str), encoding="utf-8"
    )
    paths["replay_sources"] = str(replay_path)

    # Verify replay immediately (self-check)
    replay_result = replay_decision(replay_src)
    manifest = {
        "schema": FORENSIC_SCHEMA,
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": card_dict.get("event_id"),
        "decision": card_dict.get("decision"),
        "files": {
            "card": CARD_FILENAME,
            "radio": RADIO_FILENAME,
            "acta": ACTA_FILENAME,
            "replay_sources": REPLAY_SOURCES_FILENAME,
        },
        "input_hash": (card_dict.get("audit") or {}).get("input_hash"),
        "output_hash": (card_dict.get("audit") or {}).get("output_hash"),
        "bundle_hash": content_hash(
            {
                "card_out": (card_dict.get("audit") or {}).get("output_hash"),
                "radio": radio,
                "replay": replay_src,
            }
        ),
        "self_replay_ok": replay_result.get("replay_ok"),
        "disclaimers": list(card_dict.get("disclaimers") or [])[:4],
    }
    man_path = out / MANIFEST_FILENAME
    man_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    paths["manifest"] = str(man_path)
    paths["self_replay_ok"] = str(bool(replay_result.get("replay_ok")))
    return paths


def load_and_replay_bundle(bundle_dir: Path | str, *, base: Path | None = None) -> dict[str, Any]:
    """Load replay_sources.json from a forensic bundle and re-verify."""
    d = Path(bundle_dir)
    src_path = d / REPLAY_SOURCES_FILENAME
    if not src_path.is_file():
        # allow pointing at outbox that only has card
        card_path = d / CARD_FILENAME
        if card_path.is_file():
            card = json.loads(card_path.read_text(encoding="utf-8"))
            src = extract_replay_sources(card)
        else:
            raise FileNotFoundError(f"no {REPLAY_SOURCES_FILENAME} or {CARD_FILENAME} in {d}")
    else:
        src = json.loads(src_path.read_text(encoding="utf-8"))
    return replay_decision(src, base=base)
