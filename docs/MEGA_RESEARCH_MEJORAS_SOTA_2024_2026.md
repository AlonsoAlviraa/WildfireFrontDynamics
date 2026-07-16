# Mega-research: mejoras implementables (SOTA 2024–2026)

> **Fecha:** 2026-07-16  
> **Alcance:** literatura mundial reciente (NDWS, WildfireSpreadTS, PINNs, digital twins, UAV RGB–IR, EFFIS/Copernicus) cruzada con **WildfireFrontDynamics**  
> **Regla:** solo propuestas accionables; cada ítem tiene *qué dice el paper*, *qué tenemos*, *qué implementar*, *prioridad*, *riesgo*

---

## 0. Dónde estamos (baseline del proyecto)

| Producto | Estado | Techo actual |
|----------|--------|--------------|
| Ops `front_dynamics_v1` | Tobarra A ratio 0.82; 7 packs; FOV fix; O3 2/3 | Falta multi-ancla O1/O5 y perímetro O2 |
| ML `ndws_v21` | IoU ~0.226 Δ+0.076; G1 features/temporal T=2 **NO_PROMOTE** | Plateau copy-dominated |
| ML `clm_v28` + LOFO 4/4 | Δ>0 en 4 fuentes (mean Δ ~0.27) | Mejor pista ML industrial |

**Mensaje de la literatura global:** el salto ya no está en “otra U-Net con otro loss”; está en (1) **serie temporal real + pretrain**, (2) **física / híbridos**, (3) **fusión multi-sensor operativa**, (4) **validación geométrica oficial**, (5) **digital twin / producto decisor**.

---

## 1. Mapa de la frontera científica (2024–2026)

### 1.1 Next-day spread (satélite / NDWS-like)

| Línea | Evidencia | Hallazgo clave |
|-------|-----------|----------------|
| **Huot et al. NDWS** (dataset base) | Google Research / Kaggle | Benchmark 64×64 multi-canal; copy baseline muy fuerte |
| **WildfireSpreadTS** (multi-día) | NeurIPS-era multi-temporal dataset | Entrada de **5 días** > 1 día; 23 canales; CV leave-one-year |
| **SwinUnet + pretrain** (2025) | [arXiv:2502.12003](https://arxiv.org/html/2502.12003v1) | SOTA en WFTS con **ImageNet pretrain**; multi-day AP 0.404 vs single-day 0.383 |
| **MA-Net multi-día** | Nature Sci Rep 2024 | Horizonte 1–5 días; multimodal weather+space |
| **APAU-Net + weather forecast** | 2025 multimodal satellite | Atrous pyramid + attention; reportan mIoU alto en setup enriquecido (cuidado: no comparable 1:1 a nuestro protocolo any_fire) |
| **SegFormer / ViT** | Stanford CS231n 2025 | Transformers capturan contexto global; fallan en ignición/onset |
| **Ensemble / MAPE** | MDPI Fire 2024 | Ensembles para área/velocidad (otro framing, no máscara 64²) |

**Implicación para nosotros:** T=2/T=3 en NDWS legacy17 **casi no movió** el techo → coherente con papers que exigen (a) **pretrain**, (b) **5 días reales** tipo WFTS, (c) **métrica AP/PR** además de IoU vs copy.

### 1.2 Física + híbridos

| Línea | Evidencia | Hallazgo |
|-------|-----------|----------|
| **PiNN wildfire parameters** | Vogiatzoglou et al. 2024–25 (CMAME / arXiv:2406.14591) | Aprende parámetros de un modelo de propagación interpretable |
| **Physics-informed LSTM** | 2025 hybrid sim+DL | R² alto emulando frentes de simulación física |
| **PhysFire-WM / PDE+PINN** | 2025 surveys | Surrogates de PDE para ops |
| **USFS Finney DL surrogate** | Firelab 2024 | DL emula modelo físico de alta resolución |
| **Generative 2D/3D** | MDPI Fire 2025 | Generative AI más allá de U-Net clásica |

**Implicación:** no sustituir ROS ops por PINN mañana; sí **regularizar ML** (crecimiento solo en normal al frente, wind-aligned) y/o **calibrar Rothermel-like** con ROS observada.

### 1.3 UAV / térmico / fusión multi-modal

| Línea | Evidencia | Hallazgo |
|-------|-----------|----------|
| **FireCast-Fusion** | 2026 UAV RGB–thermal + env | Fusión multimodal para horizonte corto |
| **SAR + UAV optical/thermal** | Nature Sci Rep 2025 | SAR all-weather + UAV detalle de frente |
| **LiDAR + multispectral fuels** | 2026 review | Mejora clasificación de combustible |
| **Live fuel moisture (LFMC)** | USFS / SERDP 2025–26 | FMC es driver crítico; productos ML satelitales emergentes |

**Implicación ops:** vuestro stack LWIR + Heligrafics es **exactamente** el nicho UAV térmico del SOTA; falta **RGB alineado**, **meteo en escena**, y **perímetro independiente**.

### 1.4 Validación operativa / Europa

| Fuente | Uso para el proyecto |
|--------|----------------------|
| **EFFIS Rapid Damage Assessment** | Perímetros quemados diarios (MODIS/VIIRS + Sentinel-2 refinamiento); fires ≳30 ha |
| **Copernicus EMS Mapping** | Perímetros de activación; validación geométrica (papers GR 2023: ~96% acuerdo área) |
| **FirEUrisk / GWIS** | Contexto riesgo y datos abiertos |

**Implicación O2:** sin pedir croquis a CMA, se puede **intentar** cruzar IF grandes (Cardoso multi-día) con EFFIS/EMS si hay solapamiento temporal → desbloquea Hausdorff “oficial-lite”.

### 1.5 Digital twins

| Línea | Evidencia |
|-------|-----------|
| **NASA Wildfire Digital Twin** (2024) | Fusión in-situ + air + space; API ligera para tablet |
| **FIRETWIN** (2025) | DT táctico 3D + sensing multi-modal |
| **Reviews Digital Twin wildland fire** | Springer 2024; MDPI Fire 2024 |

**Implicación producto:** no hace falta un DT completo; el **mínimo industrial** es: estado observado (máscara/frente) + meteo + predicción corta + capa GIS + incertidumbre — vuestro informe CMA ya es el embrión.

---

## 2. Matriz de mejoras (priorizada para *este* repo)

Leyenda prioridad: **P0** (1–2 sem, alto ROI) · **P1** (mes) · **P2** (trimestre) · **P3** (I+D largo)

### A. Validación y datos (desbloquea O1/O2/O5 — mayor ROI industrial)

| ID | Mejora | SOTA que lo respalda | En el repo | Esfuerzo | Dep. externa |
|----|--------|----------------------|------------|----------|--------------|
| **A1** | Ingest EFFIS/CEMS perímetros por bbox+fecha IF | EFFIS RDA, CEMS Mapping | Nuevo `scripts/fetch_effis_perimeter.py` + `eval_perimeter_hausdorff --mode official` | M | Baja (APIs/datos abiertos) |
| **A2** | Tabla anclas Vp/ha multi-IF (CMA) | Protocolos ops Europa | `data/infocam_anchors.json` ya listo | S | **Alta** (Pablo/CMA) |
| **A3** | Hotspots FIRMS/VIIRS como ancla de dirección de avance | Active fire products | Overlay en packs | S–M | Baja |
| **A4** | AEMET / ERA5-Land en escena CLM | Multimodal weather papers | `fetch_aemet_fwi` parcial | M | Media |
| **A5** | LFMC / combustible fino (FMC product) | USFS FMC ML | Canal en physics schema o capa ops | M–L | Media |
| **A6** | Cardoso 10 días completo + alineación multi-fase | Multi-temporal WFTS | Packs multi-ventana | M | Media (Dropbox) |

**Recomendación A:** **A1 + A3** sin esperar a nadie; **A2** en paralelo por correo.

### B. Ops ROS / frente (vuestro diferencial real)

| ID | Mejora | SOTA | Implementación concreta | P |
|----|--------|------|-------------------------|---|
| **B1** | ROS por sector angular (cabeza / flanco / cola) | Literatura ROS operacional clásica + UAV front papers | Partir contorno en arcos vs viento; reportar 3 ROS | **P0** |
| **B2** | Incertidumbre explícita (bootstrap de estimadores) | Ensembles / abstención ops | Intervalo P25–P75 ya parcial → PDF de incertidumbre en brief | **P0** |
| **B3** | Corregistro multi-frame + optical flow LWIR | Multi-modal UAV fusion | Flow entre frames térmicos → ROS denso; comparar con normal_ray | **P1** |
| **B4** | Fusión RGB+LWIR (si hay bandas EO en Dropbox) | FireCast-Fusion, SAR+UAV | Máscara térmica refinada con bordes visibles | **P1** |
| **B5** | Calibración física blanda (Rothermel/Behave-lite) | PiNN + physics hybrids | Usar ROS observada para estimar *ros_max* local; no reescalar en silencio | **P1** |
| **B6** | Segmentación adaptativa por FOV (ya empezado) | — | Ampliar FOV guard + MAD por ROI | **P0** (continuar) |
| **B7** | Producto “DT light”: estado t0 + ROS + cono de incertidumbre 15–60 min | NASA DT / FIRETWIN (versión mínima) | Extrusión geométrica del frente con ROS sectorial + wind | **P1** |

**Recomendación B:** **B1+B2+B7** convierten el TFG en producto que el SOTA llama “decision support”, sin promesa de U-Net mágica.

### C. ML NDWS / G1 (si aún pelea; o kill honesto)

| ID | Mejora | SOTA | Notas vs v21/v27 | P |
|----|--------|------|------------------|---|
| **C1** | Protocolo tipo **WFTS**: multi-day real + leave-one-year | WildfireSpreadTS + SwinUnet 2025 | Nuestro T=2/3 en NDWS Huot es débil; WFTS es el dataset correcto | **P1** |
| **C2** | **ImageNet / encoder pretrain** (ResNet/Swin) | SwinUnet SOTA depende de pretrain | Entrenar residual U-Net from scratch es desventaja | **P1** |
| **C3** | Arquitecturas attention: **UTAE, MA-Net, APAU, SwinUnet** | 2024–25 papers | Un solo cambio por run; no apilar | **P1–P2** |
| **C4** | Métricas **AP / PR-AUC / growth IoU** además de IoU full | WFTS reporta AP; nosotros IoU vs copy | Evita “empate con copy” confuso | **P0** |
| **C5** | Weather **forecast** channels (no solo analysis) | APAU-Net enhanced NDWS | Requiere re-export de datos | **P2** |
| **C6** | Self-supervised pretrain en satélite | Conclusión SwinUnet paper | Costoso; solo si G1 sigue vivo | **P3** |
| **C7** | **KILL G1** features+temporal si v27b falla | Nuestra evidencia empírica | Congelar `ndws_v21`; valor en CLM | **P0** si v27b NO |

**Recomendación C:** Si v27b no gana a v21 → **KILL G1** y mover GPU a **C1/C2 en CLM o WFTS**, no más physics* en Huot.

### D. ML Transfer CLM (mejor pista abierta)

| ID | Mejora | SOTA | En el repo | P |
|----|--------|------|------------|---|
| **D1** | LOFO ya hecho 4/4 | LOYO CV en WFTS | `CLM_LOFO_ALL_FOLDS_REPORT.json` | ✅ |
| **D2** | Ensemble de folds LOFO → producto `clm_ensemble` | Ensembles Fire 2024 | Soft-vote 4 checkpoints | **P0** |
| **D3** | Domain adaptation (NDWS→CLM adversarial / CORAL) | Domain shift literature | Fine-tune ya funciona; DA si LOFO cae | **P2** |
| **D4** | Test-time adaptation con 1 pasada térmica | Digital twin / online calib | Actualizar BN/prompt con frame actual | **P2** |
| **D5** | Predict **growth mask** only (Δ fuego) con métrica growth-IoU | Papers “incremental growth” | Alineado residual+delta | **P1** |

**Recomendación D:** **D2** es el siguiente ship industrial ML (1–2 días).

### E. Producto / industrial / CMA

| ID | Mejora | SOTA | P |
|----|--------|------|---|
| **E1** | API ligera (predict + pack) estilo NASA DT “tablet” | NASA Wildfire DT | **P1** |
| **E2** | Capa única QGIS + timeline + brief ES (O4) | Decision support ops | **P0** |
| **E3** | Uncertainty maps en HTML ops | Abstención + ensembles | **P0** |
| **E4** | Benchmark público “CLM aerial front dynamics” (sin crudos sensibles) | Falta dataset abierto europeo UAV | **P2** |
| **E5** | XAI (Integrated Gradients / saliency) en CLM | APAU-Net IG | **P2** |

---

## 3. Roadmap de 90 días (alineado a papers, no a hype)

### Mes 1 (actual loop) — ya en curso
- Cerrar G1 (v27b) o KILL documentado  
- Congelar ops + CLM LOFO  
- A1 EFFIS attempt + E2/E3  

### Mes 2 — “SOTA-compatible ops”
- B1 ROS sectorial + B7 cono 15–60 min (extrusión, no U-Net táctica)  
- A1/A3 validación satélite  
- D2 ensemble CLM  

### Mes 3 — “SOTA-compatible ML” (solo si GPU y datos)
- C1 WFTS o multi-day serio **o** Swin/UTAE en CLM con pretrain  
- B4 RGB+IR si el Dropbox lo permite  
- A5 FMC si hay capa usable  

---

## 4. Anti-recomendaciones (SOTA también las mata)

| Idea tentadora | Por qué no (literatura + vuestra evidencia) |
|----------------|-----------------------------------------------|
| Más pos_weight / filter-only | Agotado; copy sigue dominando |
| Prometer 15/30/60 min táctico con NDWS IoU 0.22 | Papers SOTA tampoco lo venden como despacho; y SwinUnet falla en “onset” |
| KMZ como perímetro | Confundir footprint con fuego (vuestro propio análisis) |
| LSTM 3D sin datos multi-día reales | WFTS existe precisamente porque Huot T=1 no basta |
| Generative 3D fire | Interesante (MDPI 2025) pero fuera de TFG/CMA scope |

---

## 5. Quick wins técnicos (checklist de ingeniería)

```
[ ] A1  fetch EFFIS/CEMS perimeter for Cardoso/Tobarra bbox
[ ] B1  sector ROS (head/flank/rear) in front_dynamics
[ ] B2  uncertainty band in operational_report.html
[ ] B7  simple envelope forecast 15/30/60 from ROS+wind (geometry only)
[ ] C4  log AP + growth-IoU in unet_train eval
[ ] D2  average 4 LOFO weights → models/clm_ensemble/
[ ] E2  main_front.gpkg + 1-page PDF from existing packs
[ ] C7  G1_KILL doc after v27b if flat
```

---

## 6. Referencias clave (entrada)

1. Huot et al. — *Next Day Wildfire Spread* dataset (Google)  
2. WildfireSpreadTS — multi-temporal multi-modal fire dataset  
3. Lahrichi et al. 2025 — SwinUnet + multi-day SOTA ([arXiv:2502.12003](https://arxiv.org/abs/2502.12003))  
4. Nature Sci Rep 2024 — MA-Net multimodal wildfire spread  
5. Vogiatzoglou et al. — Physics-informed NN wildfire parameters (2024–25)  
6. NASA Wildfire Digital Twin (2024)  
7. FIRETWIN — tactical multi-modal digital twin (2025)  
8. EFFIS Rapid Damage Assessment / Copernicus EMS  
9. FireCast-Fusion — UAV RGB–thermal short-horizon (2026)  
10. MDPI Fire 2025 — Generative AI for 2D/3D wildfire (survey/perspective)

---

## 7. Conclusión ejecutiva

| Si el objetivo es… | La mejora SOTA más rentable es… |
|--------------------|----------------------------------|
| **Impresionar a CMA / TFG ops** | B1 sector ROS + B7 cono geométrico + A1 EFFIS + anclas |
| **Impresionar en ML industrial** | D2 ensemble LOFO + C4 métricas AP; no más physics en NDWS Huot |
| **Publicar / SOTA IoU** | Cambiar de dataset a **WFTS** + **pretrain + multi-day** (C1/C2) |
| **“Digital twin” de verdad** | E1 API + estado observado + meteo + incertidumbre (NASA-like light) |

**Frase final:** el SOTA mundial no contradice vuestro camino — lo **confirma**: la física observada del frente (UAV térmico) + transfer multi-incendio + validación geométrica externa son el núcleo; la U-Net NDWS es un **benchmark de investigación**, no el producto de despacho.
