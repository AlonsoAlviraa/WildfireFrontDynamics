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
    """Holdout metrics from champion ensemble — thin wrap of decide_service."""
    from ..product.decide_service import load_ml_metrics_v34

    return load_ml_metrics_v34()


def _load_open_metrics(open_pack_dir: Path | None) -> dict[str, Any] | None:
    """Open CEMS pack metrics — thin wrap of decide_service."""
    from ..product.decide_service import load_open_metrics_from_pack

    return load_open_metrics_from_pack(open_pack_dir)


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


def _link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        try:
            dst.symlink_to(src.resolve())
        except OSError:
            shutil.copy2(src, dst)


def _prepare_incremental_ingest(
    config: IncidentConfig,
    *,
    n_keep: int = 2,
) -> tuple[Path | None, Path | None]:
    """Build a temporary stage with the last ``n_keep`` images (and masks).

    Returns ``(images_dir, masks_dir|None)``. On failure returns ``(None, None)``
    so the caller falls back to full re-ingest.
    """
    staged = list_inbox_tiffs(config.stage_images)
    if len(staged) < n_keep:
        return None, None
    keep = staged[-n_keep:]
    inc_root = config.work_dir / "stage" / "incremental"
    inc_images = inc_root / "images"
    if inc_images.is_dir():
        for p in inc_images.iterdir():
            if p.is_file() or p.is_symlink():
                p.unlink(missing_ok=True)
    else:
        inc_images.mkdir(parents=True, exist_ok=True)
    for src in keep:
        _link_or_copy(src, inc_images / src.name)

    inc_masks: Path | None = None
    if config.stage_masks.is_dir() and any(config.stage_masks.glob("*.tif*")):
        mask_dir = inc_root / "masks"
        if mask_dir.is_dir():
            for p in mask_dir.iterdir():
                if p.is_file() or p.is_symlink():
                    p.unlink(missing_ok=True)
        else:
            mask_dir.mkdir(parents=True, exist_ok=True)
        for src in keep:
            # Match common mask naming: same stem or stem + _mask
            candidates = [
                config.stage_masks / src.name,
                config.stage_masks / f"{src.stem}_mask{src.suffix}",
                config.stage_masks / f"{src.stem}_mask.tif",
            ]
            for m in candidates:
                if m.is_file():
                    _link_or_copy(m, mask_dir / m.name)
                    break
        if any(mask_dir.glob("*.tif*")):
            inc_masks = mask_dir
    return inc_images, inc_masks


def _humanize_decision_reason(reason: str) -> str:
    """E6 — map machine reason tokens to short operator-facing ES/EN notes."""
    r = str(reason or "").strip()
    if not r:
        return r
    table = {
        "ops_confidence_ok": "Ops térmico con confianza suficiente para GO (no es orden táctica)",
        "ops+open_fusion": "Fusión ops + perímetro open por encima del umbral GO",
        "ops_required_for_go": "Política exige ops térmico para GO → sin ops no hay GO",
        "open_only_monitoring": "Solo open/CEMS → HOLD de monitorización (sin ROS de frente)",
        "open_cems_monitoring_only": "Open CEMS disponible → HOLD monitorización",
        "ml_only_not_field_ros": "Solo ML → HOLD lab (no ROS de campo)",
        "ml_only_blocked_by_policy": "field_ops: ML-only bloqueado → ABSTAIN",
        "no_available_sources": "Ninguna fuente disponible → ABSTAIN",
        "no_sources": "Sin fuentes fusionables",
        "below_action_threshold": "Confianza por debajo del umbral de acción → ABSTAIN",
        "field_ops_fail_closed_reliability_unverified": (
            "field_ops fail-closed: reliability this-run no verificada → GO degradado a ABSTAIN"
        ),
        "ml_holdout_research_only_conf_zero": (
            "IoU holdout es proveniencia de research (no sube confidence_pred)"
        ),
        "ml_live_abstained_conf_zero": "ML live abstuvo → conf ML no cuenta para fusión",
        "ml_live:veto_hold": "Veto ML live: GO → HOLD",
    }
    if r in table:
        return f"{r} — {table[r]}"
    if r.startswith("policy:"):
        return f"{r} — perfil de decisión activo"
    if r.startswith("confidence_pred<"):
        return f"{r} — confianza fusionada bajo umbral de abstención"
    if ":holdout_quality=" in r and ":not_fused" in r:
        return f"{r} — metadata holdout visible, no fusionada como calidad live"
    if r.startswith("ops_thermal_front:conf="):
        return f"{r} — peso ops en fusión"
    if r.startswith("open_cems_perimeter:conf="):
        return f"{r} — peso open/CEMS en fusión (capado; no cadastre nacional)"
    if r.startswith("missing:"):
        return f"{r} — fuente ausente en este card"
    return r


def _uncertainty_band_notes(card_dict: dict[str, Any]) -> list[str]:
    """E6 / R-UQ1 — short epistemic vs aleatory notes for the MD card."""
    notes: list[str] = []
    metrics = card_dict.get("metrics") if isinstance(card_dict.get("metrics"), dict) else {}
    ops = metrics.get("ops") if isinstance(metrics.get("ops"), dict) else {}
    conf = card_dict.get("confidence_pred")
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None

    # Aleatory (data) proxies from ops metrics when present
    grade = str(ops.get("quality_grade") or "").upper()
    n_frames = ops.get("n_frames") or ops.get("n_frames_staged")
    ros = ops.get("primary_ros_m_min")
    if grade or n_frames or ros is not None:
        bits = []
        if grade:
            bits.append(f"grade={grade}")
        if n_frames is not None:
            bits.append(f"n_frames={n_frames}")
        if ros is not None:
            bits.append(f"ROS={ros} m/min")
        notes.append(
            "u_data (aleatoria/obs): " + ", ".join(bits) + " — calidad de la observación térmica"
        )
    else:
        notes.append(
            "u_data (aleatoria/obs): sin métricas ops en card — riesgo de dato alto → favorecer ABSTAIN"
        )

    # Epistemic proxies: policy + reliability + ML not fused
    audit = card_dict.get("audit") if isinstance(card_dict.get("audit"), dict) else {}
    sys_rel = (
        audit.get("system_reliability") if isinstance(audit.get("system_reliability"), dict) else {}
    )
    rel_status = str(
        sys_rel.get("status") or ("pass" if card_dict.get("system_reliability_pass") else "unknown")
    )
    policy_id = (
        (metrics.get("policy_id") if isinstance(metrics, dict) else None)
        or audit.get("policy_id")
        or "—"
    )
    notes.append(
        f"u_model (epistémica/rails): policy={policy_id} · reliability_status={rel_status} · "
        "ML holdout no fusionado en field_ops"
    )
    if conf_f is not None:
        if conf_f < 0.25:
            band = "VERY_LOW → map Orion-style reject → ABSTAIN"
        elif conf_f < 0.45:
            band = "LOW → HOLD/ABSTAIN según fuentes"
        elif conf_f < 0.65:
            band = "MID → HOLD o GO solo con ops + umbral"
        else:
            band = "HIGH conf de producto — sigue sin ser orden táctica"
        notes.append(f"confidence_pred={conf_f:.3f} band: {band}")
    notes.append(
        "Mapa UQ: aleatoria alta o solo ML → ABSTAIN; open-only → HOLD; "
        "ops fuerte + gate this-run → GO posible. Nunca labels EVACUATE/SAFE."
    )
    return notes


def render_decision_card_md(card_dict: dict[str, Any]) -> str:
    """Human one-pager for the Fire Decision Card in the outbox."""
    dec = card_dict.get("decision") or "—"
    conf = card_dict.get("confidence_pred")
    conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
    label = card_dict.get("confidence_pred_label") or "—"
    event = card_dict.get("event_id") or "—"
    audit = card_dict.get("audit") or {}
    sys_rel = (
        audit.get("system_reliability") if isinstance(audit.get("system_reliability"), dict) else {}
    )
    rel_status = str(sys_rel.get("status") or "").upper()
    if not rel_status:
        rel_status = "PASS" if card_dict.get("system_reliability_pass") else "FAIL/UNKNOWN"
    policy_id = (
        (
            (card_dict.get("metrics") or {}).get("policy_id")
            if isinstance(card_dict.get("metrics"), dict)
            else None
        )
        or audit.get("policy_id")
        or "—"
    )
    lines = [
        f"# Fire Decision Card — {event}",
        "",
        f"**Decision: {dec}** · confidence_pred={conf_s} ({label})",
        "",
        f"- Policy: `{policy_id}`",
        f"- System reliability gates: **{rel_status}** "
        f"(pass={bool(card_dict.get('system_reliability_pass'))})",
        f"- Built (UTC): {card_dict.get('built_at_utc') or '—'}",
        "- ML-live fusion (field): **OFF** under field_ops — IoU ≠ ROS",
        "",
        "## Sources",
        "",
    ]
    for s in card_dict.get("sources") or []:
        avail = "yes" if s.get("available") else "no"
        conf_src = s.get("confidence")
        conf_src_s = f"{float(conf_src):.3f}" if isinstance(conf_src, (int, float)) else "—"
        role = s.get("role") or s.get("source_type") or ""
        role_s = f" · role={role}" if role else ""
        lines.append(
            f"- **{s.get('id')}**: available={avail} · conf={conf_src_s} · w={s.get('weight')}{role_s}"
        )
    lines += ["", "## Reasons (legible)", ""]
    for r in (card_dict.get("reasons") or [])[:20]:
        lines.append(f"- {_humanize_decision_reason(str(r))}")
    lines += ["", "## Uncertainty band (Orion-style rails)", ""]
    for n in _uncertainty_band_notes(card_dict):
        lines.append(f"- {n}")
    lines += ["", "## Disclaimers", ""]
    for d in card_dict.get("disclaimers") or []:
        lines.append(f"- {d}")
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


def should_use_incremental_ingest(
    *,
    force: bool,
    n_new_frames: int,
    n_staged: int,
    n_updates: int,
    has_ops_file: bool,
    last_error: str | None,
) -> bool:
    """Whether last-pair incremental geotiff ingest is allowed.

    Full reprocess when forced, first update, missing prior ops, or no new frames.
    """
    return (
        not force
        and n_new_frames > 0
        and n_staged >= 2
        and n_updates > 0
        and has_ops_file
        and not last_error
    )


def write_this_run_reliability_gate(
    outbox: Path,
    event_id: str,
    ops_m: dict[str, Any],
    *,
    ml_metrics: dict[str, Any] | None = None,
    open_metrics: dict[str, Any] | None = None,
    require_ops_for_go: bool = True,
    decision_policy: str = "field_ops",
    git_commit: str | None = None,
) -> Path:
    """This-run R1–R4 self-check bound to the current incident event.

    Writes ``outbox/reliability_gate_report.json``. PASS means:

    * multi-frame ops quality floor (grade A/B, n_frames>=2, ROS present)
    * card engine determinism + abstention heuristic for *this* inputs
    * content hashes bound to this event's ops/ml/open metrics

    It is **not** suite-level five-nines CI enforcement. Does not copy docs
    suite samples. ``field_unlock`` is true only when all R1–R4 pass.
    """
    from ..product.confidence import (
        build_decision_card,
        content_hash,
        system_reliability_report,
    )

    outbox = Path(outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "ml_metrics": ml_metrics,
        "ops_metrics": ops_m,
        "open_metrics": open_metrics,
        "require_ops_for_go": require_ops_for_go,
        "git_commit": git_commit,
        "policy_id": decision_policy or "field_ops",
    }
    card_a = build_decision_card(event_id, **kwargs)
    card_b = build_decision_card(event_id, **kwargs)
    ha = content_hash(
        {
            "d": card_a.decision.value,
            "c": card_a.confidence_pred,
            "s": card_a.sources,
            "r": card_a.reasons,
        }
    )
    hb = content_hash(
        {
            "d": card_b.decision.value,
            "c": card_b.confidence_pred,
            "s": card_b.sources,
            "r": card_b.reasons,
        }
    )
    determinism_ok = ha == hb

    # R2: multi-frame thermal ops quality floor (not mere dict non-empty).
    n_frames = int(ops_m.get("n_frames_staged") or ops_m.get("n_frames") or 0)
    grade = str(ops_m.get("quality_grade") or "").strip().upper()
    ros = ops_m.get("primary_ros_m_min")
    try:
        # ROS floor: strictly positive (zero / missing is not a usable ops signal).
        ros_ok = ros is not None and float(ros) > 0.0
    except (TypeError, ValueError):
        ros_ok = False
    gates_ok = n_frames >= 2 and grade in {"A", "B"} and ros_ok

    abstention_enforced = bool(card_a.audit.get("abstention_heuristic_ok"))
    ops_hash = content_hash(
        {
            "quality_grade": ops_m.get("quality_grade"),
            "primary_ros_m_min": ops_m.get("primary_ros_m_min"),
            "n_frames_staged": n_frames,
            "area_ha_max": ops_m.get("area_ha_max"),
            "speed_vs_ref_ratio": ops_m.get("speed_vs_ref_ratio"),
        }
    )
    provenance_ok = bool(
        card_a.audit.get("input_hash")
        and card_a.audit.get("output_hash")
        and card_a.audit.get("schema") == "fire_decision_card_v1"
        and ops_hash
    )
    rel = system_reliability_report(
        gates_ok=gates_ok,
        determinism_ok=determinism_ok,
        abstention_enforced=abstention_enforced,
        provenance_ok=provenance_ok,
    )
    failures: list[str] = []
    if not determinism_ok:
        failures.append("determinism_hash_mismatch")
    if not provenance_ok:
        failures.append("provenance_incomplete")
    if not gates_ok:
        failures.append("ops_quality_floor_failed")
    passed = bool(rel.get("system_reliability_pass"))
    report: dict[str, Any] = {
        "ok": passed,
        "failures": failures,
        "suite_only": False,
        # Unlock field only when this-run quality floor + hashes all pass.
        "field_unlock": passed,
        "event_id": event_id,
        "provenance": {
            "kind": "this_run",
            "event_id": event_id,
            "input_hash": card_a.audit.get("input_hash"),
            "output_hash": card_a.audit.get("output_hash"),
            "ops_hash": ops_hash,
            "n_frames": n_frames,
            "quality_grade": grade or None,
            "git_commit": git_commit,
            "note": (
                "this_run PASS = multi-frame ops quality floor (A/B, n>=2, ROS) "
                "+ card engine hashes for this event; not suite five-nines CI."
            ),
        },
        "system_reliability": rel,
    }
    path = outbox / "reliability_gate_report.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


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
    reliability_gate: Path | str | dict | None = None,
    ml_metrics: dict[str, Any] | None = None,
    ml_live_metrics: dict[str, Any] | None = None,
    open_metrics: dict[str, Any] | None = None,
    write_this_run_gate: bool = True,
) -> dict[str, str]:
    """Write Fire Decision Card (JSON + MD) into the operator outbox.

    Paid-value artifact: GO / HOLD / ABSTAIN with confidence, sources, audit.
    Incident path is ops-primary (``require_ops_for_go=True`` by default).
    Default policy ``field_ops`` (stricter organism template).

    Optional live ML: pass ``ml_live_metrics`` or drop ``outbox/ml_prediction.json``
    (schema ml_prediction_v1 or ml_live_metrics_v1). No ROS fields in ML path.

    Reliability: does **not** auto-load checked-in ``docs/RELIABILITY_GATE_REPORT.json``
    (stale PASS would unlock field_ops GO). Generates a this-run gate report
    under ``outbox/reliability_gate_report.json`` when ``write_this_run_gate``
    is True (default). Pass ``reliability_gate`` explicitly to override.
    """
    from ..product.confidence import build_decision_card
    from ..product.decide_service import load_ml_live_metrics

    outbox = Path(outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    ops_m = ops_metrics_for_decision(ops, n_frames=n_frames)
    # Reuse in-memory metrics when caller already resolved them (avoid re-reads).
    ml_m = (
        ml_metrics
        if ml_metrics is not None
        else (_load_ml_metrics_optional() if include_ml_metrics else None)
    )
    open_m = open_metrics if open_metrics is not None else _load_open_metrics(open_pack_dir)
    ml_live_m = ml_live_metrics
    if ml_live_m is None:
        pred_path = outbox / "ml_prediction.json"
        if pred_path.is_file():
            ml_live_m = load_ml_live_metrics(pred_path, include_repo_root=True)

    gate: Path | str | dict | None = reliability_gate
    if gate is None and write_this_run_gate:
        gate = write_this_run_reliability_gate(
            outbox,
            event_id,
            ops_m,
            ml_metrics=ml_m,
            open_metrics=open_m,
            require_ops_for_go=require_ops_for_go,
            decision_policy=decision_policy or "field_ops",
            git_commit=git_commit,
        )
    elif gate is None:
        outbox_gate = outbox / "reliability_gate_report.json"
        if outbox_gate.is_file():
            gate = outbox_gate
    card = build_decision_card(
        event_id,
        ml_metrics=ml_m,
        ml_live_metrics=ml_live_m,
        ops_metrics=ops_m,
        open_metrics=open_m,
        require_ops_for_go=require_ops_for_go,
        git_commit=git_commit,
        policy_id=decision_policy or "field_ops",
        reliability_gate=gate,
        # Incident default: fusion OFF until U1 human promote
        allow_ml_live_in_fusion=False,
        extra_metrics={
            "product": "incident_runtime_v1",
            "outbox": str(outbox.resolve()),
            "n_frames": n_frames,
            "reliability_gate_path": str(gate) if isinstance(gate, (str, Path)) else None,
            "ml_prediction_present": ml_live_m is not None,
        },
    )
    payload = card.to_dict()
    json_path = outbox / DECISION_CARD_FILENAME
    md_path = outbox / DECISION_CARD_MD_FILENAME
    tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(json_path)
    md_path.write_text(render_decision_card_md(payload), encoding="utf-8")

    # Preserve / re-emit live ML prediction for decide --ml-prediction path.
    if ml_live_m is not None:
        try:
            ml_pred_path = outbox / "ml_prediction.json"
            if not ml_pred_path.is_file():
                live_doc = {
                    "schema": "ml_prediction_v1",
                    "product_id": ml_live_m.get("product_id"),
                    "abstain": ml_live_m.get("abstain"),
                    "confidence": ml_live_m.get("confidence"),
                    "diagnostics": {
                        "mean_entropy": ml_live_m.get("mean_entropy"),
                        "member_disagreement": ml_live_m.get("member_disagreement"),
                        "mean_margin": ml_live_m.get("mean_margin"),
                        "n_members": ml_live_m.get("n_members"),
                    },
                    "ml_live_metrics": ml_live_m,
                }
                ml_pred_path.write_text(
                    json.dumps(live_doc, indent=2, default=str), encoding="utf-8"
                )
        except OSError:
            pass

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

    # Recompute pack from staged images (full or incremental last-pair)
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

    # Incremental: when only new frames arrived on a prior successful run, feed
    # last-pair subset of staged images rather than re-ingesting every frame.
    # Full reprocess on force / first update / missing prior ops / config error.
    images_dir = config.stage_images
    ingest_masks = masks_arg
    incremental = False
    ops_path = config.outbox / "operational_metrics.json"
    can_incremental = should_use_incremental_ingest(
        force=force,
        n_new_frames=len(new_frames),
        n_staged=n_staged,
        n_updates=int(state.n_updates or 0),
        has_ops_file=ops_path.is_file(),
        last_error=state.last_error,
    )
    if can_incremental:
        try:
            inc_images, inc_masks = _prepare_incremental_ingest(config, n_keep=2)
            if inc_images is not None:
                images_dir = inc_images
                if inc_masks is not None:
                    ingest_masks = inc_masks
                incremental = True
        except OSError:
            images_dir = config.stage_images
            ingest_masks = masks_arg
            incremental = False

    try:
        metrics = run_geotiff_ingest(
            images_dir,
            ingest_masks,
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
        # Prefer ops already returned in-memory; fall back to disk only if thin.
        if not (isinstance(ops, dict) and ops.get("quality_grade") is not None):
            if ops_path.is_file():
                full_ops = json.loads(ops_path.read_text(encoding="utf-8"))
                ops = full_ops
        elif ops_path.is_file():
            # Merge any extra disk fields not present in the in-memory dict.
            try:
                disk_ops = json.loads(ops_path.read_text(encoding="utf-8"))
                if isinstance(disk_ops, dict):
                    merged = dict(disk_ops)
                    merged.update(ops)
                    ops = merged
            except (OSError, json.JSONDecodeError):
                pass

        decision_artifacts: dict[str, Any] = {}
        if isinstance(ops, dict) and ops:
            # Preload open/ml once for this tick (decision card + this-run gate).
            ml_pre = _load_ml_metrics_optional() if config.include_ml_metrics else None
            open_pre = _load_open_metrics(config.open_pack_dir)
            decision_artifacts = publish_decision_card(
                config.outbox,
                config.event_id,
                ops,
                n_frames=n_staged,
                open_pack_dir=config.open_pack_dir,
                include_ml_metrics=config.include_ml_metrics,
                require_ops_for_go=config.require_ops_for_go,
                decision_policy=config.decision_policy or "field_ops",
                ml_metrics=ml_pre,
                open_metrics=open_pre,
            )
            decision_artifacts["ingest_mode"] = "incremental_last_pair" if incremental else "full"

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
