"""Process staged LWIR frames into operator outbox (incident_runtime_v1)."""

from __future__ import annotations

import atexit
import contextlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cli import run_geotiff_ingest
from ..emergency_products import (
    expansion_bearing_deg_from_centroids,
    load_main_front_centroids,
    write_emergency_envelope_file,
    write_envelope_geojson,
)
from ..identity import sha256_of_file
from ..models import GeometrySpeedConfig
from ..scientific_ops import OperationalReference
from .state import (
    STATE_FILENAME,
    FrameRecord,
    IncidentState,
    load_state,
    save_state,
    utc_now_iso,
)

HEARTBEAT_FILENAME = "watch_heartbeat.json"
LOG_FILENAME = "incident_log.jsonl"
DECISION_CARD_FILENAME = "fire_decision_card.json"
DECISION_CARD_MD_FILENAME = "fire_decision_card.md"

TIFF_EXTENSIONS = {".tif", ".tiff"}
LOCK_FILENAME = ".incident_watch.lock"

# Repo root (…/WildfireFrontDynamics) for optional ML catalog metrics
_REPO_ROOT = Path(__file__).resolve().parents[2]


def acquire_work_dir_lock(work_dir: Path) -> Path:
    """Exclusive lock file so two watchers do not race the same work_dir."""
    work_dir.mkdir(parents=True, exist_ok=True)
    lock_path = work_dir / LOCK_FILENAME
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Steal if PID is dead (stale lock after crash)
        try:
            old = lock_path.read_text(encoding="utf-8").strip()
            if old.isdigit() and not _pid_alive(int(old)):
                lock_path.unlink(missing_ok=True)
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise RuntimeError(f"another incident runtime holds {lock_path} (pid={old or '?'})")
        except RuntimeError:
            raise
        except OSError as exc:
            raise RuntimeError(f"cannot acquire lock {lock_path}: {exc}") from exc
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
    except OSError:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise

    def _release() -> None:
        try:
            if lock_path.is_file() and lock_path.read_text(encoding="utf-8").strip() == str(
                os.getpid()
            ):
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_release)
    return lock_path


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not ours
    except OSError:
        return False
    return True


@dataclass
class IncidentConfig:
    """Runtime configuration for one incident."""

    event_id: str
    sensor_id: str
    estimated_error_m: float
    inbox: Path
    work_dir: Path
    masks_dir: Path | None = None
    band: int = 1
    threshold: float | None = None
    mad_z: float | None = 6.0
    respect_alpha: bool = True
    min_component_pixels: int = 200
    scientific_clean: bool = True
    max_components: int = 5
    morph_close_pixels: int = 3
    min_component_area_m2: float = 100.0
    ref_name: str | None = None
    ref_vp_m_min: float | None = None
    ref_area_ha: float | None = None
    # Optional open CEMS pack dir (scorecard_pista_b.json) fused into Decision Card
    open_pack_dir: Path | None = None
    # Attach ML v34 holdout metrics as transparency signal (not field ROS)
    include_ml_metrics: bool = True
    # Incident path is ops-primary: GO requires thermal ops grade
    require_ops_for_go: bool = True
    # Decision policy profile (config/decision_policies.json); default field_ops for incidents
    decision_policy: str = "field_ops"
    # File stability: size must be unchanged across two polls (watch uses this).
    min_file_age_s: float = 0.5

    def __post_init__(self) -> None:
        self.inbox = Path(self.inbox)
        self.work_dir = Path(self.work_dir)
        if self.masks_dir is not None:
            self.masks_dir = Path(self.masks_dir)
        if self.open_pack_dir is not None:
            self.open_pack_dir = Path(self.open_pack_dir)
        # Prefer external masks over MAD when provided.
        if self.masks_dir is not None and self.masks_dir.is_dir():
            self.mad_z = None
            self.threshold = None

    @property
    def stage_images(self) -> Path:
        return self.work_dir / "stage" / "images"

    @property
    def stage_masks(self) -> Path:
        return self.work_dir / "stage" / "masks"

    @property
    def outbox(self) -> Path:
        return self.work_dir / "outbox"

    @property
    def state_path(self) -> Path:
        return self.outbox / STATE_FILENAME


def list_inbox_tiffs(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    files = [
        p
        for p in inbox.iterdir()
        if p.is_file() and p.suffix.lower() in TIFF_EXTENSIONS and not p.name.startswith(".")
    ]
    return sorted(files, key=lambda p: p.name.lower())


def _file_stable(
    path: Path,
    min_age_s: float,
    prev_sizes: dict[str, int] | None = None,
) -> bool:
    """Skip files still being written.

    Requires min age and, when ``prev_sizes`` is provided, two consecutive
    observations with the same size (true stability across polls).
    """
    try:
        st = path.stat()
    except OSError:
        return False
    if st.st_size <= 0:
        return False
    if time.time() - st.st_mtime < min_age_s:
        return False
    if prev_sizes is not None:
        key = str(path.resolve())
        prev = prev_sizes.get(key)
        prev_sizes[key] = int(st.st_size)
        if prev is None or prev != int(st.st_size):
            return False
    return True


def _atomic_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    shutil.copy2(src, tmp)
    tmp.replace(dest)


def _pair_mask(config: IncidentConfig, stem: str) -> bool:
    """Copy external mask into stage if available. Returns True if newly copied."""
    if config.masks_dir is None or not config.masks_dir.is_dir():
        return False
    mask_src = _find_mask(config.masks_dir, stem)
    if mask_src is None:
        return False
    config.stage_masks.mkdir(parents=True, exist_ok=True)
    mask_dest = config.stage_masks / f"{stem}_mask{mask_src.suffix}"
    if mask_dest.is_file():
        try:
            if sha256_of_file(mask_dest) == sha256_of_file(mask_src):
                return False
        except OSError:
            pass
    _atomic_copy(mask_src, mask_dest)
    return True


def stage_new_frames(
    config: IncidentConfig,
    state: IncidentState,
    *,
    prev_sizes: dict[str, int] | None = None,
) -> list[FrameRecord]:
    """Copy new stable GeoTIFFs from inbox into stage/images (dedup by sha256)."""
    config.stage_images.mkdir(parents=True, exist_ok=True)
    known = {f.get("sha256") for f in state.frames if f.get("sha256")}
    staged: list[FrameRecord] = []

    if not config.inbox.is_dir():
        return staged

    for src in list_inbox_tiffs(config.inbox):
        if not _file_stable(src, config.min_file_age_s, prev_sizes):
            continue
        try:
            digest = sha256_of_file(src)
        except OSError as exc:
            rec = FrameRecord(
                path=str(src.resolve()),
                sha256=f"skip:{src.name}",
                stem=src.stem,
                accepted_at_utc=utc_now_iso(),
                size_bytes=0,
                status="skipped",
                reason=f"hash_failed:{exc}",
            )
            state.upsert_frame(rec)
            continue

        # Late mask attach for already-known frames
        if digest in known:
            if _pair_mask(config, src.stem):
                rec = FrameRecord(
                    path=str(src.resolve()),
                    sha256=digest,
                    stem=src.stem,
                    accepted_at_utc=utc_now_iso(),
                    size_bytes=int(src.stat().st_size),
                    status="staged",
                    reason="late_mask",
                )
                state.upsert_frame(rec)
                staged.append(rec)
            continue

        dest = config.stage_images / src.name
        try:
            dest_same = dest.is_file() and sha256_of_file(dest) == digest
        except OSError:
            dest_same = False
        if not dest_same:
            _atomic_copy(src, dest)
        _pair_mask(config, src.stem)

        rec = FrameRecord(
            path=str(src.resolve()),
            sha256=digest,
            stem=src.stem,
            accepted_at_utc=utc_now_iso(),
            size_bytes=int(src.stat().st_size),
            status="staged",
            reason="",
        )
        state.upsert_frame(rec)
        known.add(digest)
        staged.append(rec)
    return staged


def _find_mask(masks_dir: Path, stem: str) -> Path | None:
    """Resolve mask by exact / _mask naming only (no open prefix globs)."""
    for cand in (
        masks_dir / f"{stem}.tif",
        masks_dir / f"{stem}_mask.tif",
        masks_dir / f"{stem}.tiff",
        masks_dir / f"{stem}_mask.tiff",
    ):
        if cand.is_file():
            return cand
    return None


def build_emergency_briefing_md(
    event_id: str,
    ops: dict[str, Any],
    *,
    n_frames: int,
    latency_s: float | None,
    decision_summary: dict[str, Any] | None = None,
) -> str:
    """One-page emergency briefing for the live outbox."""
    sector = ops.get("sector_ros") or {}
    secs = sector.get("sectors") or {}
    env = ops.get("short_horizon_envelope") or {}
    envelopes = env.get("envelopes") or []
    lines = [
        f"# Emergency briefing — {event_id}",
        "",
        f"_Product: incident_runtime_v1 · frames staged: {n_frames}_",
        "",
    ]
    if decision_summary:
        dec = decision_summary.get("decision") or "—"
        conf = decision_summary.get("confidence_pred")
        conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
        label = decision_summary.get("confidence_pred_label") or "—"
        lines += [
            "## Decision Card",
            "",
            f"- **Decision: {dec}** (confidence_pred={conf_s} · {label})",
            "- Full card: `fire_decision_card.json` · human: `fire_decision_card.md`",
            "- GO / HOLD / ABSTAIN is system advice with abstention — **not** a dispatch order",
            "",
        ]
    lines += [
        "## Status",
        "",
        f"- **Quality grade:** {ops.get('quality_grade') or 'n/a'}",
        f"- **Primary ROS:** {ops.get('speed_median_m_min')} m/min "
        f"(n={ops.get('speed_n_observable')})",
        f"- **Engine:** {ops.get('engine') or 'front_dynamics_v1'}",
    ]
    if latency_s is not None:
        lines.append(f"- **Last update latency:** {latency_s:.2f} s")
    lines += ["", "## Sector ROS (observed guidance)", ""]
    if secs:
        lines += [
            f"- **Head:** {secs.get('head_m_min')} m/min",
            f"- **Flank:** {secs.get('flank_m_min')} m/min",
            f"- **Rear:** {secs.get('rear_m_min')} m/min",
        ]
        if secs.get("head_bearing_deg") is not None:
            lines.append(f"- **Head bearing:** {secs.get('head_bearing_deg')}°")
        if sector.get("label_es"):
            lines.append(f"- _{sector.get('label_es')}_")
    else:
        lines.append(f"- **Abstained:** {sector.get('reason') or 'no sectors / need ≥2 frames'}")

    lines += ["", "## Short-horizon envelope (extrapolated)", ""]
    if env.get("label_es") or env.get("label_en"):
        lines.append(f"- _{env.get('label_es') or env.get('label_en')}_")
    if envelopes:
        for e in envelopes:
            h = e.get("horizon_min")
            lines.append(
                f"- **{h} min:** head {e.get('head_radius_m')} m · "
                f"flank {e.get('flank_radius_m')} m · rear {e.get('rear_radius_m')} m"
            )
    else:
        lines.append(f"- Abstained: {env.get('reason') or 'need ROS from ≥2 frames'}")

    lines += [
        "",
        "## Blocked / not claimed",
        "",
        "- **NOT validated tactical dispatch**",
        "- **NOT official perimeter** (thermal mask ≠ fire perimeter)",
        "- **15/30/60 envelope is extrapolated guidance only**",
        "",
        "## Artifacts",
        "",
        "- `fire_decision_card.json` — GO/HOLD/ABSTAIN + audit (paid-value unit)",
        "- `fire_decision_card.md` — human decision one-pager",
        "- `incident_state.json` — machine state",
        "- `main_front.geojson` — observed main front",
        "- `emergency_envelope_guidance.geojson` — GIS rings/wedges",
        "- `operational_metrics.json` — full ops metrics",
        "- `operational_report.html` — visual dashboard",
        "",
    ]
    return "\n".join(lines)


def _load_ml_metrics_optional() -> dict[str, Any] | None:
    """Holdout metrics from champion ensemble (transparency only, not field ROS)."""
    man = _REPO_ROOT / "models" / "clm_ensemble" / "manifest.json"
    if not man.is_file():
        return None
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metrics = data.get("metrics")
    return dict(metrics) if isinstance(metrics, dict) else None


def _load_open_metrics(open_pack_dir: Path | None) -> dict[str, Any] | None:
    if open_pack_dir is None:
        return None
    scp = Path(open_pack_dir) / "scorecard_pista_b.json"
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


def ops_metrics_for_decision(ops: dict[str, Any], *, n_frames: int = 0) -> dict[str, Any]:
    """Normalize operational_metrics.json fields for the confidence engine."""
    ros = ops.get("speed_median_m_min")
    if ros is None:
        ros = ops.get("primary_ros_m_min")
    n = int(ops.get("n_frames_staged") or ops.get("speed_n_observable") or n_frames or 0)
    return {
        "quality_grade": ops.get("quality_grade"),
        "primary_ros_m_min": ros,
        "n_frames_staged": n,
        "n_frames": n,
        "area_ha_max": ops.get("area_ha_max"),
        "area_ha": ops.get("area_ha_max"),
        "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
        "engine": ops.get("engine"),
        "speed_status": ops.get("speed_status"),
    }


def render_decision_card_md(card_dict: dict[str, Any]) -> str:
    """Human one-pager for the Fire Decision Card in the outbox."""
    dec = card_dict.get("decision") or "—"
    conf = card_dict.get("confidence_pred")
    conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
    label = card_dict.get("confidence_pred_label") or "—"
    event = card_dict.get("event_id") or "—"
    lines = [
        f"# Fire Decision Card — {event}",
        "",
        f"**Decision: {dec}** · confidence_pred={conf_s} ({label})",
        "",
        f"- System reliability gates: "
        f"{'PASS' if card_dict.get('system_reliability_pass') else 'FAIL'}",
        f"- Built (UTC): {card_dict.get('built_at_utc') or '—'}",
        "",
        "## Sources",
        "",
    ]
    for s in card_dict.get("sources") or []:
        avail = "yes" if s.get("available") else "no"
        conf_src = s.get("confidence")
        conf_src_s = f"{float(conf_src):.3f}" if isinstance(conf_src, (int, float)) else "—"
        lines.append(
            f"- **{s.get('id')}**: available={avail} · conf={conf_src_s} · w={s.get('weight')}"
        )
    lines += ["", "## Reasons", ""]
    for r in (card_dict.get("reasons") or [])[:16]:
        lines.append(f"- {r}")
    lines += ["", "## Disclaimers", ""]
    for d in card_dict.get("disclaimers") or []:
        lines.append(f"- {d}")
    audit = card_dict.get("audit") or {}
    lines += [
        "",
        "## Audit",
        "",
        f"- schema: `{audit.get('schema') or 'fire_decision_card_v1'}`",
        f"- input_hash: `{(audit.get('input_hash') or '')[:16]}…`",
        f"- output_hash: `{(audit.get('output_hash') or '')[:16]}…`",
        "",
        "Machine JSON: `fire_decision_card.json`",
        "",
    ]
    return "\n".join(lines)


def publish_decision_card(
    outbox: Path,
    event_id: str,
    ops: dict[str, Any],
    *,
    n_frames: int = 0,
    open_pack_dir: Path | None = None,
    include_ml_metrics: bool = True,
    require_ops_for_go: bool = True,
    decision_policy: str = "field_ops",
    git_commit: str | None = None,
) -> dict[str, str]:
    """Write Fire Decision Card (JSON + MD) into the operator outbox.

    Paid-value artifact: GO / HOLD / ABSTAIN with confidence, sources, audit.
    Incident path is ops-primary (``require_ops_for_go=True`` by default).
    Default policy ``field_ops`` (stricter organism template).
    """
    from ..product.confidence import build_decision_card

    outbox = Path(outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    ops_m = ops_metrics_for_decision(ops, n_frames=n_frames)
    ml_m = _load_ml_metrics_optional() if include_ml_metrics else None
    open_m = _load_open_metrics(open_pack_dir)
    card = build_decision_card(
        event_id,
        ml_metrics=ml_m,
        ops_metrics=ops_m,
        open_metrics=open_m,
        require_ops_for_go=require_ops_for_go,
        git_commit=git_commit,
        policy_id=decision_policy or "field_ops",
        extra_metrics={
            "product": "incident_runtime_v1",
            "outbox": str(outbox.resolve()),
            "n_frames": n_frames,
        },
    )
    payload = card.to_dict()
    json_path = outbox / DECISION_CARD_FILENAME
    md_path = outbox / DECISION_CARD_MD_FILENAME
    tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(json_path)
    md_path.write_text(render_decision_card_md(payload), encoding="utf-8")

    # M2.9 — forensic acta + radio-bridge + replay sources (paid audit trail)
    forensic_paths: dict[str, str] = {}
    try:
        from ..product.forensics import write_forensic_bundle

        forensic_paths = write_forensic_bundle(
            outbox,
            payload,
            ml_metrics=ml_m,
            ops_metrics=ops_m,
            open_metrics=open_m,
            require_ops_for_go=require_ops_for_go,
        )
    except Exception:  # noqa: BLE001 — card is primary; forensics best-effort
        forensic_paths = {}

    out: dict[str, Any] = {
        "fire_decision_card_json": str(json_path),
        "fire_decision_card_md": str(md_path),
        "decision": payload.get("decision"),
        "confidence_pred": payload.get("confidence_pred"),
        "confidence_pred_label": payload.get("confidence_pred_label"),
    }
    for k in ("radio", "acta", "manifest", "replay_sources"):
        if forensic_paths.get(k):
            out[f"forensic_{k}"] = forensic_paths[k]
    if forensic_paths.get("self_replay_ok") is not None:
        out["forensic_self_replay_ok"] = forensic_paths["self_replay_ok"]
    return out


def publish_emergency_layers(
    outbox: Path,
    event_id: str,
    *,
    n_frames: int = 0,
    latency_s: float | None = None,
    decision_summary: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Write emergency envelope GIS + briefing from operational_metrics + main_front."""
    ops_path = outbox / "operational_metrics.json"
    mf_path = outbox / "main_front.geojson"
    artifacts: dict[str, str] = {}
    if not ops_path.is_file():
        return artifacts

    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    bearing = None
    center = None
    if mf_path.is_file():
        cents = load_main_front_centroids(mf_path)
        if cents:
            bearing = expansion_bearing_deg_from_centroids(cents)
            center = cents[-1]
            # Re-enrich if sector missing or bearing newly available
            if bearing is not None:
                from ..emergency_products import enrich_ops_dict

                ops = enrich_ops_dict(ops, expansion_bearing_deg=bearing)
                ops_path.write_text(json.dumps(ops, indent=2, default=str), encoding="utf-8")

    env = ops.get("short_horizon_envelope") or {}
    env_json = outbox / "emergency_envelope.json"
    write_emergency_envelope_file(env, env_json)
    artifacts["emergency_envelope_json"] = str(env_json)

    gj_path = outbox / "emergency_envelope_guidance.geojson"
    write_envelope_geojson(
        env,
        gj_path,
        center_xy=center,
        fire_id=event_id,
        expansion_bearing_deg=bearing or (ops.get("sector_ros") or {}).get("expansion_bearing_deg"),
    )
    artifacts["emergency_envelope_guidance_geojson"] = str(gj_path)

    brief = outbox / "emergency_briefing.md"
    brief.write_text(
        build_emergency_briefing_md(
            event_id,
            ops,
            n_frames=n_frames,
            latency_s=latency_s,
            decision_summary=decision_summary,
        ),
        encoding="utf-8",
    )
    artifacts["emergency_briefing_md"] = str(brief)
    return artifacts


def _operational_ref(config: IncidentConfig) -> OperationalReference | None:
    if config.ref_vp_m_min is None and config.ref_area_ha is None:
        return None
    return OperationalReference(
        name=config.ref_name or "operational_anchor",
        vp_m_min=config.ref_vp_m_min,
        area_ha=config.ref_area_ha,
    )


def write_heartbeat(outbox: Path, summary: dict[str, Any]) -> Path:
    """Atomic operator heartbeat for field monitoring."""
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / HEARTBEAT_FILENAME
    payload = {
        "product": "incident_runtime_v1",
        "updated_at_utc": utc_now_iso(),
        "status": summary.get("status"),
        "event_id": summary.get("event_id"),
        "n_staged": summary.get("n_staged"),
        "new_frames": summary.get("new_frames"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "decision": summary.get("decision"),
        "confidence_pred": summary.get("confidence_pred"),
        "confidence_pred_label": summary.get("confidence_pred_label"),
        "latency_s": summary.get("latency_s"),
        "error": summary.get("error") or summary.get("last_error"),
        "outbox": str(outbox.resolve()),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def append_incident_log(outbox: Path, summary: dict[str, Any]) -> Path:
    """Append one JSON line per update (durable field log)."""
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / LOG_FILENAME
    line = {
        "ts_utc": utc_now_iso(),
        "status": summary.get("status"),
        "event_id": summary.get("event_id"),
        "n_staged": summary.get("n_staged"),
        "new_frames": summary.get("new_frames"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "decision": summary.get("decision"),
        "confidence_pred": summary.get("confidence_pred"),
        "latency_s": summary.get("latency_s"),
        "error": summary.get("error"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, default=str) + "\n")
    return path


def publish_operator_telemetry(outbox: Path, summary: dict[str, Any]) -> dict[str, str]:
    """Heartbeat + JSONL after each process_incident_once."""
    hb = write_heartbeat(outbox, summary)
    log = append_incident_log(outbox, summary)
    return {"heartbeat": str(hb), "log": str(log)}


def process_incident_once(
    config: IncidentConfig,
    *,
    force: bool = False,
    prev_sizes: dict[str, int] | None = None,
    acquire_lock: bool = False,
) -> dict[str, Any]:
    """Stage new frames from inbox and recompute outbox if anything changed.

    Returns a summary dict suitable for JSON CLI output.
    """
    if acquire_lock:
        acquire_work_dir_lock(config.work_dir)

    config.work_dir.mkdir(parents=True, exist_ok=True)
    config.outbox.mkdir(parents=True, exist_ok=True)

    if not config.inbox.is_dir():
        early_summary: dict[str, Any] = {
            "product": "incident_runtime_v1",
            "event_id": config.event_id,
            "new_frames": 0,
            "n_staged": 0,
            "updated": False,
            "outbox": str(config.outbox.resolve()),
            "status": "waiting_for_frames",
            "error": f"inbox_missing:{config.inbox}",
        }
        publish_operator_telemetry(config.outbox, early_summary)
        return early_summary

    state = load_state(config.state_path) or IncidentState(
        event_id=config.event_id,
        sensor_id=config.sensor_id,
        created_at_utc=utc_now_iso(),
    )
    state.event_id = config.event_id
    state.sensor_id = config.sensor_id
    if not state.created_at_utc:
        state.created_at_utc = utc_now_iso()

    t0 = time.perf_counter()
    # When min_file_age_s==0 (tests), skip two-poll size gate
    size_cache = prev_sizes if config.min_file_age_s > 0 else None
    new_frames = stage_new_frames(config, state, prev_sizes=size_cache)
    staged_tiffs = list_inbox_tiffs(config.stage_images)
    n_staged = len(staged_tiffs)

    summary: dict[str, Any] = {
        "product": "incident_runtime_v1",
        "event_id": config.event_id,
        "new_frames": len(new_frames),
        "n_staged": n_staged,
        "updated": False,
        "outbox": str(config.outbox.resolve()),
    }

    if n_staged == 0:
        state.last_error = "no_staged_frames"
        save_state(state, config.state_path)
        summary["status"] = "waiting_for_frames"
        summary["state"] = state.to_dict()
        publish_operator_telemetry(config.outbox, summary)
        return summary

    # Do not idle after a failed update: watch mode only force=True on the first
    # poll, so a permanent idle here would strand newly staged frames forever.
    has_unprocessed = any(f.get("status") == "staged" for f in state.frames)
    if (
        not new_frames
        and not force
        and not state.last_error
        and not has_unprocessed
        and (config.outbox / "operational_metrics.json").is_file()
    ):
        # Nothing new; return last state
        summary["status"] = "idle"
        summary["quality_grade"] = state.quality_grade
        summary["primary_ros_m_min"] = state.primary_ros_m_min
        summary["state"] = state.to_dict()
        publish_operator_telemetry(config.outbox, summary)
        return summary

    # Recompute full pack from staged images
    masks_arg: Path | None = None
    mad_z = config.mad_z
    threshold = config.threshold
    if config.stage_masks.is_dir() and any(config.stage_masks.glob("*.tif*")):
        masks_arg = config.stage_masks
        mad_z = None
        threshold = None
    elif masks_arg is None and mad_z is None and threshold is None:
        # Prefer explicit config; only auto-enable MAD when masks dir was never set
        if config.masks_dir is None:
            mad_z = 6.0
        else:
            summary["status"] = "error"
            err_msg = "masks_dir_set_but_no_stage_masks_and_no_mad"
            summary["error"] = err_msg
            state.last_error = err_msg
            save_state(state, config.state_path)
            summary["state"] = state.to_dict()
            publish_operator_telemetry(config.outbox, summary)
            return summary

    try:
        metrics = run_geotiff_ingest(
            config.stage_images,
            masks_arg,
            config.outbox,
            config.event_id,
            config.sensor_id,
            config.estimated_error_m,
            config.band,
            threshold,
            GeometrySpeedConfig(),
            mad_z,
            config.respect_alpha,
            config.min_component_pixels,
            scientific_clean=config.scientific_clean,
            max_components=config.max_components,
            morph_close_pixels=config.morph_close_pixels,
            min_component_area_m2=config.min_component_area_m2,
            operational_ref=_operational_ref(config),
            write_operational=True,
        )
        latency = time.perf_counter() - t0
        ops = metrics.get("operational") if isinstance(metrics.get("operational"), dict) else {}
        # Prefer full ops file for grade/ROS
        ops_path = config.outbox / "operational_metrics.json"
        if ops_path.is_file():
            full_ops = json.loads(ops_path.read_text(encoding="utf-8"))
            ops = full_ops

        decision_artifacts: dict[str, Any] = {}
        if isinstance(ops, dict) and ops:
            decision_artifacts = publish_decision_card(
                config.outbox,
                config.event_id,
                ops,
                n_frames=n_staged,
                open_pack_dir=config.open_pack_dir,
                include_ml_metrics=config.include_ml_metrics,
                require_ops_for_go=config.require_ops_for_go,
                decision_policy=config.decision_policy or "field_ops",
            )

        emergency = publish_emergency_layers(
            config.outbox,
            config.event_id,
            n_frames=n_staged,
            latency_s=latency,
            decision_summary=decision_artifacts or None,
        )

        state.n_updates += 1
        state.last_latency_s = round(latency, 4)
        state.last_error = None
        state.quality_grade = ops.get("quality_grade") if isinstance(ops, dict) else None
        state.quality_label_es = ops.get("quality_label_es") if isinstance(ops, dict) else None
        state.primary_ros_m_min = ops.get("speed_median_m_min") if isinstance(ops, dict) else None
        state.speed_n_observable = ops.get("speed_n_observable") if isinstance(ops, dict) else None
        state.area_ha_max = ops.get("area_ha_max") if isinstance(ops, dict) else None
        state.speed_vs_ref_ratio = ops.get("speed_vs_ref_ratio") if isinstance(ops, dict) else None
        state.engine = ops.get("engine") if isinstance(ops, dict) else None
        state.n_frames_staged = n_staged
        for f in state.frames:
            if f.get("status") == "staged":
                f["status"] = "processed"
        # Keep only path artifacts in state (not decision scalars)
        fdc_paths = {
            k: v
            for k, v in decision_artifacts.items()
            if k.startswith("fire_decision_card") and isinstance(v, str)
        }
        state.artifacts = {
            "outbox": str(config.outbox.resolve()),
            "operational_metrics": str(ops_path),
            "main_front": str(config.outbox / "main_front.geojson"),
            "incident_state": str(config.state_path),
            **emergency,
            **fdc_paths,
        }
        save_state(state, config.state_path)

        summary["status"] = "updated"
        summary["updated"] = True
        summary["latency_s"] = round(latency, 4)
        summary["quality_grade"] = state.quality_grade
        summary["quality_label_es"] = state.quality_label_es
        summary["primary_ros_m_min"] = state.primary_ros_m_min
        summary["speed_n_observable"] = state.speed_n_observable
        summary["area_ha_max"] = state.area_ha_max
        summary["speed_vs_ref_ratio"] = state.speed_vs_ref_ratio
        summary["engine"] = state.engine
        summary["decision"] = decision_artifacts.get("decision")
        summary["confidence_pred"] = decision_artifacts.get("confidence_pred")
        summary["confidence_pred_label"] = decision_artifacts.get("confidence_pred_label")
        summary["artifacts"] = state.artifacts
        summary["new_frame_stems"] = [f.stem for f in new_frames]
        summary["metrics"] = {
            k: metrics.get(k)
            for k in (
                "num_observations",
                "num_components",
                "operational",
            )
            if k in metrics
        }
        if isinstance(ops, dict):
            summary["sector_ros"] = ops.get("sector_ros")
            summary["short_horizon_envelope"] = ops.get("short_horizon_envelope")
            summary["speed_p25_m_min"] = ops.get("speed_p25_m_min")
            summary["speed_p75_m_min"] = ops.get("speed_p75_m_min")
            summary["primary_methods_used"] = ops.get("primary_methods_used")
            summary["mean_coreg_shift_m"] = ops.get("mean_coreg_shift_m")
            summary["speed_status"] = ops.get("speed_status")
        summary["state"] = state.to_dict()
        publish_operator_telemetry(config.outbox, summary)
        return summary
    except Exception as exc:  # noqa: BLE001 — surface in state for operators
        latency = time.perf_counter() - t0
        state.last_latency_s = round(latency, 4)
        state.last_error = str(exc)
        save_state(state, config.state_path)
        summary["status"] = "error"
        summary["error"] = str(exc)
        summary["latency_s"] = round(latency, 4)
        summary["state"] = state.to_dict()
        publish_operator_telemetry(config.outbox, summary)
        return summary
