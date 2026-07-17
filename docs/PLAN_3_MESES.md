# Plan 3 meses — WildfireFrontDynamics (loop-engineering)

| Campo | Valor |
|-------|--------|
| **Horizonte** | 2026-07-17 → 2026-10-17 (~13 semanas) |
| **Norte** | Producto **pagable**: Decision Card + audit + métricas + dual (ops LWIR / open CEMS) + ML v34 documentado |
| **No-norte** | Mapitas gratis, IoU como extinción, 99.9999% de acierto del fuego |
| **Método** | Hipótesis → un cambio → métrica → GO/NO_GO → adaptar plan |
| **Revisión** | Cada ciclo: `python scripts/run_plan_cycle.py` actualiza `docs/PLAN_3_MESES_STATUS.json` |

---

## 0. Línea base (congelada al arrancar)

| Activo | Estado | Evidencia |
|--------|--------|-----------|
| ML | `clm_ensemble_v34` IoU 0.8963 Δ 0.2545 | manifest |
| Ops | incident_runtime + Tobarra A | smoke + anchors |
| Open | 4 packs CEMS (máx ~5.3k ha) | outputs/open_if |
| Producto | Decision Card + Metrics Hub + reliability gate | `wildfire_front/product/` |
| Venta narrativa | One-pager audit/abstención | ONEPAGER_COMERCIAL_ES |
| Bloqueos | O1 2ª ancla, O2 nacional | externos |

---

## 1. Objetivos de trimestre

### GO_Q (mínimo a 3 meses)

```
GO_Q =
  (Decision Card en CLI incident + open_if) AND
  (Metrics Hub regenerable en CI/make) AND
  (Reliability gate en make product-gate PASS) AND
  (≥6 packs open O 4 packs + FIRMS overlay + Δt mejorado) AND
  (1 piloto documentado O 10 contactos con 2 respuestas) AND
  (v34 no regresa: IoU ≥ 0.890) AND
  (informe trimestre 8–12 pp)
```

### GO_Q+ (stretch)

```
GO_Q+ = GO_Q AND
  (2ª ancla CLM confirmed O perímetro nacional 1 IF) AND
  (carta de interés / presupuesto piloto) AND
  (API mínima decision-card JSON)
```

---

## 2. Tres meses (fases)

### Mes 1 — Producto de decisión (sem 1–4)

**Tema:** que el entregable sea una **decisión auditada**, no un zip de mapas.

| ID | Entrega | Métrica | Status |
|----|---------|---------|--------|
| M1.1 | Plan 3M + cycle runner | status JSON auto | **DONE** |
| M1.2 | Decision Card CLI (`wildfire-front decide`) | test + smoke | **DONE** |
| M1.3 | Metrics hub en `make product-gate` | always green | **DONE** |
| M1.4 | FIRMS overlay bbox open packs | geojson + count | **DONE** (script; 0 hotspots si CSV 24h vacío en bbox histórico) |
| M1.5 | Parse CEMS acquisition time si existe en XML | Δt real en ≥1 pack | **AT_RISK** → diferido (props CEMS sin tiempo útil) |
| M1.6 | 6ª activación CEMS o 5ª con multi-MONIT | n_packs ≥ 5 | **ADAPT:** 4 packs OK demo; 5ª bajo demanda |
| M1.7 | One-pager + pricing plantilla | doc | **DONE** |
| M1.8 | Review M1 + adaptar Mes 2 | status | **DONE** (cycle runner) |

**Kill M1:** no reabrir bucle ML infinito; no claim 99.9999% fuego.

### Mes 2 — Campo y credibilidad (sem 5–8)

| ID | Entrega | Métrica |
|----|---------|---------|
| M2.1 | Integrar Decision Card en `incident update` outbox | artifact en outbox |
| M2.2 | Multi-ancla: Cardoso o open-source Vp documentado | O1 progress |
| M2.3 | dNBR/STAC opcional post-fuego 1 pack | layer o BLOCKED doc |
| M2.4 | 10 outreach (GEACAM, Heligrafics, bomberos, Firelogue) | CSV updated |
| M2.5 | Piloto script: rebuild pack < 10 min SLA medido | latency json |
| M2.6 | Informe técnico v1.1 CMA dual + FDC | DOCX/MD |
| M2.7 | Review M2 + adaptar Mes 3 | status |

### Mes 3 — Piloto y cierre (sem 9–13)

| ID | Entrega | Métrica |
|----|---------|---------|
| M3.1 | API/CLI `decide` + `metrics-hub` estable | version tag |
| M3.2 | 1 demo con tercero (acta 1 página) | doc |
| M3.3 | GO_Q scorecard final | JSON |
| M3.4 | Memoria trimestre / TFG capítulos producto | 8–12 pp |
| M3.5 | Backlog Q2 (solo si GO_Q) | 1 página |
| M3.6 | Tag `v1.1-decision-card` | git |

---

## 3. Ritual de adaptación (cada ciclo)

1. Correr `python scripts/run_plan_cycle.py`  
2. Lee evidencias (hub, packs, tests, git)  
3. Marca DONE/BLOCKED/AT_RISK en status  
4. Si bloqueo externo > 14 días → pivot (más open / menos wait Pablo)  
5. Commit status + cambios de código del ciclo  

---

## 4. Capacidad (1 persona)

| Área | % tiempo |
|------|----------|
| Producto decisión / reliability | 35% |
| Open data + métricas | 25% |
| Ops incident / CLM campo | 20% |
| Outreach / docs venta | 15% |
| ML solo si datos nuevos | 5% |

---

## 5. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Nadie paga FDC | Demo con ABSTAIN real; venta a calidad/IT no solo mando |
| Solo open CEMS | Pivot a “audit layer” sobre herramientas que ya usan |
| Pablo no responde | O1 open-proxy + no parar mes |
| Scope creep FIRE-RES | Solo cita + FDC, no CFD |

---

## 6. Enlaces vivos

- Status: `docs/PLAN_3_MESES_STATUS.json`  
- Metrics: `docs/METRICS_HUB.md` / `METRICS_DASHBOARD.html`  
- Producto: `docs/PRODUCT_REDESIGN_PAID_VALUE.md`  
- Open IF: `docs/PISTA_B_OPEN_IF.md`  
- Comercial: `docs/ONEPAGER_COMERCIAL_ES.md`  
