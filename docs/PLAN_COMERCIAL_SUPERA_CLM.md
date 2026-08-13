# Plan largo — superar “solo CLM” y poder vender

> **Glosario (2026-08-12):** **`VENTA_GO` ≠ `GO_Q`**.  
> - **`VENTA_GO`** = empaque dual-track E1–E6 / scorecard `demo_sellable` (packaging).  
> - **`GO_Q`** = gate de producto (**partial** hasta demo tercero + acta firmada).  
> - **`VENTA_GO=true` no autoriza outbound, LinkedIn, web ni “field sell-ready”.**  
> - field_ops ML fusion **ON** (cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho · FREEZE_ML · no inventar métricas. Embargo outbound intacto.

> **Método:** loop-engineering · dual-track (A CLM + B open) · métricas honestas  
> **Inicio ejecución:** 2026-07-17  
> **Principio:** no se “vence” a CLM en IoU inventando datos; se **supera el producto vendible** en ejes que el mercado paga y CLM-solo no cubre.

---

## 1. Qué significa “mejor que CLM” (definición de venta)

**CLM hoy (fuerte):**
- Secuencias LWIR reales + máscaras
- Ensemble ML v34 IoU **0.8963** Δ **+0.2545** (holdout) — provenance only, ≠ ROS
- Ops ROS local Tobarra (ancla A)
- Dependencia: Heligrafics/Pablo, anclas confirmadas según SSOT

**“Mejor para vender” = score multi-eje ≥ CLM-solo en 4/6 y sin regresión en honestidad:**

| Eje | Peso | CLM-solo | Target vendible | Cómo ganar |
|-----|------|----------|-----------------|------------|
| **E1 Reproducibilidad demo** | 20% | Baja (datos privados) | Alta | CEMS public download |
| **E2 Multi-incendio público** | 20% | 0 perímetros open | ≥3 packs open | EMSR + index |
| **E3 Escala de evento** | 10% | Tobarra ~39 ha | 10²–10³ ha | CEMS 1–3k ha |
| **E4 Validación geométrica** | 15% | O2 BLOCKED nacional | O2 CEMS GO_PROXY + Hausdorff | multi-MONIT |
| **E5 Producto empaquetado** | 20% | scripts técnicos | one-pager + demo 1 cmd + mapa | comercial |
| **E6 ML transfer** | 15% | v34 fuerte | Mantener / no regresar | no tocar holdout |

**No se reclama:** “nuestro IoU es mejor que CLM en Cardoso” usando CEMS.  
**Sí se reclama:** “producto dual: (1) frente térmico CLM cuando hay dron, (2) perímetro/timeline open-data en IF grandes sin NDA, listo para **ensayo** comercial”.

### Gate VENTA_GO (packaging only — not GO_Q)

```
VENTA_GO =
  (E1 demo open reproducible) AND
  (E2 ≥ 3 packs CEMS o 2 packs + índice multi-IF) AND
  (E5 one-pager + demo script + mapa) AND
  (E6 v34 no regresa) AND
  (scorecard comparativo publicado)
```

**Does not imply:** GO_Q complete · field_ops fusion ON · outbound cleared · silent-GO ≤1e-6.

### Gate VENTA_GO+ (stretch packaging)

```
VENTA_GO+ = VENTA_GO AND
  (contacto ops o carta de interés) AND
  (perímetro nacional o 2ª ancla CLM) AND
  (pricing/pilot offer 1 página)
```

Still **≠ GO_Q**.

---

## 2. Arquitectura de producto vendible

```
┌─────────────────────────────────────────────────────────┐
│  WildfireFrontDynamics — Dual Product (sellable pack)   │
├──────────────────────┬──────────────────────────────────┤
│  A · Thermal Front   │  B · Open Perimeter Intelligence │
│  (CLM / Heligrafics) │  (CEMS / EFFIS / public)         │
│  · incident_runtime  │  · open_if packs                 │
│  · ROS local + ancla │  · multi-MONIT area/ROS proxy    │
│  · clm_ensemble_v34  │  · Hausdorff CEMS↔CEMS           │
│  · NDA / campo       │  · zero NDA demo                 │
└──────────────────────┴──────────────────────────────────┘
           │
           ▼
   Demo comercial unificada + scorecard + one-pager
   (outbound still needs Claims + Alonso)
```

---

## 3. Roadmap largo (12 semanas, no solo 1 mes)

### Fase 0 (hecha / en curso)
- v34 ML + incident runtime
- Pista B EMSR578/583 packs
- Field kit, dual product docs

### Fase 1 — Empaque de venta (sem 1–2) ← **ahora**
1. Índice multi-pack open_if  
2. Scorecard **CLM vs Open** (ejes E1–E6)  
3. One-pager comercial ES (sin claims inventados)  
4. Demo one-command sellable  
5. ≥1 activación CEMS adicional (famosa / multi-MONIT)

### Fase 2 — Credibilidad técnica (sem 3–6)
1. Parsear tiempos de adquisición CEMS (XML/metadata) → ROS con Δt real  
2. Overlay FIRMS en bbox pack  
3. dNBR Sentinel (STAC) opcional post-fuego  
4. 5+ packs en catálogo + mapa índice Europa/ES  
5. Benchmark ForeFire (opcional) vs perímetro CEMS en 1 caso

### Fase 3 — Piloto comercial (sem 7–10)
1. Oferta piloto 4–8 semanas (precio / entregables)  
2. Landing/README “qué compran”  
3. SLA demo: rebuild pack < 10 min  
4. Legal: disclaimers CEMS vs táctico  
5. 3 llamadas / emails a GEACAM, Heligrafics, bomberos autonómicos (**Alonso send**)

### Fase 4 — Escala (sem 11–12+)
1. API mínima `open_if` + `incident` status  
2. Multi-tenant outbox  
3. Integración GIS (WMS/export)  
4. Si datos CLM nuevos → v35 ML (solo con OK Alonso; default FREEZE)

---

## 4. Propuesta de valor (texto de venta, 30 s)

> “Medimos la **dinámica de frente real** cuando hay cámara térmica en campo (CLM),  
> y cuando no, entregamos **inteligencia de perímetro open-data** (Copernicus EMS)  
> con timeline, crecimiento y mapas en minutos — sin esperar NDA ni un solo incendio ancla.”

---

## 5. Kill list comercial

- Prometer extinguishment / despacho táctico  
- Decir que CEMS = perímetro catastral nacional  
- Vender IoU ML como ROS de dron  
- Equivaler **VENTA_GO** a **GO_Q** / field sell-ready  
- Silent-GO ≤1e-6 / “cinco nueves” contractuales  
- Demo que solo funciona en un PC con 200 GB de Dropbox  

---

## 6. Checklist VENTA_GO (packaging — actualizar cada iteración)

- [x] Pack open multi-temporal (EMSR578/583/581/632)  
- [x] Índice multi-IF + comparación CLM (`COMPARE_CLM_VS_OPEN*`)  
- [x] One-pager comercial (`ONEPAGER_COMERCIAL_ES.md`) — hygiene 2026-08-12  
- [x] Demo 1 comando (`scripts/demo_sellable_product.py`)  
- [x] ≥3 activaciones (4 packs; max ~5.3k ha EMSR632)  
- [x] Scorecard E1–E6 → **VENTA_GO = true** (dual ~95 vs CLM-solo ~39, 5/6 ejes) — **packaging only**  

**Verificación 2026-07-17:** `python scripts/demo_sellable_product.py --skip-build` → `venta_go: true`.  
**GO_Q (2026-08-12):** sigue **partial** (`go_q_met=false` hasta demo+acta).

---

*Documento vivo. La venta se gana con demo + honestidad + multi-fuente, no con un solo IoU.*
