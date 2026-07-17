"""Shared Decision Card service for CLI and minimal HTTP API.

Loads optional ML / ops / open sources and builds a Fire Decision Card.
Records wall-clock latency for SLA measurement (metrics-only path).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from .confidence import DecisionCard, build_decision_card

REPO_ROOT = Path(__file__).resolve().parents[2]
API_VERSION = "decide_api_v1"
PRODUCT_ID = "fire_decision_card"


def _as_path(value: str | Path | None, *, base: Path | None = None) -> Path | None:
    if value is None or value == "":
        return None
    p = Path(value)
    if not p.is_absolute() and base is not None:
        cand = (base / p).resolve()
        if cand.exists():
            return cand
        # also try repo root
        cand2 = (REPO_ROOT / p).resolve()
        if cand2.exists():
            return cand2
    return p


def load_ml_metrics_v34(*, base: Path | None = None) -> dict[str, Any] | None:
    man = _as_path("models/clm_ensemble/manifest.json", base=base or REPO_ROOT)
    if man is None or not man.is_file():
        man = REPO_ROOT / "models" / "clm_ensemble" / "manifest.json"
    if not man.is_file():
        return None
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metrics = data.get("metrics")
    return dict(metrics) if isinstance(metrics, dict) else None


def load_ops_metrics_from_work_dir(
    work_dir: str | Path | None,
    *,
    base: Path | None = None,
) -> dict[str, Any] | None:
    wd = _as_path(work_dir, base=base)
    if wd is None:
        return None
    # Prefer full decision card already written, else incident_state, else ops json
    fdc = wd / "outbox" / "fire_decision_card.json"
    if fdc.is_file():
        try:
            card = json.loads(fdc.read_text(encoding="utf-8"))
            ops = (card.get("metrics") or {}).get("ops")
            if isinstance(ops, dict) and ops:
                return dict(ops)
        except (OSError, json.JSONDecodeError):
            pass
    st_path = wd / "outbox" / "incident_state.json"
    if st_path.is_file():
        try:
            st = json.loads(st_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return {
            "quality_grade": st.get("quality_grade"),
            "primary_ros_m_min": st.get("primary_ros_m_min"),
            "n_frames_staged": st.get("n_frames_staged") or st.get("n_frames_seen"),
            "area_ha_max": st.get("area_ha_max"),
            "speed_vs_ref_ratio": st.get("speed_vs_ref_ratio"),
        }
    ops_path = wd / "outbox" / "operational_metrics.json"
    if ops_path.is_file():
        try:
            ops = json.loads(ops_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        ros = ops.get("speed_median_m_min") or ops.get("primary_ros_m_min")
        return {
            "quality_grade": ops.get("quality_grade"),
            "primary_ros_m_min": ros,
            "n_frames_staged": ops.get("n_frames_staged") or ops.get("speed_n_observable"),
            "area_ha_max": ops.get("area_ha_max"),
            "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
        }
    return None


def load_open_metrics_from_pack(
    open_pack: str | Path | None,
    *,
    base: Path | None = None,
) -> dict[str, Any] | None:
    pack = _as_path(open_pack, base=base)
    if pack is None:
        return None
    scp = pack / "scorecard_pista_b.json"
    if not scp.is_file():
        return None
    try:
        sc = json.loads(scp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "max_area_ha": sc.get("max_area_ha"),
        "n_timeline_steps": sc.get("n_timeline_steps"),
        "activation": sc.get("activation"),
        "O2_cems_delineation": sc.get("O2_cems_delineation"),
    }


def resolve_sources(
    request: Mapping[str, Any],
    *,
    base: Path | None = None,
) -> dict[str, Any | None]:
    """Resolve ml/ops/open metrics from request paths or inline dicts."""
    base = base or Path.cwd()
    ml_m = request.get("ml_metrics")
    ops_m = request.get("ops_metrics")
    open_m = request.get("open_metrics")
    if ml_m is None and request.get("use_ml_v34"):
        ml_m = load_ml_metrics_v34(base=base)
    if ops_m is None and request.get("work_dir"):
        ops_m = load_ops_metrics_from_work_dir(request.get("work_dir"), base=base)
    if open_m is None and request.get("open_pack"):
        open_m = load_open_metrics_from_pack(request.get("open_pack"), base=base)
    return {
        "ml_metrics": dict(ml_m) if isinstance(ml_m, Mapping) else None,
        "ops_metrics": dict(ops_m) if isinstance(ops_m, Mapping) else None,
        "open_metrics": dict(open_m) if isinstance(open_m, Mapping) else None,
    }


def decide_from_request(
    request: Mapping[str, Any] | None = None,
    *,
    base: Path | None = None,
    git_commit: str | None = None,
) -> dict[str, Any]:
    """Build Decision Card payload + latency_ms from a request dict.

    Empty / missing sources → ABSTAIN (honest default).
    """
    t0 = time.perf_counter()
    req = dict(request or {})
    event_id = str(req.get("event_id") or "decision")
    require_ops = bool(req.get("require_ops_for_go", False))
    sources = resolve_sources(req, base=base)
    card: DecisionCard = build_decision_card(
        event_id,
        ml_metrics=sources["ml_metrics"],
        ops_metrics=sources["ops_metrics"],
        open_metrics=sources["open_metrics"],
        require_ops_for_go=require_ops,
        git_commit=git_commit,
        extra_metrics={
            "channel": req.get("channel") or "decide_service",
            "api_version": API_VERSION,
        },
    )
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    payload = card.to_dict()
    payload["latency_ms"] = latency_ms
    payload["api_version"] = API_VERSION
    payload["product"] = PRODUCT_ID
    return payload
