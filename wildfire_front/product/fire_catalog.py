"""Discover incident work-dirs and demo packs for the product SPA fire picker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wildfire_front.product.plain_language import enrich_actions, enrich_intake_steps

_OUTBOX_MARKERS = (
    "main_front.geojson",
    "fronts.geojson",
    "fronts_wgs84.geojson",
    "fire_decision_card.json",
    "operational_metrics.json",
    "summary.json",
    "incident_state.json",
    "emergency_envelope_guidance.geojson",
)

# Known offline demo packs (relative to repo root)
_KNOWN_PACKS: tuple[tuple[str, str, str], ...] = (
    ("demo_v2", "outputs/demo_v2", "Demo sintético (fronts.geojson)"),
    ("demo_cli_smoke", "outputs/demo_cli_smoke", "Demo CLI smoke"),
    ("demo_third_party", "outputs/demo_third_party", "Pack third-party demo"),
    ("brazatortas_2025", "outputs/observatorio/brazatortas_2025", "Observatorio Brazatortas"),
    ("tobarra_ops", "outputs/fuel_stack/tobarra", "Tobarra fuel/envelope stack"),
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _has_any(folder: Path, names: tuple[str, ...]) -> bool:
    return any((folder / n).is_file() for n in names)


def _inspect_work_dir(path: Path, *, kind: str, label: str | None = None) -> dict[str, Any] | None:
    if not path.is_dir():
        return None
    outbox = path / "outbox"
    root = path
    search_roots = [outbox, root] if outbox.is_dir() else [root]
    has_geo = False
    has_card = False
    has_ops = False
    event_id = None
    decision = None
    for r in search_roots:
        if _has_any(r, ("main_front.geojson", "fronts.geojson", "fronts_wgs84.geojson", "emergency_envelope_guidance.geojson")):
            has_geo = True
        card = _load_json(r / "fire_decision_card.json")
        if card:
            has_card = True
            event_id = event_id or card.get("event_id")
            decision = decision or card.get("decision")
        ops = _load_json(r / "operational_metrics.json")
        if ops:
            has_ops = True
        summary = _load_json(r / "summary.json") or _load_json(r / "incident_state.json")
        if summary:
            event_id = event_id or summary.get("event_id") or summary.get("event")
    # demo packs without outbox: fronts at root
    if not has_geo and (path / "fronts.geojson").is_file():
        has_geo = True
    if not (has_geo or has_card or has_ops or outbox.is_dir()):
        return None
    fid = path.name
    return {
        "id": fid,
        "label": label or fid,
        "kind": kind,
        "work_dir": str(path.resolve()),
        "work_dir_rel": _rel_to_repo(path),
        "has_outbox": outbox.is_dir(),
        "has_geojson": has_geo,
        "has_decision_card": has_card,
        "has_ops_metrics": has_ops,
        "event_id": event_id,
        "decision": str(decision).upper() if decision else None,
        "rebuild_cmd": f'python -m wildfire_front app --work-dir "{_rel_to_repo(path)}" --open',
        "map_cmd": f'python -m wildfire_front map --work-dir "{_rel_to_repo(path)}" --no-live --open',
        "status_cmd": f'python -m wildfire_front incident status --work-dir "{_rel_to_repo(path)}"',
        "decide_cmd": f'python -m wildfire_front decide --policy field_ops --work-dir "{_rel_to_repo(path)}" --explain',
        "acta_cmd": f'python -m wildfire_front export-acta --work-dir "{_rel_to_repo(path)}"',
    }


def _rel_to_repo(path: Path) -> str:
    try:
        # best-effort relative path from cwd
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def scan_fire_catalog(
    repo: Path | str | None = None,
    *,
    incidents_glob: str = "outputs/incidents",
    include_known_packs: bool = True,
    max_fires: int = 40,
) -> list[dict[str, Any]]:
    """Scan incident work-dirs + optional demo packs for the SPA fire picker."""
    root = Path(repo) if repo is not None else Path.cwd()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(entry: dict[str, Any] | None) -> None:
        if not entry:
            return
        key = str(Path(entry["work_dir"]).resolve())
        if key in seen:
            return
        seen.add(key)
        found.append(entry)

    inc_root = root / incidents_glob
    if inc_root.is_dir():
        for child in sorted(inc_root.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            # skip pure temp noise unless it has markers
            _add(_inspect_work_dir(child, kind="incident"))

    if include_known_packs:
        for pid, rel, label in _KNOWN_PACKS:
            p = root / rel
            entry = _inspect_work_dir(p, kind="pack", label=label)
            if entry:
                entry["id"] = pid
                entry["label"] = label
                _add(entry)

    # sort: incidents with geo/card first
    def _score(e: dict[str, Any]) -> tuple:
        return (
            0 if e.get("has_geojson") else 1,
            0 if e.get("has_decision_card") else 1,
            e.get("kind") != "incident",
            str(e.get("id") or ""),
        )

    found.sort(key=_score)
    return found[: max(1, int(max_fires))]


def product_action_catalog() -> list[dict[str, Any]]:
    """All major product capabilities as CTAs with plain-language layer.

    Each row has title/why/cmd plus plain, for_fire, simple_cta (modo simple).
    """
    raw = [
        {
            "id": "app",
            "group": "Consola",
            "title": "Abrir / regenerar consola",
            "cmd": "python -m wildfire_front app --work-dir DIR --open",
            "why": "SPA mapa + brief + decisión",
        },
        {
            "id": "list_fires",
            "group": "Consola",
            "title": "Listar incendios descubiertos",
            "cmd": "python -m wildfire_front app --list-fires",
            "why": "Catálogo outputs/incidents + packs",
        },
        {
            "id": "map",
            "group": "Mapa",
            "title": "Mapa estado (local)",
            "cmd": "python -m wildfire_front map --work-dir DIR --no-live --open",
            "why": "Solo capas outbox",
        },
        {
            "id": "map_live",
            "group": "Mapa",
            "title": "Mapa + FIRMS NRT (red)",
            "cmd": "python -m wildfire_front map --lat 40.9 --lon -3.1 --radius-km 40 --output outputs/maps/live",
            "why": "Hotspots satélite (≠ perímetro)",
        },
        {
            "id": "brief",
            "group": "Operario",
            "title": "Brief profesional",
            "cmd": "python -m wildfire_front brief --role operator",
            "why": "Gates + next action",
        },
        {
            "id": "operator",
            "group": "Operario",
            "title": "Tablero 4 actos",
            "cmd": "python -m wildfire_front operator",
            "why": "Semáforo GO_Q",
        },
        {
            "id": "ensayo",
            "group": "Operario",
            "title": "Ensayo 4 actos",
            "cmd": "python -m wildfire_front ensayo",
            "why": "do --all",
        },
        {
            "id": "operator_next",
            "group": "Operario",
            "title": "Qué falta para GO_Q",
            "cmd": "python -m wildfire_front next",
            "why": "Solo humano: demo tercero + acta",
        },
        {
            "id": "operator_checklist",
            "group": "Operario",
            "title": "Checklist operario",
            "cmd": "python -m wildfire_front checklist",
            "why": "7 ítems de dominio",
        },
        {
            "id": "explain_abstain",
            "group": "Operario",
            "title": "Por qué se calla (ABSTAIN)",
            "cmd": "python -m wildfire_front operator explain-abstain",
            "why": "ABSTAIN ≠ bug",
        },
        {
            "id": "commands",
            "group": "Consola",
            "title": "Mapa de comandos",
            "cmd": "python -m wildfire_front help",
            "why": "Inventario CLI por rol",
        },
        {
            "id": "incident_hub",
            "group": "Campo",
            "title": "Hub incident",
            "cmd": "python -m wildfire_front incident",
            "why": "doctor / update / watch / status",
        },
        {
            "id": "incident_status",
            "group": "Campo",
            "title": "Status outbox",
            "cmd": "python -m wildfire_front incident status --work-dir DIR",
            "why": "Leer productos del incendio",
        },
        {
            "id": "incident_update",
            "group": "Campo",
            "title": "Procesar inbox → outbox",
            "cmd": "python -m wildfire_front incident update --inbox INBOX --work-dir DIR --force",
            "why": "Cargar frames nuevos",
        },
        {
            "id": "incident_watch",
            "group": "Campo",
            "title": "Vigilancia en bucle",
            "cmd": "python -m wildfire_front incident watch --inbox INBOX --work-dir DIR",
            "why": "Loop cuando llegan frames",
        },
        {
            "id": "doctor_field",
            "group": "Campo",
            "title": "Doctor drop-zone",
            "cmd": "python -m wildfire_front doctor --inbox INBOX",
            "why": "Pre-flight timestamps/CRS",
        },
        {
            "id": "decide",
            "group": "Decisión",
            "title": "Decision Card field_ops",
            "cmd": "python -m wildfire_front decide --policy field_ops --work-dir DIR --explain",
            "why": "GO/HOLD/ABSTAIN",
        },
        {
            "id": "export_acta",
            "group": "Decisión",
            "title": "Exportar acta forense",
            "cmd": "python -m wildfire_front export-acta --work-dir DIR",
            "why": "Acta + radio + replay sources",
        },
        {
            "id": "replay",
            "group": "Decisión",
            "title": "Replay forense",
            "cmd": "python -m wildfire_front replay-decide --work-dir DIR",
            "why": "Verificar hashes",
        },
        {
            "id": "serve_decide",
            "group": "Decisión",
            "title": "API local decide",
            "cmd": "python -m wildfire_front serve-decide --port 8765",
            "why": "POST /v1/decide en local",
        },
        {
            "id": "multihorizon",
            "group": "Ops ROS",
            "title": "Multihorizon 1–24 h",
            "cmd": "python -m wildfire_front multihorizon --ros-m-min 5.71 --method hybrid --geojson outputs/maps/mh.geojson",
            "why": "Anillos field_ops (no ML IoU)",
        },
        {
            "id": "ml",
            "group": "ML lab",
            "title": "Hub ML lab",
            "cmd": "python -m wildfire_front ml",
            "why": "Lab ≠ field fusion · IoU ≠ ROS",
        },
        {
            "id": "ml_list",
            "group": "ML lab",
            "title": "Catálogo de modelos",
            "cmd": "python -m wildfire_front ml list",
            "why": "Productos / pesos",
        },
        {
            "id": "ml_show",
            "group": "ML lab",
            "title": "Scorecard lab",
            "cmd": "python -m wildfire_front ml show",
            "why": "Offline rails",
        },
        {
            "id": "ml_doctor",
            "group": "ML lab",
            "title": "Doctor ML",
            "cmd": "python -m wildfire_front ml doctor",
            "why": "Weights / catálogo / rails",
        },
        {
            "id": "ml_predict",
            "group": "ML lab",
            "title": "Predict lab",
            "cmd": "python -m wildfire_front ml predict --list-products",
            "why": "Inferencia lab (no despacho)",
        },
        {
            "id": "ml_card",
            "group": "ML lab",
            "title": "Card offline demo",
            "cmd": "python -m wildfire_front ml card --mode offline --scenario hold",
            "why": "Demo card sin red",
        },
        {
            "id": "ml_cases",
            "group": "ML lab",
            "title": "Casos de enseñanza",
            "cmd": "python -m wildfire_front ml cases",
            "why": "Teaching surface",
        },
        {
            "id": "ml_loop",
            "group": "ML lab",
            "title": "Bucle lab (curve/freeze/…)",
            "cmd": "python -m wildfire_front ml next",
            "why": "Investigación continua (no GO_Q)",
        },
        {
            "id": "ingest",
            "group": "Nuevo incendio",
            "title": "Ingest GeoTIFF batch",
            "cmd": "python -m wildfire_front ingest-geotiff --images IMG --masks MASKS --sensor-id lwir_drone --estimated-error-m 2 --event-id EVENT --output DIR --operational",
            "why": "Crear productos térmicos",
        },
        {
            "id": "demo",
            "group": "Nuevo incendio",
            "title": "Demo sintético",
            "cmd": "python -m wildfire_front demo --output outputs/demo_new",
            "why": "Generar incendio de prueba",
        },
        {
            "id": "teach",
            "group": "Eng",
            "title": "Teach (4 actos docs)",
            "cmd": "python -m wildfire_front teach",
            "why": "Guion de enseñanza",
        },
        {
            "id": "show",
            "group": "Eng",
            "title": "Show gates",
            "cmd": "python -m wildfire_front show",
            "why": "Snapshot GO_MES / GO_Q / fusión",
        },
        {
            "id": "demo_third_party",
            "group": "Eng",
            "title": "Pack third-party",
            "cmd": "python -m wildfire_front demo-third-party",
            "why": "Pack demo terceros",
        },
        {
            "id": "dry_run_h3",
            "group": "Eng",
            "title": "Dry-run H3",
            "cmd": "python -m wildfire_front dry-run-h3",
            "why": "Camino eng teach→pack",
        },
    ]
    return enrich_actions(raw)


def new_fire_intake_steps() -> list[dict[str, Any]]:
    """Step-by-step path to load a new fire into the console (with plain layer)."""
    raw = [
        {
            "step": "1",
            "title": "Preparar carpeta del incendio",
            "detail": "Crea outputs/incidents/MI_IF/ y un inbox con GeoTIFF + máscaras (timestamps en nombre).",
            "cmd": "mkdir outputs\\incidents\\MI_IF\\inbox",
        },
        {
            "step": "2",
            "title": "Pre-flight doctor",
            "detail": "Valida CRS, timestamps y máscaras antes de procesar.",
            "cmd": "python -m wildfire_front doctor --inbox outputs/incidents/MI_IF/inbox",
        },
        {
            "step": "3",
            "title": "Procesar → outbox",
            "detail": "Una pasada update escribe frentes / envelope / métricas.",
            "cmd": "python -m wildfire_front incident update --inbox outputs/incidents/MI_IF/inbox --work-dir outputs/incidents/MI_IF --force",
        },
        {
            "step": "4",
            "title": "Decision Card",
            "detail": "Política field_ops (ABSTAIN es válido si faltan fuentes).",
            "cmd": "python -m wildfire_front decide --policy field_ops --work-dir outputs/incidents/MI_IF --explain",
        },
        {
            "step": "5",
            "title": "Abrir consola en ese incendio",
            "detail": "Regenera la SPA con mapa + brief + card.",
            "cmd": "python -m wildfire_front app --work-dir outputs/incidents/MI_IF --open",
        },
        {
            "step": "6",
            "title": "Atajo demo sintético",
            "detail": "Si no tienes GeoTIFF reales, genera un incendio sintético y ábrelo.",
            "cmd": "python -m wildfire_front demo --output outputs/demo_new ; python -m wildfire_front app --work-dir outputs/demo_new --open",
        },
    ]
    return enrich_intake_steps(raw)
