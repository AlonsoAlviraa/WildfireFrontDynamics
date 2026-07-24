# Plan de programación — Gmail completo + producto (2026-07-24)

| Campo | Valor |
|-------|--------|
| **Fuentes** | Gmail inbox/sent (~jun–jul 2026) re-leído hoy; repo `main` @ `3cfc28a` |
| **Objetivo** | Priorizar ingeniería según **datos ya en casa** y **blockers reales** |
| **Siguiente paso (único)** | **P0 — Arreglar CI en `main`** (run [30032071338](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/runs/30032071338)) |

---

## 1. Inventario de emails (hilos incendios / datos)

### 1.1 CCAA y canales con respuesta (estado al 24 jul)

| Hilo | De | Fecha | Resultado | Acción |
|------|-----|-------|-----------|--------|
| **REDIAM Andalucía** | `rediam.atiende.csma@juntadeandalucia.es` | 22 jul | **GO datos públicos**: perímetros 2008–2025 + áreas recorridas; sugiere ASEMA | Packs AND ya en repo (`data/open_if/rediam_andalucia/`). Opcional follow-up ASEMA (sin reply) |
| **RAI Extremadura** | `rai@juntaex.es` | 22–23 jul | **GO 3 SHP 2025** (Alburquerque, Caminomorisco, Burguillos) + Word registro; Alonso envió form; RAI **“Gracias”** | Trámite cerrado. Packs en `data/open_if/extremadura_rai_2025/` |
| DG Medio Natural EXT | `dgcpatymn.agmn@` | 22 jul | Reenvío a `dgpeiiff.prs@juntaex.es` | Superado por canal RAI |
| Galicia Planificación Forestal | `forestal.mediorural@` | 22 jul | Competencia = **Defensa do Monte** | Hecho |
| Galicia Defensa do Monte | `defensadomonte.mediorural@` | 22 jul | **Traslado a Extinción**; sin SHP | Esperar Extinción (7–14 d); no re-spam |
| **USC Amiama → Díaz-Varela** | `carlos.amiama@usc.gal` → `ramon.diaz@usc.es` | 22 + **24 jul** | Amiama reenvía a coordinador máster; **Díaz-Varela (24 jul): universidades sin acceso a datos; hay que pedir a Servicio Prevención Xunta** (datos sensibles / IP) | **Canal USC cerrado para datos.** Solo queda Xunta Extinción/Prevención |
| CyL CDF Nuria Ramos | `nuria.ramos@jcyl.es` | 17 jul | Canal transparencia + 1 incendio concreto + portal abiertos | Formalizado |
| CyL Acceso Información | `accesoinformacion@jcyl.es` | 17 jul | Acuse **4082/2026**; plazo **1 mes** desde 17/07 → ~**17 ago 2026** silencio = desestimada | Esperar resolución; no reenviar |
| CTFC Brunet (FIRE-RES) | `pau.brunet@ctfc.cat` | 16 jul | Deriva a **administración CLM** / propuesta regional | No datos |
| CTFC Duane | `andrea.duane@ctfc.cat` | 17 jul | FIRE-RES finalizado; deliverables fire-res.eu | Lectura opcional |
| INIA Madrigal | `incendio@inia.csic.es` | 17 jul | **Sin datos**; asesoría solo con **contrato CSIC de pago** | No insistir sin presupuesto |
| Firelogue / Fraunhofer Berchtold | `claudia.berchtold@fkie.fraunhofer.de` | 17 jul | Catálogo metadatos Zenodo; pide concretar feedback (¿staff ops?) | Opcional: 1 respuesta corta con brief + enlace scorecard lab (no urgente) |

### 1.2 Enviados sin respuesta útil (no re-spamear)

- ASEMA / DG incendios Andalucía (ops) — sin reply.
- INFOEX DG Bayón — superado por RAI.
- Varios buzones Galicia/USC del 22 jul (ruido de reenvíos).
- Heligrafics / CMA metadatos CLM (16 jul) — sin reply leída en este pase.

### 1.3 Fuera de alcance WFD (ignorados en plan)

- VisionSetil / setas (24 jul): otro proyecto.
- Airbus / FUE beca, prácticas UN, InfoJobs, PayPal, etc.

### 1.4 Cambio vs plan 23 jul

| Item | 23 jul | **24 jul** |
|------|--------|------------|
| USC | Esperar coordinador | **Cerrado**: Díaz-Varela → pedir a Xunta, no a universidad |
| RAI | Gracias recibida | Sin cambio (cerrado OK) |
| CyL | 4082 pendiente | Plazo legal ~17 ago |
| CI `main` | Rojo | **Sigue rojo** en `3cfc28a` |

---

## 2. Qué ya tenemos (ingeniería + datos)

### Datos

| CCAA | Estado | En repo |
|------|--------|---------|
| CLM | OPS gold Tobarra (LWIR) | Sí (pista A) |
| Andalucía | REDIAM O2 + Níjar gold + PSB | Sí (`rediam_andalucia`) |
| Extremadura | RAI 3 SHP 2025 | Sí (`extremadura_rai_2025` raw + zips) |
| Galicia | Solo hilo admin; USC no da datos | No pack |
| CyL | Solicitud 4082/2026 abierta | No pack formal |

### Producto dual

- **Ops:** `front_dynamics_v1`, Decision Card GO/HOLD/ABSTAIN.
- **Open industrial** AND/EXT + demo multi-CCAA.
- **ML:** ensemble v34, uncertainty, U1 **TEST honest** (mean IoU eval ~0.857; selective@80 ~0.90; ECE ~0.15), nested CV VAL, scorecard lab, `research_open` fusion experimental; **`field_ops` fusion OFF**.
- Catalog holdout 0.8963 = provenance only (no mezclar en pitch).

### Artefactos clave

- `docs/ML_PRODUCT_SCORECARD.json`, `docs/ML_U1_PROMOTE_RECORD.json`
- `docs/design/ML_FOCUS_PRODUCT_V1.md`
- Scripts fit/eval U1, promote, scorecard, progressive burn, packs AND/EXT

---

## 3. Qué falta (priorizado)

| P | Item | Tipo | Depende de email |
|---|------|------|------------------|
| **P0** | CI `main` verde (Tests 3.11/3.12 + Lint) | Ingeniería | No |
| **P1** | E2E demo: ML live JSON → Decision Card (Níjar / Tobarra / Caminomorisco) | Ingeniería | Datos ya OK |
| **P1** | Pitch honesto: no 0.8963 como “certeza en vivo” | Docs/demo | — |
| **P2** | ECE TEST ~0.15 → bajar o abstain más agresivo | ML | Pesos locales |
| **P2** | CyL pack si resuelven 4082 (~17 ago deadline silencio) | Datos | Email CyL |
| **P2** | Galicia pack si Extinción envía SHP | Datos | Email GAL |
| **P3** | ASEMA O1/Vp (1 follow-up corto) | Datos | Email |
| **P3** | Respuesta opcional Fraunhofer (brief + scorecard) | Outreach | Email |
| **P3** | `field_ops` live fusion | Producto | No aún |
| **P3** | Contrato INIA | Negocio | Presupuesto |

---

## 4. Plan de programación por sprints

### Sprint 0 — **Siguiente paso (esta semana)**  
**Objetivo:** CI verde en `main`.

| ID | Tarea | DoD | Est. |
|----|--------|-----|------|
| **S0-1** | Diagnosticar [CI run 30032071338](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/runs/30032071338) (pytest + ruff/mypy) | Log + lista tests/lints rojos | 0.5 d |
| **S0-2** | Arreglar fallos ML rails / scorecard / promote / imports | Suite CI verde en Actions | 1–2 d |
| **S0-3** | Smoke: `test_u1_honest_eval`, `test_ml_focus_protocol`, packs AND/EXT, demo multi-CCAA | Job success | 0.5 d |
| **S0-4** | Nota START_HERE: “CI verde + scorecard lab honest” | 1 párrafo | 0.25 d |

**No incluir en Sprint 0:** retrain, más CCAA, outreach masivo, VisionSetil.

### Sprint 1 — ML en el Decision Card (1–2 semanas)

| ID | Tarea | DoD |
|----|--------|-----|
| S1-1 | Script demo: pack open o fixture → `ml_prediction.json` → Decision Card | HOLD/ABSTAIN documentado |
| S1-2 | Banner multi-CCAA ML-first (U1 TEST, no 0.90 confuso) | HTML/guion |
| S1-3 | Experiment corto abstain / ECE si conf poco fiable | Nota métrica |

### Sprint 2 — Datos cuando el email cierre

| ID | Tarea | Trigger |
|----|--------|---------|
| S2-1 | Pack CyL open industrial | Resolución 4082/2026 o portal + 1 IF |
| S2-2 | Pack Galicia si llegan SHP | Mail Extinción (no USC) |
| S2-3 | Tests offline + scorecard multi-CCAA | Tras S2-1/2 |

### Sprint 3 — Piloto humano (2–3 semanas)

| ID | Tarea |
|----|--------|
| S3-1 | Informe 2 págs Níjar/Caminomorisco + Tobarra: qué ML dice / cuándo se calla |
| S3-2 | 2–3 demos (EXT contacto, 1 técnico; USC solo si piden feedback teórico) |
| S3-3 | Decisión: mantener `research_open` fusion o revertir |

---

## 5. Siguiente paso concreto (ejecutar ya)

### P0 — Arreglar CI en `main`

**Por qué es el siguiente paso (no otro email ni otro modelo):**

1. **Gmail no desbloquea producto hoy:** AND + EXT + CLM ya en casa; USC acaba de cerrar el canal de datos; Galicia Extinción y CyL son espera.
2. **CI failed** en `3cfc28a` (y en commits ML previos): CodeQL **success**, workflow **CI failure**.
3. Bloquea confianza externa y cualquier promote serio.
4. Acotado y medible (Actions verde).

**Checklist:**

```text
1. Abrir https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/runs/30032071338
2. Reproducir local:
   $env:PYTHONPATH = "."
   python -m pytest tests/ -q -m "not slow and not requires_weights" --tb=line
3. Corregir fallos (candidatos: SplitContext, scorecard schema, promote paths, ruff/mypy)
4. Push fix → CI success en main
5. Solo entonces Sprint 1 (ML live → Decision Card)
```

**Run de referencia:** CI #96, SHA `3cfc28a`, conclusion `failure`  
https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/runs/30032071338

| Job | Resultado |
|-----|-----------|
| Tests (Python 3.11) | **FAIL** — step “Run tests with coverage” |
| Tests (Python 3.12) | **FAIL** — step “Run tests with coverage” |
| Lint & Type-check | **FAIL** — step “Ruff lint” |
| ML smoke test | success |
| Docker build | success |
| CodeQL (otro workflow) | success |

---

## 6. Roadmap de una página

```text
[AHORA]  Fix CI main  ← siguiente paso único
   │
   ▼
[1] ML live JSON → Decision Card (AND/EXT/CLM ya en casa)
   │
   ▼
[2] Si email CyL (≤17 ago) o GAL Extinción → pack + test
   │
   ▼
[3] Piloto humano + informe honesty
   │
   ▼
[4] Solo entonces: bajar ECE / retrain / field_ops fusion
```

**Emails en paralelo (bajo coste, no bloquean código):**

| Cuándo | Acción |
|--------|--------|
| Ahora | **Nada urgente** de outreach |
| ~1 ago (si silencio >10 d) | 1 follow-up corto Galicia Extinción |
| Si CyL pide aclaración | Responder formal; si no, esperar hasta ~17 ago |
| Opcional | 1 mail ASEMA (no re-pedir REDIAM); 1 respuesta Fraunhofer con brief |
| Nunca sin presupuesto | INIA contrato |
| No más | Fríos multi-CCAA; insistir a USC por datos |

---

## 7. Anti-plan (no hacer)

- Más emails fríos multi-CCAA.
- Insistir a USC por perímetros (respuesta 24 jul: no tienen acceso).
- Encender `field_ops` live fusion.
- Mezclar claim IoU 0.8963 con U1 TEST en el pitch.
- Contratar INIA sin presupuesto.
- Retrain ensemble “por si acaso” sin CI verde y sin demo Decision Card.
- Mezclar trabajo VisionSetil en este sprint WFD.

---

## 8. Resumen ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| ¿Datos suficientes para programar? | **Sí** — CLM + AND + EXT |
| ¿Bloquea algún email el producto? | **No** (GAL/CyL son upside) |
| ¿Novedad hoy? | USC **cierra** canal datos (Díaz-Varela) |
| ¿Siguiente paso de código? | **Arreglar CI en main** |
| Después | Demo ML → Decision Card con packs ya en casa |

---

*Plan generado 2026-07-24 a partir de relectura de hilos Gmail (§1) y Actions API (CI failure en `3cfc28a`). Supersede `PLAN_PROGRAMACION_EMAILS_20260723.md` en el punto USC y en la fecha del siguiente paso.*
