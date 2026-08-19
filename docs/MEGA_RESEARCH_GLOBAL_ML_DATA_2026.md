# Mega research global ML + datos — decisiones verificables para WFD

**Corte de evidencia:** 2026-08-16  
**Ámbito:** China, EE. UU., Europa, Australia, Canadá y modelos globales  
**Registro legible por máquina:** `research/global_ml_data_registry_2026.json`

## 1. Resultado ejecutivo

La mejora prioritaria de WildfireFrontDynamics no es cambiar U-Net por el nombre de una arquitectura nueva. El cuello de botella es la combinación de:

1. métricas de transición que no oculten falsos crecimientos;
2. pares temporales reales, con hora y tipo de label compatibles;
3. generalización por incendio/región, no por tiles aleatorios;
4. calibración y abstención cerca del frente;
5. separación estricta entre observación, proxy satelital y simulación.

La investigación global converge en tres escalas distintas que el producto debe mantener separadas:

| Escala | Evidencia fuerte | Uso correcto en WFD |
|---|---|---|
| UAV, segundos/minutos | FireSentry, BurnedAreaUAV, LWIR propio | Segmentación/seguimiento del frente observado; no next-day satelital |
| Satélite, horas/días | GOFER, PT-FireSprd, WFTS, TS-SatFire, RCDA | Progresión externa y predicción diaria; no ROS táctica sin ancla |
| Física/simulación | FireBench, USFS surrogate, Wang/CA | Priors, stress tests y ensembles; no ground truth real |

## 2. Hallazgos que cambian el proyecto

### H1 — La métrica de crecimiento existente tenía soporte condicionado por el target

`model_growth` evaluaba la predicción solamente donde el target decía que hubo crecimiento. Un falso crecimiento fuera de esa región desaparecía de la métrica. El resultado podía parecer un IoU de crecimiento cuando era esencialmente sensibilidad dentro del área verdadera.

Se implementó una familia v2:

```text
pred_growth = prediction(t1) AND NOT observed(t0)
true_growth = observed(t1)  AND NOT observed(t0)
growth_transition_iou = IoU(pred_growth, true_growth) en toda la rejilla
```

También se añadió Average Precision sobre píxeles no quemados en `t0`, alineada con la práctica de WildfireSpreadTS y FireSentry. Las métricas antiguas permanecen etiquetadas como `legacy_target_conditioned_metrics` para reproducir scorecards previos; no deben usarse para promocionar un modelo nuevo.

### H2 — El parser Caldor confundía offset UTC con segundos

Los nombres FireBench `...T20_20_07_00.kml` significan `20:20-07:00`; el parser histórico interpretaba `07` como segundos. Ahora el inventario:

- conserva el offset;
- emite UTC;
- calcula `delta_hours` entre perímetros;
- marca pares compatibles con horizonte 12–36 h.

Esto abre 21 progresiones NIROPS fechadas de Caldor (más un perímetro final MTBS) como banco externo estadounidense. El bridge de labels ya está materializado; faltan covariates compatibles antes de ejecutar el modelo WFD sobre este incendio.

La auditoría local reproducible (`python scripts/audit_firebench_caldor.py`) encontró 20 pares consecutivos, de los cuales **15** caen entre 12 y 36 h. El HDF5 contiene 22 polígonos, 7 capas espaciales y 105 estaciones. El bridge de laboratorio es viable, pero train/redistribución quedan bloqueados: hay estaciones Synoptic y no existe un aviso Synoptic dentro de `DATA_LICENSES/` del paquete staged.

El builder reproducible (`python scripts/build_firebench_caldor_pack.py`) une todas las geometrías de cada KML y produce un grid común EPSG:32610 a 30 m de 2.199×1.302 píxeles. Conserva por separado:

- `raw_masks`: observación NIROPS sin alterar;
- `cumulative_masks`: unión temporal derivada y explícitamente etiquetada;
- MTBS final: referencia excluida de los pares temporales.

En los 20 pares la retención del perímetro anterior fue al menos 99,85 %, por lo que no apareció ningún shrink material bajo el umbral conservador del 5 %. Esto valida la geometría del bridge, no los derechos de entrenamiento ni la compatibilidad de canales del modelo.

### H3 — “FireBench” nombra dos cosas distintas

- El FireBench original de Google es un corpus **sintético** de simulaciones 3D de alta fidelidad.
- El paquete Caldor 2026.x de SJSU es un **benchmark observacional** de modelos con KML NIROPS, HDF5, daño, severidad, canopy y estaciones.

No deben mezclarse en inventario, licencia ni claims. El Caldor local es v2026.1; existe v2026.2, pero actualizar no es prioridad hasta cerrar el bridge y revisar la diferencia de versión.

### H4 — La mejor aportación china inmediata es protocolo + datos, no una fórmula mágica

RCDA-Net (Wuhan, 2026) plantea exactamente la tarea correcta: segmentación del **incremento** de fuego, 12 canales, 256×256, Dice y atención contextual/de canal. Reporta IoU 0.308 y F1 0.471 en su split. Dos cautelas:

- el equipo es chino, pero los datos son Canadá/Alaska; no valida China ni España;
- WFD debe reproducir primero U-Net/copy/dilated-copy con split por incendio antes de portar AGCA/CAA.

FireSentry (Tsinghua/KDD 2026) es el candidato más cercano al térmico UAV: RGB+IR, subsegundo y variables ambientales. En el commit auditado las regiones A–E ya están públicas aunque el README aún marca B–E como diferidas. No hay licencia explícita, las máscaras proceden de SAM2 y los datos forestales siguen restringidos. Es candidato de pretraining tras aclarar derechos y realizar auditoría humana, no ground truth automático.

FY-3D y el producto Himawari adaptado aportan detección térmica independiente; no producen directamente polígonos de propagación ni sustituyen labels de frente.

## 3. Matriz mundial y decisión

| Fuente | Región del dato | Tarea comparable | Valor | Decisión |
|---|---|---:|---|---|
| Next Day Wildfire Spread | EE. UU. | Sí, daily extent | baseline histórico | Mantener v21 como referencia, no seguir exprimiendo arquitectura scratch |
| WildfireSpreadTS | EE. UU. | Sí, daily multi-day | 607 eventos/13.607 imágenes | P1: benchmark T=5 + encoder preentrenado |
| TS-SatFire | EE. UU. | Sí, multi-task | AF/BA QA manual en test | P1: pretraining multi-task; descarga pesada |
| GOFER | California | Parcial, hourly progression | 28 incendios; perímetros/line/ROS | P0: validación temporal externa |
| FireBench Caldor | California | Sí tras bridge | 21 progresiones + MTBS + 300+ benchmarks | P0: raster/schema bridge; rights gate |
| RCDA | Canadá/Alaska | Sí, incremental daily | 8.131 muestras 256² | P0 protocolo; P1 reproducción; atención solo si gana |
| FireSentry | China/no especificado | Sí, UAV short-horizon | RGB+IR+meteo | P1 condicionado a licencia y mask QA |
| FY-3D | Global/China | No, detección | sensor independiente | P2 hotspot corroboration |
| PT-FireSprd | Portugal | Sí, progression/fire-runs | Mediterráneo, confianza | P0: principal externo real para WFD |
| DEA Hotspots | Australia | No, hotspots | servicio vivo | P1 discovery/QA, no label de perímetro |
| CNFDB | Canadá | No por sí solo | gran corpus final | P2 pretraining/contexto, no next-day |
| Prithvi-EO-2.0 | Global | No directo | encoder EO temporal | P2, solo después de fijar protocolo/datos |

## 4. Evaluación nueva obligatoria

Todo modelo nuevo debe entregar, por incendio y agregado micro/macro:

1. `model_iou` y delta contra copy;
2. `model_growth_transition_iou`;
3. delta contra dilated-copy en transición;
4. `model_change_transition_iou`;
5. Average Precision de crecimiento;
6. FCER derivada solo de `t0`, junto con su cobertura del crecimiento observado;
7. calibración/ECE en región próxima al frente;
8. curva cobertura-rendimiento y abstención;
9. métricas de borde (F1 con tolerancia y, cuando el CRS lo permita, Hausdorff/ASSD en metros).

La selección de threshold, temperatura, ensemble y abstención se hace solo en VAL. TEST y regiones externas se ejecutan una vez con parámetros congelados.

## 5. Arquitectura recomendada, por fases

### P0 — antes de entrenar

- Migrar dashboards y scorecards a transición v2 sin borrar cifras legacy.
- Bridge Caldor KML → geometría normalizada → raster común, con intervals y rights gate.
- Evaluar PT-FireSprd por confianza y duración, no como una media única.
- Añadir split `leave-one-fire-out` y, para WFTS, `leave-one-year-out`.
- Auditar covariates por tiempo efectivo: forecast disponible en `t0`, nunca análisis futuro de `t1`.

### P1 — un benchmark controlado

Comparar, con el mismo split y seeds:

1. copy;
2. dilated-copy;
3. U-Net actual;
4. U-Net con encoder preentrenado;
5. RCDA-lite o SwinUnet preentrenado.

Se promociona solamente si mejora transición v2 y AP, no solo full-mask IoU. La literatura WFTS muestra que el beneficio de Swin depende fuertemente de pretraining y que cinco días superan a uno; por eso no tiene sentido probar un Transformer desde cero sobre los mismos pocos pares CLM.

### P2 — incertidumbre y física

- Región de evaluación centrada en el frente (FCER/ring) para ECE y ranking de incertidumbre.
- Ensemble/estudiante destilado para inferencia rápida.
- Priors Wang/Rothermel/CA como canal o regularizador, calibrados por región.
- FireBench sintético para stress tests y pretraining de dinámica; validación final siempre real.
- Prithvi para EO pre/post o burn scar, no como sustituto directo de la rama térmica.

### P3 — probabilístico generativo

Difusión/flow matching permite varias trayectorias plausibles, una propiedad correcta para fuego. Pero hoy no resuelve la ausencia de pares españoles ni la calibración. Se investiga después de que un modelo determinista gane a copy en múltiples incendios externos.

## 6. Datos: gates de admisión

Un dataset solo entra en train/eval si el manifiesto registra:

- identidad de evento y geografía real;
- timestamp con zona horaria y `observed_at`/`available_at` separados;
- label kind: active fire, extent, monitoring, final scar o simulation;
- resolución/CRS y método de alineación;
- derechos de entrenamiento, derivados, redistribución y uso comercial por separado;
- procedencia de la máscara (humana, sensor, algoritmo, simulador);
- split group (`event_id`, año, región, sensor);
- checksums y versión;
- riesgos de leakage.

FireSentry ilustra por qué: “dataset público” no implica que todas las regiones, capas forestales o máscaras tengan el mismo nivel de acceso y ground truth.

## 7. Roadmap con criterios de salida

| Prioridad | Entrega | Done when |
|---|---|---|
| P0 | Métricas transición v2 | tests + scorecard con semántica explícita |
| P0 | Caldor temporal QA | 21 KML fechados + MTBS con UTC, intervalos y conteo 12–36 h |
| P0 | Caldor bridge | raster común + pares sin shrink imposible + licencia cerrada |
| P0 | Re-eval CLM/LATAM/PT | mismos pesos; copy/dilated/v2/AP; cero tuning TEST |
| P1 | RCDA reproduction | dataset versionado; split por evento; U-Net baseline reproducida |
| P1 | Pretrained temporal model | gana a U-Net en ≥2 geografías y no empeora calibración |
| P1 | FCER uncertainty | ECE + coverage-risk cerca del frente |
| P2 | FireSentry thermal adapter | rights+QA aprobados; split por región; no SAM2 como verdad incuestionada |
| P2 | Physics surrogate | gana latencia con error y dominio documentados |

## 8. Anti-claims

- Afiliación china ≠ datos de incendios chinos.
- Final scar ≠ progresión diaria.
- Hotspot ≠ perímetro.
- KML observado ≠ tensor listo para U-Net.
- Simulación de alta fidelidad ≠ validación real.
- IoU full-mask alto ≠ capacidad de predecir crecimiento.
- Threshold elegido en TEST ≠ resultado sellado.
- Foundation model de burn scar ≠ SOTA de propagación.

## 9. Fuentes primarias

- Google Research, Next Day Wildfire Spread: https://research.google/pubs/next-day-wildfire-spread-a-machine-learning-dataset-to-predict-wildfire-spreading-from-remote-sensing-data/
- WildfireSpreadTS dataset: https://zenodo.org/records/8006177
- SwinUnet time series: https://arxiv.org/abs/2502.12003
- TS-SatFire: https://arxiv.org/abs/2412.11555
- GOFER hourly progression: https://essd.copernicus.org/articles/16/1395/2024/
- FireBench synthetic: https://research.google/blog/firebench-using-high-performance-computing-to-advance-machine-learning-and-wildfire-research/
- FireBench Caldor v2026.1: https://zenodo.org/records/19041000
- FireBench Caldor v2026.2: https://zenodo.org/records/20279621
- USFS high-resolution DL surrogate: https://research.fs.usda.gov/firelab/projects/deeplearning
- RCDA-Net paper: https://doi.org/10.1080/01431161.2026.2619148
- RCDA dataset: https://zenodo.org/records/16641619
- FireSentry: https://github.com/Munan222/FireSentry-Benchmark-Dataset
- FY-3D fire product: https://essd.copernicus.org/articles/14/3489/2022/
- PT-FireSprd: https://essd.copernicus.org/articles/15/3791/2023/
- DEA Hotspots: https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/
- Canadian NFDB: https://cwfis.cfs.nrcan.gc.ca/index.php/datamart/metadata/nfdbpoly
- Prithvi-EO-2.0: https://research.ibm.com/publications/from-pixels-to-predictions-prithvi-eo-20-for-land-disaster-and-ecosystem-intelligence
- Boundary-aware UQ/FCER: https://arxiv.org/abs/2605.03148

## 10. Estado de esta iteración

Completado:

- investigación trazable por región y tarea;
- registro machine-readable;
- métrica v2 de crecimiento/cambio/shrink independiente;
- Average Precision de crecimiento;
- propagación a evaluación, early stopping y scorecards;
- corrección timezone Caldor + intervalos;
- bridge Caldor real: 21 raw/cumulative masks alineadas + MTBS separado;
- Caldor `clean17_physical_v1`: 15 pares × 17 covariables reales y 171 GeoTIFF espacialmente auditados; reparación temporal pendiente;
- rights gate Caldor evaluation-only por aviso Synoptic ausente;
- FCER `t0`-only, cobertura FCER y boundary F1 tolerante;
- re-evaluación congelada del ensemble CLM v34 en 200 parches TEST;
- archivo RCDA completo verificado, split por incendio y checkpoint upstream reproducido;
- suite amplia: 1.102 tests passed, 1 skipped y 4 tests slow/weights deseleccionados;
- Ruff/mypy focalizados y release gate en PASS.

### Re-evaluación v34 sin tuning de TEST

Comando: `python scripts/reeval_global_front_metrics.py --max-patches 200 --device cpu`  
Artefacto: `outputs/ml_eval/global_metrics_2026/clm_ensemble_v34.json`

| Métrica | Resultado |
|---|---:|
| full-mask IoU | 0,8963 |
| delta contra copy | +0,2545 |
| growth transition IoU v2 | 0,7835 |
| change transition IoU v2 | 0,7341 |
| growth AP macro | 0,8872 |
| FCER growth IoU (radio 3 px) | 0,8640 |
| FCER growth AP macro | 0,9172 |
| crecimiento observado cubierto por FCER | **19,58 %** |
| boundary F1 macro (tolerancia 1 px) | 0,7228 |
| delta boundary F1 vs dilated-copy | +0,2361 |

La cifra FCER alta **no es un score global**: el anillo de radio 3 captura solo el 19,58 % del crecimiento observado. Por eso el gate debe usar transition IoU global + cobertura FCER y nunca FCER aislada. La re-evaluación reproduce el IoU 0,8963 del manifiesto, lo que también comprueba que las nuevas métricas no cambian inferencia ni threshold.

Pendiente de la siguiente iteración del mega-goal:

- resolver la zona horaria de PT-FireSprd antes de unir meteo y ejecutar el modelo;
- reparar disponibilidad ERC y ventana válida HRRR del bridge Caldor;
- convertir el proxy LATAM/AU en un protocolo sellado con covariables espacialmente reales;
- reentrenar RCDA sobre el split sellado y entrenar/adaptar Caldor sobre `clean17_physical_v1`;
- obtener licencia y correspondencias temporales explícitas antes de entrenar con FireSentry.

## 11. Segunda auditoría: compatibilidad real y calibración FCER

### Caldor ya tiene clean17 físico, pero no un checkpoint compatible

La adquisición `clean17_physical_v1` materializa los 15 pares de 12–36 h sobre
una rejilla común EPSG:32610 de 2.199×1.302 píxeles a 30 m. Sus 17 canales son
reales: pendiente/aspecto USGS 3DEP; diez campos HRRR; altura, base, densidad y
presencia de canopy LF2020; y ERC gridMET. Los 135 subconjuntos HRRR contienen
solo los nueve registros GRIB necesarios por lead y cada ciclo fue inicializado
como mínimo una hora antes de `t0`.

La auditoría estructural comprobó 15×17 canales, 171 GeoTIFF únicos, hashes,
CRS, resolución, dimensiones y nodata. La auditoría semántica posterior separa
ese PASS espacial de un FAIL temporal: el ERC etiquetado con el día `t0` declara
cierre a las 07:00 UTC del día siguiente, y los resúmenes HRRR cubren leads
0–24 desde el ciclo, no exactamente `[t0,t1]`. No entran MTBS, RAVG, `t1` como
label ni placeholders, pero el paquete no es model-ready hasta reparar ambos
puntos. Artefactos:
`docs/CALDOR_CLEAN17_ACQUISITION.json` y `docs/CALDOR_CLEAN17_AUDIT.json`.

Esto no desbloquea el checkpoint `legacy17`: sus huecos constantes durante el
entrenamiento ahora contienen presión, nubosidad, visibilidad, punto de rocío y
canopy físico. Aplicarlo directamente sería un cambio de distribución no
validado. `model_inference_allowed=false` y `model_iou_allowed=false` se
mantienen hasta entrenar o adaptar explícitamente sobre el nuevo esquema.

### PT-FireSprd y LATAM/Australia

La matriz reproducible `docs/EXTERNAL_ML_COMPATIBILITY_AUDIT.json` separa tres
casos:

| Pack | Labels temporales | Inputs legacy17 | Uso actual |
|---|---:|---:|---|
| Caldor | 15 pares 12–36 h | clean17 sí; legacy17 no | geometría y entrenamiento clean17; checkpoint legacy bloqueado |
| PT-FireSprd São João Pesqueira | 8 escenas alineadas | no | progresión/geometry; inferencia bloqueada |
| LATAM/AU EMSR real_proxy | 4 pares utilizables | shape sí, semántica no | benchmark proxy exploratorio |

PT-FireSprd conserva `timestamp_tz=unspecified_in_source`; el adaptador anterior
lo presentaba como UTC por el contrato de nombres. Eso no altera el orden ni
los deltas internos, pero sí impide una unión meteorológica auditable.

En LATAM/AU, el IoU pack-macro del proxy es 0,7374 frente a 0,8074 de copy
(delta −0,0701). En macro por los cuatro pares, 0,7696 frente a 0,8306
(delta −0,0610). El modelo no supera copy en ninguno de los cuatro pares.
Esto invalida cualquier lectura de 0,7374 como transferencia positiva, aunque
el pipeline de inferencia sea técnicamente ejecutable.

### Calibración cerca del frente

La re-evaluación congelada de 200 parches añade, sobre el FCER derivado solo de
`t0`:

| Métrica | Resultado |
|---|---:|
| ECE FCER macro | 0,1875 |
| error selectivo a 80 % cobertura | 0,1493 |
| AURC normalizada | 0,1472 |
| prevalencia de crecimiento dentro de FCER | 0,8480 |

Estas cifras se acompañan obligatoriamente de la cobertura de crecimiento
observado del FCER (19,58 %): calibrar bien un anillo estrecho no demuestra
calibración global ni captura de saltos de largo alcance.

Fuentes primarias adicionales:

- USGS 3DEP: https://data.usgs.gov/datacatalog/data/USGS:3a81321b-c153-416f-98b7-cc8e5f0e17c3
- NOAA HRRR y archivos: https://rapidrefresh.noaa.gov/hrrr/
- LANDFIRE data/fuels: https://landfire.gov/data
- gridMET/Climatology Lab: https://www.climatologylab.org/gridmet.html

## 12. Auditoría reproducible RCDA-Net (China / datos Canadá-Alaska)

Se descargó el archivo oficial completo de Zenodo: 6.699.819.425 bytes y MD5
`d7856d77dcb823d0bdb5e10c6bac4f87`, idéntico al publicado. Extraído contiene
8.131 pares input/label, 886 incendios y años 2015–2019: 6.501 muestras TRAIN y
1.630 TEST. El barrido de los 8.131 pares comprobó forma, dtype, finitud,
binariedad y retención del perímetro previo al 100 %.

El split upstream no está separado por incendio: `UID_FIRE_656` aparece con 21
días en TRAIN (11–31 de agosto de 2018) y siete días inmediatamente posteriores
en TEST (1–7 de septiembre). El protocolo corregido reserva todos los incendios
TEST y mueve el UID solapado por completo a TEST:

| Split sellado | Incendios | Muestras |
|---|---:|---:|
| TRAIN | 596 | 5.552 |
| VAL | 106 | 928 |
| TEST | 184 | 1.651 |

La normalización se ajusta solo en TRAIN, el threshold se selecciona en VAL y
TEST queda para una única pasada tras congelar checkpoint y threshold. Se
reproduce con:

```text
python scripts/build_rcda_sealed_splits.py
python scripts/reproduce_rcda_full.py --threads 8
```

El checkpoint oficial sobre las 1.630 escenas TEST y la búsqueda upstream de
threshold reproduce con threshold 0,6: IoU 0,308310, F1 0,471310, precisión
0,484011 y recall 0,459259. Excluyendo las siete escenas filtradas del UID 656,
IoU 0,308194 y F1 0,471175. La cercanía numérica demuestra reproducción, no
independencia: `train.py` selecciona checkpoint por F1 de TEST y `eval.py`
selecciona threshold en ese mismo TEST.

Como referencia sellada sin entrenamiento, el radio de dilatación elegido solo
en VAL es 3 px y logra en TEST crecimiento IoU 0,110810/F1 0,199512. El copy de
extensión completa alcanza IoU 0,864960, ejemplo de por qué full-mask puede
ocultar una predicción débil de crecimiento.

Artefactos: `docs/RCDA_NET_FULL_PROTOCOL.json`,
`outputs/ml_eval/rcda_full_upstream/reproduction.json` y
`outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json`.

La auditoría causal y el plan de mejora quedan en
`docs/RCDA_CALDOR_RESULTS_AUDIT.md` y su espejo reproducible
`docs/RCDA_CALDOR_RESULTS_AUDIT.json`.

Fuentes primarias:

- Dataset RCDA/Wuhan: https://zenodo.org/records/16641619
- Loader: https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/dataset.py
- Entrenamiento: https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/train.py
- Evaluación: https://raw.githubusercontent.com/hxxAlways/RCDA-Net/main/eval.py

## 13. Auditoría reproducible FireSentry (China / UAV subsegundo)

La inspección del árbol Git fijado en el commit
`f8693204071a871562a3b4b4e24797a6a0d3ae3f` cambia una afirmación del README:
las cinco regiones A–E están públicamente presentes, no solo A. El árbol suma
684 blobs y 225,1 MB: 448 MP4, 230 JPEG, cinco CSV y el README. No existe un
archivo de licencia, por lo que acceso público no equivale a permiso de
entrenamiento, redistribución o uso comercial.

Se descargó una muestra mínima de Región A, en cuarentena y fijada por SHA-256,
para verificar el formato sin incorporar el corpus al entrenamiento:

- máscara e infrarrojo `video_001.mp4`: 832×480, 30 fps, 17 frames y 0,567 s;
- ambas secuencias coinciden exactamente en resolución, tasa, frames y duración;
- los tres frames de máscara muestreados ocupan solo 0,13–0,19 % de píxeles
  positivos, por lo que el desbalance es extremo;
- el asset visible es un JPEG 1920×1080, no un vídeo, y su relación con
  `video_001` no está documentada;
- el CSV usa GB18030, contiene 3.328 filas y 272 minutos únicos, no declara zona
  horaria ni relación con clips, y viento/dirección están vacíos en todas las filas;
- hay 6 valores CO y 186 valores O₃ negativos, que requieren reglas de QA.

El protocolo obligatorio queda así: licencia explícita antes de cualquier
training; mapeo temporal RGB/IR/máscara/ambiente; QA humana estratificada de las
máscaras SAM2; split por región y nunca por frames o clips adyacentes; evaluación
leave-one-region-out; y resultados térmicos separados del IoU diario de perímetros.
FireSentry puede servir para pretraining de encoder térmico/segmentación, pero no
para comparación numérica directa con NDWS, Caldor o PT-FireSprd.

Artefacto: `docs/FIRESENTRY_DATASET_AUDIT.json`.

Fuentes primarias:

- Repositorio/datos: https://github.com/Munan222/FireSentry-Benchmark-Dataset
- Árbol fijado: https://api.github.com/repos/Munan222/FireSentry-Benchmark-Dataset/git/trees/08461dd263986e99addbc1736e37436d2b371ea4?recursive=1
- Preprint: https://arxiv.org/abs/2512.03369
