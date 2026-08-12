"""Live Ops Kernel — same-origin POST acts for SPA ``app --serve``.

Loopback-only product surface: Estado · Decidir · Acta invoke real Python APIs
(no free-form shell from the browser). Path allowlist under ``base_dir``
(default: repo root). Honesty rails always present; fusion never ON.

Endpoints (served only when live ops enabled on the SPA HTTP server):
  GET  /live/v1/health
  POST /live/v1/status
  POST /live/v1/decide
  POST /live/v1/export-acta
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wildfire_front.product.decide_service import (
    REPO_ROOT,
    PathNotAllowedError,
    UntrustedInlineMetricsError,
    decide_from_request,
)

LIVE_OPS_SCHEMA = "wfd_live_ops_v1"

LIVE_PATH_STATUS = "/live/v1/status"
LIVE_PATH_DECIDE = "/live/v1/decide"
LIVE_PATH_EXPORT_ACTA = "/live/v1/export-acta"
LIVE_PATH_REPLAY = "/live/v1/replay-third-party"
LIVE_PATH_HEALTH = "/live/v1/health"

HONESTY_RAILS: dict[str, Any] = {
    "field_ops_ml_live_fusion": "OFF",
    "not_tactical_dispatch": True,
    "go_q_invent_forbidden": True,
    "iou_is_not_ros": True,
    "nrt_not_official_perimeter": True,
    "hotspots_not_burned_area": True,
    "lab_go_ne_field_fusion": True,
}


def honesty_rails() -> dict[str, Any]:
    """Immutable honesty snapshot (never enable fusion / invent GO_Q)."""
    return dict(HONESTY_RAILS)


def live_ops_payload_block(*, enabled: bool) -> dict[str, Any]:
    """Embed in SPA payload so the browser knows same-origin live acts exist."""
    return {
        "enabled": bool(enabled),
        "schema": LIVE_OPS_SCHEMA,
        "endpoints": {
            "health": LIVE_PATH_HEALTH,
            "status": LIVE_PATH_STATUS,
            "decide": LIVE_PATH_DECIDE,
            "export_acta": LIVE_PATH_EXPORT_ACTA,
            "replay_third_party": LIVE_PATH_REPLAY,
        },
        "policy_default": "field_ops",
        "channel": "live_ops_loopback",
        "note": (
            "Activo solo con app --serve (loopback). POST same-origin; sin shell "
            "desde el browser. Fusion OFF; no inventa GO_Q; no despacho táctico. "
            "file:// o sin serve: fallback a copiar CLI."
        ),
        "honesty_rails": honesty_rails(),
    }


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_work_dir(
    work_dir: str | Path | None,
    *,
    base: Path | None = None,
) -> Path:
    """Resolve and allowlist ``work_dir`` under ``base`` (repo root by default).

    Rejects empty, ``..`` segments, null bytes, and paths that escape base.
    """
    root = Path(base or REPO_ROOT).resolve()
    if work_dir is None or str(work_dir).strip() == "":
        raise PathNotAllowedError("work_dir required")
    raw = str(work_dir).strip().replace("\\", "/")
    if "\x00" in raw:
        raise PathNotAllowedError("null byte in work_dir")
    # Reject parent traversal tokens before resolve (Windows + posix)
    parts = [p for p in raw.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PathNotAllowedError("path traversal rejected")
    p = Path(work_dir)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (root / p).resolve()
    if not _is_under(resolved, root):
        raise PathNotAllowedError(f"work_dir outside allowlist: {work_dir}")
    if not resolved.exists():
        raise PathNotAllowedError(f"work_dir not found: {work_dir}")
    if not resolved.is_dir():
        raise PathNotAllowedError(f"work_dir is not a directory: {work_dir}")
    return resolved


def _rel_to_base(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _lightweight_incident_status(work_dir: Path) -> dict[str, Any]:
    """Outbox status without importing incident.pipeline (avoids heavy cli import).

    Reads the same outbox artifacts the SPA / doctor surface care about:
    incident_state, fire_decision_card, operational_metrics.
    """
    wd = Path(work_dir)
    outbox = wd / "outbox"
    state = _read_json_file(outbox / "incident_state.json")
    card = _read_json_file(outbox / "fire_decision_card.json") or _read_json_file(
        wd / "fire_decision_card.json"
    )
    ops = _read_json_file(outbox / "operational_metrics.json") or _read_json_file(
        wd / "operational_metrics.json"
    )
    report: dict[str, Any] = {
        "product": "incident_runtime_v1",
        "command": "status",
        "source": "live_ops_lightweight",
        "work_dir": str(wd.resolve()),
        "outbox": str(outbox.resolve()),
        "has_state": state is not None,
        "has_decision_card": card is not None,
        "has_ops_metrics": ops is not None,
        "status": "no_state" if state is None else "ready",
    }
    if state is None and card is None:
        report["message"] = (
            "No incident_state.json / Decision Card in outbox — "
            "run incident update/watch or decide first"
        )
        return report
    if state:
        report.update(
            {
                "event_id": state.get("event_id"),
                "quality_grade": state.get("quality_grade"),
                "quality_label_es": state.get("quality_label_es"),
                "primary_ros_m_min": state.get("primary_ros_m_min"),
                "area_ha_max": state.get("area_ha_max"),
                "n_updates": state.get("n_updates"),
                "updated_at_utc": state.get("updated_at_utc"),
                "last_error": state.get("last_error"),
            }
        )
    if card:
        report["decision"] = card.get("decision")
        report["confidence_pred"] = card.get("confidence_pred")
        report["event_id"] = report.get("event_id") or card.get("event_id")
    if ops:
        report["ops_primary_ros_m_min"] = ops.get("primary_ros_m_min") or ops.get(
            "speed_median_m_min"
        )
        if report.get("primary_ros_m_min") is None:
            report["primary_ros_m_min"] = report.get("ops_primary_ros_m_min")
    return report


def handle_status(
    body: dict[str, Any] | None = None,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Incident outbox status (lightweight JSON read; no heavy pipeline import)."""
    req = dict(body or {})
    root = Path(base or REPO_ROOT).resolve()
    wd = resolve_work_dir(req.get("work_dir"), base=root)
    report = _lightweight_incident_status(wd)
    return {
        "ok": True,
        "act": "status",
        "schema": LIVE_OPS_SCHEMA,
        "work_dir": str(wd),
        "work_dir_rel": _rel_to_base(wd, root),
        "result": report,
        "summary": {
            "status": report.get("status"),
            "event_id": report.get("event_id"),
            "decision": report.get("decision"),
            "quality_grade": report.get("quality_grade"),
            "primary_ros_m_min": report.get("primary_ros_m_min"),
            "has_state": report.get("has_state"),
            "has_decision_card": report.get("has_decision_card"),
            "message": report.get("message"),
        },
        "honesty_rails": honesty_rails(),
    }


def handle_decide(
    body: dict[str, Any] | None = None,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """field_ops Decision Card via decide_from_request (fusion OFF).

    Channel ``live_ops_loopback`` (not ``http_api``) so work_dir sources under
    the allowlisted base load like CLI — without accepting client free-floating
    reliability booleans or enabling ML live fusion. ABSTAIN remains valid when
    sources are genuinely empty.
    """
    req_in = dict(body or {})
    root = Path(base or REPO_ROOT).resolve()
    wd = resolve_work_dir(req_in.get("work_dir"), base=root)
    event_id = str(req_in.get("event_id") or Path(wd).name or "live_ops")
    # Loopback Live Ops: load paths under base, never client-asserted R1–R4,
    # never ML fusion ON. Distinct from unauthenticated multi-tenant HTTP.
    req = {
        "channel": "live_ops_loopback",
        "policy_id": str(req_in.get("policy_id") or req_in.get("policy") or "field_ops"),
        "work_dir": str(wd),
        "event_id": event_id,
        "require_ops_for_go": bool(req_in.get("require_ops_for_go", False)),
        "use_ml_v34": False,
        "allow_ml_live_in_fusion": False,
        "ml_live_trusted": False,
    }
    try:
        # trust_client_reliability=True only unlocks path loading under base+repo
        # roots; free-floating gates still rejected (channel not in test set).
        card = decide_from_request(req, base=root, trust_client_reliability=True)
    except UntrustedInlineMetricsError as exc:
        return {
            "ok": False,
            "act": "decide",
            "schema": LIVE_OPS_SCHEMA,
            "error": "untrusted_inline_metrics",
            "detail": str(exc),
            "honesty_rails": honesty_rails(),
        }
    # Surface slim card fields for SPA hero + honesty proof
    fusion = (
        (card.get("rails") or {}).get("field_ops_ml_live_fusion")
        or (card.get("policy") or {}).get("ml_live_fusion")
        or "OFF"
    )
    if fusion and str(fusion).upper() not in ("OFF", "FALSE", "0", "NO"):
        # Hard rail: never surface fusion ON from live ops
        fusion = "OFF"
    outbox_card = _read_json_file(wd / "outbox" / "fire_decision_card.json") or _read_json_file(
        wd / "fire_decision_card.json"
    )
    outbox_decision = (outbox_card or {}).get("decision")
    return {
        "ok": True,
        "act": "decide",
        "schema": LIVE_OPS_SCHEMA,
        "work_dir": str(wd),
        "work_dir_rel": _rel_to_base(wd, root),
        "channel": "live_ops_loopback",
        "result": card,
        "summary": {
            "decision": card.get("decision"),
            "confidence_pred": card.get("confidence_pred"),
            "confidence_pred_label": card.get("confidence_pred_label"),
            "event_id": card.get("event_id"),
            "system_reliability_pass": card.get("system_reliability_pass"),
            "latency_ms": card.get("latency_ms"),
            "policy_id": (card.get("policy") or {}).get("id")
            or req["policy_id"],
            "field_ops_ml_live_fusion": "OFF",
            "reasons_head": list((card.get("reasons") or [])[:4]),
            "outbox_decision": outbox_decision,
            "note": (
                "Live recompute field_ops (fusion OFF). "
                "outbox_decision is last stored card if any — not an override."
            ),
        },
        "honesty_rails": honesty_rails(),
    }


def handle_export_acta(
    body: dict[str, Any] | None = None,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Forensic export-acta (write_forensic_bundle) from work_dir outbox card."""
    from wildfire_front.product.forensics import (
        render_acta_md,
        render_radio_bridge,
        write_forensic_bundle,
    )

    req = dict(body or {})
    root = Path(base or REPO_ROOT).resolve()
    wd = resolve_work_dir(req.get("work_dir"), base=root)
    card_path = wd / "outbox" / "fire_decision_card.json"
    if not card_path.is_file():
        # Fall back to decide then export
        decide_body = {
            "work_dir": str(wd),
            "event_id": str(req.get("event_id") or wd.name),
            "policy_id": "field_ops",
        }
        decided = handle_decide(decide_body, base=root)
        if not decided.get("ok"):
            return {
                "ok": False,
                "act": "export_acta",
                "schema": LIVE_OPS_SCHEMA,
                "error": "no_decision_card",
                "detail": (
                    f"missing {card_path.name} and live decide failed: "
                    f"{decided.get('error') or decided.get('detail')}"
                ),
                "honesty_rails": honesty_rails(),
            }
        card = decided.get("result") or {}
        # Persist card so outbox is usable next time
        outbox = wd / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            json.dumps(card, indent=2, default=str), encoding="utf-8"
        )
    else:
        card = json.loads(card_path.read_text(encoding="utf-8"))

    out_dir = wd / "outbox"
    paths = write_forensic_bundle(
        out_dir,
        card,
        require_ops_for_go=bool(req.get("require_ops_for_go", False)),
        operator=req.get("operator"),
    )
    acta_preview = render_acta_md(card)[:1200]
    radio_preview = render_radio_bridge(card)[:600]
    return {
        "ok": True,
        "act": "export_acta",
        "schema": LIVE_OPS_SCHEMA,
        "work_dir": str(wd),
        "work_dir_rel": _rel_to_base(wd, root),
        "result": {
            "paths": paths,
            "decision": card.get("decision"),
            "event_id": card.get("event_id"),
            "acta_preview": acta_preview,
            "radio_preview": radio_preview,
        },
        "summary": {
            "decision": card.get("decision"),
            "event_id": card.get("event_id"),
            "acta": paths.get("acta"),
            "radio": paths.get("radio"),
            "card": paths.get("card"),
            "replay_sources": paths.get("replay_sources"),
        },
        "honesty_rails": honesty_rails(),
    }


def handle_replay_third_party(
    body: dict[str, Any] | None = None,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Forensic replay of third-party pack or work_dir outbox (consistency only).

    ``replay_ok`` is internal consistency — not cryptographic authenticity.
    """
    from wildfire_front.product.forensics import load_and_replay_bundle, replay_decision

    req = dict(body or {})
    root = Path(base or REPO_ROOT).resolve()
    bundle_raw = req.get("bundle") or req.get("pack")
    sources_raw = req.get("sources")
    work_raw = req.get("work_dir")

    try:
        if sources_raw:
            # sources is a file, not a dir — resolve under base without is_dir check
            raw = str(sources_raw).strip().replace("\\", "/")
            if "\x00" in raw or any(p == ".." for p in raw.split("/") if p):
                raise PathNotAllowedError("path traversal rejected")
            p = Path(sources_raw)
            resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
            if not _is_under(resolved, root):
                raise PathNotAllowedError(f"sources outside allowlist: {sources_raw}")
            if not resolved.is_file():
                raise PathNotAllowedError(f"sources not found: {sources_raw}")
            src = json.loads(resolved.read_text(encoding="utf-8"))
            result = replay_decision(src, base=root)
            target_rel = _rel_to_base(resolved, root)
        elif bundle_raw:
            # Allow pack dir under repo (may not be a work_dir)
            raw = str(bundle_raw).strip().replace("\\", "/")
            if "\x00" in raw or any(p == ".." for p in raw.split("/") if p):
                raise PathNotAllowedError("path traversal rejected")
            p = Path(bundle_raw)
            resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
            if not _is_under(resolved, root):
                raise PathNotAllowedError(f"bundle outside allowlist: {bundle_raw}")
            if not resolved.is_dir():
                raise PathNotAllowedError(f"bundle not found: {bundle_raw}")
            result = load_and_replay_bundle(resolved, base=root)
            target_rel = _rel_to_base(resolved, root)
        elif work_raw:
            wd = resolve_work_dir(work_raw, base=root)
            result = load_and_replay_bundle(wd / "outbox", base=root)
            target_rel = _rel_to_base(wd, root)
        else:
            # Default third-party pack
            default = root / "outputs" / "demo_third_party"
            if not default.is_dir():
                return {
                    "ok": False,
                    "act": "replay_third_party",
                    "schema": LIVE_OPS_SCHEMA,
                    "error": "pack_missing",
                    "detail": "outputs/demo_third_party missing — run build_demo_third_party_pack.py",
                    "honesty_rails": honesty_rails(),
                }
            result = load_and_replay_bundle(default, base=root)
            target_rel = "outputs/demo_third_party"
    except PathNotAllowedError as exc:
        raise exc
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "act": "replay_third_party",
            "schema": LIVE_OPS_SCHEMA,
            "error": "not_found",
            "detail": str(exc),
            "honesty_rails": honesty_rails(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "act": "replay_third_party",
            "schema": LIVE_OPS_SCHEMA,
            "error": "replay_failed",
            "detail": str(exc)[:300],
            "honesty_rails": honesty_rails(),
        }

    replay_ok = bool(result.get("replay_ok"))
    return {
        "ok": True,
        "act": "replay_third_party",
        "schema": LIVE_OPS_SCHEMA,
        "target_rel": target_rel,
        "result": {
            "replay_ok": replay_ok,
            "expected_decision": result.get("expected_decision"),
            "got_decision": result.get("got_decision"),
            "match_decision": result.get("match_decision"),
            "match_output_hash": result.get("match_output_hash"),
        },
        "summary": {
            "replay_ok": replay_ok,
            "decision_match": result.get("match_decision"),
            "expected": result.get("expected_decision"),
            "got": result.get("got_decision"),
            "note": (
                "replay_ok = forensic consistency offline — "
                "not cryptographic authenticity"
            ),
        },
        "honesty_rails": honesty_rails(),
    }


def handle_health(*, live_ops_enabled: bool = True) -> dict[str, Any]:
    return {
        "ok": True,
        "act": "health",
        "schema": LIVE_OPS_SCHEMA,
        "live_ops_enabled": bool(live_ops_enabled),
        "endpoints": [
            LIVE_PATH_HEALTH,
            LIVE_PATH_STATUS,
            LIVE_PATH_DECIDE,
            LIVE_PATH_EXPORT_ACTA,
            LIVE_PATH_REPLAY,
        ],
        "honesty_rails": honesty_rails(),
        "disclaimer": "Not tactical dispatch. Loopback demo only.",
    }


def dispatch_live(
    path: str,
    body: dict[str, Any] | None = None,
    *,
    base: Path | None = None,
    method: str = "POST",
) -> tuple[int, dict[str, Any]]:
    """Route a live path to the matching handler. Returns (http_status, payload)."""
    p = (path or "").rstrip("/") or "/"
    # Normalize without trailing slash except root
    aliases = {
        LIVE_PATH_HEALTH.rstrip("/"): "health",
        "/live/health": "health",
        LIVE_PATH_STATUS.rstrip("/"): "status",
        LIVE_PATH_DECIDE.rstrip("/"): "decide",
        LIVE_PATH_EXPORT_ACTA.rstrip("/"): "export_acta",
        "/live/v1/export_acta": "export_acta",
        LIVE_PATH_REPLAY.rstrip("/"): "replay_third_party",
        "/live/v1/replay": "replay_third_party",
    }
    kind = aliases.get(p)
    if kind is None:
        return 404, {
            "ok": False,
            "error": "not_found",
            "path": path,
            "honesty_rails": honesty_rails(),
        }

    if kind == "health":
        if method.upper() not in ("GET", "HEAD", "POST"):
            return 405, {"ok": False, "error": "method_not_allowed"}
        return 200, handle_health(live_ops_enabled=True)

    if method.upper() != "POST":
        return 405, {
            "ok": False,
            "error": "method_not_allowed",
            "detail": f"{kind} requires POST",
            "honesty_rails": honesty_rails(),
        }

    try:
        if kind == "status":
            return 200, handle_status(body, base=base)
        if kind == "decide":
            return 200, handle_decide(body, base=base)
        if kind == "export_acta":
            return 200, handle_export_acta(body, base=base)
        if kind == "replay_third_party":
            return 200, handle_replay_third_party(body, base=base)
    except PathNotAllowedError as exc:
        return 400, {
            "ok": False,
            "act": kind,
            "error": "path_not_allowed",
            "detail": str(exc),
            "honesty_rails": honesty_rails(),
        }
    except FileNotFoundError as exc:
        return 400, {
            "ok": False,
            "act": kind,
            "error": "not_found",
            "detail": str(exc),
            "honesty_rails": honesty_rails(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return 500, {
            "ok": False,
            "act": kind,
            "error": "internal_error",
            "detail": str(exc)[:300],
            "honesty_rails": honesty_rails(),
        }

    return 404, {"ok": False, "error": "not_found", "path": path}


def check_demo_day_artifacts(
    *,
    repo: Path | None = None,
) -> dict[str, Any]:
    """Presence checks for third-party pack + reliability (demo-day gate)."""
    root = Path(repo or REPO_ROOT).resolve()
    checks = {
        "sla_work_dir": root / "outputs" / "incidents" / "_sla_measure",
        "third_party_pack": root / "outputs" / "demo_third_party",
        "reliability_md": root / "docs" / "RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
        "reliability_json": root / "docs" / "RELIABILITY_GATE_REPORT.json",
        "build_pack_script": root / "scripts" / "build_demo_third_party_pack.py",
        "replay_script": root / "scripts" / "run_third_party_replay.py",
        "cheatsheet": root / "docs" / "CHEATSHEET_DEMO_12MIN.md",
        "h1_runbook": root / "docs" / "H1_GO_Q_RUNBOOK.md",
    }
    present: dict[str, Any] = {}
    missing: list[str] = []
    for key, path in checks.items():
        ok = path.exists()
        try:
            rel = str(path.resolve().relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = str(path)
        present[key] = {"path": rel, "ok": ok}
        if not ok:
            missing.append(key)
    return {
        "schema": "wfd_demo_day_artifacts_v1",
        "ok": len(missing) == 0,
        "missing": missing,
        "artifacts": present,
        "go_q_met": False,
        "go_q_invent_forbidden": True,
        "replay_cmd": "python scripts/run_third_party_replay.py",
        "pack_cmd": "python scripts/build_demo_third_party_pack.py",
        "honesty_rails": honesty_rails(),
    }
