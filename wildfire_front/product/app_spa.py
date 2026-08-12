"""Product SPA: accessible ops console (Leaflet map + dashboard).

Composes:
  · operator brief  (``product.operator_ux.build_operator_brief``)
  · fire-status map (``map_status.build_fire_status_map_payload``)
  · optional Decision Card / ops metrics from ``--work-dir`` outbox

UI (Stitch «WFD Industrial C2»): dark EOC/map-first shell, dense KPIs, short labels.
Modo fácil by default. HTML renderer: ``app_spa_html.render_product_app_html``.

Schema: ``wfd_product_app_v1``
Honesty: not tactical dispatch · field_ops fusion OFF · no GO_Q invent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from wildfire_front.map_status import build_fire_status_map_payload
from wildfire_front.product.app_spa_html import render_product_app_html
from wildfire_front.product.fire_catalog import (
    new_fire_intake_steps,
    product_action_catalog,
    scan_fire_catalog,
)
from wildfire_front.product.live_ops import live_ops_payload_block
from wildfire_front.product.operator_ux import (
    BRIEF_ROLES,
    ROLE_PLAYBOOKS,
    build_operator_brief,
)
from wildfire_front.product.plain_language import build_plain_language_payload
from wildfire_front.product.spa_honesty_ui import (
    build_h1_eng_rehearsal,
    build_split_conf_view,
    build_sr_ladder,
    build_uncertainty_bar_view,
    load_decision_log_surface,
    load_vv_scorecard_surface,
)

SCHEMA = "wfd_product_app_v1"
DEFAULT_OUTPUT = Path("outputs") / "app"
DEFAULT_TITLE = "WFD OPS"
DEFAULT_UI_MODE = "simple"  # plain language; CLI hidden until advanced
MAX_PACK_FIRES = 8
# Soft cap on pack payload JSON characters (~2.5 MiB) to avoid OOM in browser
MAX_PACK_JSON_CHARS = 2_500_000
# Same-origin proxy path when SPA is served with --bridge-decide (avoids CORS)
BRIDGE_PROXY_PATH = "/bridge/v1/decide"
BRIDGE_PROXY_HEALTH = "/bridge/health"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_http_url(url: str | None) -> bool:
    """True only when scheme is http(s) and hostname is exactly loopback.

    Rejects prefix tricks like ``http://127.0.0.1.evil.example`` and
    userinfo forms like ``http://127.0.0.1@evil.example``.
    """
    if not url or not str(url).strip():
        return False
    try:
        parsed = urlparse(str(url).strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in _LOOPBACK_HOSTS


_DECISION_CARD_CANDIDATES = (
    "outbox/fire_decision_card.json",
    "fire_decision_card.json",
)
_OPS_METRICS_CANDIDATES = (
    "outbox/operational_metrics.json",
    "operational_metrics.json",
)
_SUMMARY_CANDIDATES = (
    "outbox/summary.json",
    "summary.json",
    "outbox/incident_state.json",
    "incident_state.json",
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _first_json(work_dir: Path | None, candidates: tuple[str, ...]) -> dict[str, Any] | None:
    if work_dir is None:
        return None
    root = Path(work_dir)
    for rel in candidates:
        hit = _load_json(root / rel)
        if hit is not None:
            return hit
    return None


def _slim_decision_card(card: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep SPA payload compact — drop heavy nested audit blobs when huge."""
    if not card:
        return None
    keep_keys = (
        "event_id",
        "decision",
        "confidence_pred",
        "confidence_pred_label",
        "system_reliability_pass",
        "sources",
        "metrics",
        "reasons",
        "disclaimers",
        "audit",
        "schema",
        "policy_id",
        "channel",
    )
    out = {k: card[k] for k in keep_keys if k in card}
    # Cap sources / reasons for embed size
    if isinstance(out.get("sources"), list):
        out["sources"] = out["sources"][:8]
    if isinstance(out.get("reasons"), list):
        out["reasons"] = out["reasons"][:12]
    if isinstance(out.get("disclaimers"), list):
        out["disclaimers"] = out["disclaimers"][:6]
    return out


def _slim_ops_metrics(ops: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ops:
        return None
    keys = (
        "quality_grade",
        "primary_ros_m_min",
        "speed_median_m_min",
        "speed_p95_m_min",
        "area_ha_max",
        "area_ha_last",
        "area_ha_first",
        "n_frames",
        "num_observations",
        "observation_count",
        "speed_status",
        "accepted_input_ratio",
        "interval_s_median",
    )
    slim = {k: ops[k] for k in keys if k in ops}
    # some cards nest grade under different names
    if "quality_grade" not in slim and ops.get("grade"):
        slim["quality_grade"] = ops.get("grade")
    return slim or dict(list(ops.items())[:20])


def role_playbook_hints() -> dict[str, dict[str, Any]]:
    """Short role → playbook hints for SPA role switcher (no gate invention)."""
    out: dict[str, dict[str, Any]] = {}
    for key in sorted(BRIEF_ROLES):
        play = ROLE_PLAYBOOKS[key]
        out[key] = {
            "id": key,
            "title": play.get("title"),
            "audience": play.get("audience"),
            "hint": str(play.get("audience") or play.get("title") or key),
            "primary_cmd": play.get("primary_cmd"),
            "sequence_head": list(play.get("sequence") or [])[:3],
        }
    return out


def _hero_from_decision(
    decision: dict[str, Any] | None,
    brief: dict[str, Any],
) -> dict[str, Any]:
    if decision:
        hero_decision = str(decision.get("decision") or "ABSTAIN").upper()
        hero_conf = decision.get("confidence_pred")
        hero_label = decision.get("confidence_pred_label")
    else:
        hero_decision = "BRIEF"
        hero_conf = None
        hero_label = str(brief.get("overall_light") or "AMARILLO")
    hero_plain = {
        "GO": "El sistema se atreve a proponer una orientación con las fuentes actuales.",
        "HOLD": "Hay datos, pero no bastan o chocan: espera / revisa antes de actuar.",
        "ABSTAIN": "El sistema se calla a propósito — callarse es correcto si faltan fuentes.",
        "BRIEF": "Vista de producto (semáforo / brief) sin Decision Card local del incendio.",
    }.get(hero_decision, "Lectura de apoyo del incendio — no es despacho táctico.")
    return {
        "decision": hero_decision,
        "confidence_pred": hero_conf,
        "confidence_label": hero_label,
        "overall_light": brief.get("overall_light"),
        "headline": brief.get("headline"),
        "plain": hero_plain,
        "for_fire": (
            "Primera lectura del incendio activo: si habla (GO/HOLD) o se calla (ABSTAIN)."
        ),
    }


def _slim_map_for_pack(map_payload: dict[str, Any] | None) -> dict[str, Any]:
    """Keep client-switchable map slice without unbounded bulk."""
    if not map_payload:
        return {
            "schema": "wfd_fire_status_map_v1",
            "layers": [],
            "center": {"lon": -3.7, "lat": 40.4},
            "zoom": 7,
            "connectivity": {"status": "skipped"},
            "layer_summary": [],
        }
    layers_out: list[dict[str, Any]] = []
    for lyr in list(map_payload.get("layers") or [])[:6]:
        if not isinstance(lyr, dict):
            continue
        gj = lyr.get("geojson")
        if isinstance(gj, dict) and isinstance(gj.get("features"), list):
            feats = gj["features"][:80]
            gj = {**gj, "features": feats}
        layers_out.append(
            {
                "id": lyr.get("id"),
                "name": lyr.get("name"),
                "source": lyr.get("source"),
                "geojson": gj,
            }
        )
    return {
        "schema": map_payload.get("schema") or "wfd_fire_status_map_v1",
        "layers": layers_out,
        "center": map_payload.get("center") or {"lon": -3.7, "lat": 40.4},
        "zoom": map_payload.get("zoom") or 7,
        "connectivity": dict(map_payload.get("connectivity") or {}),
        "layer_summary": list(map_payload.get("layer_summary") or [])[:12],
        "firms": map_payload.get("firms"),
    }


def _outbox_last_run(wd: Path | None) -> dict[str, Any] | None:
    """Optional outbox snapshot for «Último acto» panel (no shell-exec)."""
    if wd is None:
        return None
    card = _first_json(wd, _DECISION_CARD_CANDIDATES)
    ops = _first_json(wd, _OPS_METRICS_CANDIDATES)
    if not card and not ops:
        return None
    return {
        "source": "outbox",
        "decision": (card or {}).get("decision"),
        "confidence_pred": (card or {}).get("confidence_pred"),
        "event_id": (card or {}).get("event_id"),
        "quality_grade": (ops or {}).get("quality_grade") or (ops or {}).get("grade"),
        "primary_ros_m_min": (ops or {}).get("primary_ros_m_min"),
        "hint": (
            "Lectura embebida del outbox al regenerar la SPA "
            "(no ejecuta comandos desde el navegador)."
        ),
    }


def _build_pack_entry(
    *,
    fire_row: dict[str, Any],
    repo_root: Path,
    brief: dict[str, Any],
    live: bool,
    day_range: int,
    fixture_csv: Path | str | None,
) -> dict[str, Any]:
    wd = Path(fire_row["work_dir"])
    map_payload = build_fire_status_map_payload(
        work_dir=wd,
        geojson_paths=None,
        bbox=None,
        center=None,
        live=bool(live),
        day_range=int(day_range or 1),
        fixture_csv=fixture_csv,
        title=f"{fire_row.get('id')} · map",
    )
    decision = _slim_decision_card(_first_json(wd, _DECISION_CARD_CANDIDATES))
    ops = _slim_ops_metrics(_first_json(wd, _OPS_METRICS_CANDIDATES))
    hero = _hero_from_decision(decision, brief)
    wd_rel = fire_row.get("work_dir_rel")
    return {
        "id": fire_row.get("id"),
        "label": fire_row.get("label") or fire_row.get("id"),
        "work_dir_rel": wd_rel,
        "hero": hero,
        "decision_card": decision,
        "ops_metrics": ops,
        "map": _slim_map_for_pack(map_payload),
        "outbox_last_run": _outbox_last_run(wd),
        "cmds": {
            "rebuild_cmd": fire_row.get("rebuild_cmd"),
            "map_cmd": fire_row.get("map_cmd"),
            "status_cmd": fire_row.get("status_cmd"),
            "decide_cmd": fire_row.get("decide_cmd"),
            "acta_cmd": fire_row.get("acta_cmd"),
        },
    }


def build_product_app_payload(
    *,
    work_dir: Path | str | None = None,
    role: str = "operator",
    geojson_paths: list[Path | str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    center: tuple[float, float] | None = None,
    live: bool = False,
    day_range: int = 1,
    fixture_csv: Path | str | None = None,
    title: str = DEFAULT_TITLE,
    repo: Any = None,
    scan: bool = True,
    fire_id: str | None = None,
    ui_mode: str = DEFAULT_UI_MODE,
    bridge_decide: str | None = None,
    pack_fires: bool = False,
    pack_fire_ids: list[str] | None = None,
    pack_cap: int = MAX_PACK_FIRES,
    live_ops_enabled: bool = False,
) -> dict[str, Any]:
    """Compose full SPA model (brief + map + fire catalog + product actions).

    ``ui_mode`` default is ``simple`` (plain language, CLI hidden in HTML until
    the user toggles Avanzado). Payload always includes both layers.

    Optional:
      · ``bridge_decide`` — base URL for live Decision Card refresh (local only)
      · ``pack_fires`` / ``pack_fire_ids`` — multi-IF client switch pack (cap N)
      · ``live_ops_enabled`` — same-origin POST /live/v1/* when SPA is ``--serve``
    """
    repo_root = Path(repo) if repo is not None else Path.cwd()
    catalog = scan_fire_catalog(repo_root) if scan else []
    mode = str(ui_mode or DEFAULT_UI_MODE).strip().lower()
    if mode not in ("simple", "advanced"):
        mode = DEFAULT_UI_MODE
    plain_block = build_plain_language_payload()
    role_key = str(role or "operator").strip().lower()
    if role_key not in BRIEF_ROLES:
        role_key = "operator"

    # Resolve work_dir from fire_id if needed
    wd: Path | None
    if work_dir is not None:
        wd = Path(work_dir)
    elif fire_id:
        match = next((f for f in catalog if f.get("id") == fire_id), None)
        wd = Path(match["work_dir"]) if match else None
    else:
        # Prefer richest incident in catalog for empty open
        wd = None
        for f in catalog:
            if f.get("has_geojson") and f.get("has_decision_card"):
                wd = Path(f["work_dir"])
                break
        if wd is None and catalog:
            wd = Path(catalog[0]["work_dir"])

    # Mark selected fire in catalog
    selected_id = None
    if wd is not None:
        wd_res = str(wd.resolve())
        for f in catalog:
            try:
                same = str(Path(f["work_dir"]).resolve()) == wd_res
            except Exception:
                same = f.get("work_dir_rel") == str(wd).replace("\\", "/")
            f["selected"] = same
            if same:
                selected_id = f.get("id")
    else:
        for f in catalog:
            f["selected"] = False

    brief = build_operator_brief(repo_root, role=role_key)
    role_hints = role_playbook_hints()

    map_payload = build_fire_status_map_payload(
        work_dir=wd,
        geojson_paths=geojson_paths,
        bbox=bbox,
        center=center,
        live=bool(live),
        day_range=int(day_range or 1),
        fixture_csv=fixture_csv,
        title=f"{title} · map",
    )

    decision = _slim_decision_card(_first_json(wd, _DECISION_CARD_CANDIDATES))
    ops = _slim_ops_metrics(_first_json(wd, _OPS_METRICS_CANDIDATES))
    summary = _first_json(wd, _SUMMARY_CANDIDATES)
    hero = _hero_from_decision(decision, brief)

    rails = {
        "field_ops_ml_live_fusion": (brief.get("rails") or {}).get(
            "field_ops_ml_live_fusion", "OFF"
        ),
        "ml_product_go": bool((brief.get("rails") or {}).get("ml_product_go", True)),
        "iou_is_not_ros": True,
        "lab_go_ne_field_fusion": True,
        "not_tactical_dispatch": True,
        "go_q_invent_forbidden": True,
        "nrt_not_official_perimeter": True,
        "hotspots_not_burned_area": True,
    }

    layers_summary = list(map_payload.get("layer_summary") or [])
    connectivity = dict(map_payload.get("connectivity") or {})

    actions = product_action_catalog()
    # Bind DIR placeholder to selected work-dir for one-click copy
    wd_rel = None
    if wd is not None:
        try:
            wd_rel = str(wd.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
        except Exception:
            wd_rel = str(wd).replace("\\", "/")
    bound_actions: list[dict[str, Any]] = []
    for a in actions:
        cmd = str(a.get("cmd") or "")
        if wd_rel:
            cmd = cmd.replace("DIR", wd_rel)
        bound_actions.append({**a, "cmd": cmd, "cmd_template": a.get("cmd")})

    rebuild_selected = (
        f'python -m wildfire_front app --work-dir "{wd_rel}" --role {role_key} --open'
        if wd_rel
        else f"python -m wildfire_front app --role {role_key} --open"
    )

    # Optional multi-fire pack (client-side IF switch without re-running Python).
    # When pack requested but catalog empty: still emit structure (enabled=False).
    pack_block: dict[str, Any] | None = None
    want_pack = bool(pack_fires) or bool(pack_fire_ids)
    if want_pack:
        cap = max(1, min(int(pack_cap or MAX_PACK_FIRES), MAX_PACK_FIRES))
        entries: dict[str, Any] = {}
        truncated = False
        skipped_oversize = 0
        if catalog:
            id_filter = set(pack_fire_ids) if pack_fire_ids else None
            candidates: list[dict[str, Any]] = []
            # Prefer selected first, then catalog order
            ordered = sorted(
                catalog,
                key=lambda f: (0 if f.get("selected") else 1, str(f.get("id") or "")),
            )
            for f in ordered:
                if id_filter is not None and f.get("id") not in id_filter:
                    continue
                candidates.append(f)
                if len(candidates) >= cap:
                    break
            for f in candidates:
                try:
                    entry = _build_pack_entry(
                        fire_row=f,
                        repo_root=repo_root,
                        brief=brief,
                        live=False,  # pack is offline-stable
                        day_range=int(day_range or 1),
                        fixture_csv=fixture_csv,
                    )
                except Exception:
                    continue
                fid = str(f.get("id"))
                probe = json.dumps({**entries, fid: entry}, ensure_ascii=False)
                if len(probe) > MAX_PACK_JSON_CHARS:
                    # Hard rail: never accept an entry that pushes (or alone exceeds) the cap
                    truncated = True
                    if not entries:
                        # Oversized first entry: try ultra-slim (no geojson features)
                        slim_map = dict(entry.get("map") or {})
                        layers = []
                        for lyr in list(slim_map.get("layers") or [])[:2]:
                            if isinstance(lyr, dict):
                                layers.append(
                                    {
                                        "id": lyr.get("id"),
                                        "name": lyr.get("name"),
                                        "source": lyr.get("source"),
                                        "geojson": None,
                                    }
                                )
                        slim_map["layers"] = layers
                        entry_slim = {**entry, "map": slim_map}
                        probe2 = json.dumps({fid: entry_slim}, ensure_ascii=False)
                        if len(probe2) <= MAX_PACK_JSON_CHARS:
                            entries[fid] = entry_slim
                        else:
                            skipped_oversize += 1
                        # continue scanning other fires only if still empty after skip
                        if not entries:
                            continue
                        break
                    break
                entries[fid] = entry
        pack_block = {
            "enabled": bool(entries),
            "cap": cap,
            "max_json_chars": MAX_PACK_JSON_CHARS,
            "n": len(entries),
            "fire_ids": list(entries.keys()),
            "truncated": truncated,
            "skipped_oversize": skipped_oversize,
            "baseline_id": selected_id,
            "note": (
                "Selector cambia hero/map en cliente cuando el IF está en el pack. "
                "IF fuera del pack: estado limpio (BRIEF) + copiar rebuild — no se "
                "muestra el mapa del IF anterior."
                if entries
                else "Pack solicitado pero catálogo vacío o sin entradas empaquetables."
            ),
            "by_id": entries,
        }

    bridge_url = (str(bridge_decide).strip() if bridge_decide else "") or None
    if bridge_url and not is_loopback_http_url(bridge_url):
        bridge_url = None

    return {
        "schema": SCHEMA,
        "product": "WildfireFrontDynamics",
        "version": "0.1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "title": title,
        "subtitle": "Industrial ops · mapa · decisión · no despacho táctico",
        "ui_mode": mode,
        "work_dir": str(wd) if wd else None,
        "work_dir_rel": wd_rel,
        "selected_fire_id": selected_id,
        "role": brief.get("role") or role_key,
        "role_hints": role_hints,
        "hero": hero,
        "brief": brief,
        "map": map_payload,
        "decision_card": decision,
        "ops_metrics": ops,
        "outbox_last_run": _outbox_last_run(wd),
        "last_act": {
            "act": None,
            "cmd": None,
            "ts": None,
            "hint": (
                "Con --serve: pulse Estado / Decidir / Acta (live). "
                "Sin serve: copiar CLI (sin shell en browser)."
            ),
        },
        "live_ops": live_ops_payload_block(enabled=bool(live_ops_enabled)),
        "bridge_decide": {
            "enabled": bool(bridge_url),
            "url": bridge_url,
            "endpoint": "/v1/decide",
            "health": "/health",
            # Same-origin proxy when SPA is run with --serve (preferred; avoids CORS)
            "proxy_path": BRIDGE_PROXY_PATH if bridge_url else None,
            "proxy_health": BRIDGE_PROXY_HEALTH if bridge_url else None,
            "prefer_proxy": True,
            "note": (
                "Solo activo con --bridge-decide (loopback hostname exact). "
                "Con --serve, la SPA usa proxy same-origin /bridge/v1/decide → upstream. "
                "file:// o upstream caído: fallback silencioso a card embebida. "
                "serve-decide necesita --base-dir del repo para work_dir relativo. "
                "No fusion; no despacho táctico."
            ),
        },
        "pack": pack_block,
        "incident_summary": (
            {
                "event_id": (summary or {}).get("event_id") or (decision or {}).get("event_id"),
                "keys": sorted((summary or {}).keys())[:24] if summary else [],
                "present": summary is not None,
            }
            if wd
            else None
        ),
        "fires": catalog,
        "fire_count": len(catalog),
        "product_actions": bound_actions,
        "new_fire_intake": new_fire_intake_steps(),
        "plain_language": plain_block,
        "glossary": plain_block.get("glossary") or [],
        "rebuild": {
            "selected_cmd": rebuild_selected,
            "list_fires_cmd": "python -m wildfire_front app --list-fires",
            "with_role_cmd": rebuild_selected,
            "note": (
                "La SPA es estática (sin servidor). Con --pack-fires el selector puede "
                "cambiar IF empaquetados en cliente; fuera del pack o tras nuevos datos, "
                "ejecuta rebuild (o Pro: copiar con --role)."
            ),
            "note_simple": (
                "Al cambiar de incendio empaquetado, la consola actualiza mapa y decisión "
                "en el navegador. Si no está empaquetado, pulse «Abrir consola»."
            ),
        },
        "layer_summary": layers_summary,
        "connectivity": connectivity,
        "rails": rails,
        # Agent A honesty UI (Mes2 PR1-A uncertainty bar · A6 H1 · A7 SR · A8 decision-log)
        "uncertainty_bar": build_uncertainty_bar_view(
            confidence_pred=(
                (hero or {}).get("confidence_pred")
                if (hero or {}).get("confidence_pred") is not None
                else (decision or {}).get("confidence_pred")
            ),
            confidence_label=(
                (hero or {}).get("confidence_label")
                or (decision or {}).get("confidence_pred_label")
            ),
        ),
        "split_conf": build_split_conf_view(
            confidence_pred=(
                (hero or {}).get("confidence_pred")
                if (hero or {}).get("confidence_pred") is not None
                else (decision or {}).get("confidence_pred")
            ),
            confidence_label=(
                (hero or {}).get("confidence_label")
                or (decision or {}).get("confidence_pred_label")
            ),
            ops_metrics=ops if isinstance(ops, dict) else None,
        ),
        "h1_eng_rehearsal": build_h1_eng_rehearsal(
            repo_root=repo_root,
            live_ops_enabled=bool(live_ops_enabled),
        ),
        "sr_ladder": build_sr_ladder(
            decision=str((decision or {}).get("decision") or (hero or {}).get("decision") or "")
        ),
        "decision_log": load_decision_log_surface(
            work_dir=wd,
            decision_card=decision if isinstance(decision, dict) else None,
            repo_root=repo_root,
        ),
        "vv_scorecard": load_vv_scorecard_surface(
            work_dir=wd,
            repo_root=repo_root,
        ),
        "disclaimer": (
            "Not validated tactical dispatch. Thermal mask ≠ official perimeter. "
            "15/30/60 envelopes are extrapolated guidance only. "
            "FIRMS NRT hotspots ≠ burned area. field_ops ML fusion = OFF. "
            "ABSTAIN is a product feature, not a crash."
        ),
        "disclaimer_simple": plain_block.get("disclaimer_simple"),
        "docs": {
            "app": "docs/APP.md",
            "map": "docs/FIRE_STATUS_MAP.md",
            "operator_cli": "docs/OPERATOR_CLI_CHANGES.md",
            "start_here": "docs/START_HERE.md",
            "audit_spa": "docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md",
            "cheatsheet": "docs/CHEATSHEET_DEMO_12MIN.md",
            "h1_runbook": "docs/H1_GO_Q_RUNBOOK.md",
        },
    }


# HTML lives in app_spa_html.py (Stitch accessible redesign). Re-export for tests/API.
__all__ = [
    "SCHEMA",
    "DEFAULT_OUTPUT",
    "DEFAULT_TITLE",
    "DEFAULT_UI_MODE",
    "MAX_PACK_FIRES",
    "MAX_PACK_JSON_CHARS",
    "BRIDGE_PROXY_PATH",
    "is_loopback_http_url",
    "build_product_app_payload",
    "render_product_app_html",
    "write_product_app",
]


def write_product_app(
    payload: dict[str, Any],
    output_dir: Path | str,
    *,
    html_name: str = "index.html",
    json_name: str = "app_payload.json",
) -> dict[str, Path]:
    """Write SPA HTML + JSON payload; return paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / html_name
    json_path = out / json_name
    html_path.write_text(render_product_app_html(payload), encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"html": html_path, "json": json_path}
