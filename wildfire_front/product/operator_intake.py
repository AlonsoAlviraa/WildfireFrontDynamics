"""Simple photo/data intake for a non-technical command-post operator.

Three acts: open the folder, drop GeoTIFFs, process. Spanish messages.
Never invents ROS / GO_Q. JPG from a phone is rejected with a plain reason.
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wildfire_front.product.path_sandbox import PathNotAllowedError, is_under, realpath

TIFF_EXTENSIONS = {".tif", ".tiff"}

INTAKE_SCHEMA = "wfd_operator_intake_v1"
INCIDENTS_REL = Path("outputs") / "incidents"
MAX_UPLOAD_FILES = 8
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


def sanitize_fire_id(name: str | None) -> str:
    raw = _SAFE_ID.sub("_", str(name or "").strip())
    raw = raw.strip("._-")[:40]
    return raw or "nuevo_incendio"


def inbox_of(work_dir: Path) -> Path:
    return Path(work_dir) / "inbox"


def _list_tiffs(inbox: Path) -> list[Path]:
    from wildfire_front.incident.pipeline import list_inbox_tiffs

    return list_inbox_tiffs(inbox)


def _infer_ts(path: Path) -> str:
    from wildfire_front.ingestion.geotiff import infer_timestamp

    return infer_timestamp(path)


def spanish_doctor_line(check: dict[str, Any]) -> str:
    cid = str(check.get("id") or "")
    level = str(check.get("level") or "")
    if cid == "inbox_exists" and level == "pass":
        return "La carpeta de fotos está lista."
    if cid == "inbox_exists":
        return "No encuentro la carpeta de fotos."
    if cid == "inbox_has_tiffs" and level == "pass":
        return str(check.get("message") or "Hay fotos térmicas.")
    if cid == "inbox_has_tiffs":
        return "Aún no hay fotos .tif en la carpeta."
    if cid == "timestamps" and level == "pass":
        return "Las fotos tienen fecha en el nombre. Bien."
    if cid == "timestamps" and level == "fail":
        return (
            "Las fotos no tienen fecha en el nombre. "
            "Renómbralas así: 20260817_153000_frente.tif"
        )
    if cid == "timestamps":
        return "Algunas fotos no tienen fecha en el nombre y el sistema las ignorará."
    return str(check.get("message") or cid)


def intake_guide(*, work_dir: Path | None = None, fire_id: str | None = None) -> dict[str, Any]:
    """Payload for the Meter fotos tab (always Spanish, cmds only for Pro)."""
    wd = Path(work_dir) if work_dir else None
    inbox = inbox_of(wd) if wd else None
    files = _list_tiffs(inbox) if inbox and inbox.is_dir() else []
    return {
        "schema": INTAKE_SCHEMA,
        "fire_id": fire_id or (wd.name if wd else "nuevo_incendio"),
        "inbox": str(inbox) if inbox else None,
        "n_photos": len(files),
        "photos": [p.name for p in files[:20]],
        "need_geotiff": True,
        "jpg_not_enough": True,
        "not_tactical_dispatch": True,
        "steps": [
            {
                "n": 1,
                "title": "Abre la carpeta",
                "plain": "Pulsa el botón. Se abre una carpeta de Windows. Ahí van las fotos.",
            },
            {
                "n": 2,
                "title": "Suelta las fotos térmicas",
                "plain": (
                    "Solo valen fotos térmicas con mapa (.tif o .tiff). "
                    "Un JPG o una foto del móvil no sirve."
                ),
            },
            {
                "n": 3,
                "title": "Pulsa Procesar",
                "plain": "El sistema lee las fotos y actualiza la palabra grande. No es una orden de extinción.",
            },
        ],
        "name_hint": "Pon la fecha en el nombre: 20260817_153000_frente.tif",
        "cmd_open": (
            f'explorer "{inbox}"' if inbox else "explorer outputs\\incidents\\MI_IF\\inbox"
        ),
        "cmd_process": (
            "python -m wildfire_front incident update --inbox DIR/inbox --work-dir DIR --force"
        ),
        "cmd_app": "python -m wildfire_front app --work-dir DIR --serve",
    }


def need_to_know(
    *,
    card: dict[str, Any] | None,
    ops: dict[str, Any] | None,
    snapshot: dict[str, Any] | None = None,
    inbox_n: int | None = None,
) -> dict[str, Any]:
    """Three lines a commander can read without training."""
    have: list[str] = []
    missing: list[str] = []
    cited = (snapshot or {}).get("cited") or {}
    ros = cited.get("ros_m_min")
    if ros is None and isinstance(ops, dict):
        ros = ops.get("primary_ros_m_min")
        if ros is None:
            ros = ops.get("speed_median_m_min")
    ha = cited.get("area_ha")
    if ha is None and isinstance(ops, dict):
        ha = ops.get("area_ha_max")
        if ha is None:
            ha = ops.get("area_ha_last")
    grade = cited.get("quality_grade") or ((ops or {}).get("quality_grade") if ops else None)
    if inbox_n:
        have.append(f"{inbox_n} foto(s) en la carpeta")
    if ros is not None:
        have.append(f"velocidad citada {ros} m/min")
    else:
        missing.append("velocidad del frente (hace falta más de una foto con fecha)")
    if ha is not None:
        have.append(f"área citada {ha} ha")
    if grade:
        have.append(f"calidad de las fotos {grade}")
    srcs = (card or {}).get("sources") or []
    miss_ids = [
        str(s.get("id") or "")
        for s in srcs
        if isinstance(s, dict) and s.get("available") is False
    ]
    if any("cems" in i or "open" in i for i in miss_ids):
        missing.append("perímetro de Copernicus (el satélite oficial)")
    if any("ml" in i for i in miss_ids):
        missing.append("predicción de laboratorio (no es la velocidad)")
    dec = str((card or {}).get("decision") or "").upper()
    if dec == "GO":
        action = "Hay una lectura. No lances medios solo por esta pantalla."
        if missing:
            action = "Hay lectura, pero faltan datos. Trátalo como espera. No lances medios."
    elif dec == "HOLD":
        action = "Espera y revisa. Los datos no bastan o chocan."
    elif dec == "ABSTAIN":
        action = "El sistema se calla a propósito. Mete más fotos o revisa las fechas."
    else:
        action = "Mete las fotos en Meter fotos y pulsa Procesar. Luego lee la palabra grande."
    return {
        "have": have or ["Todavía no hay cifras de este incendio."],
        "missing": missing or ["Nada grave apuntado."],
        "action": action,
        "decision": dec or None,
        "not_tactical_dispatch": True,
    }


def ensure_named_work_dir(name: str, *, base: Path) -> Path:
    """Create outputs/incidents/<id>/{inbox} under base. Fail closed outside."""
    safe = sanitize_fire_id(name)
    rel = INCIDENTS_REL / safe
    root = Path(realpath(base))
    target = (root / rel).resolve()
    incidents_root = (root / INCIDENTS_REL).resolve()
    incidents_root.mkdir(parents=True, exist_ok=True)
    if not is_under(str(target), str(incidents_root)):
        raise PathNotAllowedError("fire id escapes incidents root")
    target.mkdir(parents=True, exist_ok=True)
    (target / "inbox").mkdir(exist_ok=True)
    (target / "outbox").mkdir(exist_ok=True)
    return target


def intake_status(work_dir: Path, *, fire_id: str | None = None) -> dict[str, Any]:
    wd = Path(work_dir)
    inbox = inbox_of(wd)
    inbox.mkdir(parents=True, exist_ok=True)
    from wildfire_front.incident.doctor import doctor_incident

    files = _list_tiffs(inbox)
    other = []
    if inbox.is_dir():
        other = [
            p.name
            for p in inbox.iterdir()
            if p.is_file() and p.suffix.lower() not in TIFF_EXTENSIONS and not p.name.startswith(".")
        ]
    doctor = doctor_incident(inbox=inbox, work_dir=wd, event_id=fire_id or wd.name)
    checks = [spanish_doctor_line(c) for c in (doctor.get("checks") or [])[:8]]
    n_ts = sum(1 for p in files if _infer_ts(p))
    return {
        "schema": INTAKE_SCHEMA,
        "ok": True,
        "act": "intake_status",
        "fire_id": fire_id or wd.name,
        "work_dir": str(wd),
        "inbox": str(inbox),
        "n_photos": len(files),
        "n_with_date": n_ts,
        "photos": [{"name": p.name, "has_date": bool(_infer_ts(p))} for p in files[:30]],
        "rejected_not_tif": other[:12],
        "checks": checks,
        "jpg_not_enough": bool(other),
        "ready": bool(files) and n_ts > 0,
        "go_q_met": False,
        "hint": (
            "Listo para Procesar."
            if files and n_ts
            else (
                "Hay archivos que no son .tif — el sistema no los usará."
                if other and not files
                else "Suelta fotos .tif con fecha en el nombre."
            )
        ),
        "not_tactical_dispatch": True,
    }


def open_inbox(work_dir: Path) -> dict[str, Any]:
    inbox = inbox_of(work_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    opened = False
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", str(inbox)], close_fds=True)
            opened = True
        else:
            subprocess.Popen(["xdg-open", str(inbox)], close_fds=True)
            opened = True
    except OSError:
        opened = False
    return {
        "schema": INTAKE_SCHEMA,
        "ok": True,
        "act": "intake_open",
        "opened": opened,
        "inbox": str(inbox),
        "hint": (
            "Carpeta abierta. Suelta ahí las fotos .tif."
            if opened
            else f"Abre esta carpeta a mano: {inbox}"
        ),
        "not_tactical_dispatch": True,
    }


def _safe_filename(name: str) -> str:
    base = Path(str(name or "foto.tif")).name
    base = base.replace("..", "").replace("/", "").replace("\\", "")
    if Path(base).suffix.lower() not in TIFF_EXTENSIONS:
        raise ValueError("not_tif")
    return base


def stamp_if_needed(name: str) -> str:
    probe = Path(name)
    if _infer_ts(probe):
        return name
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{probe.name}"


def receive_files(
    work_dir: Path,
    files: list[dict[str, Any]],
    *,
    stamp_missing: bool = True,
) -> dict[str, Any]:
    inbox = inbox_of(work_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    rejected: list[dict[str, str]] = []
    for item in (files or [])[:MAX_UPLOAD_FILES]:
        raw_name = str(item.get("name") or "foto.tif")
        try:
            fname = _safe_filename(raw_name)
        except ValueError:
            rejected.append(
                {
                    "name": raw_name,
                    "why": "Un JPG o PNG del móvil no sirve. Hace falta .tif térmico con mapa.",
                }
            )
            continue
        if stamp_missing:
            fname = stamp_if_needed(fname)
        b64 = str(item.get("content_b64") or item.get("b64") or "")
        if not b64:
            rejected.append({"name": fname, "why": "archivo vacío"})
            continue
        try:
            blob = base64.b64decode(b64, validate=False)
        except (ValueError, TypeError):
            rejected.append({"name": fname, "why": "no se pudo leer el archivo"})
            continue
        if len(blob) > MAX_UPLOAD_BYTES:
            rejected.append({"name": fname, "why": "demasiado grande (máx. 16 MB)"})
            continue
        if len(blob) < 8:
            rejected.append({"name": fname, "why": "archivo vacío"})
            continue
        dest = inbox / fname
        dest.write_bytes(blob)
        saved.append(fname)
    status = intake_status(work_dir)
    status["act"] = "intake_upload"
    status["saved"] = saved
    status["rejected"] = rejected
    status["ok"] = bool(saved) or not files
    status["hint"] = (
        f"Guardadas {len(saved)} foto(s). Pulsa Procesar."
        if saved
        else (rejected[0]["why"] if rejected else status.get("hint"))
    )
    return status


def process_intake(
    work_dir: Path,
    *,
    fire_id: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Doctor + one inbox pass + Decision Card. Never invents GO_Q."""
    from wildfire_front.incident.pipeline import IncidentConfig, process_incident_once
    from wildfire_front.product.decide_service import decide_from_request

    wd = Path(work_dir)
    event_id = fire_id or wd.name
    inbox = inbox_of(wd)
    inbox.mkdir(parents=True, exist_ok=True)
    status = intake_status(wd, fire_id=event_id)
    if not status["n_photos"]:
        return {
            **status,
            "ok": False,
            "act": "intake_process",
            "processed": False,
            "hint": "No hay fotos .tif. Abre la carpeta, suéltalas y vuelve a pulsar Procesar.",
            "go_q_met": False,
            "not_tactical_dispatch": True,
        }
    cfg = IncidentConfig(
        event_id=event_id,
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=wd,
        min_file_age_s=0.0,
        decision_policy="field_ops",
    )
    try:
        summary = process_incident_once(cfg, force=True)
    except Exception as exc:  # noqa: BLE001 — operator surface, fail closed
        return {
            **status,
            "ok": False,
            "act": "intake_process",
            "processed": False,
            "hint": "No pude leer esas fotos. Tienen que ser térmicas con mapa (.tif), no un JPG.",
            "detail": str(exc)[:200],
            "go_q_met": False,
            "not_tactical_dispatch": True,
        }
    req = {
        "channel": "live_ops_loopback",
        "policy_id": "field_ops",
        "work_dir": str(wd),
        "event_id": event_id,
        "require_ops_for_go": True,
        "use_ml_v34": False,
        "allow_ml_live_in_fusion": False,
        "ml_live_trusted": False,
    }
    try:
        card = decide_from_request(req, base=base)
    except Exception as exc:  # noqa: BLE001 — operator surface, fail closed
        return {
            **status,
            "ok": False,
            "act": "intake_process",
            "processed": True,
            "update": {
                "status": summary.get("status"),
                "new_frames": summary.get("new_frames"),
                "n_staged": summary.get("n_staged"),
            },
            "hint": "Las fotos se leyeron, pero no pude hacer la tarjeta. Prueba Decidir.",
            "detail": str(exc)[:200],
            "go_q_met": False,
            "not_tactical_dispatch": True,
        }
    dec = str(card.get("decision") or "ABSTAIN").upper()
    word = {"GO": "SEGUIR", "HOLD": "ESPERAR", "ABSTAIN": "SE CALLA"}.get(dec, dec)
    return {
        "schema": INTAKE_SCHEMA,
        "ok": True,
        "act": "intake_process",
        "processed": True,
        "fire_id": event_id,
        "work_dir": str(wd),
        "inbox": str(inbox),
        "n_photos": status["n_photos"],
        "update": {
            "status": summary.get("status"),
            "new_frames": summary.get("new_frames"),
            "n_staged": summary.get("n_frames") or summary.get("n_staged"),
        },
        "decision": dec,
        "word": word,
        "confidence_pred": card.get("confidence_pred"),
        "card": {
            "decision": card.get("decision"),
            "confidence_pred": card.get("confidence_pred"),
            "event_id": card.get("event_id"),
            "system_reliability_pass": card.get("system_reliability_pass"),
            "sources": card.get("sources"),
            "reasons": (card.get("reasons") or [])[:4],
        },
        "hint": (
            f"Listo. La lectura es {word}. No es una orden de despacho."
        ),
        "go_q_met": False,
        "not_tactical_dispatch": True,
    }
