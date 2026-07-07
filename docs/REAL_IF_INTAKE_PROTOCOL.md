# Protocolo de recepción de incendios forestales reales

Este documento convierte el material recibido por Dropbox en un proceso
auditable antes de usarlo para mejorar `WildfireFrontDynamics`.

## Principio

Primero inventariar, después modelar. No se debe entrenar, calibrar ni extraer
conclusiones hasta saber qué variables existen, con qué calidad temporal y con
qué calidad espacial.

## Material recibido

| Transfer | Pista visible | Estado |
|---|---|---|
| `https://www.dropbox.com/t/5CFtPw4KTkAHXysh` | `TOBARRA-AB-20240802.zip + 4 more items` | pendiente de descarga completa |
| `https://www.dropbox.com/t/arTaQmPMwPTMQTU5` | `LA ESTRELLA-ACOM1.zip` | pendiente de descarga completa |
| `https://www.dropbox.com/t/01E9lT3qwcfWB7HU` | `LA ESTRELLA-ACOM2.zip` | pendiente de descarga completa |
| pendiente | `CARDOSO (GU)` | pendiente de recepción |

## Inventarios a generar

- `data/real_if/inventories/file_inventory.csv`
- `data/real_if/inventories/event_inventory.csv`
- `data/real_if/inventories/time_series_inventory.csv`
- `data/real_if/inventories/missing_variables.md`

## Variables obligatorias

| Familia | Variables |
|---|---|
| Identificación | nombre, provincia, municipio, fecha inicio, fecha control/extinción |
| Temporal | timestamps, orden de observaciones, duración, resolución temporal |
| Espacial | coordenadas, CRS, mapas, perímetros, KML/SHP/GPX |
| Meteorología | viento, temperatura, humedad, precipitación, estación, resolución |
| Campo | imágenes, informes, planificación, partes operativos, observaciones |
| Validación | perímetros independientes, croquis, mapas de evolución, anotaciones |

## Clasificación de utilidad

Cada archivo debe quedar etiquetado como una o varias de estas categorías:

- `observation`: sirve para observar geometría o estado del incendio;
- `weather`: aporta variables meteorológicas;
- `context`: aporta planificación, operación o interpretación;
- `validation`: referencia independiente para evaluar;
- `discard`: no útil o duplicado.

## Criterio para elegir primer incendio candidato

Un incendio pasa a candidato del pipeline si cumple:

1. al menos tres momentos temporales útiles;
2. localización suficientemente clara;
3. algún soporte espacial o georreferenciable;
4. meteo sincronizable o aproximable;
5. referencia independiente parcial o posibilidad de anotarla.

Si falta 1 o 2, el incendio sólo sirve como contexto. Si falta 3, no se debe
estimar velocidad métrica. Si falta 5, no se debe reportar precisión.

## Siguiente implementación recomendada

Crear un script `scripts/inventory_real_if_material.py` que recorra una carpeta
bruta descargada, calcule hashes, detecte tipos de archivo, extraiga timestamps
de nombres/metadatos cuando sea posible y produzca los CSV de inventario.

Primera implementación disponible:

```powershell
python scripts\inventory_real_if_material.py `
  --source data\real_if\raw_dropbox `
  --output data\real_if\inventories\file_inventory.csv
```
