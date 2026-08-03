# Mega-plan: predicción de avance (ROS) para medios institucionales

> **Fecha:** 2026-07-31  
> **Objetivo:** poder **ayudar hora a hora a medios de extinción** diciendo **a qué velocidad puede avanzar** el frente según **masa forestal / vegetación, altura, terreno, viento y humedad** — con honestidad operativa (no despacho táctico ciego).  
> **Ancla de verdad del repo:** Tobarra (LWIR + ancla Vp 7 m/min + perímetros ops Pablo)  
> **Producto actual:** ROS **observado** fuerte; ROS **predictivo fuel+terreno** = plan (aún no shippable como GO de campo)

---

## 0. El problema que vendemos (en una frase)

Los mandos no necesitan solo “un mapa bonito”: necesitan  
**“en esta ladera de matorral de 2 m, con 20 % de pendiente y viento a favor, el frente puede ir a X–Y m/min en los próximos 30–60 min; en el flanco, Z m/min; y si no confiamos, nos callamos (ABSTAIN).”**

Eso exige **tres velocidades distintas** que hoy se confunden:

| Tipo de ROS | Qué es | Estado WFD hoy |
|-------------|--------|----------------|
| **ROS observada** | Medida entre 2 pasadas térmicas / perímetros | **GO eng** (Tobarra A) |
| **ROS potencial física** | Modelo tipo Rothermel / FBP según combustible + pendiente + viento + humedad | **NO implementado como producto** |
| **ROS predictiva híbrida** | Física calibrada con lo observado + incertidumbre | **Plan (este doc)** |

**Regla de oro institucional:**  
`ROS_pred` **nunca** se vende sin banda de incertidumbre y sin opción **ABSTAIN**.  
La física sin observación local es **orientación**; la observación sin física no generaliza a “mañana en otra ladera”.

---

## 1. Qué dice la ciencia (síntesis de muchos estudios)

### 1.1 Modelo clásico de superficie (Rothermel 1972 → BEHAVE / Scott–Burgan 2005)

El modelo de **Rothermel** sigue siendo el núcleo de BEHAVE, FARSITE, FlamMap, NEXUS.  
La ROS de superficie depende, en esencia, de:

| Factor | Efecto (dirección cualitativa) | Evidencia |
|--------|--------------------------------|-----------|
| **Carga de combustible fino** (1-h, 10-h) | ↑ carga fina → ↑ ROS e intensidad | Rothermel 1972; Scott & Burgan 2005 (40 fuel models) |
| **Profundidad del lecho de combustible** | ↑ profundidad (matorral alto) → ↑ ROS en modelos SH/GS | Scott & Burgan SH5/SH7, GS2–GS4 |
| **SA/V** (superficie/volumen) del fino | Fino muerto (agujas, hierba) se propaga más rápido | Rothermel; Mediterranean custom models |
| **Humedad del combustible fino (FMC)** | ↑ humedad → ↓ ROS; hay humedad de extinción por modelo | Burgan & Rothermel; LFMC products USFS/SERDP |
| **Pendiente** | ↑ pendiente a favor → ↑ ROS (componente orográfica) | Rothermel; Salis et al. mediterráneo |
| **Viento medio en la superficie del combustible** | Driver dominante en cabeza; flancos mucho más lentos | Scott 2012 intro fire behavior |
| **Tipo de vegetación / fuel model** | Hierba > matorral fino > bajo bosque denso (a menudo) | Scott–Burgan GR/GS/SH/TU/TL |
| **Cubierta de dosel** | Dosel denso → menos viento en superficie, más litter, a veces ↓ ROS superficial; puede habilitar **fuego de copa** | Van Wagner 1977 crown fire; canopy metrics |

**Órdenes de magnitud (literatura mediterránea / simulaciones):**

- ROS media en casos mediterráneos FARSITE a menudo **~1–15 m/min**; picos locales **>40–100 m/min** en hierba fina + pendiente fuerte (Salis et al. 2016 y similares).  
- Tobarra ops (**~5–7 m/min**) es **plausible** en matorral/pasto mediterráneo con viento moderado — no es un outlier de lab.

### 1.2 Modelos de combustible mediterráneos (España / Grecia / Italia)

Estudios clave a usar como **biblioteca de fuel models**, no como verdad local sin calibrar:

| Estudio / línea | Aporte |
|-----------------|--------|
| **Scott & Burgan 2005** | 40 modelos estándar (GR, GS, SH, TU, TL, SB…) con ROS/intensidad relativa |
| **Dimitrakopoulos & Panov 2002** | Fuel models mediterráneos: pastos, phrygana, maquis &lt;1.5 m / 1.5–3 m |
| **Salis et al.** (Med. FARSITE, ES/IT/GR) | **Fuel models custom mejoran** predicción de área vs modelos genéricos; pendiente y fuel dominan |
| **Vega et al. 2024** (España) | Fuel models custom para **matorral y helecho** (k-medoids) — muy relevante CLM/Noroeste |
| **Elia et al.** (WUI Apulia) | Maquis con poco dosel → ROS/FLI más severos; **altura y carga** del matorral críticas |
| **Kalabokidis / Palaiologou** (Lesvos) | Canopy Cover, CBH, CBD, Tree Height + custom pine/maquis understory |

**Mensaje para CLM / España:**  
No basta con CLC genérico “bosque / matorral”. Hace falta **altura de matorral / carga fina / % cover** (maquis 1–3 m se comporta distinto que pastizal o pinar con hojarasca).

### 1.3 Terreno (altura del suelo, pendiente, cañones)

| Factor | Efecto | Fuente |
|--------|--------|--------|
| **Pendiente** | Acelera a favor de la pendiente; frena en contra | Rothermel; FARSITE |
| **Aspecto** | Sur/SO mediterráneo más seco → FMC más bajo | Clima local + DEM |
| **Cañones / chimeneas** | Aceleraciones y comportamientos extremos | Viegas canyon fire |
| **Confluencias de viento** | Reactivaciones de flanco | Mapas ARGOS Tobarra (SE1/SE2) |
| **Barrancos** | Saltos de zona crítica (ver mapa Pablo 21:33) | Ops INFOCAM |

### 1.4 Altura de vegetación / masa forestal (dosel vs superficie)

| Concepto | Por qué importa |
|----------|-----------------|
| **Altura del matorral / fuelbed depth** | Entra en fuel model (SH/GS); controla ROS superficial |
| **Canopy Base Height (CBH)** | Si la llama alcanza la copa → transición a **crown fire** (Van Wagner) |
| **Canopy Bulk Density (CBD)** | Intensidad y sostenibilidad del fuego de copa |
| **Canopy Cover** | Sombrea y reduce viento en superficie; también produce litter |
| **Biomasa / load (t/ha)** | Intensidad (kW/m) y calor por área; no es lo mismo que ROS |

**Distinción institucional a enseñar en sala:**  
- **Masa forestal alta** ≠ siempre “más rápido”: a veces es **más intenso** y más lento en superficie, o salta a copas.  
- **Matorral fino seco** a menudo es el **más rápido** en cabeza.

### 1.5 Humedad y meteo

| Variable | Producto / fuente típica |
|----------|--------------------------|
| FMC 1-h / 10-h | Modelos de humedad + estación (Aemet) |
| **LFMC** (live fuel moisture) | Productos satélite ML (USFS/SERDP 2025–26) |
| Viento 10 m + rachas | Aemet / ERA5 / estación local |
| T, HR | Aemet (como en mapa Tobarra Pre Análisis) |
| FWI / ISI / BUI | Canadian FWI / EFFIS (índice, no ROS local) |

### 1.6 ML y física híbrida (2024–2026)

| Línea | Uso en el plan |
|-------|----------------|
| **PiNN / physics-informed** (Vogiatzoglou et al.) | Aprender parámetros de un modelo de propagación interpretable |
| **DL surrogates** de simulación (USFS Finney) | Emular FARSITE/FlamMap en tiempo real |
| **NDWS / WildfireSpreadTS** | Next-day **máscara** satélite ≠ ROS m/min de sala |
| **FireCast-Fusion UAV** | Fusión térmico + entorno a corto horizonte |

**Implicación:** el SOTA empuja a **híbridos**: no sustituir Rothermel por una U-Net opaca en sala de mando.

---

## 2. Arquitectura objetivo WFD (híbrido institucional)

```
                    ┌─────────────────────────────┐
   LWIR / pasadas   │  A. OBSERVED ROS (hoy GO)   │──► ROS_obs, grado A/B/C
   Perímetros ops   │  front_dynamics_v1          │    capa frente
                    └─────────────┬───────────────┘
                                  │ calibra / ancla
                                  ▼
┌──────────────┐    ┌─────────────────────────────┐    ┌──────────────────┐
│ Fuel stack   │───►│  B. PHYSICS PRIOR ROS       │───►│  C. HYBRID PRED  │
│ DEM/pendiente│    │  Rothermel-like / FBP-lite  │    │  15/30/60 min    │
│ Viento/FMC   │    │  por sector / pixel         │    │  + incertidumbre │
│ Altura dosel │    └─────────────────────────────┘    │  + ABSTAIN       │
└──────────────┘              ▲                        └────────┬─────────┘
                              │ calibración                      │
                              │                                  ▼
                    ┌─────────┴───────────┐          Decision Card
                    │ D. ML residual      │          GO / HOLD / ABSTAIN
                    │ (opcional, lab)     │          “apoyo a medios”
                    │ no field_ops solo   │
                    └─────────────────────┘
```

### Capas de entrada (stack “mañana a la tarde”)

| Capa | Resolución objetivo | Fuente ES |
|------|---------------------|-----------|
| DEM / pendiente / aspecto | 5–25 m | MDT IGN / Copernicus DEM |
| Land cover / fuel class | 10–100 m | CLC + **fuel model map** custom Med |
| Altura vegetación | 10–30 m | LiDAR PNOA / CHM Sentinel-1/2 proxies |
| Carga / biomasas | 100 m–1 km | mapas regionales / EFFIS fuel |
| Viento | 1–10 km + local | Aemet, ERA5-Land, parte ops |
| FMC / LFMC | 0.5–1 km | producto satélite + estación |
| Frente actual | m–decenas m | LWIR / perímetro ops |
| Validación | — | Vp parte, perímetros Pablo, CEMS |

### Salidas para medios (producto pagable)

| Salida | Unidad | Uso en sala |
|--------|--------|-------------|
| **ROS cabeza / flancos / retaguardia** | m/min (+ banda p10–p90) | Asignar medios a flanco vs cabeza |
| **Mapa de ROS potencial** | capa raster | “dónde se puede disparar” |
| **Envolvente 30/60 min** | polígono + disclaimer | No es perímetro oficial |
| **Drivers** | % contrib. viento/pendiente/fuel | Explicabilidad |
| **Decision Card** | GO/HOLD/ABSTAIN | Cuándo confiar |

---

## 3. Plan por fases (mega roadmap)

### Fase 0 — Congelar el relato (1 semana) ✅ parcialmente hecho

- [x] ROS observada Tobarra  
- [x] Ancla Vp + ha  
- [x] Perímetros ops multi-hora Pablo  
- [ ] One-pager institucional: “observado vs potencial vs predictivo”  
- [ ] Matriz de **no-claims** firmada (este doc §7)

### Fase 1 — Fuel + terreno stack CLM (2–4 semanas) **P0 ingeniería**

| ID | Entrega | DoD | Estado 2026-07-31 |
|----|---------|-----|-------------------|
| **F1.1** | Pipeline DEM: pendiente, aspecto, elevación en bbox IF | GeoTIFF alineado a pack ops | ✅ GLO-30 + **pendiente por sector** (wedges head/flank/rear) |
| **F1.2** | Mapa fuel class v0: CLC → Scott–Burgan **provisional** + tabla Med custom (Dimitrakopoulos / Vega 2024) | JSON + raster | ✅ WorldCover 10 m Tobarra + CLC/WC crosswalk (`fuel/fuel_map.py`); SIOSE local opt-in |
| **F1.3** | Altura vegetación v0: PNOA LiDAR CHM o proxy NDVI×CLC | Raster height_m | 🟡 proxy por fuel model height |
| **F1.4** | Script `build_fuel_terrain_stack.py --fire tobarra` | Artefacto en `outputs/fuel_stack/tobarra/` | ✅ |
| **F1.5** | Tests de CRS/alineación | pytest | ✅ stack + terrain tests |

**No** predice aún en F1 puro; F2 monta el prior físico encima del tablero.

### Fase 2 — Physics prior ROS (3–5 semanas) **P0 ciencia/producto**

| ID | Entrega | DoD | Estado 2026-07-31 |
|----|---------|-----|-------------------|
| **F2.1** | Implementar **Rothermel-lite** o wrapper (`Rothermel` R / python port / BEHAVE tables) por pixel o por sector polar | `ros_potential_m_min` | ✅ `fuel/rothermel_lite.py` |
| **F2.2** | Entradas: fuel model + slope + midflame wind + FMC escenario (p85/p95 como en literatura) | 2 escenarios clima | ✅ banda p10–p90 por FMC/viento |
| **F2.3** | Calibración **Tobarra**: ROS_potential vs ROS_obs y vs Vp 7 | ratio band documentado | 🟡 engineering k recipe single-fire (raw metrics always; not multi-IF) |
| **F2.4** | Salida sectorial (head/flank/rear) alineada con `front_dynamics` | GeoJSON + JSON | 🟡 JSON sectores; GeoJSON envelope P1 |
| **F2.5** | ABSTAIN si falta viento o fuel class = unknown | tests | ✅ |

Referencias de implementación: tablas Scott–Burgan; paquete R `Rothermel`; lógica FlamMap “condiciones constantes por pixel”.

### Fase 3 — Predicción corta 15/30/60 (4–8 semanas) **P1**

| ID | Entrega | DoD | Estado 2026-07-31 |
|----|---------|-----|-------------------|
| **F3.1** | Propagación de frente: normal al frente × ROS_hybrid | máscara/envolvente | 🟡 origin extrusion v3 (no CA mask) |
| **F3.2** | ROS_hybrid = α·ROS_obs + (1−α)·ROS_physics, α↑ si hay pasadas recientes | α en audit | ✅ fuel.hybrid + envelope audit |
| **F3.3** | Ensemble de escenarios (viento ±, FMC ±) → banda | p10/p50/p90 | ✅ hybrid flat head w/ obs + physics_only |
| **F3.4** | Validación temporal Tobarra (ventanas O3) | scorecard | ✅ multi-window scorecard + Pablo context (no O3 LWIR multi-pass yet) |
| **F3.5** | Integración Decision Card política `field_ops` **sin** fusionar ML máscara | reasons honestos | ✅ attach weight=0 audit; no fusion flip |

Producto: `short_horizon_envelope_v3_hybrid` — `wildfire_front/fuel/envelope.py`, `scripts/build_hybrid_envelope.py`, design `docs/DESIGN_ENVELOPE_V3_HYBRID.md`.

### Fase 4 — Multi-IF + Med custom fuels (2–3 meses) **P1 datos**

| ID | Entrega | Dep. |
|----|---------|------|
| **F4.1** | Perímetros multi-IF (Pablo) Cardoso/Hellín/Estrella | Outreach |
| **F4.2** | Fuel models **España** (Vega 2024 matorral/helecho + maquis) | Literatura + GIS |
| **F4.3** | LOFO-style validación: predecir ROS en IF held-out | Datos |
| **F4.4** | CEMS/EFFIS solo como validación de **área**, no de ROS táctica | Ya parcial |

### Fase 5 — ML residual / PINN (opcional, lab) **P2**

| ID | Entrega | Kill si… |
|----|---------|----------|
| **F5.1** | Residual U-Net: error de física vs observado | No bate física calibrada en Tobarra |
| **F5.2** | PiNN de parámetros de Rothermel locales | No interpretable / no estable |
| **F5.3** | **Nunca** `field_ops.allow_ml_live_in_fusion` sin gates | Honesty rails |

### Fase 6 — Producto “medios institucionales” (continuo)

| ID | Entrega |
|----|---------|
| **F6.1** | Brief radio: “cabeza X m/min (banda), flanco Y, drivers: matorral 2 m + pendiente 15 % + viento W” |
| **F6.2** | Capa GIS “dónde NO ir / zona de oportunidad” solo como **extrapolación marcada** |
| **F6.3** | SLA: update cada pasada térmica o cada 30 min con meteo |
| **F6.4** | Formación 30 min a mandos: leen Decision Card + no confunden con orden táctica |

---

## 4. Mapa de variables → acciones de medios (guion sala)

| Condición | ROS típica (orden mag.) | Mensaje a medios |
|-----------|-------------------------|------------------|
| Pastizal fino + viento fuerte + pendiente a favor | Muy alta (decenas m/min posibles en lit.) | Priorizar cabeza; líneas cortafuegos rápidas |
| Matorral 1–3 m (maquis) seco | Alta–muy alta | Flancos + anclar cola; vigilar saltos |
| Pinar con hojarasca, poco viento | Media | Trabajo de liquidación; vigilar copas si CBH baja |
| Dosel denso + viento bajo | Baja en superficie | No confiar en “bosque = lento” si hay matorral bajo |
| Barranco / confluencia | Localmente extrema | No exponer medios en chimenea |
| Sin pasada térmica reciente | Desconocida | **ABSTAIN** predictivo; solo open HOLD |

*(Órdenes de magnitud de literatura; la banda numérica local sale de Fase 2–3 calibrada en Tobarra.)*

---

## 5. Datos abiertos / nacionales a enchufar YA

| Dataset | Uso en plan |
|---------|-------------|
| **MDT25 / MDT05 IGN** | pendiente, aspecto |
| **PNOA LiDAR** | altura dosel / matorral |
| **CLC / SIOSE** | fuel class v0 |
| **Aemet** (ya parcialmente en repo) | T, HR, viento, FWI |
| **ERA5-Land** | relleno espacial |
| **EFFIS fuel / burnt** | contexto regional |
| **CEMS EMSR*** | validación área post-fuego |
| **Mapas ARGOS/INFOCAM** (Pablo) | truth operativa de comportamiento |

---

## 6. KPIs de éxito (no IoU)

| KPI | Target mes 1–3 | Target mes 6 |
|-----|----------------|--------------|
| Tobarra: \|ROS_physics − ROS_obs\| / ROS_obs | &lt; 50 % en cabeza | &lt; 30 % |
| Cobertura mapa fuel+DEM en IF CLM | 1 IF (Tobarra) | ≥ 4 IF |
| Decision Card con drivers fuel/terreno | demo | en incident outbox |
| Falsos “GO tácticos” | 0 | 0 |
| Brief legible por mando no técnico | 1 plantilla | usado en 1 piloto |

---

## 7. No-claims (imprescindible para vender sin quemarse)

1. **No** es un orden de despacho ni sustituye al PMA/INFOCAM.  
2. **No** promete precisión de 15/30/60 min sin banda y sin observación reciente.  
3. **Fuel model genérico** sin calibración local **sobreestima** a menudo el área (Salis et al.).  
4. **Masa forestal alta** no implica siempre ROS alta.  
5. **ML de máscara next-day** (v34) **no** es ROS de frente aéreo.  
6. Perímetros CEMS/EFFIS **no** validan ROS m/min táctica.  
7. Sin viento/FMC fiables → **ABSTAIN** predictivo.

---

## 8. Encaje con el repo HOY

| Módulo actual | Rol en el mega-plan |
|---------------|---------------------|
| `front_dynamics_v1` | Capa **A** (ROS_obs) — base |
| `eval_tobarra_pablo_perimeters` | Validación geométrica / ha multi-hora |
| `decision_card` / policies | Capa de producto y ABSTAIN |
| `fetch_aemet_fwi` | Semilla meteo |
| `cn_physics_prior` / research | Semilla física experimental |
| ML v34 | Solo residual lab (Fase 5), no sala |
| Open CEMS 2026 packs | Contexto área, no ROS |

**Hecho 2026-07-31:** `wildfire_front/fuel/*` + scripts + corpus ~93 estudios + graph v4.  
**Siguiente unidad:** PNOA MDT real + SIOSE/MFE en bbox Tobarra; factor de ajuste tipo Cell2Fire sobre residual physics−obs; envolvente 30/60 min.

---

## 9. Bibliografía mínima de trabajo (para el equipo)

1. Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in wildland fuels*. USDA FS INT-115.  
2. Scott, J.H. & Burgan, R.E. (2005). *Standard fire behavior fuel models*. RMRS-GTR-153.  
3. Scott, J.H. (2012+). *Introduction to Fire Behavior Modeling* (NIFTT / Pyrologix notes).  
4. Van Wagner, C.E. (1977). Conditions for the start and spread of crown fire. *Can. J. For. Res.*  
5. Salis et al. — Predicting wildfire spread in Mediterranean landscapes (FARSITE + custom fuels; ES cases).  
6. Dimitrakopoulos & Panov (2002) — Mediterranean fuel models (Greece).  
7. Vega et al. (2024) — Custom fuel models shrub & bracken (Spain). *J. Environ. Manage.*  
8. Elia et al. — Fuel models Mediterranean WUI; ROS/FLI by fuel type.  
9. Viegas et al. — Canyon / extreme fire behaviour Europe.  
10. Vogiatzoglou et al. (2024–25) — Physics-informed wildfire parameters (PINN).  
11. USFS / SERDP LFMC ML products (2025–26) — live fuel moisture.  
12. Finney / Firelab DL surrogates (2024) — physics emulation.  
13. Repo: `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`, `research/models.md`, Tobarra ops + Pablo KMZ.

---

## 10. Resumen ejecutivo para dirección / CMA

| Pregunta | Respuesta |
|----------|-----------|
| ¿Podemos ayudar mañana a la tarde? | **Sí en ROS observada** si hay pasadas térmicas; **orientación de potencial** solo tras Fase 1–2 |
| ¿Podemos decir velocidad según vegetación y terreno? | **Ese es el plan**: física Rothermel-like + fuel mediterráneo + DEM + altura; calibrado en Tobarra |
| ¿Cuándo es vendible a medios? | Cuando haya banda p10–p90, ABSTAIN, y al menos 1 IF calibrado (Tobarra) con ratio vs obs/Vp documentado |
| ¿Bloqueo principal? | Stack fuel+DEM+altura + meteo en escena; multi-IF perímetros (Pablo); no más retrain ML ciego |

---

*Documento vivo. Actualizar tras Fase 1 con paths reales de rasters y tras primera calibración Tobarra physics vs ops.*
