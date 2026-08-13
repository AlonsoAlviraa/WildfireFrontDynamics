# Checklist QA — CLI + SPA

Inventario de lo que existe hoy y **debe funcionar** al probar el producto.

- **Producto:** apoyo a la decisión, **no** despacho táctico.
- **ABSTAIN / HOLD son correctos** (no son fallos).
- Fusion ON ≠ GO_Q complete ≠ orden de extinción.
- Solo hay **1 ancla grade-A (Tobarra)**. Hellín sigue `pending_external`.
- Catalog IoU **0.8963** es provenance only. **IoU ≠ ROS**. No inventar Vp/ha.

Arranque (PowerShell, raíz del repo):

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
```

Entrada CLI: `python -m wildfire_front …` (o `wildfire-front …`).  
Globales en casi todos: `--json` · `-v/--verbose` · `-q/--quiet`.

Compañeros: `docs/CHEATSHEET_DEMO_12MIN.md` · `docs/START_HERE.md` · `docs/H1_GO_Q_RUNBOOK.md`.

---

## 0. Humo de 10 minutos

Si esto falla, para.

| # | Qué | Comando / acción | Debe pasar |
|---|-----|------------------|------------|
| 1 | Mapa CLI | `python -m wildfire_front commands` | Lista Operario + Decision Card |
| 2 | Alias | `python -m wildfire_front spa --help` | Es `app` |
| 3 | Gates | `python -m wildfire_front show` | GO_Q **partial** / AMARILLO, `go_q_met=false`, fusion **ON** |
| 4 | Hub H1 | `python -m wildfire_front operator` | 4 actos, no cierra GO_Q |
| 5 | Decidir vacío | `python -m wildfire_front decide --policy field_ops --explain` | Card; suele **ABSTAIN** |
| 6 | Web Live Ops | `python -m wildfire_front app --fire _sla_measure --serve` | Abre `http://127.0.0.1:8766/` |
| 7 | 3 actos web | Pulsa **Estado · Decidir · Acta** | Con `--serve`: resultado en **Último acto**. Sin serve: toast «CLI copiado» |
| 8 | Tablero | Panel **Tablero IF** | 1 confirmed, 0 ml_strong, Hellín `pending_external`, **sin 2ª ancla** |

---

## 1. CLI

### 1.1 Descubrir

| Comando | Qué debe hacer |
|---------|----------------|
| `--help` / `--version` | Ayuda y versión |
| `commands` / `ayuda` / `help` / `cmds` | Mapa por rol |
| `commands --json` | JSON `wfd_cli_commands_v1` |

### 1.2 Operario / ensayo H1 (12 min)

| Comando | Qué debe hacer | No debe |
|---------|----------------|---------|
| `operator` | Hub + semáforo AMARILLO | Cerrar GO_Q |
| `operator checklist` | 7 checks de archivos; `eng_prep_ok` | Decir GO_Q complete |
| `operator do --act 1` | **Ver**: HTML multi-CCAA → `outputs/demo_multi_ccaa/index.html` | Inventar Vp |
| `operator do --act 2` | **Callarse**: honesty card offline (ABSTAIN en field_ops es OK) | Tratar ABSTAIN como bug |
| `operator do --act 3` | **Decidir**: `decide --policy field_ops --explain` | Inventar GO |
| `operator do --act 4` | **Probar**: pack + replay en `outputs/demo_third_party/` | `go_q_met=true` |
| `operator do --all` | Actos 1→4 | Firmar acta |
| `operator do --act 4 --open` | Abre el acta de ensayo | Ser acta de tercero |
| `teach` / `teach --act 3` | Narra los actos | — |
| `teach --act 3 --run` | Narra y ejecuta el acto | — |
| `show` / `show --open` | Tablero de gates + abre docs | Flip de gates |
| `demo-third-party` | Igual que acto 4 | Cerrar GO_Q |
| `demo-third-party --skip-build --no-replay` | Pack rápido | — |

Tras acto 4, `outputs/demo_third_party/REHEARSAL_SUMMARY.json` debe tener `go_q_met: false`. `replay_ok` = consistencia forense, **no** autenticidad de tercero.

### 1.3 SPA / consola web (genera el HTML)

| Comando | Qué debe hacer |
|---------|----------------|
| `app` | Escribe `outputs/product_app/index.html` |
| `app --open` | Igual + abre el navegador (`file://`, **sin** Live Ops) |
| `spa --open` / `console --open` | Alias de `app` |
| `app --list-fires` | Catálogo (`_sla_measure`, etc.) |
| `app --fire _sla_measure --open` | Consola de ese IF |
| `app --work-dir outputs/incidents/_sla_measure --open` | Igual por ruta |
| `app --serve --fire _sla_measure` | Loopback **8766**, Live Ops ON |
| `app --demo-day` | Presentador H1: `_sla_measure` + serve. **No** pone GO_Q |
| `app --ui-mode advanced --open` | Modo Pro (muestra CLI) |
| `app --ui-mode simple --open` | Fácil (CLI oculta) — default |
| `app --role field --open` | Playbook Campo (también `lab`, `decision`, `operator`) |
| `app --all-fires --open` / `--pack-fires --pack-cap 4` | Pack multi-IF en el HTML (cambio de fuego sin rerun) |
| `app --no-scan --open` | Sin picker |
| `app --lat 40.9 --lon -3.1 --fixture-csv tests/fixtures/firms_sample_hotspots.csv --open` | Mapa con FIRMS de disco |
| `app --live …` | Intenta FIRMS de red (puede fallar sin API; no es bug de producto) |
| `app --bridge-decide http://127.0.0.1:8765 --ui-mode advanced --serve` | Botón **Refrescar card** (junto a `serve-decide`) |

### 1.4 Decision Card

| Comando | Qué debe hacer |
|---------|----------------|
| `decide --list-policies` | Lista `default` / `field_ops` / `research_open` / `demo` |
| `decide --policy field_ops --explain` | Card + razones. Fuentes vacías → **ABSTAIN** |
| `decide --event-id prueba --output outputs/tmp_card.json` | Escribe JSON |
| `decide --work-dir outputs/incidents/_sla_measure --policy field_ops --explain` | Fusiona outbox del IF |
| `decide --use-ml-v34 --explain` | Métricas de catálogo v34 (calidad lab, **no** ROS de campo) |
| `decide --require-ops-for-go --explain` | Nunca GO sin ops térmica |

### 1.5 HTTP Decision Card (otro puerto)

```powershell
python -m wildfire_front serve-decide --port 8765
```

Otra terminal:

```powershell
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/v1/openapi.json
curl -s http://127.0.0.1:8765/v1/policies
curl -s -X POST http://127.0.0.1:8765/v1/decide -H "Content-Type: application/json" -d "{\"policy_id\":\"field_ops\",\"require_ops_for_go\":true}"
```

Debe responder. No debe inventar GO_Q.

### 1.6 Acta forense + replay (no es acta H1 de tercero)

```powershell
python -m wildfire_front decide --work-dir outputs/incidents/_sla_measure --output outputs/incidents/_sla_measure/outbox/fire_decision_card.json
python -m wildfire_front export-acta --work-dir outputs/incidents/_sla_measure
python -m wildfire_front replay-decide --work-dir outputs/incidents/_sla_measure
```

Deben salir `fire_decision_acta.md`, `fire_decision_radio.txt`, `replay_sources.json`.  
`replay_ok` = hashes coinciden, **no** “el tercero firmó”.

### 1.7 Incidente en vivo (inbox → outbox)

Necesitas una carpeta de GeoTIFF (IF real o demo).

| Subcomando | Qué debe hacer |
|------------|----------------|
| `incident doctor --inbox DIR --event-id IF1` | Preflight: nombres, CRS, máscaras |
| `incident update --inbox DIR --work-dir outputs/incidents/IF1 --sensor-id X --estimated-error-m 5` | Una pasada → outbox |
| `incident update … --force` | Recalcula aunque no haya frames nuevos |
| `incident status --work-dir outputs/incidents/IF1` | Lee estado **sin** procesar |
| `incident watch --inbox DIR --work-dir … --interval-s 2 --max-iterations 3` | Loop corto y sale |

Sin TIFFs en inbox, `doctor`/`update` deben fallar **con error claro**, no inventar frente.

### 1.8 Demo sintético + ingest

```powershell
python -m wildfire_front demo --output outputs/demo --seed 7
python -m wildfire_front ingest-geotiff --images DIR --sensor-id demo --estimated-error-m 5 --operational --output outputs/geotiff-demo
```

`demo` escribe informe HTML.  
`ingest-geotiff` sin `--images` o sin `--sensor-id` / `--estimated-error-m` → error (correcto).

---

## 2. Web (SPA)

Abre **dos modos** y prueba ambos:

```powershell
# A) Live Ops (el que importa para H1)
python -m wildfire_front app --fire _sla_measure --serve
# http://127.0.0.1:8766/

# B) Estático (file://) — no hay POST
python -m wildfire_front app --fire _sla_measure --open
```

### 2.1 Cabecera

| Control | Debe |
|---------|------|
| Selector de incidente | Cambia mapa + card (si hay pack) o pide rebuild |
| **Ops / Campo / Lab / Decisión** | Cambia hints del playbook |
| **Fácil / Pro** | Fácil oculta CLI; Pro la enseña |
| **?** | Modal de ayuda; Cerrar / clic fuera lo cierra |

### 2.2 Mapa

| Control | Debe |
|---------|------|
| Mapa Leaflet | Carga; capas frente / FIRMS |
| Chip de capas + conexión | Números o “—” honesto, no crash |
| Leyenda | “FIRMS NRT ≠ perímetro” |
| Botón ◎ centrar | Recuadra el IF |

### 2.3 Tres actos (siempre visibles)

| Botón | Con `--serve` | Sin `--serve` |
|-------|---------------|---------------|
| **Estado** | POST `/live/v1/status` → outbox en **Último acto** | Copia CLI `incident status` + toast |
| **Decidir** | POST `/live/v1/decide` → GO/HOLD/**ABSTAIN** | Copia CLI `decide` |
| **Acta** | POST `/live/v1/export-acta` → paths del bundle | Copia CLI `export-acta` |

Después de un acto live: **Copiar path** y (en Pro) **Replay pack** (`/live/v1/replay-third-party`). Replay ≠ acta H1.

### 2.4 Paneles del rail (solo lectura)

| Panel | Debe mostrar | No debe |
|-------|--------------|---------|
| Palabra grande + texto | Decisión en claro | Orden de extinción |
| **Banda incertidumbre** | Conf. predicción + “**no es ROS**” | ROS/Vp inventado |
| KPIs / next | Datos del outbox o “—” | Inventar métricas |
| **Último acto** | Resultado live o CLI copiado | 501 desnudo sin serve |
| **Decision log** | Última entrada o “sin sidecar” | Inventar `decision_id` |
| **ACK** | Con serve: marca ack. Sin serve: no finge backend | Ser acta H1 |
| **V&V eng** | `eng_stub` o “sin sidecar”; field IoU/ROS/grade = **—** | Scores de campo |
| **Tablero IF** | n_fires, 1 confirmed, 0 ml_strong, Hellín pending | 2ª ancla, promote, POST |
| **Conf. ML vs Conf. ROS** | Dos cajas; ML ≠ ROS | Mezclar IoU con ROS |
| **Ensayo H1** | `go_q_met=false`; **Copiar cmd** | Decir que es acta |
| **Escala SR** | S0–S3; no vender field GO | — |
| **Abrir consola** | Copia comando rebuild | — |
| **Solo mapa** | Copia comando de mapa | — |
| **Refrescar card** | Solo si arrancaste con `--bridge-decide` y `serve-decide` | Fusionar por su cuenta |

### 2.5 Pestañas inferiores

| Tab | Debe |
|-----|------|
| **Overview** | KV ops + rails (fusion ON, GO_Q partial). En Pro: **Copiar next cmd** |
| **Decisión** | Card o “Sin tarjeta”; **Copiar** |
| **Acciones** | Inventario de acciones + filtros + copiar cada una |
| **Nuevo** | Pasos de intake (texto, no sube TIFFs) |
| **Términos** | Glosario (IoU ≠ ROS, ABSTAIN, etc.) |
| **Lista** | Fuegos del catálogo; clic = mismo efecto que el selector |

### 2.6 Endpoints Live Ops (solo con `--serve`)

Base: `http://127.0.0.1:8766`

- `GET /live/v1/health`
- `POST /live/v1/status`
- `POST /live/v1/decide`
- `POST /live/v1/export-acta`
- `POST /live/v1/replay-third-party`
- `POST /live/v1/ack-decision`

Fuera de loopback o path traversal → rechazo. Eso es correcto.

---

## 3. Lo que DEBE fallar

Si no falla, hay bug de honestidad.

```powershell
python scripts/refuse_promote_without_cite.py --attempt-promote --fire-id hellin_2024
# exit 1 · error: no cite = no promote

python scripts/copy_cite_to_real_if.py
# exit 1 · error: missing --cite

python scripts/score_if_weakness_board.py --fire-id no_existe
# exit 1

python scripts/check_release_flags.py
# PASS · GO_Q partial · fusion ON
```

En la web: el bloque de **2ª ancla** debe quedar **oculto**. El tablero no tiene botón de promote.

---

## 4. Lo que NO hay que “hacer funcionar” (humano)

- Enviar correos Hellín / Cardoso / R4
- Poner Hellín `confirmed` o inventar Vp/ha
- Cerrar GO_Q (hace falta demo de tercero + acta firmada)
- GO_MES+ (hace falta 2ª grade-A)
- Retrain v34 / v35

---

## Orden práctico

1. Sección 0 (humo).
2. CLI operario actos 1–4.
3. `app --serve` y picar **todo** el rail + las 6 pestañas en Fácil y en Pro.
4. `decide` / `export-acta` / `replay-decide`.
5. `incident doctor` si hay TIFFs.
6. Los 4 fail-closed del §3.

**Cite o silencio honesto.** No hay 2ª ancla inventada. Dry-run H1 ≠ acta.
