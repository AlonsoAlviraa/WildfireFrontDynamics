"""Plain-language layer for the product SPA (modo simple).

Maps every major CLI command and product surface to:
  · short human title
  · one-line plain explanation
  · what it does *for a fire* (operator value)

Also holds the operator glossary (GO/HOLD/ABSTAIN, ROS, FIRMS, gates…).

Honesty rails (do not dilute in copy):
  · not tactical dispatch
  · field_ops ML fusion OFF
  · ABSTAIN is a product feature
  · IoU ≠ ROS · NRT hotspot ≠ burned area / official perimeter
"""

from __future__ import annotations

from typing import Any

SCHEMA = "wfd_plain_language_v1"

# ── Glossary (UI + payload) ──────────────────────────────────────────────────

GLOSSARY: list[dict[str, str]] = [
    {
        "id": "go",
        "term": "GO",
        "plain": "El sistema se atreve a proponer una orientación operativa con las fuentes actuales.",
        "for_fire": "Hay señal suficiente para mirar el incendio con una propuesta (no es una orden de extinción).",
    },
    {
        "id": "hold",
        "term": "HOLD",
        "plain": "Hay datos, pero no bastan o chocan entre sí: espera / revisa antes de actuar.",
        "for_fire": "No lances recursos solo por esta tarjeta; el fuego puede estar mal cubierto o en duda.",
    },
    {
        "id": "abstain",
        "term": "ABSTAIN",
        "plain": "El sistema se calla a propósito: callarse es correcto cuando faltan fuentes fiables.",
        "for_fire": "No inventa un perímetro ni una velocidad del fuego. ABSTAIN no es un fallo del software.",
    },
    {
        "id": "ros",
        "term": "ROS (velocidad de propagación)",
        "plain": "Metros por minuto que avanza el frente observado en las imágenes térmicas.",
        "for_fire": "Te dice si el frente va rápido o lento en el tramo medido — no es un pronóstico de IoU de ML.",
    },
    {
        "id": "front",
        "term": "Frente",
        "plain": "Línea del borde del fuego reconstruida a partir de máscaras térmicas en el tiempo.",
        "for_fire": "Dónde estaba el borde activo en cada instante (observado, no oficial de extinción).",
    },
    {
        "id": "envelope",
        "term": "Envelope (envolvente)",
        "plain": "Zona de orientación a 15/30/60 min extrapolando el ROS observado.",
        "for_fire": "Una guía de hacia dónde podría crecer el frente si se mantiene el ritmo — no es un perímetro oficial.",
    },
    {
        "id": "firms",
        "term": "FIRMS NRT",
        "plain": "Puntos calientes satélite casi en tiempo real (NASA/NOAA).",
        "for_fire": "Marcan posibles focos; no son el área quemada ni el perímetro de extinción (latencia y falsos positivos).",
    },
    {
        "id": "decision_card",
        "term": "Decision Card",
        "plain": "Tarjeta GO / HOLD / ABSTAIN con fuentes, pesos y razones auditables.",
        "for_fire": "Resume si el sistema se atreve a orientar sobre este incendio y por qué (o por qué se calla).",
    },
    {
        "id": "outbox",
        "term": "Outbox",
        "plain": "Carpeta de productos ya generados del incendio (frentes, métricas, card).",
        "for_fire": "Lo que la consola y el mapa leen para mostrarte el estado del IF.",
    },
    {
        "id": "inbox",
        "term": "Inbox",
        "plain": "Carpeta de entrada: GeoTIFF / máscaras nuevas aún sin procesar.",
        "for_fire": "Donde dejas las fotos térmicas nuevas del incendio antes del update.",
    },
    {
        "id": "go_mes",
        "term": "GO_MES",
        "plain": "Semáforo de producto mínimo del mes (ingeniería + packs base listos).",
        "for_fire": "No es una decisión sobre un incendio concreto: es “¿el producto base está listo?”.",
    },
    {
        "id": "go_q",
        "term": "GO_Q",
        "plain": "Semáforo de calidad comercial: demo con tercero + acta. No se inventa en código.",
        "for_fire": "Para vender/validar el producto hace falta humano externo; más ML no cierra GO_Q.",
    },
    {
        "id": "fusion",
        "term": "Fusión ML en campo",
        "plain": "Mezclar predicción de red neuronal en la decisión de campo. En field_ops está OFF.",
        "for_fire": "La sala no usa IoU de laboratorio como si fuera ROS o perímetro oficial.",
    },
    {
        "id": "iou",
        "term": "IoU",
        "plain": "Métrica de solape de máscaras en el laboratorio ML (calidad de segmentación).",
        "for_fire": "No es la velocidad del fuego ni el área quemada operativa. IoU ≠ ROS.",
    },
    {
        "id": "multihorizon",
        "term": "Multihorizon",
        "plain": "Anillos de orientación a 1 / 3 / 5 / 12 / 24 horas a partir del ROS de campo.",
        "for_fire": "Escenarios de crecimiento del frente en el tiempo (field_ops), no “next-day” de ML.",
    },
    {
        "id": "quality_grade",
        "term": "Grade / calidad ops",
        "plain": "Nota de calidad de la secuencia (frames, intervalos, observabilidad).",
        "for_fire": "Si la nota es mala, confía menos en ROS y envelopes de ese incendio.",
    },
    {
        "id": "work_dir",
        "term": "work-dir",
        "plain": "Carpeta del incendio (incident o pack demo) que la consola está mirando.",
        "for_fire": "Cambia de IF = cambia work-dir y regenera la SPA (es estática, sin servidor).",
    },
    {
        "id": "not_tactical",
        "term": "No despacho táctico",
        "plain": "WFD no ordena medios ni sustituye al mando de extinción.",
        "for_fire": "Apoya la lectura del incendio; la decisión de recursos es humana y oficial.",
    },
]

# ── Feature map: every major CLI / product surface ───────────────────────────
# Keys align with product_action ids, CLI top-level names, and commands-map groups.

FEATURES: list[dict[str, Any]] = [
    # Consola / entry
    {
        "id": "app",
        "cli": "app / spa / console",
        "group": "Consola",
        "title": "Consola ops (SPA)",
        "plain": "Pantalla única: mapa + semáforo + decisión + funciones del producto.",
        "for_fire": "Ves el incendio elegido, su decisión y las herramientas sin pelearte con la CLI.",
        "simple_cta": "Abrir o regenerar la consola de este incendio",
    },
    {
        "id": "list_fires",
        "cli": "app --list-fires",
        "group": "Consola",
        "title": "Listar incendios",
        "plain": "Descubre packs e incidentes ya generados en el repo.",
        "for_fire": "Encuentras el ID del IF para abrirlo en la consola.",
        "simple_cta": "Ver qué incendios hay disponibles",
    },
    {
        "id": "operator",
        "cli": "operator / (sin comando)",
        "group": "Operario",
        "title": "Tablero operario",
        "plain": "Semáforo + 4 actos de demo + qué falta para GO_Q.",
        "for_fire": "Entrada en <30 s: ¿estoy listo para enseñar el producto sobre el fuego?",
        "simple_cta": "Ver el semáforo del producto (4 actos)",
    },
    {
        "id": "brief",
        "cli": "brief / resumen",
        "group": "Operario",
        "title": "Brief de una pantalla",
        "plain": "Resumen profesional: gates, next action y secuencia recomendada.",
        "for_fire": "Qué mirar ahora y qué comando sigue (por rol: operator/field/lab/decision).",
        "simple_cta": "Leer el resumen de estado y la siguiente acción",
    },
    {
        "id": "ensayo",
        "cli": "ensayo / operator do --all",
        "group": "Operario",
        "title": "Ensayo de 4 actos",
        "plain": "Recorre ver → callarse → decidir → probar en un solo pase.",
        "for_fire": "Entrenas el guion de demo del producto sin saltarte el ABSTAIN honesto.",
        "simple_cta": "Practicar la demo completa (4 actos)",
    },
    {
        "id": "operator_next",
        "cli": "next / go_q / operator next",
        "group": "Operario",
        "title": "Qué falta para GO_Q",
        "plain": "Solo humano: demo con tercero + acta. El código no lo cierra.",
        "for_fire": "Saber si el bloqueo es humano (no “falta más ML sobre el IF”).",
        "simple_cta": "Ver qué falta para la calidad comercial",
    },
    {
        "id": "operator_checklist",
        "cli": "checklist / operator checklist",
        "group": "Operario",
        "title": "Checklist operario",
        "plain": "7 ítems de dominio del producto (entrada, semáforo, actos, GO_Q).",
        "for_fire": "Compruebas que sabes manejar la herramienta antes de una demo de incendio.",
        "simple_cta": "Repasar el checklist de dominio",
    },
    {
        "id": "explain_abstain",
        "cli": "operator explain-abstain",
        "group": "Operario",
        "title": "Por qué se calla",
        "plain": "Explica ABSTAIN en lenguaje normal (no es un crash).",
        "for_fire": "Cuando el sistema no propone nada sobre el fuego, entiendes el porqué.",
        "simple_cta": "Entender un ABSTAIN en palabras simples",
    },
    {
        "id": "commands",
        "cli": "commands / help",
        "group": "Consola",
        "title": "Mapa de comandos",
        "plain": "Inventario de CLI agrupado por rol (operario, campo, lab…).",
        "for_fire": "Si necesitas una función concreta del incendio, aquí está el nombre del comando.",
        "simple_cta": "Ver el mapa de todas las funciones (modo avanzado)",
    },
    # Mapa
    {
        "id": "map",
        "cli": "map --work-dir … --no-live",
        "group": "Mapa",
        "title": "Mapa de estado (local)",
        "plain": "Mapa Leaflet solo con capas del outbox (frentes / envelopes).",
        "for_fire": "Dibuja el frente y la envolvente del incendio sin red.",
        "simple_cta": "Ver solo el mapa local del incendio",
    },
    {
        "id": "map_live",
        "cli": "map --lat … --lon …",
        "group": "Mapa",
        "title": "Mapa + FIRMS",
        "plain": "Añade hotspots satélite NRT (necesita red o fixture).",
        "for_fire": "Compara tu frente térmico con focos satélite cercanos (≠ perímetro oficial).",
        "simple_cta": "Añadir focos satélite al mapa (no es el área quemada)",
    },
    # Campo
    {
        "id": "incident_hub",
        "cli": "incident",
        "group": "Campo",
        "title": "Hub de incidente",
        "plain": "Puerta a doctor / update / watch / status del runtime de campo.",
        "for_fire": "Todo el ciclo de vida de un IF en una carpeta de trabajo.",
        "simple_cta": "Entrar al menú de operaciones de campo",
    },
    {
        "id": "incident_status",
        "cli": "incident status --work-dir …",
        "group": "Campo",
        "title": "Estado del outbox",
        "plain": "Lee qué productos hay ya generados para el incendio.",
        "for_fire": "Compruebas frentes, métricas y card sin reabrir archivos a mano.",
        "simple_cta": "¿Qué productos tiene ya este incendio?",
    },
    {
        "id": "incident_update",
        "cli": "incident update --inbox … --work-dir …",
        "group": "Campo",
        "title": "Procesar frames nuevos",
        "plain": "Una pasada: inbox → reconstrucción → outbox (frentes, ROS, envelope).",
        "for_fire": "Actualiza el estado del incendio con las últimas imágenes térmicas.",
        "simple_cta": "Meter fotos nuevas y recalcular el frente",
    },
    {
        "id": "incident_watch",
        "cli": "incident watch --inbox … --work-dir …",
        "group": "Campo",
        "title": "Vigilancia en bucle",
        "plain": "Repite el update cuando llegan frames al inbox.",
        "for_fire": "El IF se actualiza solo mientras caen imágenes nuevas.",
        "simple_cta": "Dejar el incendio actualizándose en vivo",
    },
    {
        "id": "doctor_field",
        "cli": "doctor --inbox … / incident doctor",
        "group": "Campo",
        "title": "Doctor de entrada",
        "plain": "Pre-flight: timestamps, CRS, máscaras antes de procesar.",
        "for_fire": "Evita basura en el outbox del incendio (frames rotos o desordenados).",
        "simple_cta": "Comprobar que las fotos del incendio están bien formadas",
    },
    {
        "id": "ingest",
        "cli": "ingest-geotiff …",
        "group": "Nuevo incendio",
        "title": "Ingestión GeoTIFF",
        "plain": "Batch de imágenes térmicas georreferenciadas → pack de productos.",
        "for_fire": "Crea la primera historia espacial del incendio desde cero.",
        "simple_cta": "Cargar un lote de imágenes del incendio",
    },
    {
        "id": "demo",
        "cli": "demo",
        "group": "Nuevo incendio",
        "title": "Demo sintético",
        "plain": "Genera un incendio de prueba con verdad de terreno.",
        "for_fire": "Pruebas la consola sin datos reales del campo.",
        "simple_cta": "Crear un incendio de juguete para probar",
    },
    # Decisión
    {
        "id": "decide",
        "cli": "decide --policy field_ops --explain",
        "group": "Decisión",
        "title": "Decision Card de campo",
        "plain": "Calcula GO / HOLD / ABSTAIN con rails de silencio de campo.",
        "for_fire": "¿El sistema se atreve a orientar sobre este IF o se calla?",
        "simple_cta": "Pedir la tarjeta de decisión del incendio",
    },
    {
        "id": "export_acta",
        "cli": "export-acta --work-dir …",
        "group": "Decisión",
        "title": "Acta forense",
        "plain": "Markdown de acta + línea radio + fuentes para replay.",
        "for_fire": "Deja rastro auditable de la decisión tomada sobre el incendio.",
        "simple_cta": "Exportar el acta de la decisión",
    },
    {
        "id": "replay",
        "cli": "replay-decide …",
        "group": "Decisión",
        "title": "Replay forense",
        "plain": "Verifica hashes y reproduce la card desde el bundle.",
        "for_fire": "Compruebas que nadie alteró la decisión del IF a posteriori.",
        "simple_cta": "Verificar la integridad de una decisión pasada",
    },
    {
        "id": "serve_decide",
        "cli": "serve-decide --port 8765",
        "group": "Decisión",
        "title": "API local de decisión",
        "plain": "HTTP POST /v1/decide en tu máquina (integraciones).",
        "for_fire": "Otro sistema puede pedir GO/HOLD/ABSTAIN del incendio por red local.",
        "simple_cta": "Abrir el servicio de decisión en local (avanzado)",
    },
    # Ops ROS
    {
        "id": "multihorizon",
        "cli": "multihorizon …",
        "group": "Ops ROS",
        "title": "Multihorizon 1–24 h",
        "plain": "Anillos de orientación a varias horas con ROS de campo (hybrid).",
        "for_fire": "Escenarios de crecimiento del frente a corto-medio plazo (no ML next-day).",
        "simple_cta": "Ver anillos de posible avance del fuego en horas",
    },
    # ML lab
    {
        "id": "ml",
        "cli": "ml",
        "group": "ML lab",
        "title": "Hub laboratorio ML",
        "plain": "Catálogo, scorecard y experimentos. Lab ≠ fusión de campo.",
        "for_fire": "Investiga modelos; no sustituye el ROS observado del incendio en sala.",
        "simple_cta": "Entrar al laboratorio de modelos (no es despacho)",
    },
    {
        "id": "ml_show",
        "cli": "ml show",
        "group": "ML lab",
        "title": "Scorecard lab",
        "plain": "Métricas y rails del producto ML offline.",
        "for_fire": "Transparencia de lo que el lab sabe — no es certeza en vivo del IF.",
        "simple_cta": "Ver el tablón de métricas del laboratorio",
    },
    {
        "id": "ml_list",
        "cli": "ml list",
        "group": "ML lab",
        "title": "Catálogo de modelos",
        "plain": "Productos y pesos disponibles en el lab.",
        "for_fire": "Qué modelos existen; no se fusionan en field_ops por defecto.",
        "simple_cta": "Listar modelos del laboratorio",
    },
    {
        "id": "ml_doctor",
        "cli": "ml doctor / doctor",
        "group": "ML lab",
        "title": "Doctor ML",
        "plain": "Pre-flight de weights, catálogo y rails (offline OK).",
        "for_fire": "Comprueba el lab antes de un predict; no cambia el outbox del IF de campo.",
        "simple_cta": "Comprobar que el laboratorio está sano",
    },
    {
        "id": "ml_predict",
        "cli": "ml predict …",
        "group": "ML lab",
        "title": "Predict lab",
        "plain": "Inferencia de productos listados (weights locales).",
        "for_fire": "Experimento de segmentación; no es orden operativa del incendio.",
        "simple_cta": "Lanzar una predicción de laboratorio",
    },
    {
        "id": "ml_card",
        "cli": "ml card --mode offline",
        "group": "ML lab",
        "title": "Card offline de demo",
        "plain": "Decision Card de escenarios fijos (hold/identity/abstain) sin red.",
        "for_fire": "Enseña la forma de la card sin tocar un IF real.",
        "simple_cta": "Demo de tarjeta de decisión sin red",
    },
    {
        "id": "ml_cases",
        "cli": "ml cases",
        "group": "ML lab",
        "title": "Casos de enseñanza",
        "plain": "Casos didácticos del lab (teaching surface).",
        "for_fire": "Aprender patrones de decisión; no actualiza un incendio de campo.",
        "simple_cta": "Ver casos de enseñanza del lab",
    },
    {
        "id": "ml_loop",
        "cli": "ml curve / freeze / smoke / lofo / next",
        "group": "ML lab",
        "title": "Bucle de laboratorio",
        "plain": "Curvas de riesgo, freeze, smoke, LOFO y next del lab continuo.",
        "for_fire": "Ingeniería de modelos; no cierra GO_Q ni fusión de campo.",
        "simple_cta": "Herramientas del bucle de investigación ML",
    },
    # Eng / teach
    {
        "id": "teach",
        "cli": "teach",
        "group": "Eng",
        "title": "Teach (4 actos docs)",
        "plain": "Guion de enseñanza del producto con comandos y docs.",
        "for_fire": "Preparas la narrativa de demo (incluido un IF de ejemplo).",
        "simple_cta": "Leer el guion de los 4 actos",
    },
    {
        "id": "show",
        "cli": "show",
        "group": "Eng",
        "title": "Show gates",
        "plain": "Snapshot de gates (GO_MES, GO_Q, fusión…) en texto.",
        "for_fire": "Estado de producto, no de un solo perímetro de incendio.",
        "simple_cta": "Ver el estado de los semáforos del producto",
    },
    {
        "id": "demo_third_party",
        "cli": "demo-third-party",
        "group": "Eng",
        "title": "Pack third-party",
        "plain": "Construye el pack de demo para terceros + reportes.",
        "for_fire": "Material de demo reproducible (camino H3 eng).",
        "simple_cta": "Preparar el pack de demo para un tercero",
    },
    {
        "id": "dry_run_h3",
        "cli": "dry-run-h3",
        "group": "Eng",
        "title": "Dry-run H3",
        "plain": "Camino eng teach → show → pack/replay sin inventar GO_Q.",
        "for_fire": "Ensayo técnico de la demo; el cierre humano sigue pendiente.",
        "simple_cta": "Ensayar el camino técnico de demo (H3)",
    },
    # SPA UI surfaces (not always CLI)
    {
        "id": "spa_hero",
        "cli": "(UI) hero",
        "group": "Consola",
        "title": "Semáforo hero",
        "plain": "Palabra grande GO / HOLD / ABSTAIN o BRIEF del incendio activo.",
        "for_fire": "Primera lectura: ¿el sistema habla o se calla sobre este fuego?",
        "simple_cta": "Mirar la decisión grande del incendio",
    },
    {
        "id": "spa_fire_picker",
        "cli": "(UI) selector",
        "group": "Consola",
        "title": "Selector de incendio",
        "plain": "Lista de IF descubiertos; al cambiar hay que regenerar (SPA estática).",
        "for_fire": "Elige qué incendio está “activo” en la consola.",
        "simple_cta": "Elegir otro incendio (luego regenerar)",
    },
    {
        "id": "spa_new_if",
        "cli": "(UI) Nuevo IF",
        "group": "Nuevo incendio",
        "title": "Alta de incendio nuevo",
        "plain": "Pasos guiados: carpeta → doctor → update → decide → app.",
        "for_fire": "Mete un incendio real o sintético en la consola de punta a punta.",
        "simple_cta": "Seguir los pasos para cargar un incendio nuevo",
    },
    {
        "id": "spa_rails",
        "cli": "(UI) rails",
        "group": "Consola",
        "title": "Rails de honestidad",
        "plain": "Chips fijos: fusión OFF, no despacho, IoU≠ROS, no inventar GO_Q.",
        "for_fire": "Recuerda los límites del producto mientras miras el incendio.",
        "simple_cta": "Ver las reglas que el producto no rompe",
    },
    {
        "id": "spa_glossary",
        "cli": "(UI) glosario",
        "group": "Consola",
        "title": "Glosario",
        "plain": "Términos del producto en lenguaje llano.",
        "for_fire": "Si no entiendes GO, ROS o FIRMS, aquí está la traducción.",
        "simple_cta": "Abrir el glosario",
    },
]


def _index_by_id() -> dict[str, dict[str, Any]]:
    return {str(f["id"]): f for f in FEATURES}


def get_feature(feature_id: str) -> dict[str, Any] | None:
    """Return one feature dict or None."""
    return _index_by_id().get(str(feature_id))


def enrich_action(action: dict[str, Any]) -> dict[str, Any]:
    """Merge plain-language fields into a product_action row (non-destructive)."""
    fid = str(action.get("id") or "")
    feat = get_feature(fid) or {}
    out = dict(action)
    if feat:
        out.setdefault("title", feat.get("title"))
        out["plain"] = feat.get("plain") or out.get("why") or ""
        out["for_fire"] = feat.get("for_fire") or ""
        out["simple_cta"] = feat.get("simple_cta") or out.get("title") or fid
        out["cli_label"] = feat.get("cli") or out.get("cmd")
        if not out.get("group") and feat.get("group"):
            out["group"] = feat["group"]
    else:
        out.setdefault("plain", out.get("why") or out.get("title") or "")
        out.setdefault("for_fire", "")
        out.setdefault("simple_cta", out.get("title") or fid)
        out.setdefault("cli_label", out.get("cmd"))
    return out


def enrich_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_action(a) for a in actions]


def enrich_intake_step(step: dict[str, str]) -> dict[str, Any]:
    """Add plain + for_fire to a new-fire intake step."""
    s = dict(step)
    n = str(s.get("step") or "")
    mapping = {
        "1": (
            "Creas la carpeta del incendio y el buzón de fotos.",
            "Sin carpeta no hay sitio donde guardar el estado del fuego.",
        ),
        "2": (
            "El doctor revisa que las imágenes se puedan usar.",
            "Evita procesar un IF con timestamps o CRS rotos.",
        ),
        "3": (
            "Se calculan frentes, velocidades y productos del outbox.",
            "El incendio pasa de fotos sueltas a un estado usable en mapa.",
        ),
        "4": (
            "La política de campo decide GO, HOLD o ABSTAIN.",
            "Sabes si el sistema se atreve a orientar sobre ese fuego.",
        ),
        "5": (
            "La consola se regenera mirando ese work-dir.",
            "Ves mapa + decisión del incendio en una sola pantalla.",
        ),
        "6": (
            "Atajo si no tienes GeoTIFF reales.",
            "Pruebas el flujo completo con un fuego sintético.",
        ),
    }
    plain, for_fire = mapping.get(n, (s.get("detail") or "", ""))
    s.setdefault("plain", plain)
    s.setdefault("for_fire", for_fire)
    return s


def enrich_intake_steps(steps: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [enrich_intake_step(s) for s in steps]


def build_plain_language_payload() -> dict[str, Any]:
    """Full plain-language block embedded in product SPA payload."""
    return {
        "schema": SCHEMA,
        "mode_default": "simple",
        "modes": {
            "simple": {
                "label": "Modo simple",
                "description": (
                    "Lenguaje llano: qué es cada cosa y qué aporta al incendio. "
                    "La CLI queda oculta hasta que actives Avanzado."
                ),
            },
            "advanced": {
                "label": "Avanzado",
                "description": (
                    "Muestra comandos copiables (python -m wildfire_front …) "
                    "para operadores que ya conocen la herramienta."
                ),
            },
        },
        "glossary": list(GLOSSARY),
        "features": list(FEATURES),
        "ui_hints": {
            "hero": "Grande: GO = se atreve · HOLD = espera · ABSTAIN = se calla (bien).",
            "map_local": "Cian = frente / envelope local del incendio.",
            "map_firms": "Naranja = focos satélite (no son el perímetro oficial).",
            "rebuild": (
                "La consola no es un servidor: al cambiar de incendio hay que "
                "regenerar el HTML (botón copiar rebuild en Avanzado)."
            ),
            "rails": "Las chips de honestidad no se apagan: fusión OFF y no despacho táctico.",
        },
        "disclaimer_simple": (
            "Apoyo a la lectura del incendio — no es despacho táctico ni perímetro oficial. "
            "Si faltan datos, el sistema se calla (ABSTAIN)."
        ),
    }


def features_missing_from_actions(action_ids: list[str]) -> list[str]:
    """Return feature ids that look like product CTAs but are absent from actions.

    Used in tests to keep catalog ↔ plain map aligned for core surfaces.
    """
    core = {
        "app",
        "list_fires",
        "map",
        "map_live",
        "brief",
        "operator",
        "ensayo",
        "incident_hub",
        "incident_status",
        "incident_update",
        "doctor_field",
        "decide",
        "export_acta",
        "replay",
        "multihorizon",
        "ml",
        "ml_show",
        "ingest",
        "demo",
    }
    have = set(action_ids)
    return sorted(core - have)
