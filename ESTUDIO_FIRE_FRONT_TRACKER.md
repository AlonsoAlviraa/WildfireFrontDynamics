# Estudio para un sistema de localizacion y propagacion de incendios forestales

## Resumen ejecutivo

Este documento estudia la evolucion del proyecto actual de deteccion temprana de humo hacia un sistema capaz de:

1. localizar con precision el frente de llama activo;
2. reconstruir isocronas de propagacion;
3. estimar la velocidad local de propagacion casi en tiempo real;
4. generar predicciones probabilisticas de evolucion.

La conclusion principal es que el objetivo es viable, pero no debe plantearse como una simple ampliacion del detector YOLO actual. El detector existente puede actuar como sistema de alerta y activacion, mientras que la nueva solucion necesita un nucleo geoespacial, multiespectral y temporal propio.

La arquitectura recomendada utiliza dos escalas complementarias:

- **Escala tactica, segundos-minutos:** observacion aerea RGB-termica para delimitar el frente activo y estimar velocidad local.
- **Escala estrategica, horas-dias:** observacion satelital, meteorologia, topografia y combustibles para reconstruir progresion y predecir propagacion.

No se recomienda entrenar un unico modelo que mezcle directamente ambas escalas. Sus resoluciones, frecuencias, errores y objetivos operativos son diferentes.

## Decision recomendada

Crear un proyecto hermano, manteniendo este repositorio como detector y fuente de componentes reutilizables:

```text
DetectorDeIncendios/       # deteccion temprana, alarmas y verificacion
FireFrontTracker/          # frente activo, isocronas y velocidad
shared_wildfire/           # contratos, metricas y utilidades comunes
```

El primer producto demostrable deberia ser:

> A partir de una secuencia georreferenciada RGB-termica de una quema controlada, producir cada 30-60 segundos un frente activo GeoJSON, isocronas acumuladas y un mapa de velocidad local con incertidumbre.

Ese objetivo es medible, defendible academicamente y suficientemente acotado para evitar convertir el proyecto en una plataforma GIS, un simulador fisico y un sistema de drones al mismo tiempo.

## Que podemos reutilizar del proyecto actual

| Componente actual | Reutilizacion | Uso propuesto |
|---|---:|---|
| Ingesta, manifests y auditoria | Alta | Trazabilidad de vuelos, frames, sensores y anotaciones |
| `smoke_mask_growth.py` | Alta | Base para caracteristicas geometricas y temporales de mascaras |
| `segment_smoke_sequences.py` | Media-alta | Plantilla para segmentacion y asociacion temporal |
| Tracking temporal | Media-alta | Seguimiento de regiones y eventos persistentes |
| Metricas por secuencia | Media | Evaluacion temporal y por localizacion |
| Calibracion y meta-juez | Media | Fusion de observaciones y gestion de incertidumbre |
| Detector de humo | Alta como activador | Disparar adquisicion intensiva o revision |
| Pesos YOLO de humo | Baja | El frente de llama requiere otras etiquetas y modalidades |

El codigo actual trabaja principalmente en coordenadas de imagen. La nueva dificultad dominante sera convertir observaciones en coordenadas geograficas fiables.

## El problema real: de pixeles a terreno

Una mascara precisa en una imagen no implica una localizacion precisa sobre el terreno. Para proyectar el frente se necesitan:

- calibracion intrinseca de la camara;
- distorsion de lente;
- posicion GNSS, preferiblemente RTK o PPK;
- orientacion IMU y angulos del gimbal;
- sincronizacion temporal entre sensores;
- altura y modelo digital del terreno;
- sistema de referencia de coordenadas metrico;
- modelo explicito de incertidumbre.

Sin estos elementos solo puede estimarse movimiento en pixeles. No puede defenderse una velocidad en `m/min` ni una isocrona geografica.

## Arquitectura propuesta

```text
Detector de humo existente
        |
        v
Activacion de observacion intensiva
        |
        +-------------------------------+
        |                               |
        v                               v
UAV/camara RGB-termica            Satelite + meteo + DEM
        |                               |
        v                               v
Segmentacion frente activo        Progresion y contexto regional
        |                               |
        v                               v
Proyeccion pixel -> terreno        Campo de llegada historico
        |                               |
        +---------------+---------------+
                        |
                        v
            Fusion y asimilacion de datos
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
     Frente activo   Isocronas    Velocidad/forecast
```

## Recursos prioritarios

### 1. NASA Autonomous Modular Sensor Wildfire Segmentation

- Repositorio: https://github.com/nasa/Autonomous-Modular-Sensor-Wildfire-Segmentation
- Paper: https://arxiv.org/abs/2601.14475

Es el recurso mas cercano al objetivo tactico. Incluye imagenes aereas multiespectrales del sensor AMS, con canales IR, SWIR y termicos, anotaciones humanas y segmentacion pixel a pixel.

Datos y resultados publicados:

- imagenes de misiones reales de incendios;
- parches multicanal de 256 x 256;
- escenas nocturnas, humo, nubes y falsos positivos;
- modelo combinado de clasificacion y segmentacion;
- aproximadamente 74% IoU y 84% recall publicados para localizacion activa.

Interesa especialmente porque el trabajo identifica SWIR, IR y termico como las bandas mas utiles para distinguir el frente activo.

**Como lo usaria:**

1. reproducir su pipeline como baseline;
2. adaptar el preprocesado multicanal a nuestro formato de manifests;
3. comparar U-Net/DeepLab/SegFormer frente a su modelo;
4. extraer el contorno activo de la mascara;
5. evaluar continuidad temporal y no solo IoU por imagen.

**Limitaciones:** repositorio reciente, pocas estrellas y gran parte del flujo vive en notebooks. Debe tratarse como referencia cientifica y dataset, no como software listo para produccion.

### 2. ActiveFire Landsat-8

- Repositorio: https://github.com/pereira-gha/activefire
- Paper: https://arxiv.org/abs/2101.03409

Dataset global de deteccion y segmentacion de fuego activo en Landsat-8. Contiene mas de 150.000 parches multiespectrales y mascaras, con una parte manualmente anotada. El repositorio publica codigo, pesos y licencia CC-BY-4.0.

**Como lo usaria:**

- aprender firmas espectrales de fuego activo;
- preentrenar o validar una rama multiespectral;
- estudiar generalizacion geografica;
- comparar reglas espectrales clasicas con CNN;
- construir un baseline satelital reproducible.

**No sirve para:** estimar directamente velocidad casi en tiempo real. Landsat ofrece buena resolucion espacial, pero su frecuencia temporal no permite seguimiento tactico continuo.

### 3. TS-SatFire

- Paper: https://arxiv.org/abs/2412.11555

Dataset temporal multiarea de aproximadamente 71 GB que cubre incendios de Estados Unidos entre 2017 y 2021. Incluye imagenes multitemporales, fuego activo, area quemada, meteorologia, topografia, cobertura y combustibles.

Soporta tres tareas alineadas con el nuevo proyecto:

1. deteccion de fuego activo;
2. monitorizacion diaria de area quemada;
3. prediccion de progresion al dia siguiente.

**Como lo usaria:**

- entrenar la rama estrategica multitemporal;
- reconstruir campos diarios de tiempo de llegada;
- generar isocronas de referencia;
- estudiar modelos multi-tarea compartiendo encoder;
- evaluar transferencia hacia incendios mediterraneos.

Es probablemente el recurso mas completo para unir deteccion, progresion y prediccion, pero no sustituye las observaciones aereas de alta frecuencia.

### 4. Next Day Wildfire Spread

- Paper: https://arxiv.org/abs/2112.02447
- Codigo: https://github.com/google-research/google-research/tree/master/simulation_research/next_day_wildfire_spread

Benchmark de Google Research para predecir propagacion al dia siguiente usando fuego actual, topografia, vegetacion, meteorologia, sequia y otras variables rasterizadas.

**Como lo usaria:**

- baseline de prediccion de propagacion;
- definir contratos de datos raster;
- comparar regresion logistica, random forest, CNN y modelos temporales;
- estudiar importancia de variables;
- validar que nuestro sistema supera un baseline conocido.

No debe confundirse prediccion diaria con velocidad tactica del frente. Es una tarea distinta y debe evaluarse por separado.

### 5. UN-SPIDER Burn Severity Mapping con Google Earth Engine

- Portal: https://www.un-spider.org/advisory-support/recommended-practices
- Google Earth Engine: https://earthengine.google.com/

Es una buena via para crear una primera demo geoespacial con imagenes pre y post incendio, indices como NBR/dNBR y mapas de severidad.

**Como lo usaria:**

- prototipo visual rapido;
- familiarizacion con Sentinel/Landsat y GEE;
- validacion aproximada de areas quemadas;
- generacion inicial de capas GIS y exportaciones GeoTIFF/GeoJSON.

**No debe venderse como:** localizacion del frente activo ni reconstruccion precisa de isocronas. Burn severity es principalmente analisis post-incendio.

## Recursos adicionales que merece la pena incorporar

### WildFireVQA

- Repositorio: https://github.com/mobiiin/WildFire_VQA
- Paper: https://arxiv.org/abs/2604.20190

Incluye mas de 6.000 muestras RGB-termicas radiometricas y preguntas sobre segmentacion, localizacion, direccion y planificacion. Es interesante para adquirir experiencia con TIFF termicos radiometricos y fusion RGB-termica.

No usaria un VLM para calcular el frente o la velocidad. Si podria emplearse como capa auxiliar de explicacion y control de calidad humano.

### FireNet

- Paper: https://arxiv.org/abs/1910.06407

Referencia importante de segmentacion de perimetros desde video infrarrojo aereo. Reporta procesamiento de 20 FPS y demuestra que la segmentacion tactica en video termico puede ejecutarse en tiempo real.

### Modelos level-set y asimilacion bayesiana

- Asimilacion bayesiana: https://arxiv.org/abs/2206.08501
- WRF-SFIRE/OpenWFM: https://www.openwfm.org/

Los metodos level-set representan el frente como una funcion implicita y permiten propagarlo sobre una malla. Son una base natural para:

- reconstruir el campo de tiempo de llegada;
- generar isocronas;
- calcular normales al frente;
- estimar velocidad local;
- corregir predicciones cuando llegan nuevas observaciones.

WRF-SFIRE es potente, pero demasiado complejo para ser la primera implementacion. Conviene comenzar con un level-set ligero y usar WRF-SFIRE posteriormente como simulador o fuente de datos sinteticos.

### Prediccion probabilistica

- Conditional Flow Matching para propagacion: https://arxiv.org/abs/2603.26975
- Inferencia de tiempo de llegada: https://arxiv.org/abs/2309.02615

La salida operativa no deberia ser una unica linea futura. Debe producir bandas o ensembles de incertidumbre. Estos trabajos muestran una direccion prometedora: aprender distribuciones del tiempo de llegada condicionadas por fuego actual, viento, humedad, terreno y combustible.

## Lo aprendido de GitHub, China y comunidades

### GitHub

Los repositorios mas utiles no intentan resolver todo:

- NASA AMS separa clasificacion y segmentacion para ahorrar computo.
- ActiveFire publica datasets procesados, pesos y reglas clasicas como baseline.
- Google Research estructura la prediccion como tensores raster multicanal.
- WildFireVQA conserva datos termicos radiometricos, no solo imagenes coloreadas.

Leccion: debemos versionar contratos y metadatos, no datasets pesados. Cada observacion debe conservar sensor, CRS, timestamp, calibracion, resolucion y procedencia.

### Ecosistema chino

Las busquedas en GitHub/Gitee muestran muchos proyectos pequenos de YOLO para humo o llamas, pero pocos ofrecen evaluacion geoespacial, datos abiertos o reconstruccion de propagacion. No los tomaria como base cientifica.

Si utilizaria ecosistemas chinos maduros:

- OpenMMLab/MMDetection y MMSegmentation para segmentacion y comparativas reproducibles;
- PaddleDetection/PaddleSeg para despliegue y edge;
- modelos multimodales como Qwen-VL o InternVL solo para revision auxiliar y explicaciones.

Leccion: interesa reutilizar frameworks industriales, no copiar demos de deteccion con datasets opacos.

### Reddit y X

Las comunidades sociales son utiles para descubrir problemas operativos, pero no para justificar decisiones cientificas. Las señales recurrentes son:

- los usuarios valoran mapas simples, timestamps claros y actualizaciones fiables;
- los perimetros aparentan mas precision de la que realmente tienen;
- la latencia y la antiguedad de la observacion importan tanto como la geometria;
- los vuelos no autorizados cerca de incendios pueden interferir con aeronaves de extincion;
- los sistemas deben mostrar incertidumbre y fuente de cada capa.

Leccion: toda geometria publicada debe incluir `observed_at`, `source`, `resolution`, `confidence` y `estimated_error_m`.

## Diseño de datos recomendado

### Observacion de frente

```json
{
  "front_id": "fire_2026_001__2026-06-10T12:30:00Z",
  "observed_at": "2026-06-10T12:30:00Z",
  "source": "uav_thermal",
  "sensor_id": "thermal_01",
  "crs": "EPSG:25830",
  "geometry": "GeoJSON LineString",
  "estimated_error_m": 4.5,
  "confidence": 0.87
}
```

### Campo de tiempo de llegada

Un GeoTIFF o Zarr con:

- `arrival_time_mean`;
- `arrival_time_std`;
- `last_observed_at`;
- `observation_count`;
- mascara de zona no observable.

### Velocidad local

```json
{
  "point": "GeoJSON Point",
  "observed_at": "2026-06-10T12:30:00Z",
  "rate_of_spread_m_min": 3.8,
  "direction_deg": 72.0,
  "uncertainty_m_min": 1.1,
  "method": "signed_distance_normal"
}
```

## Algoritmos recomendados

### Segmentacion del frente activo

Orden de experimentos:

1. umbral termico adaptativo y morfologia como baseline;
2. U-Net o DeepLabV3+ multiespectral;
3. SegFormer o Mask2Former;
4. fusion RGB-termica tardia;
5. modelo combinado clasificador + segmentador inspirado en NASA AMS.

La mascara de zona caliente no siempre equivale al frente activo. Debemos separar, cuando los datos lo permitan:

- frente de llama activo;
- zona caliente residual;
- area quemada;
- focos secundarios.

### Proyeccion a terreno

1. calibrar camara y lente;
2. obtener pose GNSS/IMU/gimbal por frame;
3. lanzar rayos desde pixeles del contorno;
4. intersectar rayos con DEM;
5. transformar a CRS metrico;
6. simplificar geometria sin borrar detalles relevantes;
7. propagar incertidumbre de pose y DEM.

Esta parte debe implementarse y evaluarse antes de afirmar que el sistema localiza con precision.

### Reconstruccion de isocronas

Primera version:

1. almacenar frentes con timestamp;
2. rasterizar perimetros en una malla metrica;
3. construir signed distance fields;
4. interpolar tiempos de llegada entre observaciones;
5. regularizar respetando que el fuego no puede desquemar celdas;
6. extraer curvas de nivel temporales.

Version avanzada:

- level-set con asimilacion bayesiana;
- condicionamiento por pendiente, viento y combustible;
- bandas de incertidumbre.

### Velocidad de propagacion

La velocidad debe calcularse en direccion normal al frente, no mediante cambio de area total:

```text
ROS(x) = distancia normal entre frentes / intervalo temporal
```

Compararia:

- distancia normal entre polilineas;
- diferencia de signed distance fields;
- level-set velocity;
- optical flow georreferenciado como feature auxiliar.

El optical flow no debe ser la verdad de terreno: las llamas oscilan aunque el frente no avance.

## Metricas

### Localizacion del frente

- distancia media y percentil 95 al frente real en metros;
- Hausdorff distance;
- precision/recall dentro de buffers de 5, 10 y 20 metros;
- continuidad del frente;
- latencia extremo a extremo.

### Isocronas

- error absoluto del tiempo de llegada;
- distancia entre isocronas observadas y estimadas;
- porcentaje de celdas con intervalo de incertidumbre bien calibrado;
- consistencia monotona temporal.

### Velocidad

- MAE y RMSE en `m/min`;
- error angular de direccion;
- sesgo por pendiente, combustible y viento;
- estabilidad entre actualizaciones;
- cobertura de intervalos de incertidumbre.

### Evaluacion correcta

Los splits deben realizarse por incendio, region y fecha. Dividir aleatoriamente parches del mismo incendio produciria fuga de informacion y resultados artificialmente altos.

## Hoja de ruta que seguiria

### Fase 0. Definicion y contratos, 1-2 semanas

- crear repositorio hermano;
- definir esquemas GeoJSON/GeoTIFF/Zarr;
- fijar CRS y convenciones temporales;
- importar utilidades reutilizables;
- definir metricas y protocolo anti-leakage.

### Fase 1. Demo geoespacial offline, 2-3 semanas

- reproducir UN-SPIDER/GEE para burn severity;
- descargar un incendio con varias observaciones;
- generar perimetros e isocronas diarias aproximadas;
- publicar visualizacion GIS reproducible.

Objetivo: validar la cadena geoespacial, no afirmar tiempo real.

### Fase 2. Segmentacion de frente activo, 4-6 semanas

- reproducir NASA AMS;
- entrenar baseline termico/multiespectral;
- extraer contorno activo;
- adaptar `smoke_mask_growth.py` a metricas geograficas;
- evaluar contra anotaciones humanas.

Objetivo: frente activo correcto en coordenadas de imagen.

### Fase 3. Georreferenciacion y velocidad, 4-8 semanas

- trabajar con quema controlada o dataset UAV calibrado;
- proyectar frente sobre DEM;
- generar GeoJSON con incertidumbre;
- estimar velocidad normal;
- reconstruir isocronas de minutos.

Objetivo: demostrar error metrico y velocidad medible.

### Fase 4. Prediccion estrategica, 6-10 semanas

- baselines con Next Day Wildfire Spread;
- entrenar con TS-SatFire;
- comparar CNN, ConvLSTM, Swin/SegFormer temporal;
- añadir prediccion probabilistica;
- asimilar observaciones tacticas cuando existan.

Objetivo: forecast separado y claramente evaluado.

## Hardware minimo interesante

Para investigacion inicial no compraria hardware antes de reproducir datasets publicos. Para una prueba propia posterior:

- camara termica radiometrica;
- camara RGB sincronizada;
- GNSS RTK/PPK;
- IMU y telemetria de gimbal;
- dron o plataforma autorizada;
- estacion meteorologica portatil;
- DEM de alta resolucion.

Una camara termica coloreada sin valores radiometricos limita mucho el analisis y la reproducibilidad.

## Riesgos y condiciones de exito

### Riesgos tecnicos

- la georreferenciacion puede dominar el error total;
- humo, copas y relieve ocultan el frente;
- region caliente y llama activa no son equivalentes;
- diferentes sensores observan diferentes partes del fenomeno;
- el ground truth de velocidad es dificil y caro;
- los modelos satelitales pueden no transferir bien al Mediterraneo.

### Riesgos operativos

- no se deben operar drones sin coordinacion oficial cerca de incendios activos;
- el sistema debe mostrar incertidumbre, fuente y antiguedad;
- una prediccion no puede presentarse como perimetro observado;
- las decisiones criticas requieren validacion humana.

### Condiciones de exito

- empezar con quemas controladas y datos publicos;
- separar observacion, reconstruccion y prediccion;
- evaluar en metros y minutos, no solo IoU;
- mantener trazabilidad completa;
- trabajar con expertos de incendios y GIS desde el inicio.

## Recomendacion final

Yo desarrollaria el proyecto con este orden:

1. **NASA AMS** para aprender a segmentar frente activo multiespectral real.
2. **UN-SPIDER/GEE** para construir una demo geoespacial y dominar formatos.
3. **ActiveFire** para preentrenamiento y firmas espectrales globales.
4. Una **quema controlada georreferenciada** para demostrar frente, isocronas y velocidad en metros.
5. **TS-SatFire** para progresion multitemporal y area quemada.
6. **Next Day Wildfire Spread** como baseline de prediccion estrategica.
7. Level-set y asimilacion probabilistica cuando la cadena de observacion sea fiable.

El mayor valor diferencial no estaria en otro detector, sino en unir observacion termica, georreferenciacion, reconstruccion temporal e incertidumbre en un sistema auditable.

## Fuentes principales

- NASA AMS Wildfire Segmentation: https://github.com/nasa/Autonomous-Modular-Sensor-Wildfire-Segmentation
- NASA AMS paper: https://arxiv.org/abs/2601.14475
- ActiveFire: https://github.com/pereira-gha/activefire
- ActiveFire paper: https://arxiv.org/abs/2101.03409
- TS-SatFire: https://arxiv.org/abs/2412.11555
- Next Day Wildfire Spread: https://arxiv.org/abs/2112.02447
- Google Research implementation: https://github.com/google-research/google-research/tree/master/simulation_research/next_day_wildfire_spread
- WildFireVQA: https://github.com/mobiiin/WildFire_VQA
- FireNet: https://arxiv.org/abs/1910.06407
- Bayesian level-set assimilation: https://arxiv.org/abs/2206.08501
- Arrival-time inference from satellite observations: https://arxiv.org/abs/2309.02615
- Probabilistic localized spread forecasting: https://arxiv.org/abs/2603.26975
- OpenWFM / WRF-SFIRE: https://www.openwfm.org/
- UN-SPIDER recommended practices: https://www.un-spider.org/advisory-support/recommended-practices
- Google Earth Engine: https://earthengine.google.com/