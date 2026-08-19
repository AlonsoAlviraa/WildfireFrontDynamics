"""Shared Decision Card HTTP/CLI surface (read-only + export).

Used by ``serve-decide`` and ``app --serve`` Live Ops. Does not flip stamps.
Field_ops GO rules stay in ``decide_from_request`` / ``build_decision_card``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .decide_service import API_VERSION, PRODUCT_ID, REPO_ROOT
from .path_sandbox import ensure_dir, exists_file, join_fixed, read_json, realpath, write_json

SURFACE_SCHEMA = "wfd_surface_api_v1"
STAMP_REL = ("docs", "ML_PRODUCT_GO_STATUS.json")

_flags_cache: tuple[float, int, dict[str, Any]] | None = None
_catalog_json_cache: tuple[float, int, dict[str, Any]] | None = None


def dumps_compact(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8")


def _read_json_cached(
    path: Path,
    slot: tuple[float, int, dict[str, Any]] | None,
) -> tuple[tuple[float, int, dict[str, Any]] | None, dict[str, Any] | None]:
    try:
        stat = path.stat()
    except OSError:
        return None, None
    if slot and slot[0] == stat.st_mtime and slot[1] == stat.st_size:
        return slot, slot[2]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    return (stat.st_mtime, stat.st_size, data), data


def load_stamp() -> dict[str, Any]:
    global _flags_cache
    path = Path(join_fixed(realpath(REPO_ROOT), *STAMP_REL))
    slot, data = _read_json_cached(path, _flags_cache)
    if slot:
        _flags_cache = slot
    return data or {}


def surface_health() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": SURFACE_SCHEMA,
        "product": PRODUCT_ID,
        "api_version": API_VERSION,
        "not_tactical_dispatch": True,
    }


def surface_flags() -> dict[str, Any]:
    stamp = load_stamp()
    rails = stamp.get("rails") if isinstance(stamp.get("rails"), dict) else {}
    return {
        "schema": SURFACE_SCHEMA,
        "act": "flags",
        "ok": True,
        "GO_Q": stamp.get("GO_Q"),
        "GO_MES": stamp.get("GO_MES"),
        "GO_MES_plus": stamp.get("GO_MES_plus"),
        "ml_product_go": stamp.get("ml_product_go"),
        "ml_product_go_scope": "lab_only",
        "field_ops_fusion": rails.get("field_ops_fusion"),
        "tobarra_keep_reopen": rails.get("tobarra_keep_reopen"),
        "not_claims": list(stamp.get("not_claims") or []),
        "product_id": stamp.get("product_id"),
    }


def surface_catalog() -> dict[str, Any]:
    from wildfire_front.ml.product_catalog import list_holdout_only, list_products

    products = list_products()
    holdout = list_holdout_only()
    return {
        "schema": SURFACE_SCHEMA,
        "act": "catalog",
        "ok": True,
        "products": [
            {
                "id": row.get("id"),
                "ready": bool(row.get("ready")),
                "label": row.get("label"),
                "domain": row.get("domain"),
            }
            for row in products
        ],
        "holdout_only": holdout,
        "default_product": "clm_ensemble_v34",
        "not_ready_ids": [row["id"] for row in holdout],
    }


SOURCE_BOARD_KEYS = ("ops", "open", "ml_live", "reliability")
SNAPSHOT_BASENAME = "incident_snapshot.json"
_OPS_REL = (
    ("outbox", "operational_metrics.json"),
    ("operational_metrics.json",),
)
_CARD_REL = (
    ("outbox", "fire_decision_card.json"),
    ("fire_decision_card.json",),
    ("decision_card_field_ops.json",),
    ("decision_card.json",),
)


def last_card_path(work_dir: Path) -> Path | None:
    wd = Path(realpath(work_dir))
    for rel in _CARD_REL:
        cand = Path(join_fixed(wd, *rel))
        if exists_file(cand):
            return cand
    return None


def load_last_card(work_dir: Path) -> dict[str, Any] | None:
    path = last_card_path(work_dir)
    if path is None:
        return None
    try:
        data = read_json(realpath(path))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def saved_snapshot_path(work_dir: Path) -> Path:
    wd = Path(realpath(work_dir))
    return Path(join_fixed(wd, "outbox", SNAPSHOT_BASENAME))


def load_saved_snapshot(work_dir: Path) -> dict[str, Any] | None:
    path = saved_snapshot_path(work_dir)
    if not exists_file(path):
        return None
    try:
        data = read_json(realpath(path))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if _is_snapshot_payload(data) else None


def persist_snapshot(work_dir: Path, payload: dict[str, Any]) -> str | None:
    if not payload.get("ok") or not _is_snapshot_payload(payload):
        return None
    wd = Path(realpath(work_dir))
    outbox = Path(join_fixed(wd, "outbox"))
    ensure_dir(str(outbox))
    to_save = {key: val for key, val in payload.items() if key != "latency_ms"}
    to_save["saved"] = True
    return write_json(str(outbox), SNAPSHOT_BASENAME, to_save)


def load_ops_sidecar(work_dir: Path) -> dict[str, Any] | None:
    wd = Path(realpath(work_dir))
    for rel in _OPS_REL:
        cand = Path(join_fixed(wd, *rel))
        if not exists_file(cand):
            continue
        try:
            data = read_json(realpath(cand))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _as_float(val: Any) -> float | None:
    if val is None or val is False:
        return None
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


def _as_int(val: Any) -> int | None:
    num = _as_float(val)
    if num is None:
        return None
    return int(num)


def _pick(*candidates: tuple[Any, str]) -> tuple[Any, str | None]:
    for val, src in candidates:
        if val is None or val == "":
            continue
        return val, src
    return None, None


def _ops_from_card(card: dict[str, Any]) -> dict[str, Any]:
    metrics = card.get("metrics") if isinstance(card.get("metrics"), dict) else {}
    ops = metrics.get("ops") if isinstance(metrics.get("ops"), dict) else {}
    merged = dict(ops)
    for raw in card.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or "")
        extra = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else None
        if extra and (sid == "ops_thermal_front" or sid.startswith("ops_")):
            for key, val in extra.items():
                if key not in merged or merged.get(key) is None:
                    merged[key] = val
    return merged


def _open_from_card(card: dict[str, Any]) -> tuple[dict[str, Any], str]:
    metrics = card.get("metrics") if isinstance(card.get("metrics"), dict) else {}
    if isinstance(metrics.get("open"), dict):
        return metrics["open"], "metrics.open"
    if isinstance(metrics.get("open_cems"), dict):
        return metrics["open_cems"], "metrics.open_cems"
    return {}, "metrics.open"


def cited_instant(
    card: dict[str, Any],
    *,
    work_dir: Path | None = None,
    ops_sidecar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cited ROS/area/Δt/frames/grade. Missing → null. Never invents Vp or IoU-as-ROS."""
    sidecar = ops_sidecar
    if sidecar is None and work_dir is not None:
        sidecar = load_ops_sidecar(work_dir)
    sidecar = sidecar if isinstance(sidecar, dict) else {}
    structural = sidecar.get("structural") if isinstance(sidecar.get("structural"), dict) else {}
    ops = _ops_from_card(card)
    open_m, open_prefix = _open_from_card(card)

    ros, ros_source = _pick(
        (_as_float(ops.get("primary_ros_m_min")), "metrics.ops.primary_ros_m_min"),
        (_as_float(structural.get("primary_ros_m_min")), "operational_metrics.structural.primary_ros_m_min"),
        (_as_float(sidecar.get("primary_ros_m_min")), "operational_metrics.primary_ros_m_min"),
        (_as_float(ops.get("speed_median_m_min")), "metrics.ops.speed_median_m_min"),
        (_as_float(sidecar.get("speed_median_m_min")), "operational_metrics.speed_median_m_min"),
    )
    area, area_source = _pick(
        (_as_float(ops.get("area_ha_max")), "metrics.ops.area_ha_max"),
        (_as_float(ops.get("area_ha_last")), "metrics.ops.area_ha_last"),
        (_as_float(sidecar.get("area_ha_max")), "operational_metrics.area_ha_max"),
        (_as_float(sidecar.get("area_ha_last")), "operational_metrics.area_ha_last"),
        (_as_float(open_m.get("area_ha")), f"{open_prefix}.area_ha"),
        (_as_float(open_m.get("area_rediam_ha")), f"{open_prefix}.area_rediam_ha"),
        (_as_float(open_m.get("area_rai_ha")), f"{open_prefix}.area_rai_ha"),
    )
    interval_s, interval_source = _pick(
        (_as_float(ops.get("interval_s_median")), "metrics.ops.interval_s_median"),
        (_as_float(sidecar.get("interval_s_median")), "operational_metrics.interval_s_median"),
    )
    n_frames, n_frames_source = _pick(
        (_as_int(ops.get("n_frames")), "metrics.ops.n_frames"),
        (_as_int(ops.get("n_frames_staged")), "metrics.ops.n_frames_staged"),
        (_as_int(sidecar.get("num_observations")), "operational_metrics.num_observations"),
        (_as_int(sidecar.get("observation_count")), "operational_metrics.observation_count"),
    )
    grade, grade_source = _pick(
        (ops.get("quality_grade"), "metrics.ops.quality_grade"),
        (sidecar.get("quality_grade"), "operational_metrics.quality_grade"),
    )
    if grade is not None:
        grade = str(grade)
    defendable = ops.get("speed_defendable")
    if defendable is None:
        defendable = sidecar.get("speed_defendable")
    if defendable is not None:
        defendable = bool(defendable)
    observed_at = None
    series = sidecar.get("area_ha_series")
    if isinstance(series, list) and series:
        last = series[-1] if isinstance(series[-1], dict) else {}
        observed_at = last.get("observed_at")
    if not observed_at:
        observed_at = ops.get("observed_at") or sidecar.get("updated_at_utc")

    return {
        "ros_m_min": ros,
        "ros_source": ros_source,
        "area_ha": area,
        "area_source": area_source,
        "interval_s": interval_s,
        "interval_source": interval_source,
        "n_frames": n_frames,
        "n_frames_source": n_frames_source,
        "quality_grade": grade,
        "quality_grade_source": grade_source,
        "speed_defendable": defendable,
        "observed_at": observed_at,
        "invented": False,
        "not_tactical": True,
    }


def cited_from_snapshot(snap: dict[str, Any], *, work_dir: Path | None = None) -> dict[str, Any]:
    cited = snap.get("cited")
    if isinstance(cited, dict) and cited.get("invented") is False:
        return cited
    inner = snap.get("card") if isinstance(snap.get("card"), dict) else snap
    return cited_instant(inner, work_dir=work_dir)


def cited_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """A→B deltas of cited figures. Missing on either side → null. Not dispatch."""

    def _sub(a: Any, b: Any) -> float | None:
        fa, fb = _as_float(a), _as_float(b)
        if fa is None or fb is None:
            return None
        return round(fb - fa, 6)

    def _parse_ts(raw: Any):
        if not raw:
            return None
        text = str(raw).replace("Z", "+00:00")
        try:
            from datetime import datetime

            return datetime.fromisoformat(text)
        except ValueError:
            return None

    left_ts = _parse_ts(left.get("observed_at"))
    right_ts = _parse_ts(right.get("observed_at"))
    delta_t_s = None
    if left_ts is not None and right_ts is not None:
        delta_t_s = round((right_ts - left_ts).total_seconds(), 3)

    return {
        "ros_m_min": _sub(left.get("ros_m_min"), right.get("ros_m_min")),
        "area_ha": _sub(left.get("area_ha"), right.get("area_ha")),
        "interval_s": _sub(left.get("interval_s"), right.get("interval_s")),
        "delta_t_s": delta_t_s,
        "n_frames": _sub(left.get("n_frames"), right.get("n_frames")),
        "quality_grade_from": left.get("quality_grade"),
        "quality_grade_to": right.get("quality_grade"),
        "ros_source_from": left.get("ros_source"),
        "ros_source_to": right.get("ros_source"),
        "invented": False,
        "not_tactical": True,
    }


def snapshot_drivers(board: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for key in SOURCE_BOARD_KEYS:
        row = board.get(key) if isinstance(board, dict) else None
        if isinstance(row, dict) and row.get("driver"):
            out.append(key)
    return out


def surface_card(work_dir: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    card = load_last_card(work_dir)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    if card is None:
        return {
            "ok": False,
            "act": "card",
            "schema": SURFACE_SCHEMA,
            "error": "card_missing",
            "detail": "no fire_decision_card.json in work_dir/outbox",
            "latency_ms": latency_ms,
        }
    return {
        "ok": True,
        "act": "card",
        "schema": SURFACE_SCHEMA,
        "latency_ms": latency_ms,
        "result": card,
        "summary": {
            "decision": card.get("decision"),
            "confidence_pred": card.get("confidence_pred"),
            "event_id": card.get("event_id"),
            "system_reliability_pass": card.get("system_reliability_pass"),
            "policy_id": (card.get("audit") or {}).get("policy_id") or card.get("policy_id"),
        },
    }


def surface_status(work_dir: Path) -> dict[str, Any]:
    from .live_ops import _lightweight_incident_status, honesty_rails

    wd = Path(realpath(work_dir))
    report = _lightweight_incident_status(wd)
    return {
        "ok": True,
        "act": "status",
        "schema": SURFACE_SCHEMA,
        "work_dir": str(wd),
        "result": report,
        "summary": {
            "status": report.get("status"),
            "event_id": report.get("event_id"),
            "decision": report.get("decision"),
            "quality_grade": report.get("quality_grade"),
            "has_decision_card": report.get("has_decision_card"),
            "message": report.get("message"),
        },
        "honesty_rails": honesty_rails(),
    }


def surface_export_acta(work_dir: Path, *, operator: str | None = None) -> dict[str, Any]:
    from .forensics import write_forensic_bundle
    from .live_ops import honesty_rails

    card = load_last_card(work_dir)
    if card is None:
        return {
            "ok": False,
            "act": "export_acta",
            "schema": SURFACE_SCHEMA,
            "error": "card_missing",
            "honesty_rails": honesty_rails(),
        }
    wd = Path(realpath(work_dir))
    outbox = Path(join_fixed(wd, "outbox"))
    outbox.mkdir(parents=True, exist_ok=True)
    paths = write_forensic_bundle(outbox, card, operator=operator)
    return {
        "ok": True,
        "act": "export_acta",
        "schema": SURFACE_SCHEMA,
        "paths": paths,
        "summary": {"decision": card.get("decision"), "event_id": card.get("event_id")},
        "honesty_rails": honesty_rails(),
    }


def surface_rails() -> dict[str, Any]:
    """Shared honesty rails for snapshot / compare (same names on every surface)."""
    flags = surface_flags()
    go_q = flags.get("GO_Q")
    return {
        "not_tactical_dispatch": True,
        "fusion_on_is_not_dispatch": True,
        "field_ops_fusion": flags.get("field_ops_fusion"),
        "go_q": go_q if go_q is not None else "partial",
        "go_q_partial": True,
        "go_q_complete": False,
        "signed_acta": False,
        "ml_product_go_scope": "lab_only",
    }


def _is_snapshot_payload(obj: Any) -> bool:
    if not isinstance(obj, dict) or obj.get("act") != "snapshot":
        return False
    board = obj.get("source_board")
    if not isinstance(board, dict):
        return False
    return all(key in board for key in SOURCE_BOARD_KEYS)


def _as_card(ref: Any) -> dict[str, Any] | None:
    """Accept a card dict, a snapshot payload, or a work_dir / card-file Path."""
    if isinstance(ref, dict):
        if _is_snapshot_payload(ref):
            nested = ref.get("card")
            if isinstance(nested, dict) and nested.get("sources"):
                return nested
            # Prefer the snapshot itself over a slim card that dropped sources.
            return ref
        if ref.get("act") == "snapshot" and isinstance(ref.get("card"), dict):
            return ref["card"]
        result = ref.get("result")
        if isinstance(result, dict) and (
            "decision" in result or _is_snapshot_payload(result)
        ):
            return _as_card(result)
        if "decision" in ref:
            return ref
        return None
    try:
        path = Path(ref)
    except TypeError:
        return None
    if not str(path):
        return None
    try:
        resolved = Path(realpath(path))
    except (OSError, TypeError, ValueError):
        return None
    if resolved.is_file():
        try:
            data = read_json(str(resolved))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return _as_card(data) if isinstance(data, dict) else None
    return load_last_card(resolved)


def _as_snapshot(ref: Any) -> dict[str, Any] | None:
    """Normalize cards, snapshots, work_dirs, or JSON files into a snapshot."""
    if _is_snapshot_payload(ref):
        return ref
    if isinstance(ref, dict):
        card = _as_card(ref)
        if card is None:
            return None
        if _is_snapshot_payload(card):
            return card
        return snapshot_from_card(card)
    try:
        path = Path(ref)
    except TypeError:
        return None
    if not str(path):
        return None
    try:
        resolved = Path(realpath(path))
    except (OSError, TypeError, ValueError):
        return None
    if resolved.is_file():
        try:
            data = read_json(str(resolved))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return _as_snapshot(data) if isinstance(data, dict) else None
    snap = surface_snapshot(resolved)
    return snap if snap.get("ok") else None


def _source_entry(sources: list[Any], *needles: str) -> dict[str, Any] | None:
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or "")
        for needle in needles:
            if sid == needle or sid.startswith(needle):
                return raw
    return None


def _reason_hits(reasons: list[str], *needles: str) -> bool:
    low = [r.lower() for r in reasons]
    return any(any(n in r for n in needles) for r in low)


def source_board(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """ops / open / ml_live / reliability: present or missing (+ HOLD/ABSTAIN driver)."""
    sources = [s for s in (card.get("sources") or []) if isinstance(s, dict)]
    metrics = card.get("metrics") if isinstance(card.get("metrics"), dict) else {}
    reasons = [str(r) for r in (card.get("reasons") or [])]
    decision = str(card.get("decision") or "ABSTAIN").upper()
    holdish = decision in {"HOLD", "ABSTAIN"}

    ops_s = _source_entry(sources, "ops_thermal_front", "ops_")
    open_s = _source_entry(sources, "open_cems", "open_")
    ml_s = _source_entry(sources, "ml_live_reliability", "ml_live")
    # Catalog holdout (ml_clm_ensemble) is provenance, not live fusion.

    ops_present = bool(ops_s and ops_s.get("available")) or isinstance(metrics.get("ops"), dict)
    open_present = bool(open_s and open_s.get("available")) or bool(
        metrics.get("open_cems") or metrics.get("open")
    )
    ml_present = bool(ml_s and ml_s.get("available")) or isinstance(metrics.get("ml_live"), dict)

    audit = card.get("audit") if isinstance(card.get("audit"), dict) else {}
    rel_snap = audit.get("reliability_gate_snapshot")
    rel_pass = bool(card.get("system_reliability_pass"))
    if isinstance(rel_snap, dict) and rel_snap.get("system_reliability_pass"):
        rel_pass = True
    rel_present = bool(rel_pass)

    def _row(
        key: str,
        present: bool,
        source_id: str | None,
        driver_needles: tuple[str, ...],
        driver_label: str,
    ) -> dict[str, Any]:
        driver = None
        if holdish and _reason_hits(reasons, *driver_needles) and (
            key == "reliability" or not present
        ):
            driver = driver_label
        return {
            "key": key,
            "present": bool(present),
            "status": "present" if present else "missing",
            "source_id": source_id,
            "driver": driver,
        }

    return {
        "ops": _row(
            "ops",
            ops_present,
            (ops_s or {}).get("id") if ops_s else None,
            ("missing:ops", "require_ops", "ops_required"),
            "missing",
        ),
        "open": _row(
            "open",
            open_present,
            (open_s or {}).get("id") if open_s else None,
            ("missing:open", "open_cems"),
            "missing",
        ),
        "ml_live": _row(
            "ml_live",
            ml_present,
            (ml_s or {}).get("id") if ml_s else None,
            ("missing:ml_live", "ml_live_untrusted", "ml_live_invalid"),
            "missing",
        ),
        "reliability": _row(
            "reliability",
            rel_present,
            "system_reliability",
            ("reliability_unverified", "fail_closed_reliability", "system_reliability"),
            "reliability_unverified",
        ),
    }


def snapshot_from_card(card: dict[str, Any], *, work_dir: Path | None = None) -> dict[str, Any]:
    """Shareable read-only incident snapshot. Does not invent ROS / GO_Q / RCDA."""
    if _is_snapshot_payload(card):
        out = dict(card)
        if work_dir is not None:
            out["work_dir"] = str(work_dir)
        if not isinstance(out.get("cited"), dict) or out.get("cited", {}).get("invented") is not False:
            inner = out.get("card") if isinstance(out.get("card"), dict) else out
            out["cited"] = cited_instant(inner, work_dir=work_dir)
        return out
    rails = surface_rails()
    audit = card.get("audit") if isinstance(card.get("audit"), dict) else {}
    board = source_board(card)
    decision = str(card.get("decision") or "ABSTAIN").upper()
    if decision not in {"GO", "HOLD", "ABSTAIN"}:
        decision = "ABSTAIN"
    hashes = {
        "input_hash": audit.get("input_hash"),
        "output_hash": audit.get("output_hash"),
    }
    metrics = card.get("metrics") if isinstance(card.get("metrics"), dict) else {}
    slim_metrics = {
        key: metrics[key]
        for key in ("ops", "open", "open_cems", "ml_live")
        if key in metrics
    }
    slim_sources = [
        {"id": src.get("id"), "available": src.get("available")}
        for src in (card.get("sources") or [])[:8]
        if isinstance(src, dict)
    ]
    cited = cited_instant(card, work_dir=work_dir)
    return {
        "ok": True,
        "act": "snapshot",
        "schema": SURFACE_SCHEMA,
        "not_tactical_dispatch": True,
        "decision": decision,
        "confidence": card.get("confidence_pred"),
        "reasons": list(card.get("reasons") or [])[:16],
        "event_id": card.get("event_id"),
        "policy_id": audit.get("policy_id") or card.get("policy_id"),
        "system_reliability_pass": bool(card.get("system_reliability_pass")),
        "source_board": board,
        "drivers": snapshot_drivers(board),
        "cited": cited,
        "rails": rails,
        "hashes": hashes,
        "saved": False,
        "work_dir": str(work_dir) if work_dir is not None else None,
        "card": {
            "event_id": card.get("event_id"),
            "decision": decision,
            "confidence_pred": card.get("confidence_pred"),
            "system_reliability_pass": card.get("system_reliability_pass"),
            "reasons": list(card.get("reasons") or [])[:16],
            "sources": slim_sources,
            "metrics": slim_metrics,
            "audit": {
                "input_hash": hashes["input_hash"],
                "output_hash": hashes["output_hash"],
                "policy_id": audit.get("policy_id"),
            },
        },
    }


def surface_snapshot(work_dir: Path, *, persist: bool = False) -> dict[str, Any]:
    t0 = time.perf_counter()
    wd = Path(realpath(work_dir))
    card = load_last_card(wd)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    if card is None:
        return {
            "ok": False,
            "act": "snapshot",
            "schema": SURFACE_SCHEMA,
            "error": "card_missing",
            "detail": "no fire_decision_card.json in work_dir",
            "not_tactical_dispatch": True,
            "rails": surface_rails(),
            "saved": False,
            "latency_ms": latency_ms,
        }
    payload = snapshot_from_card(card, work_dir=wd)
    payload["latency_ms"] = latency_ms
    if persist:
        saved_path = persist_snapshot(wd, payload)
        payload["saved"] = bool(saved_path)
        if saved_path:
            payload["saved_path"] = saved_path
    else:
        payload["saved"] = False
    return payload


def _present_keys(board: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in SOURCE_BOARD_KEYS:
        row = board.get(key) if isinstance(board.get(key), dict) else {}
        if row.get("present"):
            out.add(key)
    return out


def surface_compare(left: Any, right: Any, *, against: str | None = None) -> dict[str, Any]:
    """Decision-change compare. Same-input → identity (no flip). Local alert only."""
    t0 = time.perf_counter()
    left_snap = _as_snapshot(left)
    right_snap = _as_snapshot(right)
    rails = surface_rails()
    if left_snap is None or right_snap is None:
        return {
            "ok": False,
            "act": "compare",
            "schema": SURFACE_SCHEMA,
            "error": "card_missing",
            "detail": "left and right must be cards, snapshots, or work_dirs with a card",
            "not_tactical_dispatch": True,
            "rails": rails,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        }
    from_d = left_snap["decision"]
    to_d = right_snap["decision"]
    flipped = from_d != to_d
    left_keys = _present_keys(left_snap["source_board"])
    right_keys = _present_keys(right_snap["source_board"])
    appeared = sorted(right_keys - left_keys)
    disappeared = sorted(left_keys - right_keys)
    left_hash = (left_snap.get("hashes") or {}).get("input_hash")
    right_hash = (right_snap.get("hashes") or {}).get("input_hash")
    same_input = bool(left_hash and right_hash and left_hash == right_hash)
    if same_input:
        flipped = False
        kind = "identity"
    elif flipped:
        kind = "decision_flip"
    elif appeared or disappeared:
        kind = "source_change"
    else:
        kind = "identity"
    if kind == "identity":
        message = "Same-input compare: no flip. Not a dispatch order."
    elif kind == "decision_flip":
        message = f"Decision flipped {from_d} → {to_d}. Not a dispatch order."
    else:
        message = (
            f"Sources changed (appeared={appeared or '-'} disappeared={disappeared or '-'}). "
            "Not a dispatch order."
        )
    def _conf(snap: dict[str, Any]) -> float | None:
        raw = snap.get("confidence")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    left_conf = _conf(left_snap)
    right_conf = _conf(right_snap)
    conf_delta = (
        None if left_conf is None or right_conf is None else round(right_conf - left_conf, 6)
    )
    left_out = (left_snap.get("hashes") or {}).get("output_hash")
    right_out = (right_snap.get("hashes") or {}).get("output_hash")
    output_hash_changed = bool(left_out and right_out and left_out != right_out)
    left_drivers = snapshot_drivers(left_snap.get("source_board"))
    right_drivers = snapshot_drivers(right_snap.get("source_board"))
    left_cited = cited_from_snapshot(left_snap)
    right_cited = cited_from_snapshot(right_snap)
    delta = cited_delta(left_cited, right_cited)
    drivers_added = sorted(set(right_drivers) - set(left_drivers))
    drivers_removed = sorted(set(left_drivers) - set(right_drivers))
    delta["drivers_added"] = drivers_added
    delta["drivers_removed"] = drivers_removed
    delta["drivers_changed"] = bool(drivers_added or drivers_removed)
    alert = {
        "schema": "wfd_local_alert_v1",
        "kind": kind,
        "channel": "local_payload",
        "delivered": False,
        "not_sms": True,
        "not_whatsapp": True,
        "not_email": True,
        "not_tactical_dispatch": True,
        "from": from_d,
        "to": to_d,
        "message": message,
    }
    return {
        "ok": True,
        "act": "compare",
        "schema": SURFACE_SCHEMA,
        "not_tactical_dispatch": True,
        "flipped": flipped,
        "from": from_d,
        "to": to_d,
        "same_input": same_input,
        "against": against or "explicit",
        "confidence_from": left_conf,
        "confidence_to": right_conf,
        "confidence_delta": conf_delta,
        "output_hash_changed": output_hash_changed,
        "source_delta": {"appeared": appeared, "disappeared": disappeared},
        "drivers_from": left_drivers,
        "drivers_to": right_drivers,
        "cited_from": left_cited,
        "cited_to": right_cited,
        "cited_delta": delta,
        "alert": alert,
        "rails": rails,
        "left": {
            "decision": from_d,
            "source_board": left_snap["source_board"],
            "hashes": left_snap["hashes"],
            "event_id": left_snap.get("event_id"),
            "drivers": left_drivers,
            "cited": left_cited,
        },
        "right": {
            "decision": to_d,
            "source_board": right_snap["source_board"],
            "hashes": right_snap["hashes"],
            "event_id": right_snap.get("event_id"),
            "drivers": right_drivers,
            "cited": right_cited,
        },
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3),
    }


def compare_from_request(req: dict[str, Any], *, resolve_work_dir) -> dict[str, Any]:
    """HTTP/CLI helper: left/right dicts, card paths, or work_dirs.

    If only ``work_dir`` is given, compare the last saved outbox snapshot (if
    any) against the current card — that is the evolution path. No saved
    snapshot → identity against the current card.
    """
    left = req.get("left") if isinstance(req.get("left"), dict) else None
    right = req.get("right") if isinstance(req.get("right"), dict) else None
    left_path = req.get("left_card") or req.get("other_work_dir") or req.get("left_work_dir")
    right_path = req.get("right_card") or req.get("work_dir") or req.get("right_work_dir")
    if left is None and left_path:
        left = resolve_work_dir(str(left_path))
    if right is None and right_path:
        right = resolve_work_dir(str(right_path))
    against = "explicit"
    if left is None and right is not None:
        saved = None
        try:
            wd = Path(right) if not isinstance(right, dict) else None
            if wd is not None:
                saved = load_saved_snapshot(wd)
        except (OSError, TypeError, ValueError):
            saved = None
        if saved is not None:
            left = saved
            against = "saved_snapshot"
        else:
            left = right
            against = "identity"
    if right is None and left is not None:
        right = left
        if against == "explicit":
            against = "identity"
    if left is None or right is None:
        return {
            "ok": False,
            "act": "compare",
            "schema": SURFACE_SCHEMA,
            "error": "compare_refs_required",
            "detail": "pass left/right cards or work_dir (+ optional other_work_dir)",
            "not_tactical_dispatch": True,
            "rails": surface_rails(),
        }
    return surface_compare(left, right, against=against)
