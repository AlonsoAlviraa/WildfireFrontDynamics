# SOTA stack 2025–2026 — adopción para WildfireFrontDynamics

**Fecha:** 2026-08-04  
**Alcance:** térmico dron + ROS + fusión RGB–TIR · incertidumbre · open source · ecosistema China  
**Regla de oro del repo:** ops ≠ ML ≠ fusión en Decision Card.  
`field_ops.allow_ml_live_in_fusion` permanece **OFF** salvo promote humano explícito.

**Documentos relacionados**

| Doc | Rol |
|-----|-----|
| `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md` | Mejoras implementables SOTA (julio 2026) |
| `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` | Corpus fuel / ROS Med (~93 estudios) |
| `data/fire_intel/literature/corpus_v1.json` | Índice machine-readable |
| `docs/design/DECISION_POLICY.md` | GO / HOLD / ABSTAIN |
| `docs/RELIABILITY_GATE_REPORT.json` | Gate (suite-only; no field unlock) |
| `docs/INCIDENT_RUNTIME_V1.md` | Field kit + outbox + Decision Card |

---

## 0. Mensaje ejecutivo

| Frente SOTA | Madurez 2025–26 | Rol en WFD | ¿Cambia fusión field_ops? |
|-------------|-----------------|------------|---------------------------|
| Repeat-pass TIR → ROS / FI / FRP | Alta (método) | **Capa Ops térmico** | No — la refuerza |
| Fusión RGB–TIR (detección/seg) | Alta (edge) | Upstream de máscara si hay EO | No — fusión sensorial ≠ fusión ML en card |
| UQ epistémica + aleatoria | Alta (paper + código) | **Decision Card + Reliability Gate** | No — endurece ABSTAIN |
| Open source (Pyronear, FEDS, Flamap…) | Alta (producción) | Field kit, open perimeter, sim | No |
| China UAV lightweight + geo-nativo | Alta (detección) | Contrato térmico auditable | No |

**Frase única:** el SOTA fragmentado **valida** el producto dual/triple (ops medido · open · ML lab · card con rechazo), no un “super-modelo táctico”.

---

## 1. Ops térmico: TIR multi-pasada → ROS, FI, FRP

### 1.1 Lampman et al. 2026 (IJWF) — ancla metodológica principal

**Cita:** *Leveraging drone-based thermal imagery and artificial intelligence to advance wildland fire behavior quantification and prediction* — International Journal of Wildland Fire (2026).  
Autores (portal Idaho): P. Lampman et al. · [IJWF WF25133](https://connectsci.au/wf/article/35/5/WF25133/272342/Leveraging-drone-based-thermal-imagery-and)

| Pieza | Contenido |
|-------|-----------|
| Sensor | UAS + TIR |
| Pipeline | Repeat-pass → frentes/tiempo → **ROS, fireline intensity (FI), FRP** |
| ML | ANN + **Random Forest** (features derivadas del TIR) |
| Dominio | Fuego **prescrito de pastizal** (un sitio, un combustible) |
| Headline | MAE &lt; 0.04 m/s · RMSE &lt; 0.06 m/s · R² &gt; 0.90 (corto plazo) |
| Nota modelos | **RF mejor con pocos datos** y menos overfitting que ANN |

**Traducción a unidades WFD (m/min):**

| Métrica paper | m/s | m/min | vs ancla Tobarra Vp ≈ 7 m/min |
|---------------|-----|-------|-------------------------------|
| MAE &lt; 0.04 | 0.04 | **2.4** | ~34 % del Vp |
| RMSE &lt; 0.06 | 0.06 | **3.6** | ~51 % del Vp |

**Relevancia directa:** es casi el pipeline ideal de la capa Ops térmico (`front_dynamics_v1`).  
**Limitación explícita (citar siempre):** un solo sitio + un tipo de combustible; generalización limitada.

#### Uso en Reliability Gate Report

| Uso legítimo | Uso ilegítimo |
|--------------|---------------|
| Ancla **metodológica externa** (repeat-pass TIR → ROS ± FI/FRP) | MAE/R² como SLA de Tobarra/Hellín |
| Recordar que **ellos** limitan dominio | “El SOTA predice ROS táctico en vivo con ML” |
| Apoyar R1–R4 (proceso, abstención, proveniencia) | Desbloquear `field_unlock` o `system_reliability_pass` |

**Párrafo copy-paste (Reliability Gate / demo):**

> La cuantificación de ROS (y, en su caso, FI/FRP) a partir de secuencias TIR multi-pasada UAS está validada en literatura reciente de comportamiento del fuego (p. ej. Lampman et al., Int. J. Wildland Fire 2026). Ese trabajo reporta predicciones de corto plazo muy precisas en un fuego prescrito de pastizal, y advierte de generalización limitada (un dominio, un combustible). WFD adopta el mismo principio de medición geométrica desde LWIR como capa Ops, sin trasladar sus cifras de error a incendios mediterráneos operativos ni usar ML de máscaras como sustituto del ROS observado.

#### Encaje con módulos WFD

| Capa paper | Módulo WFD | Gap |
|------------|------------|-----|
| ROS geométrico TIR | `geometry_speed`, `normal_ray`, multi-estimador, coreg | Ya fuerte |
| FI (fireline intensity) | No producto ops estable | P1: Byram-like o proxy TIR |
| FRP alta res UAV | FRP solo open/FIRMS (km–375 m) | P1: local si radiométrico |
| RF short-horizon | Envelope + `hybrid_ros_prior` | Lab only; RF &gt; ANN si N pequeño |
| ANN | — | Evitar con 1–2 IF |

**Baseline obligatorio antes de promover cualquier RF de ROS:**  
`pred = último ROS observado` (copy). Si no gana en leave-one-window / leave-one-fire → **NO_PROMOTE**.

---

### 1.2 Otros estudios clave (térmico / fusión / física)

| # | Estudio | Año | Qué aporta | Prioridad WFD |
|---|---------|-----|------------|---------------|
| 1 | **FireCast-Fusion** (Abbas et al.) | 2026 | RGB–térmico UAV + env; short-horizon physics-guided | P0–P1 (envelope, no reimplementar red) |
| 2 | **Vogiatzoglou PiNN** ([arXiv:2406.14591](https://arxiv.org/abs/2406.14591)) | 2024–25 | Params de modelo interpretable desde IR (Troy Fire) | P1 lab (calibrar Rothermel-lite) |
| 3 | **FLAME 3** (Hopkins et al.) | 2024 | UAV visual + TIR **radiométrico**; NADIR 3–5 s | P0 datos (eval no-gold) |
| 4 | **RGBT-3M + CP-YOLOv11-MF** (Zhang et al.) | 2025 | Dataset multi-escena RGB–T; detección | P1 si hay EO |
| 5 | **Cardil et al.** (ops ROS bias, CA) | 2023 | Sesgo modelo ops vs ROS observada | P0 doctrina (ya en rails) |
| 6 | **SAR + UAV optical** (Rajagopal et al., Sci Rep) | 2025 | Fusión all-weather | P2 Pista B |
| 7 | **Asimilación UAV → sim** (Ge et al.) | 2024 | DA de obs UAV en spread model | P1 envelope |
| 8 | **UAV + FARSITE DA** | ~2024–26 | Error de perímetro reportado **−53 %** | P1 lab |
| 9 | **Carbonell-Rivera et al.** | 2024 | RoS vs features espectrales/geométricas | P1 features sector |
| 10 | **NASA Wildfire DT / FIRETWIN** | 2024–25 | Twin multi-modal + API ligera | P1 producto (card + outbox) |
| 11 | **Kim Cell2Fire adj.** | 2025 | Factores de ajuste ROS híbridos | P0–P1 (parcial en fuel/) |

```
Paper / SOTA                              WFD hoy
─────────                                 ───────
Repeat-pass TIR → ROS obs            ≈    front_dynamics multi-estimator
TIR → FI, FRP high-res               ≈    (casi vacío en ops; FRP open/FIRMS)
RF/ANN short-horizon ROS             ≈    hybrid/envelope 15–60 (geom + α)
                                          NO modelo ML de ROS en field_ops
```

---

## 2. Fusión RGB–TIR en UAV (detección / segmentación)

### 2.1 Take-away

La fusión multimodal está **madura** para detección y segmentación (humo denso, edge Jetson).  
**Casi nadie** la usa para ROS táctico en vivo.  
→ Refuerza mantener **ML fusion OFF** en `field_ops`.

```
Detección / segmentación RGB–TIR     →  MADURA (2026)
        │
        ▼
Máscara / bbox / humo+llama          →  input a ops
        │
        ▼
ROS / grade / envelope               →  GEOMETRÍA + calidad (front_dynamics)
        │
        ▼
ML next-day / danger maps            →  LAB o research_open
        │
        ▼
field_ops.allow_ml_live_in_fusion    →  OFF
```

**Tres fusiones distintas (no mezclar en demos):**

1. **Fusión de sensores** (RGB + TIR en el pixel) → deseable si hay datos.  
2. **Fusión de productos en la Decision Card** (ops + open + ML live) → solo con política y promote.  
3. **Fusión de labels** (entrenar con ROS inventado) → **prohibido**.

### 2.2 Sistemas 2026

| Sistema | Qué es | Resultado clave | Código / edge | Rol WFD |
|---------|--------|-----------------|---------------|---------|
| **Fire-YOLO26** (Zhang et al., Frontiers Env. Sci. 2026; Sichuan) | Dual-stream NMS-free YOLO26 + **T-FAM** (thermal-guided alignment) | FLAME 2: mAP@0.5 alto; **humo denso 71.5 % → 95.1 %** mAP@0.5; ~23 FPS Orin NX (nano) | Edge-ready | Upstream máscara si EO+LWIR |
| **RoboFireFuseNet** (Fotiou et al.) | Atención RGB+IR; llama **y** humo; real-time | Seg robusta cuando la llama se oculta | [github.com/dimfot3/RoboFireFuseNet](https://github.com/dimfot3/RoboFireFuseNet) | Mejor candidato lab (open code) |
| **YOLO-MMSC** (Wang et al., Wuhan; MDPI RS 2026) | RGB–TIR edge para **corredores de transmisión** | 94.6 % mAP@0.5, **60 FPS** Orin NX; ops 120–180 m (Matrice 4T) | Edge industrial | Template latencia/FOV, no ROS |

### 2.3 Prioridad si hay EO + LWIR alineados

| Prioridad | Acción | Por qué |
|-----------|--------|---------|
| **P1 lab** | Evaluar **RoboFireFuseNet** en un par Tobarra EO/LWIR | Código abierto |
| **P2** | T-FAM-style: TIR guía RGB (idea Fire-YOLO26) | “Térmico manda en humo” |
| **P3** | Benchmark FPS estilo YOLO-MMSC en Jetson | Solo si producto edge Heligrafics |
| **Never** | Vender mAP del detector como fiabilidad de ROS | Kill list demo |

---

## 3. Uncertainty-aware forecasting (Orion-AI-Lab)

### 3.1 Paper y código

**Paper:** Kondylatos, Papadopoulos, Camps-Valls, Papoutsis — *Uncertainty-Aware Deep Learning for Wildfire Danger Forecasting*  
([arXiv:2509.25017](https://arxiv.org/abs/2509.25017))  
**Código:** [github.com/Orion-AI-Lab/uncertainty-wildfires](https://github.com/Orion-AI-Lab/uncertainty-wildfires)  
**Datos:** Zenodo (ver paper)  
**Origen:** Orion Lab / NOA + NTUA + Camps-Valls  

| Dimensión | Contenido |
|-----------|-----------|
| Tarea | **Danger forecasting** corto plazo (next-day; exploran hasta ~10 días) |
| Modelos | BNN (variational inference) + **Deep Ensembles** |
| Incertidumbre | **Epistémica** (modelo) + **aleatoria** (datos) **juntas** |
| Mejoras reportadas | +~2.3 % F1 · **−~2.1 % ECE** vs baseline determinista |
| Ops-like | Umbrales de rechazo; mapas de peligro **+ capa de incertidumbre** |
| Horizonte | Aleatoria ↑ con lead time; epistémica más estable |

### 3.2 Oro puro para Decision Card

| Concepto | Definición | En WFD hoy | Upgrade |
|----------|------------|------------|---------|
| **Aleatoria** (datos) | Ruido / ambigüedad de la obs | grade, n_frames, coreg, FOV | Explicitar `u_data` en card |
| **Epistémica** (modelo) | “No hemos visto esto” | conf ML lab, LOFO, ECE | Solo research_open |
| **Rechazo por umbral** | u alta → no GO | GO / HOLD / **ABSTAIN** | Mapear u → tres vías |
| **Calibración** | ECE | lab ECE ensemble | Reliability Gate R3 |

```
Orion / CRC                          WFD Decision Card
─────────────────                    ─────────────────
low uncertainty + high skill    →    GO
mid / watch band                →    HOLD
reject (u > λ)                  →    ABSTAIN
```

**Dominio distinto:** Orion = peligro regional satelital-ambiental.  
WFD ops = frente térmico local.  
WFD ML = máscara next-day España.  
→ Se copian **rails de confianza**, no pesos.

**Párrafo copy-paste:**

> Modelos recientes de wildfire danger con incertidumbre epistémica y aleatoria (BNN, deep ensembles; Kondylatos et al., Orion-AI-Lab, arXiv:2509.25017) mejoran calibración y permiten rechazar predicciones de baja confianza. WFD aplica la misma lógica operativa en la Decision Card como GO/HOLD/ABSTAIN, con umbrales ligados a la calidad de la observación térmica y a la política `field_ops` (ML live fusion desactivada). No se emiten órdenes de evacuación.

### 3.3 Conformal risk control (SAFE / MONITOR / EVACUATE)

**Paper:** *Conformal Risk Control for Safety-Critical Wildfire Evacuation Mapping* ([arXiv:2603.22331](https://arxiv.org/abs/2603.22331)) — three-way CRC.

| CRC paper | Decision Card WFD | Semántica honest |
|-----------|-------------------|------------------|
| SAFE | GO (fuentes ok) | “Obs suficiente y coherente” — no “evacuad” |
| MONITOR | HOLD | “Seguir midiendo / no promover” |
| EVACUATE | — (fuera de scope) | **No mapear** a GO; nunca claim de orden de evacuación |

### 3.4 Mapa de umbrales conceptual (field_ops, ML fusion OFF)

| Señal | Baja u | Media | Alta u |
|-------|--------|-------|--------|
| Ops LWIR (grade, n_pares, coreg) | favorece GO | HOLD | ABSTAIN |
| Ancla Vp (ratio banda) | refuerza GO | HOLD | no inventar |
| ML live | **ignorado** en field_ops | — | — |
| Open perimeter (CEMS/FIRMS) | contexto | contexto | no basta solo |

**Regla Cardil + Orion:** GO solo si la incertidumbre de **datos ops** está bajo umbral; la epistémica de ML **no desbloquea** field_ops.

### 3.5 Otros (temp bajo follaje, DA)

| Trabajo | Hallazgo | Prioridad |
|---------|----------|-----------|
| AOS + ML 2026 (T superficial a través de follaje) | Recuperar T bajo dosel | P2 si radiometría |
| UAV + FARSITE DA (−53 % error perímetro) | Asimilar obs UAV al sim | P1 lab envelope |

---

## 4. Open source en GitHub (activos y útiles)

> Reddit (r/MachineLearning, r/gis, foros wildfire): discusiones dispersas, poco código nuevo.  
> La conversación técnica está en **GitHub + papers**.

| Proyecto | Qué hace | Por qué importa para WFD | Prioridad | Acción |
|----------|----------|--------------------------|-----------|--------|
| **[Pyronear](https://github.com/pyronear)** (pyro-engine, pyro-api, pyro-vision, pyro-sdis) | Edge (Pi/ONNX) → alertas FastAPI → dataset open → risk → labels | Modelo de adopción real + honestidad low-tech; referente field kit + alert pipeline | **P0 referencial** | Comparar outbox vs API; no reescribir |
| **[Orion-AI-Lab/uncertainty-wildfires](https://github.com/Orion-AI-Lab/uncertainty-wildfires)** | UQ danger forecasting | Decision Card + Reliability Gate | **P0 diseño** | Patrón ECE + reject |
| **Vision-Aided Wildfire… (HumamZrdali)** | Detectron2 + SAM2 + SAHI → seg + geo RGB/IR | Máscaras + GPS del frente aéreo | **P1 lab** | Si packs sin máscara de calidad |
| **NASA-JPL/uavsar-wildfire** | Perímetros/severidad polarimétrico SAR | Complemento open all-weather | **P2** | Pista B / humo |
| **Earth-Information-System/fireatlas (FEDS)** | Tracking VIIRS ~12 h | Perímetros sat multi-día | **P1** | Complemento EFFIS/CEMS |
| **fire2a (Chile)** | Cell2Fire + QGIS + simuladores | Sim + risk maps open | **P1 lab** | Diagnóstico hybrid ROS |
| **Flamap** (Guillaume Rozier, jul 2026) | Mapa open FR: EFFIS + FIRMS + viento ~2 h | Capa perímetro open usable en minutos | **P0 producto open** | Espejo Pista B / demo sin dron |

### 4.1 Pyronear vs WFD field kit

| Pyronear | WFD | Lección |
|----------|-----|---------|
| pyro-engine (edge detect) | `incident_runtime` + LWIR ingest | Ellos: cámara fija smoke; vosotros: dron frente |
| pyro-api (alertas, orgs, webhooks) | outbox + Decision Card + `/v1/decide` | Pipeline de alerta auditable |
| Low-tech + SDIS labels | Tobarra/Hellín + honesty card | Validación con end-user real |
| No venden ROS táctico como YOLO | Ops ≠ ML | Misma disciplina |

**Adoptar:** forma del API (metadata sensor, secuencia, webhook).  
**No adoptar:** su detector como core de ROS.

### 4.2 Stack open perimeters

```
Flamap / FEDS / EFFIS / CEMS  →  perímetro multi-día (Pista B)
UAVSAR                         →  severidad / humo-through
WFD open pack                  →  CEMS + REDIAM + RAI (ya)
```

- **Sin dron:** Flamap-style = argumento comercial open.  
- **Con dron:** ROS medido = diferencial táctico.

**Párrafo copy-paste:**

> La capa de detección y alertas open (Pyronear: edge + FastAPI) y los mapas de perímetro open (Flamap/EFFIS/FIRMS, FEDS/VIIRS) demuestran adopción real low-tech y satelital. WFD separa ese stack del ROS táctico medido por dron LWIR y del ML de máscaras de laboratorio.

---

## 5. China (GitHub + papers + instituciones)

China está muy activa en **UAV + thermal + lightweight models** (detección y edge), no en ROS multi-estimador con ancla operativa mediterránea.

### 5.1 BGC-LiteNet (Scientific Reports 2026)

| Claim | Lectura WFD |
|-------|-------------|
| BeiDou Grid Code **dentro** de la red | Geo nativo sin GIS post-hoc |
| ~0.87 M params, ~38 ms, ~88.9 % mAP, ~92.4 % geoloc accuracy | Edge real |
| Multi-escenario Anhui / Hunan / Sichuan (dataset planeado) | Generalización regional, no Med |
| Instituciones | USTC, Central South University of Forestry, Anhui Forestry Bureau + empresas locales |

**Idea transferible (sin copiar BeiDou):**

> Contrato térmico WFD = **payload + CRS + timestamp + hash + grade**  
> embebidos en Decision Card / outbox  
> → auditoría sin “confía en el GeoTIFF suelto”.

**Contrato mínimo propuesto:**

```json
"thermal_frame_contract": {
  "crs": "EPSG:...",
  "acquired_at": "ISO8601",
  "content_sha256": "...",
  "sensor": "LWIR|EO+LWIR",
  "radiometric": false,
  "georef_quality": "A|B|C|unknown"
}
```

Fortalece R4 provenance del Reliability Gate.

### 5.2 Resto CN

| Pieza | Uso WFD | No-uso |
|-------|---------|--------|
| Fire-YOLO26 / YOLO-MMSC | Detección edge RGB–TIR | ROS táctico |
| FCDNet + dataset público | Core térmico lightweight lab | Transfer ciego a CLM |
| VIF-FireDataset (Beijing Institute of Technology) | Pares VIF ultra-res para fusión lab | Labels ≠ perímetro oficial |

**Párrafo copy-paste:**

> Trabajos lightweight UAV (p. ej. BGC-LiteNet con geocódigo nativo) refuerzan la necesidad de contratos de frame térmico auto-descriptivos (CRS, tiempo, hash, calidad de georref). Eso fortalece la proveniencia del Reliability Gate sin acoplar el producto a redes de detección extranjeras.

---

## 6. Arquitectura mental unificada

```
┌─────────────────────────────────────────────────────────────┐
│  SENSING / SEGMENTATION                                     │
│  China RGB-TIR · Fire-YOLO26 · RFFNet · Pyronear vision     │
│  → máscara / alerta / geo                                   │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  OPS GEOMETRY (Lampman-like)                                │
│  front_dynamics_v1 → ROS, grade, (FI/FRP si radiométrico)   │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  OPEN PERIMETER                                             │
│  Flamap · FEDS · CEMS · UAVSAR · packs WFD                  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHYSICS / SIM                                              │
│  fire2a · Cell2Fire · FARSITE DA · Rothermel-lite hybrid    │
│  → prior + envelope; ABSTAIN sin obs                        │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION CARD                                              │
│  Orion UQ + CRC three-way → GO / HOLD / ABSTAIN             │
│  field_ops ML fusion OFF · Reliability Gate R1–R4           │
│  thermal_frame_contract (hash + CRS + time)                 │
└─────────────────────────────────────────────────────────────┘
```

| Bloque SOTA | Capa WFD | Mensaje de producto | ¿Flip field_ops fusion? |
|-------------|----------|---------------------|-------------------------|
| Lampman TIR→ROS/FI/FRP | Ops térmico | Pipeline ideal de **medición** | No |
| Fire-YOLO26 / RFFNet / MMSC | Upstream máscara | Fusión **sensorial** madura | No |
| Orion + CRC | Gates, ECE, ABSTAIN | Fusión **decisional** con rechazo | No |
| Pyronear / Flamap / FEDS | Field kit + open | Adopción real / demo sin dron | No |
| BGC-LiteNet idea | Provenance | Contrato térmico auditable | No |

---

## 7. Matriz de adopción priorizada

### P0 — citar y alinear (casi sin código)

1. **Orion + CRC** en Reliability Gate / guion demo: umbral de rechazo = ABSTAIN.  
2. **Lampman** como ancla metodológica ops (1 sitio, 1 fuel).  
3. **Pyronear + Flamap** como referentes de sistema real / capa open en minutos.  
4. **BGC-LiteNet idea**: checklist de contrato térmico en provenance.  
5. **Cardil 2023**: physics ≠ ops truth (ya doctrina).

### P1 — ingeniería acotada

| ID | Trabajo | No hacer |
|----|---------|----------|
| U1 | Campos `u_data` (ops quality) en Decision Card JSON | Deep Ensemble en field_ops |
| U2 | Documentar mapping u → GO/HOLD/ABSTAIN en `DECISION_POLICY` | SAFE/MONITOR/EVACUATE literal |
| B1 | FI/FRP opcionales en outbox solo con radiometría o proxy honest | Inventar FRP en MW sin cal |
| O1 | FEDS/Flamap-style feed en packs open si falta | Reescribir portal |
| S1 | fire2a / Cell2Fire como **diagnóstico** hybrid | Despacho táctico simulado |
| C1 | Endurecer hash+CRS+time en outbox | Embeber red con grid code chino |
| R1 | Pipeline eval FLAME3 NADIR (no-gold) vs multi-estimador | Claim grade A US → CLM |

### P2 — lab opcional

- RoboFireFuseNet / SAM2 si hay EO+IR.  
- DA estilo UAV→FARSITE para envelope.  
- AOS follaje solo con T radiométrica.  
- RF short-horizon ROS vs copy (leave-one-fire).  
- T-FAM-style fusion si Dropbox da EO.

### Kill list (sigue viva)

- mAP chino o F1 Orion como “precisión del frente CLM”.  
- MAE Lampman (0.04 m/s) como SLA Tobarra.  
- Fusión ML live en `field_ops` porque “el SOTA fusiona RGB–TIR”.  
- EVACUATE del paper CRC como claim de producto.  
- ROS de simulación sin obs LWIR.  
- Entrenar ANN de ROS con un solo IF.  
- Mezclar IoU ML con ROS ops en el mismo claim.

---

## 8. Dónde citar qué

| Documento | Citas recomendadas | No meter |
|-----------|-------------------|----------|
| **Reliability Gate Report** (this-run) | Lampman (método TIR); Orion (rechazo + ECE) | mAP Fire-YOLO26 como accuracy de fuego |
| **Acta / guion demo 30 min** | Ops = Lampman-like; ML lab separado; fusion OFF | “Como en Sichuan 95 % mAP” |
| **PILOT honesty card** | Limitación Lampman (1 sitio, 1 fuel) ↔ O1 (pocas anclas) | — |
| **Corpus / este doc** | Todos los bloques | Claim generalización pastizal→maquis |
| **GO_Q / informe trimestre** | Open stack (Pyronear, Flamap) + dual product | GO_MES+ sin O5/demo |

---

## 9. Lecturas en orden (si solo 8)

1. **Cardil 2023** — honestidad ops (sesgo modelo vs obs).  
2. **Lampman 2026 IJWF** — TIR multi-pasada → ROS/FI/FRP + RF.  
3. **FLAME 3** — dataset radiométrico para validar estimadores.  
4. **FireCast-Fusion 2026** — framing short-horizon multimodal.  
5. **Kondylatos / Orion 2025** — UQ + reject + ECE.  
6. **CRC 2026** (SAFE/MONITOR/EVACUATE) — tri-estado con control de riesgo.  
7. **Pyronear** repos — field kit + API real.  
8. **BGC-LiteNet 2026** — idea de geo/contrato nativo (no copiar red).

---

## 10. Conclusión

1. **Lampman** valida el **cómo se mide** ROS desde dron TIR; generalización limitada → perfecta para el gate, no para marketing de error.  
2. **RGB–TIR 2026** es producto de **detección**, no de ROS táctico → justifica `allow_ml_live_in_fusion: false`.  
3. **Orion + CRC** formalizan la Decision Card: umbrales de incertidumbre → GO / HOLD / ABSTAIN.  
4. **Pyronear / Flamap / FEDS** son el espejo industrial de field kit + open perimeter.  
5. **China** gana en edge y geo-nativo de detección; WFD gana defendiendo **ROS medido + card con rechazo + fusión OFF**.  
6. El error estratégico es unificar todo en un super-modelo; el SOTA fragmentado **confirma** el diseño dual/triple del repo.

---

## 11. Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-08-04 | Documento inicial: consolidación de análisis SOTA TIR/ROS/fusión, UQ Orion, open source, China y matriz P0–P2. |
