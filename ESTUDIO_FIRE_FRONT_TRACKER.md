# Estudio revisado para Wildfire Front Dynamics

**Estado:** propuesta técnica y plan de validación  
**Fecha de revisión:** 2026-06-10  
**Repositorio de partida auditado:** [AlonsoAlviraa/DetectorDeIncendios](https://github.com/AlonsoAlviraa/DetectorDeIncendios)  
**Objetivo:** determinar qué sistema puede construirse de forma defendible para observar, reconstruir y estimar la dinámica de un frente de incendio.

## 1. Conclusión ejecutiva

El proyecto es viable como línea de investigación, pero su primer resultado no debe ser un predictor completo de incendios forestales. El riesgo principal no está en elegir una red neuronal, sino en disponer de observaciones temporales calibradas que permitan medir el error en terreno.

El primer producto defendible debe ser:

> A partir de una secuencia térmica radiométrica de una quema controlada, con timestamps y georreferenciación verificables, generar frentes observados, un campo de tiempo de llegada y estimaciones locales de velocidad, indicando cuándo la velocidad no es observable por exceso de incertidumbre.

La predicción futura queda fuera del camino crítico inicial. Solo debe abordarse después de demostrar que el sistema puede localizar y reconstruir correctamente lo ya observado.

### Decisiones recomendadas

1. Mantener `DetectorDeIncendios` como sistema de alerta temprana y fuente de componentes reutilizables.
2. Desarrollar este repositorio como un proyecto modular independiente.
3. No crear todavía un tercer repositorio compartido; extraer una librería común cuando existan contratos estables y reutilización real.
4. Priorizar datos de quemas controladas y un evaluador sintético antes de entrenar modelos complejos.
5. Separar estrictamente productos `observed`, `inferred` y `forecast`.
6. Tratar la georreferenciación y la incertidumbre como funcionalidades centrales, no como postprocesado.

## 2. Pregunta de investigación

La pregunta principal no es si una red puede segmentar fuego:

> ¿Con qué precisión espacial y temporal puede reconstruirse la propagación de un frente activo a partir de observaciones aéreas térmicas incompletas?

Preguntas subordinadas:

- ¿Qué definición operacional de frente puede anotarse de forma consistente?
- ¿Cuál es el error mínimo alcanzable al proyectar una detección desde imagen a terreno?
- ¿Cuándo el desplazamiento observado es suficientemente grande frente al error espacial para estimar velocidad?
- ¿Cómo deben representarse huecos de observación, extinción local y focos secundarios?
- ¿Qué componentes del detector existente reducen realmente el trabajo?

## 3. Alcance y productos

### 3.1 Producto táctico inicial

Entradas:

- secuencia térmica radiométrica;
- RGB sincronizado cuando esté disponible;
- calibración intrínseca y distorsión;
- pose de cámara por frame;
- timestamps en UTC;
- modelo digital del terreno o superficie;
- observaciones meteorológicas disponibles.

Salidas:

- máscara de clases térmicas;
- frente observado en coordenadas métricas;
- campo de tiempo de llegada;
- isocronas reconstruidas;
- velocidad normal local;
- incertidumbre y trazabilidad de cada salida.

Actualización objetivo: cada 30-60 segundos, siempre que el movimiento sea observable.

### 3.2 Fuera del alcance inicial

- dirigir operaciones reales de extinción;
- operar drones cerca de un incendio activo sin coordinación oficial;
- prometer predicción operacional;
- inferir velocidad métrica a partir de cámaras RGB fijas no calibradas;
- usar área quemada postincendio como equivalente del frente activo;
- construir simultáneamente una plataforma GIS completa y un simulador físico.

## 4. Auditoría de `DetectorDeIncendios`

Se descargó y revisó el repositorio público en el commit:

```text
5cc86819d76da95ac3485a8026a7f0b5999baab0
2026-05-27T13:33:00+02:00
```

El repositorio contiene aproximadamente 154 módulos Python, incluidos 64 archivos de pruebas. Está orientado a detección temprana de humo mediante YOLO, agregación temporal, reducción de falsas alarmas, auditoría de datasets y pruebas edge.

### 4.1 Componentes realmente reutilizables

| Componente | Evidencia auditada | Reutilización propuesta |
|---|---|---|
| Ingesta y manifiestos | `src/data_prep/ingesta_pipeline.py` calcula hash, cámara, timestamp, estado QA y procedencia | Extender el registro para sensores, calibración, pose, CRS y archivos radiométricos |
| Identidad y deduplicación | Hash SHA-256 y manifiestos gobernados | Evitar duplicados y fugas entre incendios o quemas |
| Tracking temporal | `src/inference/track_temporal_alarm.py` agrega detecciones por secuencia y track | Reutilizar patrones de eventos y timestamps, no la geometría basada en bounding boxes |
| Política temporal | Persistencia, EMA, top-k y crecimiento aparente | Usar como referencia para control de calidad temporal |
| Métricas por secuencia | `src/evaluation/sequence_metrics.py` calcula recall, falsas alarmas y métricas por cámara | Extender a métricas por quema, sensor y localización |
| Calibración y evaluación OOD | Calibración por cámara/localización y `test_ood` final | Aplicar splits por quema, región, fecha y sensor |
| Auditoría de datasets | Módulos específicos de leakage, calidad y distribuciones | Reutilización alta |
| Edge | Exportación y benchmarks de latencia | Reutilizar después de validar el pipeline científico |

### 4.2 Componentes que no existen en el detector

La auditoría no encontró:

- segmentación de máscaras de fuego o frente;
- `smoke_mask_growth.py`;
- `segment_smoke_sequences.py`;
- calibración fotogramétrica;
- pose GNSS/IMU/gimbal;
- proyección de píxeles sobre DEM;
- geometrías GeoJSON;
- rasters georreferenciados;
- estimación métrica de velocidad.

Por tanto, el detector aporta gobernanza de datos y lógica temporal, pero no el núcleo geométrico de Wildfire Front Dynamics.

### 4.3 Limitaciones técnicas heredadas

- El manifiesto actual normaliza imágenes a JPEG, lo que destruiría valores térmicos radiométricos. Los TIFF térmicos deben conservarse sin conversión.
- Los tracks actuales trabajan con bounding boxes normalizados, insuficientes para representar un frente.
- Las dependencias no están fijadas por versión.
- Los datos, pesos y artefactos no están publicados, por lo que no puede reproducirse el rendimiento completo desde el repositorio público.
- La ejecución de pruebas requiere `pytest`, que no está incluido en el entorno actual.

## 5. La definición de frente

Antes de construir modelos se necesita una ontología estable. Deben distinguirse:

| Clase | Definición operacional |
|---|---|
| `active_flame_front` | Línea o banda estrecha donde existe combustión activa y avance observable |
| `active_fire_region` | Región con señal compatible con fuego activo |
| `residual_hotspot` | Zona caliente sin avance de frente demostrado |
| `burned_area` | Área acumulada que ya ha ardido |
| `secondary_ignition` | Componente activo desconectado del frente principal |
| `unobservable` | Zona oculta, fuera del campo de visión o sin evidencia suficiente |

Una máscara de fuego activo no equivale automáticamente a una línea de frente. El método para extraer el frente debe formar parte del protocolo de anotación y evaluación.

## 6. Requisitos mínimos de datos

### 6.1 Puerta de viabilidad del MVP

No debe comenzar el entrenamiento principal hasta disponer de al menos una secuencia que cumpla:

- térmico radiométrico o multiespectral útil;
- timestamps fiables;
- intervalo temporal conocido;
- calibración intrínseca;
- posición y orientación por frame, o imágenes ya ortorrectificadas;
- sistema de referencia y resolución espacial;
- ground truth independiente o protocolo de anotación repetible;
- varias observaciones del mismo frente durante su avance.

Si no se cumplen estos requisitos, el resultado solo puede expresarse en píxeles y segundos.

### 6.2 Datasets contrastados

| Recurso | Aporta | No resuelve | Prioridad |
|---|---|---|---:|
| FLAME 3 | RGB y térmico radiométrico sincronizado en quemas prescritas; seis quemas completas bajo solicitud | Debe auditarse si la pose y el ground truth permiten velocidad métrica | Muy alta |
| NASA AMS | Segmentación multiespectral aérea de fuego activo; IR, SWIR y térmico | No garantiza secuencia táctica ni ground truth de velocidad | Alta |
| ActiveFire Landsat-8 | Firmas espectrales y máscaras globales | Frecuencia temporal insuficiente; código antiguo | Media |
| TS-SatFire | Series satelitales, área quemada, meteorología, terreno y forecast diario | No sirve para velocidad táctica | Media, línea estratégica |
| Next Day Wildfire Spread | Baseline público para propagación diaria | No representa observación táctica | Media, línea estratégica |
| WildFireVQA | TIFF térmico radiométrico y RGB | Está diseñado para VQA, no para reconstruir propagación | Exploratoria |
| WIT-UAS-ROS | Bags con sensores de vuelos sobre quemas prescritas | Etiquetas orientadas a personas y vehículos | Auditar metadatos |

### 6.3 Hallazgos de disponibilidad

- El repositorio NASA AMS fue clonado, pero la descarga de datos falló porque su cuota de Git LFS está excedida. El código y la estructura siguen siendo auditables, pero no debe dependerse de esa descarga para el primer hito.
- ActiveFire fue descargado correctamente. Publica código y contratos útiles, pero usa una pila TensorFlow/Keras antigua y sus grandes datasets están alojados externamente.
- FLAME 3 es el candidato prioritario para solicitar y auditar porque se aproxima más al escenario del MVP.

## 7. Arquitectura propuesta

```text
DetectorDeIncendios
  alerta + cámara + timestamp
             |
             v
Wildfire Front Dynamics
  1. ingestión radiométrica y validación
  2. segmentación multiclase
  3. extracción de frente observado
  4. proyección a terreno
  5. reconstrucción temporal
  6. velocidad e incertidumbre
             |
             v
  GeoPackage / GeoParquet / GeoTIFF / Zarr
             |
             v
  visor de resultados observados e inferidos
```

La predicción estratégica debe ser un pipeline separado que consuma productos observados ya validados.

### 7.1 Estructura inicial recomendada

```text
WildfireFrontDynamics/
  docs/
  schemas/
  src/wildfire_front/
    ingestion/
    segmentation/
    georeferencing/
    reconstruction/
    metrics/
  tests/
  external/                 # ignorado por Git
```

No se recomienda copiar módulos enteros del detector. Conviene portar únicamente funciones verificadas y conservar atribución e historial de procedencia.

## 8. Contratos de datos

### 8.1 Registro de observación

Para almacenamiento interno se recomienda GeoParquet o GeoPackage con CRS explícito. GeoJSON debe reservarse para intercambio y visualización en WGS84.

Campos mínimos:

```json
{
  "observation_id": "burn_001__thermal_01__2026-06-10T12:30:00.000Z",
  "event_id": "burn_001",
  "observed_at": "2026-06-10T12:30:00.000Z",
  "acquisition_duration_ms": 33,
  "sensor_id": "thermal_01",
  "source_uri": "raw/burn_001/thermal/frame_001.tiff",
  "source_sha256": "...",
  "calibration_id": "thermal_01_cal_v2",
  "pose_id": "pose_001",
  "crs": "EPSG:25830",
  "resolution_m": 0.25,
  "processing_version": "front-pipeline-v0.1.0",
  "status": "observed",
  "confidence": 0.87,
  "estimated_error_m": 2.4
}
```

La geometría debe almacenarse como una geometría real `LineString` o `MultiLineString`, no como texto.

### 8.2 Campo de tiempo de llegada

Raster o Zarr con:

- `arrival_time_mean_s`;
- `arrival_time_std_s`;
- `observation_count`;
- `last_observed_at`;
- `state`: `unburned`, `active`, `burned`, `unobservable`;
- CRS, transformación, resolución, unidades y `nodata`.

### 8.3 Velocidad local

Cada estimación debe incluir:

- posición en CRS métrico;
- intervalo temporal utilizado;
- velocidad normal y dirección;
- error estándar o intervalo;
- desplazamiento observado;
- error espacial agregado;
- método;
- bandera `observable`.

Una regla inicial razonable es no publicar velocidad cuando el desplazamiento estimado no supera un múltiplo configurable del error espacial combinado.

## 9. Métodos recomendados

### 9.1 Evaluador sintético primero

Antes de usar fuego real debe construirse un generador simple de frentes:

1. crear geometrías con velocidad conocida;
2. simular observaciones parciales, ruido de pose y huecos;
3. reconstruir el tiempo de llegada;
4. estimar velocidad;
5. comprobar que los intervalos de incertidumbre cubren el valor real.

Este evaluador permite validar la matemática sin confundir errores geométricos con errores del segmentador.

### 9.2 Segmentación

Orden experimental:

1. umbral térmico radiométrico y morfología;
2. U-Net o DeepLabV3+ multiclase;
3. fusión RGB-térmica;
4. SegFormer u otro encoder moderno;
5. suavizado temporal o modelo secuencial solo si mejora métricas por quema.

El baseline térmico es obligatorio. Un modelo complejo solo se acepta si mejora el error métrico final, no únicamente IoU.

### 9.3 Georreferenciación

Dos rutas:

- **Preferida para el primer MVP:** imágenes ortorrectificadas o nadir con transformación conocida.
- **Avanzada:** lanzamiento de rayos desde cámara calibrada e intersección con DEM.

La incertidumbre debe incorporar, como mínimo, error de segmentación, pose, orientación, sincronización y elevación.

### 9.4 Reconstrucción temporal

Primera versión:

1. rasterizar observaciones en malla métrica;
2. mantener por separado `observed` y `inferred`;
3. generar signed distance fields;
4. estimar correspondencias en dirección normal;
5. interpolar únicamente donde exista soporte observacional;
6. representar huecos como `unobservable`;
7. extraer isocronas con incertidumbre.

No debe imponerse monotonía al frente activo. La monotonía solo aplica al estado acumulado `burned`.

### 9.5 Predicción

La predicción debe comenzar con modelos físicos o baselines simples y evaluarse separadamente:

- persistencia;
- propagación isotrópica;
- modelo condicionado por pendiente y viento;
- level-set;
- modelos aprendidos y probabilísticos.

Los modelos probabilísticos basados en WRF-SFIRE son prometedores, pero sus resultados sobre simulación no demuestran generalización a observaciones reales.

## 10. Métricas y criterios de aceptación

### 10.1 Métricas

| Producto | Métricas principales |
|---|---|
| Segmentación | IoU y recall por clase, pero también error del frente proyectado |
| Frente | distancia media, P95, Hausdorff robusta y cobertura dentro de buffers |
| Llegada | MAE temporal, error por celda y consistencia del estado acumulado |
| Velocidad | MAE/RMSE en `m/min`, error angular y porcentaje observable |
| Incertidumbre | cobertura de intervalos, calibración y sharpness |
| Sistema | latencia P50/P95, tasa de frames rechazados y disponibilidad |

### 10.2 Puertas go/no-go

Los valores finales deben fijarse tras auditar resolución y error del dataset. Las puertas iniciales son:

1. **Datos:** existe al menos una secuencia apta y reproducible.
2. **Geometría:** el error de proyección es menor que el desplazamiento típico entre observaciones.
3. **Reconstrucción:** el pipeline recupera velocidades sintéticas dentro de sus intervalos.
4. **Observación real:** el frente proyectado supera al baseline térmico simple.
5. **Velocidad:** el sistema sabe abstenerse cuando no existe observabilidad suficiente.

Los splits deben hacerse por quema/incendio, región, fecha y sensor. Nunca por parches aleatorios del mismo evento.

## 11. Hoja de ruta revisada

### Fase 0. Viabilidad de datos y contratos, 1-2 semanas

- solicitar y auditar FLAME 3 completo;
- auditar WIT-UAS-ROS y alternativas con pose;
- cerrar ontología y protocolo de anotación;
- definir esquemas y criterios go/no-go;
- documentar licencia y procedencia.

**Salida:** informe de disponibilidad y una secuencia elegida.  
**No-go:** ninguna secuencia permite evaluación métrica.

### Fase 1. Núcleo geométrico sintético, 2-3 semanas

- crear malla, geometrías y frentes sintéticos;
- implementar signed distance fields;
- reconstruir llegada e isocronas;
- estimar velocidad normal;
- calibrar abstención e incertidumbre.

**Salida:** evaluador reproducible con verdad conocida.

### Fase 2. Ingesta radiométrica y baseline, 2-4 semanas

- extender los patrones de manifiestos del detector;
- conservar TIFF y metadatos sin pérdida;
- implementar baseline térmico;
- anotar un subconjunto multiclase;
- evaluar por quema.

**Salida:** frente en coordenadas de imagen con métricas.

### Fase 3. Proyección a terreno, 4-8 semanas

- comenzar con datos ortorrectificados;
- medir error de georreferenciación;
- generar frentes métricos;
- propagar incertidumbre;
- validar con puntos o geometrías independientes.

**Salida:** frente observado auditable en CRS métrico.

### Fase 4. Dinámica observada, 4-6 semanas

- reconstruir llegada;
- producir isocronas;
- estimar velocidad local;
- implementar abstención;
- medir latencia y estabilidad.

**Salida:** demostrador táctico offline completo.

### Fase 5. Predicción estratégica, línea separada

- establecer baselines con Next Day Wildfire Spread y TS-SatFire;
- evaluar transferencia al Mediterráneo;
- asimilar observaciones tácticas;
- producir ensembles calibrados.

## 12. Riesgos principales

| Riesgo | Impacto | Mitigación |
|---|---:|---|
| No existe dataset público completo para el MVP | Crítico | Solicitar FLAME 3 y colaborar en quemas controladas |
| Error espacial mayor que el avance | Crítico | Medir observabilidad y permitir abstención |
| Etiquetas inconsistentes | Alto | Ontología y doble anotación |
| TIFF radiométrico degradado a imagen coloreada | Alto | Conservación sin pérdida y validación de metadatos |
| Dominio estadounidense no transfiere al Mediterráneo | Alto | Evaluación OOD y datos locales |
| Oclusión y focos secundarios | Alto | Estado `unobservable` y geometrías múltiples |
| Dependencia de repositorios externos frágiles | Medio | Registrar commit, licencia, hashes y mirrors permitidos |
| Uso operativo indebido | Crítico | Mantener carácter experimental y validación humana |

## 13. Hardware y operación

No debe comprarse hardware antes de superar las fases sintética y de datos públicos.

Para una futura captura propia:

- cámara térmica radiométrica;
- RGB sincronizado;
- GNSS RTK/PPK;
- IMU y telemetría de gimbal;
- calibración intrínseca y extrínseca;
- estación meteorológica;
- puntos de control o método independiente de validación;
- coordinación formal con responsables de la quema y del espacio aéreo.

Los vuelos sobre incendios activos no forman parte de una prueba académica ordinaria. Deben realizarse únicamente dentro de una operación autorizada y coordinada.

## 14. Próxima acción recomendada

La siguiente acción no es entrenar una red. Es crear un **informe de auditoría de datasets para el MVP** con una tabla binaria por recurso:

- radiométrico;
- RGB sincronizado;
- timestamps;
- pose;
- calibración;
- CRS;
- DEM;
- secuencia continua;
- etiqueta de frente;
- ground truth métrico;
- licencia;
- acceso real.

Solo después debe elegirse la primera secuencia de trabajo.

## 15. Fuentes verificadas

### Código auditado

- DetectorDeIncendios: https://github.com/AlonsoAlviraa/DetectorDeIncendios
- NASA AMS: https://github.com/nasa/Autonomous-Modular-Sensor-Wildfire-Segmentation
- ActiveFire: https://github.com/pereira-gha/activefire

### Datasets y métodos

- NASA AMS paper: https://arxiv.org/abs/2601.14475
- FLAME 3: https://arxiv.org/abs/2412.02831
- ActiveFire: https://arxiv.org/abs/2101.03409
- TS-SatFire: https://arxiv.org/abs/2412.11555
- Next Day Wildfire Spread: https://arxiv.org/abs/2112.02447
- WildFireVQA: https://arxiv.org/abs/2604.20190
- WIT-UAS: https://arxiv.org/abs/2312.09159
- FireNet: https://arxiv.org/abs/1910.06407
- Bayesian level-set assimilation: https://arxiv.org/abs/2206.08501
- Arrival-time inference: https://arxiv.org/abs/2309.02615
- Probabilistic localized spread forecasting: https://arxiv.org/abs/2603.26975
- OpenWFM / WRF-SFIRE: https://www.openwfm.org/

## 16. Veredicto

El valor diferencial de Wildfire Front Dynamics no será detectar más fuego, sino demostrar cuándo una observación permite afirmar, con error cuantificado, dónde está el frente y a qué velocidad avanza.

El proyecto debe considerarse exitoso cuando pueda producir una reconstrucción auditable y también negarse a producir una velocidad cuando los datos no la sostienen.
