# Reunión — resumen, análisis y mega plan mensual (ciclo nuevo)

| Campo | Valor |
|-------|--------|
| **Documento** | Resumen de conversación multi-sesión + plan mensual **nuevo** |
| **Proyecto** | WildfireFrontDynamics (WFD) |
| **Horizonte plan** | **2026-08-04 → 2026-09-04** (30 días) |
| **Cierre ciclo anterior** | Plan 1 mes 2026-07-17 → 2026-08-17 (casi cerrado eng; queda GO_Q humano) |
| **Autoridad gates** | `docs/GO_MES_VERDICT.md` · `docs/PROJECT_STATUS.md` · `data/infocam_anchors.json` |
| **Graph** | `.grok/graph_engineering/STATE.md` **v5** |
| **Fecha de corte** | 2026-08-04 |

> Este documento **sustituye como plan de acción del mes entrante** a los overlays de cierre del mes anterior.  
> No inventa Vp/ha, no activa fusión ML en `field_ops`, no reclama GO_MES+ ni GO_Q sin evidencia.

---

## 0. Una frase

**El mes de ingeniería cerró con GO_MES mínimo y producto dual + fuel/AEMET en `main`; el mes nuevo se gana con demo real a tercero, informe, y stretch ops (O5/O2) — no con más bucles de honesty ni k conjunto Tobarra↔Hellín.**

---

## 1. Resumen de la conversación (hilo completo)

### 1.1 Problema de partida

- Estancamiento percibido: eng GO, mes bloqueado por **externos**.
- Producto dual honesto: ops térmico vs ML lab; fusión `field_ops` **OFF**.
- Solo **1 ancla** confirmed (Tobarra Vp=7, 39 ha) → O1 OPEN, GO_MES false.
- Mega-plan ROS/vegetación/terreno en curso (DEM, WorldCover, Rothermel, envelope).

### 1.2 Outreach y datos Pablo (GEACAM/CMA)

| Fecha | Evento | Resultado |
|-------|--------|-----------|
| 30 jul | Drop Tobarra (KMZ multi-hora + mapas) | O2 ops Tobarra PARCIAL; Cardoso “sin más material” |
| 03 ago | Email corto Alonso (perímetros + Vp/ha) | Enviado vía Gmail MCP |
| 03 ago | Respuesta Pablo + WeTransfer **0308.zip** (53 MB) | Hellín + La Estrella + Cardoso |
| 03 ago | Ingest local | Boletín UNAP Hellín: **Vp media = 50 m/min**, 100 ha* |

**Pack 0308 (contenido útil):**

| IF | Material | Uso WFD |
|----|----------|---------|
| **Hellín** | KMZ 19/07 20:45 + **Boletín UNAP 20/07/2024** | **2ª ancla confirmed** |
| **La Estrella** | KMZ 07/08 14:25 (~2524 ha) + cartografía INFOCAM | Lectura SITAC Vp 20–25 (no confirmed) |
| **Cardoso** | KMZ multi-día sep 2025 + térmicos | Timeline Δha proxy (no Vp) |

### 1.3 AEMET + fuel stack (eng)

- API AEMET OpenData (key en `.env`, nunca en git).
- Encoding ISO-8859-1; `hrMedia`/`racha`; `dir=99` → variable → assumed partial.
- Pipeline Tobarra: stack DEM+WorldCover + Rothermel espacial + hybrid + envelope v3 + scorecard **PASS**.
- Commits en `main` (push): PR-α physics · PR-β envelope/AEMET · ops perimeter Pablo.

### 1.4 Validación ops multi-ancla

| IF | Vp ancla | ROS pack | Ratio | Grado |
|----|---------:|---------:|------:|-------|
| Tobarra | 7 | ~5.71 | **0.82** | **A** |
| Hellín | 50 | ~27.9 | **0.56** | **B** |

- Chase grade A + in-band en Hellín: **eng-blocked** (reglas A capan ROS≤25; banda vs Vp50 exige ROS≥25; n_primary suele ser 1–2).
- Documentado en `docs/P1_HELLIN_ENG_STATUS.md`.

### 1.5 GO_MES (cierre honesto)

Fórmula **plan mínimo** (`PLAN_1_MES_MEJORA_GLOBAL`):

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

| Componente | Definición correcta | Resultado |
|------------|---------------------|-----------|
| O1 | ≥2 anclas + ratio ∈[0.5,2] | **PASS** |
| O4 | brief ≤5 min | **PASS** |
| **P1** | smoke incident **2 IF reales sin crash** | **PASS** (`--p1-two-real`) |
| M2 | v34 holdout ≥0.890 | **PASS** |
| E1 | CI/smokes | **PASS** |

**Error de camino corregido:** se había tratado P1 como “2º grade A”. Eso es **O5 / GO_MES+**, no el mínimo del plan.

**Veredicto:** **GO_MES = true** · `docs/GO_MES_VERDICT.md`  
**No reclamado:** GO_MES+, GO_Q, ml_product_go, fusion field_ops.

### 1.6 Graph engineering

- **v4 → v5:** deja de ser primario “email Cardoso por O1”.
- Primario humano: **demo tercero**.
- Primario eng residual: O5 opcional / open packs / hygiene.
- Ciclos: c4 post-O1; GO_MES declare 2026-08-04.

### 1.7 Templates producto (listos para ejecutar)

| Doc | Función |
|-----|---------|
| `docs/GUION_DEMO_30MIN_POST_O1.md` | Guion demo 30 min |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | Acta 1 página |
| `docs/INFORME_TRIMESTRE_ESQUELETO.md` | Esqueleto 8–12 pp |
| `docs/DATA_PROXY_HONESTY.md` | Qué es confirmed vs proxy |

### 1.8 Rails de honestidad (permanentes)

1. No inventar Vp / ha oficiales (press, X, sat, Δha polígono).  
2. KMZ ops ≠ EGIF nacional.  
3. Envelope v3 / fuel physics = orientación; Decision Card **weight 0**.  
4. `field_ops.allow_ml_live_in_fusion = false`.  
5. Catalog IoU 0.8963 = provenance only; pitch lab = U1 ~0.86 + ECE.  
6. No k de calibración único Tobarra(7) ↔ Hellín(50).  
7. No reescalar ROS a Vp en silencio.

---

## 2. Análisis: qué se desbloqueó y qué sigue siendo el cuello

### 2.1 Matriz de desbloqueo

| Bloqueo histórico | Estado ahora | Quién lo desbloqueó |
|-------------------|--------------|---------------------|
| O1 2ª ancla | **PASS** | Pablo + boletín Hellín + ingest |
| Fuel/ROS physics path | **DONE** | eng PR-α/β + AEMET |
| Envelope corto horizonte | **DONE** | eng v3 + scorecard |
| P1 2 IF reales | **PASS** | smoke incident Tobarra+Hellín |
| GO_MES mínimo | **PASS** | relectura plan + smoke P1 |
| O5 2º grade A | **OPEN** | datos/reglas (Hellín B) |
| O2 perímetro nacional | **BLOCKED** | externo |
| GO_Q (demo + informe) | **OPEN** | **humano** |
| ml_product_go | **false** | política (correcto) |

### 2.2 ROI del mes anterior vs residual

| Tipo de trabajo | ROI mes pasado | ROI mes nuevo |
|-----------------|----------------|---------------|
| Más honesty graph loops | Bajo | **Bajo — no priorizar** |
| Más tune Hellín → grade A | Marginal (bloqueado por diseño) | **Bajo** salvo datos nuevos |
| Demo a tercero + acta | Medio (templates) | **Máximo** |
| Informe trimestre relleno | Bajo (esqueleto) | **Alto** (entrega/TFG) |
| Open packs / CEMS | Medio | Medio (contexto) |
| 3ª ancla formal (Cardoso Vp) | N/A | Medio (GO_MES+ / narrativa) |

### 2.3 Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Presentar GO_MES como “todo listo táctico” | Usar guion kill list; dual product + ABSTAIN |
| Confundir GO_MES con GO_MES+ | Tabla en GO_MES_VERDICT |
| Inventar Vp Cardoso/Estrella en demo | DATA_PROXY_HONESTY + anchors JSON |
| Calibrar física con Hellín 50 y Tobarra 7 juntos | Kill list explícita |
| Token Gmail / WeTransfer caducados | Re-auth; backups locales del 0308 |

---

## 3. Estado de producto (foto 2026-08-04)

### 3.1 Gates

| Gate | Valor |
|------|--------|
| GO_ENG | **true** |
| **GO_MES** | **true** (mínimo) |
| GO_MES+ | **false** |
| GO_Q | **partial** |
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| Anclas confirmed | **2** (Tobarra, Hellín) |

### 3.2 Producto dual

| Capa | ID | Mensaje de venta honesto |
|------|-----|---------------------------|
| Ops | `front_dynamics_v1` | Tobarra grade A; Hellín ancla+ops B in-band; smoke 2 IF |
| ML lab | `clm_ensemble_v34` | U1 ~0.86 / ECE ~0.15; holdout 0.8963 provenance |
| Decisión | Decision Card | GO/HOLD/ABSTAIN; fusion field_ops OFF |
| Open | multi-CCAA | Tobarra · Níjar · Caminomorisco (no EGIF) |
| Fuel | stack + AEMET + envelope v3 | física/híbrida; no despacho |

### 3.3 Datos

| Fuente | Estado |
|--------|--------|
| INFOCAM anchors | Tobarra + Hellín confirmed |
| Pablo 0308 | ingerido localmente |
| AEMET Tobarra | live path + fixture |
| Cardoso | timeline ha only |
| La Estrella | SITAC leído, no confirmed |
| CyL 4082 | wait ~2026-08-17 |
| O2 EGIF | blocked |

---

## 4. Mega plan mensual **nuevo** (2026-08-04 → 2026-09-04)

### 4.1 Objetivos del mes

#### GO_MES (ya cumplido — mantener)

- No regresar O1 (no borrar anclas).  
- No romper smoke P1 / CI.  
- No activar fusion field_ops.

#### GO_Q (objetivo principal del mes)

```
GO_Q_min =
  GO_MES
  ∧ demo con tercero (30 min) + acta firmada (M3.2)
  ∧ informe trimestre relleno 8–12 pp (M3.4)
```

#### GO_MES+ (stretch, no bloqueante de GO_Q)

```
GO_MES+ =
  GO_MES
  ∧ (O5: ≥2 packs structural grade A  OR  3ª ancla formal)
  ∧ (O2: perímetro nacional 1 IF  OR  abstención formal documentada)
  ∧ (opcional D1 CyL respuesta o silence rule)
```

### 4.2 Cinco pistas (rebalanceadas)

| ID | Pista | % tiempo | Prioridad |
|----|-------|----------|-----------|
| **H-DEMO** | Demo + acta + follow-up | **35%** | **#1** |
| **H-WRITE** | Informe trimestre / TFG chapters | **25%** | **#1** empatado |
| **E-OPS** | O5 / open packs / incident polish | **20%** | #2 |
| **E-DATA** | 3ª ancla solo con fuente formal; CyL/O2 | **10%** | #3 |
| **E-HYG** | Graph sync, tests, release notes | **10%** | #3 |

### 4.3 Semanas

#### Semana 1 (04–10 ago) — **Demo y narrativa**

| # | Acción | Owner | Entregable | GO |
|---|--------|-------|------------|-----|
| 1.1 | Agendar 1 demo 30 min (CMA, uni, partner, mentor) | Humano | fecha en calendario | H-DEMO |
| 1.2 | Ensayo interno 20 min con guion | Humano+eng | notas | — |
| 1.3 | Ejecutar demo + rellenar acta | Humano | `ACTA` firmada | **M3.2** |
| 1.4 | Commit/push docs GO_MES + plan si falta | Eng | git | hygiene |
| 1.5 | Status sync hub sin inflar claims | Eng | PLAN_3_MESES / hub | honesty |

**Kill S1:** no reabrir bucle Hellín grade A como tarea principal.

#### Semana 2 (11–17 ago) — **Informe + cierre mes viejo**

| # | Acción | Owner | Entregable | GO |
|---|--------|-------|------------|-----|
| 2.1 | Rellenar informe desde esqueleto (8–12 pp) | Humano | MD/DOCX | **M3.4** |
| 2.2 | Scorecard mes + GO_MES_VERDICT en anexo | Eng | PDF/MD | — |
| 2.3 | CyL silence rule check (~17 ago) | Humano | nota CONTACTOS | D1 |
| 2.4 | Tag git opcional `go-mes-2026-08` | Eng | tag | release |
| 2.5 | Actualizar PORTAL / START_HERE con GO_MES + demo | Eng | docs | — |

#### Semana 3 (18–24 ago) — **Stretch ops / datos**

| # | Acción | Owner | Entregable | GO |
|---|--------|-------|------------|-----|
| 3.1 | Solo si hay tiempo: 2º IF grade A (otro pack o policy O5) | Eng | scorecard O5 | GO_MES+ |
| 3.2 | Open CEMS packs prioritarios (La Mierla EMSR898…) | Eng | open_if | O2 proxy |
| 3.3 | 3ª ancla **solo** con boletín/parte explícito (Cardoso/Estrella) | Humano+eng | anchors JSON | O1+ |
| 3.4 | No forzar v35 ML sin fuego nuevo | Eng | — | anti-leakage |

#### Semana 4 (25 ago–04 sep) — **GO_Q y handoff**

| # | Acción | Owner | Entregable | GO |
|---|--------|-------|------------|-----|
| 4.1 | Checklist GO_Q (demo+acta+informe) | ambos | scorecard Q | **GO_Q?** |
| 4.2 | Plan mes 2 (post GO_Q o residual) | Humano | 1–2 pp | — |
| 4.3 | Limpieza outputs/secrets; .env never commit | Eng | git hygiene | — |
| 4.4 | Graph v6 si GO_Q: primary = scale/CCAA/O2 | Eng | STATE.md | — |

### 4.4 Backlog priorizado (acciones concretas)

#### P0 — Debe ocurrir este mes

1. **Demo real 30 min** con guion post-O1.  
2. **Acta firmada** (template listo).  
3. **Informe trimestre relleno** (esqueleto listo).  
4. Mantener rails (fusion OFF, no inventar Vp).

#### P1 — Debe si hay capacidad

5. Push/commit residual docs GO_MES + pack notes.  
6. CyL follow-up post silence rule.  
7. 1 open pack CEMS nuevo documentado.  
8. Opcional: email Pablo solo si se quiere **Vp formal Cardoso** (3ª ancla), no para reabrir O1.

#### P2 — Stretch

9. O5 segundo grade A (policy o datos).  
10. O2 perímetro nacional 1 IF.  
11. v35 ML solo con multi_if nuevo no-Cardoso leakage-safe.  
12. AEMET multi-IF (Hellín 2024-07-19) offline fixture.

### 4.5 Rituales semanales (graph)

| Día | Ritual |
|-----|--------|
| Lun | Priorizar 3 tareas; 1 demo o 1 sección informe |
| Mar–Jue | Ejecutar |
| Vie | `run_plan_cycle --execute-m1` + actualizar esta tabla de gates |
| 2–3×/sem | `wfd-external-unblock` (demo/O2, no spam O1) |
| Semanal | `wfd-autonomous-cycle` (hygiene, no motor principal) |

### 4.6 Kill list del mes nuevo

- Reclamar GO_MES+ o “listo táctico 24 h”  
- Usar Δha Cardoso o SITAC Estrella como Vp confirmed  
- Activar `field_ops` ML fusion  
- Calibrar k único 7↔50  
- Bucle infinito Hellín grade A sin datos nuevos  
- Honesty graph como sustituto de demo  
- Inventar ha EGIF desde CEMS/prensa  

---

## 5. Mapa de evidencia (para la demo y el informe)

| Claim permitido | Path de evidencia |
|-----------------|-------------------|
| GO_MES mínimo | `docs/GO_MES_VERDICT.md` |
| 2 anclas | `data/infocam_anchors.json` |
| Ratios in-band | `outputs/observatorio/anchor_scorecard.json` |
| Hellín Vp 50 | boletín + `HELLIN_TRACK_A_SCORECARD` |
| Tobarra grade A | `outputs/observatorio/tobarra_20240802/` |
| Smoke 2 IF | `smoke_incident_runtime.py --p1-two-real` |
| Fuel/AEMET | `run_tobarra_aemet_pipeline.py` · envelope scorecard PASS |
| Dual product | `docs/PRODUCTO_DUAL.md` · Decision Card |
| Proxy vs gold | `docs/DATA_PROXY_HONESTY.md` |
| Pack Pablo | `data/real_if/pablo_geacam_20260803_drop/` |

---

## 6. Criterios de éxito del mes nuevo (2026-09-04)

| Nivel | Criterio |
|-------|----------|
| **Mínimo** | GO_MES mantenido + demo hecha **o** fecha firmada + 50% informe |
| **Objetivo** | **GO_Q**: demo+acta + informe 8–12 pp |
| **Stretch** | GO_MES+ parcial (O5 o O2) sin mentir |

---

## 7. Asignación de ownership

| Owner | Responsabilidades |
|-------|-------------------|
| **Humano (Alonso)** | Agendar demo, presentar, firmar acta, escribir informe, CyL/Pablo si 3ª ancla |
| **Eng / agent** | Mantener packs, smokes, scorecards, open_if, no inventar claims |
| **Graph** | External-unblock → demo; status-sync post commits; no O1 spam |

---

## 8. Primera acción recomendada (hoy / esta semana)

1. Elegir **1 persona externa** y proponer hueco 30 min.  
2. Ensayar con `docs/GUION_DEMO_30MIN_POST_O1.md` (variante 20 min si hace falta).  
3. Tras la demo: rellenar `docs/ACTA_DEMO_TERCERO_TEMPLATE.md`.  
4. En paralelo: rellenar §1–3 del `INFORME_TRIMESTRE_ESQUELETO.md` con paths de la §5.

**No prioritario hoy:** más rebuilds Hellín, más ML, más graph honesty.

---

## 9. Índice de documentos vivos

| Doc | Rol |
|------|-----|
| **Este archivo** | Resumen reunión + **mega plan mensual nuevo** |
| `docs/GO_MES_VERDICT.md` | Veredicto GO_MES |
| `docs/PLAN_1_MES_POST_O1_UNLOCK.md` | Plan residual mes anterior (archivo vivo hasta 17 ago) |
| `docs/PLAN_1_MES_STATUS_20260804.json` | Snapshot machine |
| `docs/SCORECARD_MES_1.md` | Scorecard mes |
| `docs/PROJECT_STATUS.md` | Estado canónico corto |
| `.grok/graph_engineering/STATE.md` | Graph v5 |
| `docs/GUION_DEMO_30MIN_POST_O1.md` | Demo |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | Acta |
| `docs/INFORME_TRIMESTRE_ESQUELETO.md` | Informe |
| `docs/DATA_PROXY_HONESTY.md` | Confirmed vs proxy |
| `docs/P1_HELLIN_ENG_STATUS.md` | Hellín grade A eng-blocked (O5) |

---

## 10. Cierre

El ciclo de conversación logró:

1. **Datos** (Pablo 0308 + Hellín Vp 50).  
2. **Producto eng** (fuel, AEMET, envelope, packs).  
3. **GO_MES mínimo** con definición correcta de P1.  
4. **Templates** listos para GO_Q.

El mes nuevo no se gana “programando más lo mismo”: se gana **demostrando y escribiendo** con honestidad, y solo después stretch O5/O2.

**Próximo hito único si solo hay una hora esta semana:**  
**demo con tercero + acta empezada.**
