# Inventario público de la cosecha histórica WFIGS

Fecha de corte: 2026-08-18.

Este directorio publica únicamente metadatos de procedencia, configuración y
métricas agregadas. No incluye geometrías, pares, teselas, tensores, checkpoints
ni el fichero de splits por evento.

## Cosecha

- Fuente: `WFIGS Daily Perimeters Public`, NIFC Authoritative.
- Intervalo: 2020–2026.
- Particiones solicitadas/completadas: 70/70; fallidas: 0.
- Observaciones recibidas: 35 562.
- Incendios identificados: 15 661.
- Descarga local verificada: 2 322 055 826 bytes.

Los 70 `manifest.json` conservan consulta, paginación, recuentos, tamaño y SHA-256
de cada respuesta. Las respuestas GeoJSON no se versionan.

## Pares temporales

- Eventos con al menos dos perímetros: 1 350.
- Eventos con pares aprobados: 842.
- Pares aprobados: 3 439.
- Ventanas: 390 de 6–12 h, 1 343 de 12–24 h y 1 706 de 24–48 h.
- Splits por incendio: 583 TRAIN, 131 VALIDATION y 128 TEST.

El inventario agregado conserva los motivos de rechazo y la distribución por
región, estado y año. Los pares y los identificadores asignados a cada split no
se publican.

## Derechos

La fuente es de acceso público y se permite su uso científico interno no
comercial bajo la política conservadora del proyecto. No se encontró una licencia
afirmativa de redistribución: por ello quedan fuera de GitHub datos crudos,
geometrías, datasets derivados, tensores y checkpoints. Sí se publican código,
configuración, metodología, procedencia y métricas agregadas.

Fuentes de evidencia:

- `data/open_if/wfigs_history_2020_2026/HARVEST_REPORT.json`
- `data/open_if/wfigs_history_2020_2026/temporal_pairs/INVENTORY.json`
- `data/open_if/wfigs_history_2020_2026/RIGHTS_POLICY.json`
