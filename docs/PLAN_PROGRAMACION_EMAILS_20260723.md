# Plan de programación — estado Gmail + producto (2026-07-23)

| Campo | Valor |
|-------|--------|
| **Fuentes** | Gmail (inbox/sent ~jun–jul 2026) + repo WFD (`main` @ `3cfc28a`) |
| **Objetivo** | Priorizar trabajo de ingeniería según datos ya abiertos y blockers reales |
| **Siguiente paso (único)** | **P0 — Arreglar CI en `main`** (ver §5) |

---

## 1. Inventario de emails (por hilo)

### 1.1 Datos CCAA — respuestas con contenido

| Hilo | De | Fecha | Resultado | Acción pendiente |
|------|-----|-------|-----------|------------------|
| REDIAM Andalucía | `rediam.atiende.csma@` | 22 jul | **GO datos públicos**: perímetros 2008–2025 + áreas recorridas; apunta a Agencia de Emergencias AND | Ingeniería: ya parcialmente industrializado; opcional ASEMA follow-up |
| RAI Extremadura | `rai@juntaex.es` | 22–23 jul | **GO 3 SHP 2025** + Word; Alonso envió petición rellena; RAI **“Gracias”** | Trámite registro OK; usar packs en demo/E2E |
| DG Medio Natural EXT | `dgcpatymn.agmn@` | 22 jul | Reenvío a `dgpeiiff.prs@juntaex.es` | No prioritario si RAI ya dio datos |
| Galicia Planificación Forestal | `forestal.mediorural@` | 22 jul | Competencia = **Defensa do Monte** | Hecho (reenvío) |
| Galicia Defensa do Monte | `defensadomonte.mediorural@` | 22 jul | **Traslado a Extinción**; sin SHP aún | Seguimiento en 7–14 días |
| CyL CDF Nuria Ramos | `nuria.ramos@jcyl.es` | 17 jul | Canal **transparencia** + elegir 1 incendio + portal datos abiertos | Formalizar solicitud (ID entrada **4082/2026** ya recibida) |
| CyL Acceso Información | `accesoinformacion@jcyl.es` | 17 jul | Acuse **4082/2026** | Esperar resolución o completar requisitos si piden más |
| USC Amiama | `carlos.amiama@usc.gal` | 22 jul | Copia a coordinador máster Montes | Esperar; no bloquear ingeniería |
| CTFC Brunet (FIRE-RES) | `pau.brunet@ctfc.cat` | 16 jul | Deriva a **administración CLM** / propuesta regional | No datos; posible puente institucional |
| CTFC Duane | `andrea.duane@ctfc.cat` | 17 jul | FIRE-RES finalizado; deliverables fire-res.eu | Lectura opcional; no canal datos |
| INIA Madrigal | `incendio@inia.csic.es` | 17 jul | **Sin datos**; asesoría solo con **contrato CSIC de pago** | No insistir sin presupuesto |

### 1.2 Enviados sin respuesta útil (no re-spamear)

- ASEMA / DG incendios Andalucía (ops) — sin reply leída.
- INFOEX DG Bayón — superado por canal RAI.
- Varios buzones Galicia/USC del 22 jul (ruido).

### 1.3 Fallos / infra (email)

- GitHub Actions **CI failed** en `main` (p.ej. runs sobre `3cfc28a`, `d8c1ed3`, `2e72629`). CodeQL OK; **CI unit/lint/cov falla**.
- Algunos Delivery Failure históricos por buzones mal formados (ya corregidos en reenvíos).

---

## 2. Qué ya tenemos (ingeniería + datos)

### Datos
| CCAA | Estado datos | Packs en repo |
|------|--------------|---------------|
| CLM | OPS gold Tobarra (LWIR) | Sí (pista A) |
| Andalucía | REDIAM O2 + Níjar gold + PSB | Sí |
| Extremadura | RAI 3 SHP 2025 | Sí (raw + industrial/demo) |
| Galicia | Solo hilo administrativo | No pack |
| CyL | Solicitud 4082/2026 abierta | No pack formal |

### Producto dual
- Ops: `front_dynamics_v1`, Decision Card GO/HOLD/ABSTAIN.
- Open industrial AND/EXT + demo multi-CCAA.
- ML: ensemble v34, uncertainty, U1 **TEST honest**, nested CV VAL, scorecard lab, `research_open` fusion experimental; **field_ops fusion OFF**.

### Artefactos clave
- `docs/ML_PRODUCT_SCORECARD.json`, `docs/ML_U1_PROMOTE_RECORD.json`
- `docs/design/ML_FOCUS_PRODUCT_V1.md`, `docs/PLAN_PROGRAMACION_EMAILS_20260723.md` (este plan)
- Scripts: fit/eval U1, promote, scorecard, progressive burn, packs AND/EXT

---

## 3. Qué falta (priorizado)

| P | Item | Tipo | Dependencia email |
|---|------|------|-------------------|
| **P0** | CI `main` verde | Ingeniería | No (GitHub) |
| **P1** | E2E demo: ML live JSON → Decision Card en un pack real (Níjar o Tobarra) | Ingeniería | Datos ya OK |
| **P1** | No mezclar pitch 0.8963 catálogo con IoU TEST ~0.86 / VAL ~0.74 | Docs/demo | — |
| **P2** | ECE TEST aún ~0.15 — bajar o abstain más agresivo | ML | Pesos locales |
| **P2** | CyL: si resuelven 4082 → pack open + tests | Datos | Email CyL |
| **P2** | Galicia Extinción: si envían SHP → inventory + pack + demo card | Datos | Email GAL |
| **P3** | ASEMA O1/Vp (solo follow-up, no bloquea ML) | Datos | Email |
| **P3** | field_ops live fusion (solo si ECE + piloto humano) | Producto | No aún |
| **P3** | Contrato INIA (pago) | Negocio | Presupuesto |

---

## 4. Plan de programación por sprints

### Sprint 0 — **Siguiente paso (esta semana)**  
**Objetivo:** `CI` verde en `main` + claim público creíble.

| ID | Tarea | DoD | Est. |
|----|--------|-----|------|
| **S0-1** | Diagnosticar fallos del workflow CI en run `30032071338` (pytest/ruff/cov) | Log local reproduce + lista de tests rojos | 0.5 d |
| **S0-2** | Arreglar fallos introducidos por ML rails / scorecard / promote (imports, markers, paths Windows/Linux) | `pytest` CI suite verde en Actions | 1–2 d |
| **S0-3** | Smoke: `test_u1_honest_eval`, `test_ml_focus_protocol`, `test_and_if_pack`, `test_demo_multi_ccaa` en CI | Job success | 0.5 d |
| **S0-4** | Nota en START_HERE: “CI verde + scorecard lab” | 1 párrafo | 0.25 d |

**No incluir en Sprint 0:** retrain masivo, más CCAA, outreach masivo.

### Sprint 1 — ML en el Decision Card (1–2 semanas)
| ID | Tarea | DoD |
|----|--------|-----|
| S1-1 | Script `run_ml_live_card_demo.py`: pack open o fixture → `ml_prediction.json` → `build_decision_card` | HOLD/ABSTAIN documentado |
| S1-2 | Cablear demo multi-CCAA banner ML-first (U1 TEST, no 0.90 confuso) | HTML/guion actualizado |
| S1-3 | Abstain threshold / ECE: experiment corto si conf TEST poco fiable | Nota métrica |

### Sprint 2 — Datos cuando el email cierre
| ID | Tarea | Trigger |
|----|--------|---------|
| S2-1 | Pack CyL open industrial | Resolución 4082/2026 o portal + 1 IF |
| S2-2 | Pack Galicia si llegan SHP | Mail Extinción |
| S2-3 | Tests offline + scorecard multi-CCAA | Tras S2-1/2 |

### Sprint 3 — Piloto humano (2–3 semanas)
| ID | Tarea |
|----|--------|
| S3-1 | Informe 2 págs Níjar/Caminomorisco + Tobarra: qué ML dice / cuándo se calla |
| S3-2 | 3 demos (EXT contacto, USC si responde, 1 técnico) |
| S3-3 | Decisión: mantener research_open fusion o revertir |

---

## 5. Siguiente paso concreto (ejecutar ya)

### P0 — Arreglar CI en `main`

**Por qué es el siguiente paso (no otro email ni otro modelo):**
1. Gmail/GitHub muestran **CI failed** en commits ML recientes; CodeQL pasa → es suite de tests/lint.
2. Bloquea confianza externa y cualquier “promote” serio.
3. No depende de Galicia/CyL/ASEMA.
4. Es acotado y medible (Actions verde).

**Checklist de implementación:**
```text
1. Abrir https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions (run CI fallido en 3cfc28a)
2. Reproducir localmente con la misma matriz (Python 3.11, pytest -m "not slow and not requires_weights")
3. Corregir fallos (típicos candidatos: SplitContext callers, scorecard schema, promote paths, imports)
4. Push fix → CI success en main
5. Solo entonces Sprint 1 (ML live card demo)
```

**Comando local de arranque:**
```powershell
$env:PYTHONPATH = "."
python -m pytest tests/ -q -m "not slow and not requires_weights" --tb=line
```

---

## 6. Roadmap de una página (orden de batalla)

```text
[AHORA]  Fix CI main
   │
   ▼
[1] ML live → Decision Card demo (datos AND/EXT/CLM ya en casa)
   │
   ▼
[2] Si llega email CyL/GAL → pack + test (no anticipar)
   │
   ▼
[3] Piloto humano + informe honesty
   │
   ▼
[4] Solo entonces: bajar ECE / retrain / field_ops fusion
```

**Emails en paralelo (bajo coste, no bloquean código):**
- Calendario: follow-up Galicia Extinción si silencio >10 días.
- CyL: no reenviar hasta respuesta a 4082/2026 o petición de aclaración formal.
- ASEMA: un solo follow-up corto (no re-pedir REDIAM).

---

## 7. Anti-plan (no hacer)

- Más emails fríos multi-CCAA.
- Encender `field_ops` live fusion.
- Mezclar claim IoU 0.8963 con U1 TEST en el pitch.
- Contratar INIA sin presupuesto.
- Retrain ensemble “por si acaso” sin CI verde y sin demo Decision Card.

---

*Plan generado a partir de lectura de hilos Gmail listados en §1 y estado del repo 2026-07-23.*
