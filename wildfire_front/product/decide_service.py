"""Shared Decision Card service for CLI and minimal HTTP API.

Loads optional ML / ops / open sources and builds a Fire Decision Card.
Records wall-clock latency for SLA measurement (metrics-only path).
"""

from __future__ import annotations

import json
import math
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


def _load_json_obj(path: Path) -> dict[str, Any] | None:
    """Load a JSON object from path; None on missing/invalid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _finite_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _o2_gate_to_status(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.upper() in {"GO", "NO_GO", "SKIP", "PASS", "FAIL"}:
        u = value.upper()
        if u == "PASS":
            return "GO"
        if u == "FAIL":
            return "NO_GO"
        return u
    return str(value) if value is not None else None


def _resolve_n_timeline_steps(
    pack: Path,
    scorecard: Mapping[str, Any] | None,
    metrics_o2: Mapping[str, Any] | None,
) -> int:
    """Timeline steps from real perimeters only — never progressive/PSB."""
    timeline = pack / "timeline_perimeters.geojson"
    if timeline.is_file():
        try:
            data = json.loads(timeline.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            feats = data.get("features")
            if isinstance(feats, list):
                return len(feats)
            return 0
    for src in (scorecard, metrics_o2):
        if isinstance(src, Mapping) and isinstance(src.get("n_timeline_steps"), int):
            return int(src["n_timeline_steps"])
    perimeter_candidates = (
        pack / "vectors" / "perimeter_rediam.geojson",
        pack / "vectors" / "perimeter_rai.geojson",
        pack / "vectors" / "perimeter_official.geojson",
        pack / "vectors" / "perimeter.geojson",
    )
    if any(p.is_file() for p in perimeter_candidates):
        return 1
    return 0


def _pick_official_area_ha(
    metrics_o2: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
    scorecard: Mapping[str, Any] | None,
) -> tuple[float | None, str | None]:
    """Official ha only — ban FIRMS hull / firms proxies (closed list)."""
    # Ordered (source_label, mapping, key)
    candidates: list[tuple[str, Mapping[str, Any] | None, str]] = [
        ("metrics_o2.area_rediam_ha", metrics_o2, "area_rediam_ha"),
        ("metrics_o2.area_rai_ha", metrics_o2, "area_rai_ha"),
        ("metrics_o2.area_attr_ha", metrics_o2, "area_attr_ha"),
        ("metrics_o2.max_area_ha", metrics_o2, "max_area_ha"),
        ("manifest.area_rediam_ha", manifest, "area_rediam_ha"),
        ("manifest.area_rai_ha", manifest, "area_rai_ha"),
        ("manifest.area_ha", manifest, "area_ha"),
        ("scorecard.max_area_ha", scorecard, "max_area_ha"),
    ]
    for label, mapping, key in candidates:
        if not isinstance(mapping, Mapping):
            continue
        # Hard ban: never read firms / hull keys even if mis-named into priority
        if "firms" in key.lower() or "hull" in key.lower():
            continue
        val = _finite_float(mapping.get(key))
        if val is not None and val >= 0.0:
            return val, label
    return None, None


def _o2_delineation_from_industrial(
    scorecard: Mapping[str, Any],
) -> str:
    gates = scorecard.get("gates")
    if isinstance(gates, Mapping):
        for gk in ("O2_REDIAM", "O2_RAI", "O2_cems", "O2_cems_delineation"):
            if gk in gates:
                mapped = _o2_gate_to_status(gates.get(gk))
                if mapped is not None:
                    return mapped
    for field in ("O2_cems_delineation", "O2_cems", "O2_REDIAM", "O2_RAI"):
        raw = scorecard.get(field)
        if isinstance(raw, str):
            mapped = _o2_gate_to_status(raw)
            if mapped is not None:
                return mapped
    return "SKIP"


def industrial_scorecard_to_open_metrics(
    pack: Path,
    scorecard: Mapping[str, Any],
    *,
    source_scorecard: str,
    kind: str = "OTHER",
) -> dict[str, Any] | None:
    """Map AND/EXT/other industrial scorecard + companions → open_metrics.

    Returns None when max_area_ha cannot be resolved from official keys.
    Never sets ROS/Vp keys; never uses area_firms* as ha.
    """
    del kind  # kind reserved for audit extensions; filename is source_scorecard
    m2 = _load_json_obj(pack / "metrics_o2.json") or {}
    man = _load_json_obj(pack / "manifest.json") or {}
    area, area_source = _pick_official_area_ha(m2, man, scorecard)
    if area is None or area_source is None:
        return None
    n_steps = _resolve_n_timeline_steps(pack, scorecard, m2)
    pack_id = (
        scorecard.get("pack_id")
        or man.get("pack_id")
        or man.get("codigo")
        or scorecard.get("activation")
        or pack.name
    )
    activation = (
        scorecard.get("pack_id")
        or man.get("pack_id")
        or man.get("codigo")
        or scorecard.get("activation")
        or pack.name
    )
    out: dict[str, Any] = {
        "max_area_ha": float(area),
        "n_timeline_steps": int(n_steps),
        "activation": str(activation),
        "O2_cems_delineation": _o2_delineation_from_industrial(scorecard),
        "pack_id": str(pack_id),
        "source_scorecard": source_scorecard,
        "vp_invented": bool(scorecard["vp_invented"])
        if isinstance(scorecard.get("vp_invented"), bool)
        else False,
        "firms_hull_is_official_burned_area": bool(
            scorecard["firms_hull_is_official_burned_area"]
        )
        if isinstance(scorecard.get("firms_hull_is_official_burned_area"), bool)
        else False,
        "area_source": area_source,
    }
    if scorecard.get("track") is not None:
        out["track"] = scorecard.get("track")
    if scorecard.get("decision_open") is not None:
        out["decision_open"] = scorecard.get("decision_open")
    if scorecard.get("verdict") is not None:
        out["verdict"] = scorecard.get("verdict")
    attr = scorecard.get("attribution")
    if attr is None:
        attr = man.get("attribution")
    if attr is not None:
        out["attribution"] = attr
    return out


def _legacy_pista_b_to_open_metrics(
    pack: Path,
    scorecard: Mapping[str, Any],
) -> dict[str, Any] | None:
    area = _finite_float(scorecard.get("max_area_ha"))
    if area is None or area < 0.0:
        return None
    n_raw = scorecard.get("n_timeline_steps")
    if isinstance(n_raw, int):
        n_steps = int(n_raw)
    else:
        n_steps = _resolve_n_timeline_steps(pack, scorecard, None)
    out: dict[str, Any] = {
        "max_area_ha": float(area),
        "n_timeline_steps": int(n_steps),
        "activation": scorecard.get("activation"),
        "O2_cems_delineation": scorecard.get("O2_cems_delineation"),
        "source_scorecard": "scorecard_pista_b.json",
        "vp_invented": bool(scorecard["vp_invented"])
        if isinstance(scorecard.get("vp_invented"), bool)
        else False,
        "firms_hull_is_official_burned_area": bool(
            scorecard["firms_hull_is_official_burned_area"]
        )
        if isinstance(scorecard.get("firms_hull_is_official_burned_area"), bool)
        else False,
        "area_source": "scorecard.max_area_ha",
    }
    if scorecard.get("pack_id") is not None:
        out["pack_id"] = scorecard.get("pack_id")
    elif scorecard.get("activation") is not None:
        out["pack_id"] = scorecard.get("activation")
    else:
        out["pack_id"] = pack.name
    return out


def load_open_metrics_from_pack(
    open_pack: str | Path | None,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Load open CEMS/perimeter metrics from an open_if pack directory.

    Discovery order (total function — see design §4.2):
    1. Legacy ``scorecard_pista_b.json``
    2. Named industrial AND/EXT (both present → None ambiguous)
    3. Glob ``scorecard_*_industrial.json`` (0 or ≥2 → None)
    """
    pack = _as_path(open_pack, base=base, include_repo_root=include_repo_root)
    if pack is None:
        return None

    # 1) Legacy CEMS
    pista = pack / "scorecard_pista_b.json"
    if pista.is_file():
        sc = _load_json_obj(pista)
        if sc is None:
            return None
        return _legacy_pista_b_to_open_metrics(pack, sc)

    # 2) Named industrial — check BOTH files before choosing either
    and_sc = pack / "scorecard_and_industrial.json"
    ext_sc = pack / "scorecard_ext_industrial.json"
    and_ok = and_sc.is_file()
    ext_ok = ext_sc.is_file()
    if and_ok and ext_ok:
        return None  # ambiguous malformed pack (fail honest)
    if and_ok:
        sc = _load_json_obj(and_sc)
        if sc is None:
            return None
        return industrial_scorecard_to_open_metrics(
            pack, sc, source_scorecard="scorecard_and_industrial.json", kind="AND"
        )
    if ext_ok:
        sc = _load_json_obj(ext_sc)
        if sc is None:
            return None
        return industrial_scorecard_to_open_metrics(
            pack, sc, source_scorecard="scorecard_ext_industrial.json", kind="EXT"
        )

    # 3) Glob other industrial names (only when neither named file exists)
    matches = sorted(pack.glob("scorecard_*_industrial.json"))
    if len(matches) == 0:
        return None
    if len(matches) >= 2:
        return None  # ambiguous_industrial_scorecards
    sc = _load_json_obj(matches[0])
    if sc is None:
        return None
    return industrial_scorecard_to_open_metrics(
        pack, sc, source_scorecard=matches[0].name, kind="OTHER"
    )


def operational_files_to_ops_metrics(
    operational_metrics: Mapping[str, Any] | None,
    front_dynamics: Mapping[str, Any] | None,
    summary_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build ops_metrics from window-root operational files.

    ROS is required: if no finite ROS can be resolved → return None.
    ``summary_metrics`` fills missing keys only (never overwrites ROS/grade).
    """
    ops = operational_metrics if isinstance(operational_metrics, Mapping) else None
    fd = front_dynamics if isinstance(front_dynamics, Mapping) else None
    summary = summary_metrics if isinstance(summary_metrics, Mapping) else None

    ros: float | None = None
    ros_source: str | None = None

    def _try_ros(mapping: Mapping[str, Any] | None, dotted: str, *keys: str) -> bool:
        nonlocal ros, ros_source
        if not isinstance(mapping, Mapping):
            return False
        cur: Any = mapping
        path_parts: list[str] = []
        for k in keys:
            path_parts.append(k)
            if not isinstance(cur, Mapping) or k not in cur:
                return False
            cur = cur[k]
        val = _finite_float(cur)
        if val is None:
            return False
        ros = val
        ros_source = dotted
        return True

    # ROS priority (design §4.4.2) — first finite float wins
    _ = (
        _try_ros(ops, "operational_metrics.speed_median_m_min", "speed_median_m_min")
        or _try_ros(ops, "operational_metrics.primary_ros_m_min", "primary_ros_m_min")
        or _try_ros(
            ops,
            "operational_metrics.structural.primary_ros_m_min",
            "structural",
            "primary_ros_m_min",
        )
        or _try_ros(fd, "front_dynamics.primary_ros_m_min", "primary_ros_m_min")
    )

    if ros is None:
        return None

    # Grade priority
    grade = ""
    if isinstance(ops, Mapping):
        if ops.get("quality_grade") not in (None, ""):
            grade = str(ops.get("quality_grade"))
        elif ops.get("structural_grade") not in (None, ""):
            grade = str(ops.get("structural_grade"))
        else:
            structural = ops.get("structural")
            if isinstance(structural, Mapping) and structural.get("structural_grade") not in (
                None,
                "",
            ):
                grade = str(structural.get("structural_grade"))
    if grade == "" and isinstance(fd, Mapping) and fd.get("structural_grade") not in (None, ""):
        grade = str(fd.get("structural_grade"))

    # n_frames_staged: first int > 0 wins; else first present int (incl. 0)
    n_frames = 0
    frame_keys = (
        "n_frames_staged",
        "n_frames",
        "num_observations",
        "observation_count",
        "input_count",
        "speed_n_observable",
    )
    first_present: int | None = None
    for src in (ops, fd):
        if not isinstance(src, Mapping):
            continue
        found_positive = False
        for k in frame_keys:
            if k not in src:
                continue
            try:
                iv = int(src[k])
            except (TypeError, ValueError):
                continue
            if first_present is None:
                first_present = iv
            if iv > 0:
                n_frames = iv
                found_positive = True
                break
        if found_positive:
            break
    if n_frames == 0 and first_present is not None:
        n_frames = first_present

    area_ha_max: float | None = None
    if isinstance(ops, Mapping):
        for k in ("area_ha_max", "area_ha"):
            area_ha_max = _finite_float(ops.get(k))
            if area_ha_max is not None:
                break
    if area_ha_max is None and isinstance(fd, Mapping):
        for k in ("area_ha_max", "area_ha"):
            area_ha_max = _finite_float(fd.get(k))
            if area_ha_max is not None:
                break

    speed_vs_ref: float | None = None
    if isinstance(ops, Mapping):
        speed_vs_ref = _finite_float(ops.get("speed_vs_ref_ratio"))
    if speed_vs_ref is None and isinstance(fd, Mapping):
        speed_vs_ref = _finite_float(fd.get("speed_vs_ref_ratio"))

    engine = None
    if isinstance(ops, Mapping) and ops.get("engine") is not None:
        engine = ops.get("engine")
    elif isinstance(fd, Mapping) and fd.get("engine") is not None:
        engine = fd.get("engine")

    window = None
    if isinstance(ops, Mapping) and ops.get("window") is not None:
        window = ops.get("window")
    elif isinstance(fd, Mapping) and fd.get("window") is not None:
        window = fd.get("window")

    fire_id = None
    if isinstance(ops, Mapping) and ops.get("fire_id") is not None:
        fire_id = ops.get("fire_id")
    elif isinstance(fd, Mapping) and fd.get("fire_id") is not None:
        fire_id = fd.get("fire_id")

    # Step F: summary fills missing only — never overwrite ROS/grade
    if isinstance(summary, Mapping):
        if grade == "" and summary.get("quality_grade") not in (None, ""):
            grade = str(summary.get("quality_grade"))
        elif grade == "" and summary.get("structural_grade") not in (None, ""):
            grade = str(summary.get("structural_grade"))
        if n_frames == 0:
            sum_first: int | None = None
            for k in frame_keys:
                if k not in summary:
                    continue
                try:
                    iv = int(summary[k])
                except (TypeError, ValueError):
                    continue
                if sum_first is None:
                    sum_first = iv
                if iv > 0:
                    n_frames = iv
                    break
            if n_frames == 0 and sum_first is not None:
                n_frames = sum_first
        if area_ha_max is None:
            for k in ("area_ha_max", "area_ha"):
                area_ha_max = _finite_float(summary.get(k))
                if area_ha_max is not None:
                    break
        if speed_vs_ref is None:
            speed_vs_ref = _finite_float(summary.get("speed_vs_ref_ratio"))
        if engine is None and summary.get("engine") is not None:
            engine = summary.get("engine")
        if window is None and summary.get("window") is not None:
            window = summary.get("window")
        if fire_id is None and summary.get("fire_id") is not None:
            fire_id = summary.get("fire_id")
        # Never overwrite ROS from summary (even if summary has a value)

    out: dict[str, Any] = {
        "quality_grade": grade,
        "primary_ros_m_min": float(ros),
        "n_frames_staged": int(n_frames),
        "area_ha_max": area_ha_max,
        "speed_vs_ref_ratio": speed_vs_ref,
        "ros_source": ros_source,
    }
    if engine is not None:
        out["engine"] = engine
    if window is not None:
        out["window"] = window
    if fire_id is not None:
        out["fire_id"] = fire_id
    return out


def load_infocam_anchor(
    anchors_path: Path | str,
    fire_id: str,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Load a confirmed INFOCAM anchor record (audit only — never sole ROS)."""
    try:
        path = _as_path(anchors_path, base=base, include_repo_root=include_repo_root)
    except PathNotAllowedError:
        path = Path(anchors_path)
        if not path.is_file():
            return None
    if path is None or not path.is_file():
        return None
    data = _load_json_obj(path)
    if data is None:
        return None
    rec = (data.get("anchors") or {}).get(fire_id)
    if not isinstance(rec, dict):
        return None
    if rec.get("status") != "confirmed":
        return None
    return dict(rec)


def attach_infocam_anchor_audit(
    ops_metrics: dict[str, Any] | None,
    anchor: Mapping[str, Any] | None,
    *,
    fire_id: str | None = None,
) -> dict[str, Any] | None:
    """Attach confirmed-anchor audit fields; never overwrite primary ROS from Vp."""
    if ops_metrics is None:
        return None
    if not isinstance(anchor, Mapping):
        return ops_metrics
    out = dict(ops_metrics)
    if fire_id:
        out.setdefault("fire_id", fire_id)
    if anchor.get("vp_m_min") is not None:
        out["anchor_vp_m_min"] = anchor.get("vp_m_min")
    if anchor.get("area_ha") is not None:
        out["anchor_area_ha"] = anchor.get("area_ha")
    out["anchor_status"] = "confirmed"
    if anchor.get("source") is not None:
        out["anchor_source"] = anchor.get("source")
    # Optional audit recompute of speed_vs_ref only when missing
    if out.get("speed_vs_ref_ratio") is None:
        ros = _finite_float(out.get("primary_ros_m_min"))
        vp = _finite_float(anchor.get("vp_m_min"))
        if ros is not None and vp is not None and vp > 0:
            out["speed_vs_ref_ratio"] = float(ros) / float(vp)
    return out


def load_ops_metrics_from_work_dir(
    work_dir: str | Path | None,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Load ops metrics from incident outbox (A–C) or temporal window root (D/E/F).

    A–C return only when ROS is finite (complete ops). Parse errors and ROS-less
    stubs fall through so window-root D/E/F can still resolve honestly.
    """
    wd = _as_path(work_dir, base=base, include_repo_root=include_repo_root)
    if wd is None:
        return None
    # A) Prefer full decision card already written (complete = finite ROS)
    fdc = wd / "outbox" / "fire_decision_card.json"
    if fdc.is_file():
        try:
            card = json.loads(fdc.read_text(encoding="utf-8"))
            ops = (card.get("metrics") or {}).get("ops")
            if isinstance(ops, dict) and ops:
                ros_a = _finite_float(ops.get("primary_ros_m_min"))
                if ros_a is None:
                    ros_a = _finite_float(ops.get("speed_median_m_min"))
                if ros_a is not None:
                    out_a = dict(ops)
                    out_a["primary_ros_m_min"] = ros_a
                    return out_a
        except (OSError, json.JSONDecodeError):
            pass
    # B) incident_state — fall through on parse error or missing ROS
    st_path = wd / "outbox" / "incident_state.json"
    if st_path.is_file():
        try:
            st = json.loads(st_path.read_text(encoding="utf-8"))
            if isinstance(st, dict):
                ros_b = _finite_float(st.get("primary_ros_m_min"))
                if ros_b is not None:
                    return {
                        "quality_grade": st.get("quality_grade"),
                        "primary_ros_m_min": ros_b,
                        "n_frames_staged": st.get("n_frames_staged")
                        or st.get("n_frames_seen"),
                        "area_ha_max": st.get("area_ha_max"),
                        "speed_vs_ref_ratio": st.get("speed_vs_ref_ratio"),
                    }
        except (OSError, json.JSONDecodeError):
            pass
    # C) outbox operational_metrics — fall through on parse error or missing ROS
    ops_path = wd / "outbox" / "operational_metrics.json"
    if ops_path.is_file():
        try:
            ops = json.loads(ops_path.read_text(encoding="utf-8"))
            if isinstance(ops, dict):
                ros_c = _finite_float(ops.get("speed_median_m_min"))
                if ros_c is None:
                    ros_c = _finite_float(ops.get("primary_ros_m_min"))
                if ros_c is not None:
                    return {
                        "quality_grade": ops.get("quality_grade"),
                        "primary_ros_m_min": ros_c,
                        "n_frames_staged": ops.get("n_frames_staged")
                        or ops.get("speed_n_observable"),
                        "area_ha_max": ops.get("area_ha_max"),
                        "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
                    }
        except (OSError, json.JSONDecodeError):
            pass

    # D/E/F) temporal window root layout
    ops_root = _load_json_obj(wd / "operational_metrics.json")
    fd_root = _load_json_obj(wd / "front_dynamics.json")
    summary_raw = _load_json_obj(wd / "summary.json")
    summary_metrics: dict[str, Any] | None = None
    if isinstance(summary_raw, dict):
        nested = summary_raw.get("metrics")
        # Nested metrics preferred; else tolerate flat summary keys at top level
        summary_metrics = dict(nested) if isinstance(nested, dict) else dict(summary_raw)

    if ops_root is None and fd_root is None and summary_metrics is None:
        return None
    return operational_files_to_ops_metrics(ops_root, fd_root, summary_metrics)


def _normalize_ml_live_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Accept flat ml_live_metrics_v1 or outbox ml_prediction_v1 wrapper."""
    if str(data.get("schema") or "") == "ml_live_metrics_v1":
        return dict(data)
    nested = data.get("ml_live_metrics")
    if isinstance(nested, Mapping):
        return dict(nested)
    # Tolerate thin wrapper with top-level confidence + diagnostics
    if "confidence" in data and ("mean_entropy" in data or "diagnostics" in data):
        out = dict(data)
        raw_diag = data.get("diagnostics")
        diag: dict[str, Any] = dict(raw_diag) if isinstance(raw_diag, Mapping) else {}
        for k in ("mean_entropy", "member_disagreement", "mean_margin", "n_members"):
            if k not in out and k in diag:
                out[k] = diag[k]
        out.setdefault("schema", "ml_live_metrics_v1")
        return out
    return dict(data)


def load_ml_live_metrics(
    value: Mapping[str, Any] | str | Path | None,
    *,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any] | None:
    """Load ml_live_metrics_v1 from inline mapping or allowlisted JSON path.

    Also accepts incident ``outbox/ml_prediction.json`` wrappers that embed
    an ``ml_live_metrics`` block (schema ``ml_prediction_v1``).
    """
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        return _normalize_ml_live_payload(value)
    path = _as_path(value, base=base, include_repo_root=include_repo_root)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return _normalize_ml_live_payload(data)


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
        ml_live_trusted = raw_trust if isinstance(raw_trust, bool) else True
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
