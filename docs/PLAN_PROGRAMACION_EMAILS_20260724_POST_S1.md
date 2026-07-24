# Plan de programación — post Sprint 1 (2026-07-24, tarde)

| Campo | Valor |
|-------|--------|
| **Fuentes** | Gmail re-leído (inbox + hilos incendios jun–jul 2026); repo `main` @ `573fa7a` |
| **Objetivo** | Priorizar ingeniería con **datos ya en casa** y **blockers reales** |
| **Siguiente paso (único)** | ~~P1 piloto pack~~ **HECHO** (loop-engineering 2026-07-24). Siguiente: confirmar CI + opcional ECE lab / emails CyL-GAL |

---

## 0. Delta vs plan de la mañana (`PLAN_PROGRAMACION_EMAILS_20260724.md`)

| Item | Mañana 24 jul | **Ahora** |
|------|---------------|-----------|
| CI `main` | Rojo @ `3cfc28a` | **Verde** @ `5f2d0f6` (CI #98); Sprint 1 push `573fa7a` en vuelo |
| Sprint 0 (CI) | Siguiente paso | **Cerrado** |
| Sprint 1 (ML → Card) | Pendiente | **Cerrado + pushed** (`573fa7a`) |
| Emails datos | AND/EXT GO; USC cierra datos | **Sin mails nuevos** de CCAA desde Díaz-Varela / RAI “Gracias” |
| Scorecard lab | U1 TEST honest | Sin cambio: IoU eval ~0.857, ECE ~0.15, `ml_product_go=false` |
| Policies | research_open fusion exp. ON | **field_ops fusion OFF**; research_open **ON** experimental |

---

## 1. Inventario Gmail (incendios / datos)

### 1.1 Hilos con respuesta (sin novedad desde última lectura)

| Hilo | De | Última fecha útil | Estado | Acción |
|------|-----|-------------------|--------|--------|
| **REDIAM Andalucía** | `rediam.atiende.csma@` | 22 jul | **GO** públicos (perímetros + áreas) | Packs en repo; ASEMA sin reply |
| **RAI Extremadura** | `rai@juntaex.es` | 22–23 jul | **GO** 3 SHP 2025 + “Gracias” (form OK) | Packs en repo; trámite cerrado |
| Galicia Planificación | `forestal.mediorural@` | 22 jul | → Defensa do Monte | Hecho |
| Galicia Defensa do Monte | `defensadomonte.mediorural@` | 22 jul | Traslado a **Extinción**; sin SHP | **Esperar**; follow-up ~**1 ago** si silencio |
| **USC Díaz-Varela** | `ramon.diaz@usc.es` | **24 jul** | Uni **sin datos**; pedir a Xunta Prevención | **No insistir por datos a USC** |
| CyL Nuria Ramos / transparencia | `nuria.ramos@` / `accesoinformacion@` | 17 jul | Acuse **4082/2026**; plazo ~**17 ago** | Esperar; no reenviar |
| CTFC Brunet / Duane | CTFC | 16–17 jul | Sin datos; FIRE-RES cerrado | Cerrado |
| INIA Madrigal | `incendio@inia.csic.es` | 17 jul | Solo contrato de pago | No insistir |
| Fraunhofer / Firelogue | Berchtold | 17 jul | Zenodo + pide concretar | Opcional 1 reply (no bloquea) |

### 1.2 Enviados sin respuesta útil

- ASEMA / DG incendios Andalucía  
- INFOEX DG Bayón (superado por RAI)  
- Heligrafics / CMA metadatos CLM  
- Ruido reenvíos Galicia 22 jul  

### 1.3 Inbox reciente no-WFD (ignorar en plan producto)

- VisionSetil (Picek, iNaturalist, CI VisionSetil)  
- Airbus / FUE, prácticas, InfoJobs, etc.  
- GitHub: fallo CI intermedio `54b3b7a` (pre-fix mypy); **no reabrir** — superado por `5f2d0f6` verde  

### 1.4 Conclusión email

**Ningún email nuevo desbloquea datos hoy.**  
AND + EXT + CLM bastan para piloto y demo. GAL/CyL = upside de espera.

---

## 2. Estado ingeniería (repo)

### Commits relevantes en `main`

| SHA | Qué |
|-----|-----|
| `573fa7a` | **Sprint 1**: `run_ml_live_card_demo`, fixtures offline, pitch U1 honest, abstain/ECE note |
| `5f2d0f6` / `54b3b7a` | **CI verde** (ruff + mypy clean-venv + tests) |
| `3cfc28a` … | ML rails, U1 TEST honest, nested CV, research_open promote |

### Producto dual

| Superficie | Estado |
|------------|--------|
| Ops `front_dynamics_v1` | Decision Card GO/HOLD/ABSTAIN |
| ML ensemble v34 | Uncertainty + U1 TEST honest (scorecard lab) |
| Demo | `scripts/run_ml_live_card_demo.py` offline/live/from-json |
| Fusion | `research_open` experimental ON · **`field_ops` OFF** |
| Claims | Pitch: U1 ~0.86 / sel@80 / ECE ~0.15; **0.8963 provenance only** |

### Datos en casa

| CCAA | Pack / material |
|------|-----------------|
| CLM | Tobarra OPS gold (LWIR) |
| Andalucía | REDIAM + Níjar + PSB |
| Extremadura | RAI 3 SHP 2025 (Caminomorisco, Alburquerque, Burguillos) |
| Galicia / CyL | Solo admin; **sin pack** |

### Artefactos demo

- `scripts/run_ml_live_card_demo.py`  
- `tests/test_ml_live_card_demo.py` + fixtures `tests/fixtures/ml/`  
- `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md`  
- Scorecard: `docs/ML_PRODUCT_SCORECARD.json` (`u1_test_honest=true`, `ml_product_go=false`)  

---

## 3. Qué falta (priorizado)

| P | Item | Tipo | Depende de email |
|---|------|------|------------------|
| **P0** | Confirmar CI **verde** en `573fa7a` (run en curso al redactar) | Ingeniería | No |
| **P1** | **Piloto pack real**: open/ops pack → live o offline metrics → Card + **informe 2 págs** honesty | Producto | No (datos en casa) |
| **P1** | Cablear demo con **pack AND o EXT real** (no solo fixture sintético) en el script | Ingeniería | No |
| **P2** | ECE TEST ~0.15 → bajar o abstain más agresivo (sin retrain masivo primero) | ML lab | Pesos locales |
| **P2** | CyL pack si resuelven 4082 (deadline silencio ~17 ago) | Datos | Email CyL |
| **P2** | Galicia pack si Extinción envía SHP | Datos | Email GAL |
| **P3** | 1 follow-up ASEMA / 1 reply Fraunhofer (opcional) | Outreach | Email |
| **P3** | `field_ops` live fusion | Producto | No — solo tras piloto + ECE |
| **P3** | INIA contrato | Negocio | Presupuesto |

---

## 4. Plan por sprints (actualizado)

### Sprint 0 — CI  
**Estado: HECHO** (`5f2d0f6` CI success).

### Sprint 1 — ML en Decision Card  
**Estado: HECHO** (`573fa7a`).

### Sprint 2 — **Siguiente (esta / próxima semana)** — Piloto honesty multi-pack  
**Objetivo:** que un técnico vea *en packs reales* qué dice el ML y cuándo se calla.

| ID | Tarea | DoD |
|----|--------|-----|
| **S2-1** | Extender `run_ml_live_card_demo` (o wrapper) a **1 pack open** (Caminomorisco o Níjar) + opcional Tobarra ops metrics | Card JSON + README en `outputs/` con fuentes listadas |
| **S2-2** | Informe **≤2 págs** (MD/PDF): 3 casos (HOLD / ABSTAIN / ML-only vs field_ops); claims U1 honest; disclaimers no-táctico | `docs/PILOT_HONESTY_CARD_*.md` |
| **S2-3** | Tests offline: pack fixture o mock scorecard_pista_b → card path no regresa | pytest verde en CI |
| **S2-4** | Si CI `573fa7a` roja → fix inmediato (bloquea confianza) | Actions green |

**No incluir:** retrain ensemble, field_ops ON, más fríos multi-CCAA.

### Sprint 3 — Datos cuando el email cierre (paralelo, no bloquea)

| ID | Trigger |
|----|---------|
| S3-1 | CyL 4082 resolución o portal + 1 IF → pack open |
| S3-2 | Galicia Extinción SHP → inventory + pack |
| S3-3 | Follow-up Galicia Extinción **~1 ago 2026** si silencio total |

### Sprint 4 — Lab ML (después del piloto pack)

| ID | Tarea |
|----|--------|
| S4-1 | Experiment abstain threshold / ECE residual (nota métrica) |
| S4-2 | Decisión: mantener research_open fusion o revertir |
| S4-3 | Solo entonces valorar field_ops fusion |

---

## 5. Siguiente paso concreto (ejecutar ya)

### P1 — Piloto pack real → Decision Card + informe honesty

**Por qué (no otro email, no retrain):**

1. Gmail **no aporta** datos nuevos; AND/EXT/CLM ya bastan.  
2. Sprint 1 demostró el cable ML→Card con **fixtures**; falta **credibilidad de pack real**.  
3. El pitch ya es U1-honest; el hueco es el **guion de piloto humano** (qué se ve / cuándo ABSTAIN).  
4. ECE/retrain sin piloto es optimización prematura.

**Checklist:**

```text
1. Confirmar Actions verde en 573fa7a
   https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions
2. Elegir 1–2 packs: Caminomorisco (EXT RAI) y/o Níjar (AND) + Tobarra ops si hay métricas
3. Correr / extender run_ml_live_card_demo con open pack + research_open
4. Documentar en MD de 2 págs: decisiones, flags live, disclaimers, no 0.8963
5. Tests offline del path pack→card
```

**Comando arranque (offline actual):**

```powershell
$env:PYTHONPATH = "."
python scripts/run_ml_live_card_demo.py --mode offline --scenario hold
python scripts/run_ml_live_card_demo.py --mode offline --scenario abstain
```

**Emails en paralelo (bajo coste):**

| Cuándo | Acción |
|--------|--------|
| ~1 ago | 1 follow-up corto Galicia Extinción si silencio |
| ≤17 ago | Esperar CyL 4082; solo responder si piden aclaración |
| Opcional | ASEMA 1 follow-up; Fraunhofer 1 reply con brief + scorecard lab |
| Nunca | Fríos multi-CCAA; datos a USC; INIA sin presupuesto |

---

## 6. Roadmap de una página

```text
[HECHO]  CI main verde
[HECHO]  Sprint 1 ML live → Decision Card (fixtures + pitch U1)
   │
   ▼
[AHORA]  Piloto pack real AND/EXT/CLM + informe honesty 2 págs
   │
   ▼
[ESP]    Email CyL / GAL Extinción → pack (si llega)
   │
   ▼
[LUEGO]  ECE / abstain lab · decidir research_open · (nunca field_ops sin piloto)
```

---

## 7. Anti-plan

- Más outreach frío multi-CCAA.  
- Insistir a USC por perímetros.  
- Encender `field_ops` live fusion.  
- Pitch con 0.8963 como certeza en vivo.  
- Retrain “por si acaso” sin informe de piloto.  
- Mezclar VisionSetil en sprints WFD.  

---

## 8. Resumen ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| ¿Emails nuevos de datos? | **No** (último útil: USC cierra, RAI cerrado) |
| ¿Datos suficientes? | **Sí** — CLM + AND + EXT |
| ¿CI / Sprint 1? | CI fix **hecho**; Sprint 1 **hecho y en main** |
| ¿Siguiente paso código? | **Piloto pack real + informe honesty** |
| ¿Blocker email? | **Ninguno** |

---

*Plan 2026-07-24 post-S1. Supersede el “siguiente paso = fix CI” del plan matinal del mismo día.*
