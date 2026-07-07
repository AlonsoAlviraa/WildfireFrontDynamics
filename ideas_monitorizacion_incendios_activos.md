# Ideas y plan de análisis para monitorización de incendios activos

**Fecha:** 2026-07-07  
**Contexto:** nos han compartido material real de varios incendios forestales
mediante Dropbox Transfer. Antes de mejorar el programa hay que auditar desde
cero qué datos hay, qué variables temporales existen y qué falta para alimentar
el pipeline de `WildfireFrontDynamics`.

## Resumen de los correos recibidos

Nos ofrecen material seleccionado de varios IF. Inicialmente mencionan 8 IF,
pero finalmente indican que hay alguno menos y que queda pendiente el incendio
de **CARDOSO (GU)** del año pasado, con duración aproximada de 10 días.

Enlaces recibidos:

- `https://www.dropbox.com/t/5CFtPw4KTkAHXysh`
- `https://www.dropbox.com/t/arTaQmPMwPTMQTU5`
- `https://www.dropbox.com/t/01E9lT3qwcfWB7HU`

Metadatos visibles sin descarga completa:

- Link 1: `TOBARRA-AB-20240802.zip + 4 more items`
- Link 2: `LA ESTRELLA-ACOM1.zip`
- Link 3: `LA ESTRELLA-ACOM2.zip`
- Pendiente: `CARDOSO (GU)`

## Respuesta recomendada al correo

```text
Buenos días,

Muchísimas gracias por preparar y compartir todo el material. Nos viene muy bien.

Antes de empezar a extraer conclusiones o adaptar el programa, lo primero que
vamos a hacer es una auditoría completa desde cero de cada incendio: inventario
de archivos, fechas, series temporales disponibles, imágenes, meteorología,
planificación y cualquier información de campo que venga asociada.

Sí, si podéis pasarnos más información sobre los incendios nos sería muy útil,
especialmente:

- fechas y horas aproximadas de inicio, evolución y estabilización/control;
- perímetros o croquis por momentos, si existen;
- planificación o partes operativos;
- meteorología horaria o diaria, aunque sea de estación cercana;
- viento, temperatura, humedad, precipitación y cambios relevantes;
- imágenes de campo con fecha/hora y localización aproximada;
- ubicación de puntos de observación, medios, pistas, cortafuegos o referencias
  geográficas;
- cualquier shapefile, KML, GPX, ortofoto, mapa o capa GIS disponible;
- aclaración de qué representa cada carpeta/archivo si no queda claro por el
  nombre.

Con los enlaces que nos habéis mandado empezaremos ya el inventario. Cuando
tengamos revisado el contenido os devolveremos una tabla por incendio indicando:
qué datos hay, qué datos faltan, qué se puede usar para series temporales y qué
podría alimentar el modelo.

Sobre CARDOSO (GU), perfecto, cuando podáis pasárnoslo lo incorporamos al mismo
proceso. Al ser un incendio de varios días puede ser especialmente interesante
para analizar evolución temporal, meteorología y cambios de comportamiento.

Muchas gracias de nuevo por la ayuda. Os iremos contando cualquier duda concreta
que salga al revisar los archivos.

Un saludo,
Alonso
```

## Objetivo técnico inmediato

No entrenar ni modificar modelos todavía. Primero hay que construir un
**inventario científico por incendio**:

```text
archivo recibido -> timestamp -> localización -> variable -> calidad
-> utilidad para observación, inferencia, meteo o validación
```

La pregunta que debe responder el inventario es:

> ¿Qué incendios tienen suficiente información temporal, espacial y meteorológica
> para mejorar o validar el programa?

## Estructura local recomendada

Cuando se descargue el material:

```text
data/real_if/
  raw_dropbox/
    20260707_transfer_01/
    20260707_transfer_02/
    20260707_transfer_03/
  candidates/
    tobarray_ab_20240802/
    la_estrella_acom1/
    la_estrella_acom2/
    cardoso_gu_pending/
  inventories/
    real_if_inventory.csv
    real_if_timeseries_inventory.csv
    real_if_missing_data.md
```

No se debe mezclar el material bruto con datos procesados. El bruto debe quedar
conservado y trazable.

## Inventario mínimo por incendio

| Campo | Descripción |
|---|---|
| `event_id` | Identificador estable, por ejemplo `tobarra_ab_20240802` |
| `source_link` | Enlace o transferencia de origen |
| `raw_file` | Archivo original |
| `file_type` | zip, jpg, png, tif, pdf, docx, xlsx, csv, shp, kml, gpx, etc. |
| `observed_at` | Fecha/hora si existe |
| `time_quality` | exact, inferred, date_only, missing |
| `location` | municipio, provincia, coordenadas o zona |
| `spatial_quality` | exact, approximate, map_only, missing |
| `variable_family` | image, field_photo, meteo, planning, perimeter, operation, report |
| `usable_for` | observation, validation, weather, context, discard |
| `notes` | dudas o interpretación |

## Variables que necesitamos buscar

### Identificación del incendio

- nombre oficial;
- municipio/provincia;
- coordenadas aproximadas;
- fecha/hora de inicio;
- fecha/hora de estabilización/control/extinción;
- duración útil para modelar;
- superficie afectada por fecha si existe.

### Series temporales

- fotos o imágenes con timestamp;
- perímetros en varios momentos;
- partes operativos por hora/día;
- cambios de sector o flanco;
- evolución de medios o líneas de defensa;
- observaciones de campo ordenadas temporalmente.

### Meteorología

- viento: velocidad, dirección, rachas;
- temperatura;
- humedad relativa;
- precipitación;
- estabilidad atmosférica si existe;
- estación de referencia y distancia al incendio;
- resolución temporal: horaria, diaria o puntual.

### Topografía y combustible

- altitud;
- pendiente;
- orientación;
- tipo de combustible o vegetación;
- continuidad del combustible;
- cortafuegos, pistas, cultivos, urbano/interfaz.

### Geometría y validación

- perímetros oficiales;
- croquis de evolución;
- KML/GPX/SHP;
- imágenes aéreas o satélite;
- mapas de campo;
- puntos de observación;
- si existe una referencia independiente del frente.

## Decisiones antes de mejorar el programa

1. **¿Tenemos timestamps suficientes?**
   - Sin tiempo no hay serie temporal defendible.

2. **¿Tenemos coordenadas o mapas georreferenciables?**
   - Sin espacio métrico no hay velocidad en `m/min`.

3. **¿Tenemos referencia independiente?**
   - Sin referencia sólo podemos auditar/visualizar, no medir precisión.

4. **¿Tenemos meteo sincronizable?**
   - Sin meteo sólo validamos geometría; no explicamos comportamiento.

5. **¿Qué incendio es el primer candidato fuerte?**
   - Debe tener varias observaciones temporales, ubicación clara y algún tipo
     de validación.

## Integración con el pipeline actual

El pipeline actual ya acepta:

- imágenes GeoTIFF;
- máscaras;
- anotaciones independientes;
- auditoría de candidato;
- verificación de hito.

Para estos incendios reales probablemente habrá primero que construir un
adaptador de material heterogéneo:

```text
ZIP/PDF/JPG/XLSX/SHP/KML -> inventario -> normalización temporal
-> georreferenciación si procede -> candidato GeoTIFF/máscara/anotación
```

## Primeras hipótesis de uso por incendio

### TOBARRA-AB-20240802

Parece ser un paquete principal más otros cuatro elementos. Prioridad alta para
inventario porque probablemente contiene varios tipos de archivo.

### LA ESTRELLA-ACOM1 y LA ESTRELLA-ACOM2

Parecen dos partes del mismo incendio o dos agrupaciones del mismo operativo.
Hay que revisar si `ACOM1/ACOM2` son momentos, sectores, carpetas de actuación o
fuentes distintas.

### CARDOSO (GU)

Pendiente. Por duración aproximada de 10 días puede ser el mejor candidato para
series temporales largas, siempre que venga acompañado de partes, meteo o mapas.

## Próximo paso operativo

1. Descargar los tres transfers completos.
2. Calcular SHA-256 de cada ZIP/archivo bruto.
3. Extraer en carpetas separadas sin modificar originales.
4. Generar inventario automático de archivos.
5. Clasificar variables por incendio.
6. Detectar qué falta y responder con dudas concretas.
7. Elegir primer incendio candidato para adaptar al pipeline.

