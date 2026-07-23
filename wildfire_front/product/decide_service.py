"""Shared Decision Card service for CLI and minimal HTTP API.

Loads optional ML / ops / open sources and builds a Fire Decision Card.
Records wall-clock latency for SLA measurement (metrics-only path).
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .confidence import DecisionCard, build_decision_card

REPO_ROOT = Path(__file__).resolve().parents[2]
API_VERSION = "decide_api_v1"
PRODUCT_ID = "fire_decision_card"
# Max JSON body size for POST /v1/decide (and shared service callers that care).
MAX_BODY_BYTES = 1_048_576  # 1 MiB

# Free-floating R1–R4 booleans are only accepted when callers opt in *and*
# use an allowlisted channel (tests). Prefer file-based gate reports.
CLIENT_RELIABILITY_CHANNELS = frozenset({"test", "unit_test", "pytest"})


class PathNotAllowedError(ValueError):
    """Raised when work_dir/open_pack resolves outside the allowlist."""


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _allow_roots(
    base: Path | None = None,
    *,
    include_repo_root: bool = True,
) -> list[Path]:
    """Return path allow roots.

    Untrusted HTTP sandboxes must pass ``include_repo_root=False`` so only
    ``base`` is accepted (never the full repository tree).

    When ``include_repo_root=False`` and ``base`` is missing/unresolvable,
    returns an **empty** list (fail closed) — never falls back to REPO_ROOT.
    """
    roots: list[Path] = []
    candidates: list[Path | None] = [base]
    if include_repo_root:
        candidates.append(REPO_ROOT)
    for r in candidates:
        if r is None:
            continue
        try:
            rr = Path(r).resolve()
        except OSError:
            continue
        if rr not in roots:
            roots.append(rr)
    if roots:
        return roots
    if include_repo_root:
        return [REPO_ROOT.resolve()]
    # Untrusted isolation with no base: empty roots → every path fails closed.
    return []


def _as_path(
    value: str | Path | None,
    *,
    base: Path | None = None,
    allow_roots: Sequence[Path] | None = None,
    include_repo_root: bool = True,
) -> Path | None:
    """Resolve a path and reject anything outside the allowlist.

    Relative paths try ``base`` first, then each allow root.
    Absolute paths must still fall under an allowed root after resolve.
    """
    if value is None or value == "":
        return None
    p = Path(value)
    roots = [
        Path(r).resolve()
        for r in (allow_roots or _allow_roots(base, include_repo_root=include_repo_root))
    ]
    if not roots:
        raise PathNotAllowedError(
            f"path allowlist empty (untrusted channel requires base_dir; refusing: {value})"
        )
    base_r = Path(base).resolve() if base is not None else roots[0]

    if p.is_absolute():
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise PathNotAllowedError(f"path not resolvable: {value}") from exc
    else:
        # Prefer base; if missing, try each allow root (repo-relative packs).
        candidates: list[Path] = []
        for root in [base_r, *roots]:
            cand = root / p
            if cand not in candidates:
                candidates.append(cand)
        resolved = None
        first_in_allow: Path | None = None
        for cand in candidates:
            try:
                cr = cand.resolve()
            except OSError:
                continue
            if not any(_is_under(cr, root) for root in roots):
                continue
            if first_in_allow is None:
                first_in_allow = cr
            if cr.exists():
                resolved = cr
                break
        if resolved is None:
            resolved = first_in_allow
        if resolved is None:
            raise PathNotAllowedError(f"path not under allowlist: {value}")

    if resolved is None or not any(_is_under(resolved, root) for root in roots):
        raise PathNotAllowedError(
            f"path not under allowlist (base/REPO_ROOT): {value} → {resolved}"
        )
    return resolved


def load_ml_metrics_v34(*, base: Path | None = None) -> dict[str, Any] | None:
    try:
        man = _as_path("models/clm_ensemble/manifest.json", base=base or REPO_ROOT)
    except PathNotAllowedError:
        man = None
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
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    wd = _as_path(work_dir, base=base, include_repo_root=include_repo_root)
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
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    pack = _as_path(open_pack, base=base, include_repo_root=include_repo_root)
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


def load_ml_live_metrics(
    value: Mapping[str, Any] | str | Path | None,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Load ml_live_metrics_v1 from inline mapping or allowlisted JSON path."""
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        return dict(value)
    path = _as_path(value, base=base, include_repo_root=include_repo_root)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_sources(
    request: Mapping[str, Any],
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any | None]:
    """Resolve ml/ops/open/ml_live metrics from request paths or inline dicts."""
    base = base or Path.cwd()
    ml_m = request.get("ml_metrics")
    ops_m = request.get("ops_metrics")
    open_m = request.get("open_metrics")
    ml_live_m = request.get("ml_live_metrics")
    if ml_m is None and request.get("use_ml_v34"):
        # Catalog ML is always repo-local research metadata (not sandboxed).
        ml_m = load_ml_metrics_v34(base=base if include_repo_root else REPO_ROOT)
    if ops_m is None and request.get("work_dir"):
        ops_m = load_ops_metrics_from_work_dir(
            request.get("work_dir"),
            base=base,
            include_repo_root=include_repo_root,
        )
    if open_m is None and request.get("open_pack"):
        open_m = load_open_metrics_from_pack(
            request.get("open_pack"),
            base=base,
            include_repo_root=include_repo_root,
        )
    if ml_live_m is None:
        # CLI/HTTP: --ml-prediction path or ml_prediction / ml_live_path keys.
        for key in ("ml_prediction", "ml_live_path", "ml_live_metrics_path"):
            if request.get(key):
                ml_live_m = load_ml_live_metrics(
                    request.get(key),
                    base=base,
                    include_repo_root=include_repo_root,
                )
                break
    return {
        "ml_metrics": dict(ml_m) if isinstance(ml_m, Mapping) else None,
        "ops_metrics": dict(ops_m) if isinstance(ops_m, Mapping) else None,
        "open_metrics": dict(open_m) if isinstance(open_m, Mapping) else None,
        "ml_live_metrics": dict(ml_live_m) if isinstance(ml_live_m, Mapping) else None,
    }


def _opt_bool_strict(value: Any) -> bool | None:
    """Accept only real JSON/Python booleans; never ``bool("false")``."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    # Reject strings / ints / other types as unknown (not affirmative)
    return None


def _is_docs_reliability_path(path: Path) -> bool:
    """True if path sits under repository docs/ (never a field unlock key)."""
    try:
        docs_root = (REPO_ROOT / "docs").resolve()
        path.resolve().relative_to(docs_root)
        return True
    except (ValueError, OSError):
        return False


def load_reliability_gate_mapping(
    value: Mapping[str, Any] | str | Path | None,
    *,
    base: Path | None = None,
    allow_inline: bool = True,
    include_repo_root: bool = True,
    reject_docs: bool = False,
) -> Mapping[str, Any] | None:
    """Load a reliability gate report; string paths must pass allowlist.

    Inline mappings are allowed only when ``allow_inline`` is True
    (trusted CLI / in-process). HTTP must pass a path under the server base
    sandbox only (no REPO_ROOT / docs/).
    """
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        if not allow_inline:
            return None
        return dict(value)
    path = _as_path(value, base=base, include_repo_root=include_repo_root)
    if path is None or not path.is_file():
        return None
    if reject_docs and _is_docs_reliability_path(path):
        raise PathNotAllowedError(f"reliability_gate under docs/ is not a field unlock key: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def decide_from_request(
    request: Mapping[str, Any] | None = None,
    *,
    base: Path | None = None,
    git_commit: str | None = None,
    trust_client_reliability: bool | None = None,
) -> dict[str, Any]:
    """Build Decision Card payload + latency_ms from a request dict.

    Empty / missing sources → ABSTAIN (honest default).

    Path isolation
    --------------
    * Untrusted channels (``channel=http_api`` or
      ``trust_client_reliability=False``): ``work_dir`` / ``open_pack`` /
      ``reliability_gate`` resolve only under ``base`` (server sandbox).
      ``docs/`` gate paths are always rejected.
    * Trusted CLI / in-process: ``base`` and ``REPO_ROOT`` are allowed.

    Reliability flags
    -----------------
    Free-floating ``gates_ok`` / ``determinism_ok`` / ``abstention_enforced`` /
    ``provenance_ok`` are accepted **only** when
    ``trust_client_reliability=True`` **and** ``channel`` is in
    :data:`CLIENT_RELIABILITY_CHANNELS` (tests). Prefer file-based gate reports.
    """
    t0 = time.perf_counter()
    req = dict(request or {})
    event_id = str(req.get("event_id") or "decision")
    require_ops = bool(req.get("require_ops_for_go", False))
    policy_id = req.get("policy") or req.get("policy_id")
    channel = str(req.get("channel") or "decide_service")

    # Path trust: HTTP / explicit False → sandbox base only (no REPO_ROOT).
    if trust_client_reliability is False or channel == "http_api":
        include_repo_root = False
        allow_inline_gate = False
        reject_docs_gate = True
    else:
        include_repo_root = True
        allow_inline_gate = True
        reject_docs_gate = False

    # Free-floating R1–R4 booleans: opt-in + channel allowlist only.
    accept_client_bools = bool(trust_client_reliability) and channel in CLIENT_RELIABILITY_CHANNELS

    sources = resolve_sources(req, base=base, include_repo_root=include_repo_root)

    if accept_client_bools:
        gates_ok = _opt_bool_strict(req["gates_ok"]) if "gates_ok" in req else None
        determinism_ok = (
            _opt_bool_strict(req["determinism_ok"]) if "determinism_ok" in req else None
        )
        abstention_enforced = (
            _opt_bool_strict(req["abstention_enforced"]) if "abstention_enforced" in req else None
        )
        provenance_ok = _opt_bool_strict(req["provenance_ok"]) if "provenance_ok" in req else None
    else:
        gates_ok = None
        determinism_ok = None
        abstention_enforced = None
        provenance_ok = None

    reliability_gate = load_reliability_gate_mapping(
        req.get("reliability_gate"),
        base=base,
        allow_inline=allow_inline_gate and accept_client_bools,
        include_repo_root=include_repo_root,
        reject_docs=reject_docs_gate,
    )
    # Trusted non-test channels may still pass inline gate maps or files under
    # base/REPO_ROOT (file-based preferred over free-floating booleans).
    if reliability_gate is None and allow_inline_gate and not accept_client_bools:
        reliability_gate = load_reliability_gate_mapping(
            req.get("reliability_gate"),
            base=base,
            allow_inline=True,
            include_repo_root=include_repo_root,
            reject_docs=reject_docs_gate,
        )

    # HTTP / untrusted: live is display-only (no client conf fusion / ML-only HOLD).
    # Trusted CLI/in-process may pass ml_live_trusted=True (default).
    if channel == "http_api" or trust_client_reliability is False:
        ml_live_trusted = False
    else:
        raw_trust = req.get("ml_live_trusted")
        if isinstance(raw_trust, bool):
            ml_live_trusted = raw_trust
        else:
            ml_live_trusted = True
    allow_ml_live_in_fusion = bool(req.get("allow_ml_live_in_fusion", False))

    card: DecisionCard = build_decision_card(
        event_id,
        ml_metrics=sources["ml_metrics"],
        ml_live_metrics=sources.get("ml_live_metrics"),
        ops_metrics=sources["ops_metrics"],
        open_metrics=sources["open_metrics"],
        require_ops_for_go=require_ops,
        git_commit=git_commit,
        policy_id=str(policy_id) if policy_id else None,
        gates_ok=gates_ok,
        determinism_ok=determinism_ok,
        abstention_enforced=abstention_enforced,
        provenance_ok=provenance_ok,
        reliability_gate=reliability_gate,
        allow_ml_live_in_fusion=allow_ml_live_in_fusion,
        ml_live_trusted=ml_live_trusted,
        extra_metrics={
            "channel": channel,
            "api_version": API_VERSION,
            "policy_id": policy_id or "default",
            "reliability_trusted_client": accept_client_bools,
            "path_include_repo_root": include_repo_root,
            "ml_live_trusted": ml_live_trusted,
            "allow_ml_live_in_fusion": allow_ml_live_in_fusion,
        },
    )
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    payload = card.to_dict()
    payload["latency_ms"] = latency_ms
    payload["api_version"] = API_VERSION
    payload["product"] = PRODUCT_ID
    payload["policy_id"] = (payload.get("audit") or {}).get("policy_id") or policy_id or "default"
    return payload
