# Núcleo científico

## Objetivo

El núcleo reconstruye la evolución observada de bordes extraídos de máscaras
georreferenciadas. Separa explícitamente:

- `observed`: geometría extraída de la observación;
- `inferred`: llegada y velocidad derivadas de geometrías observadas;
- `ground_truth`: referencia independiente, presente sólo en datos sintéticos;
- `forecast`: no implementado.

Una frontera térmica candidata no se presenta como frente de llama validado.

## Velocidad no radial

Para cada par temporal:

1. valida CRS proyectado, resolución y timestamps crecientes;
2. empareja componentes uno a uno por distancia entre centroides;
3. remuestrea uniformemente el componente anterior;
4. calcula la normal exterior local;
5. intersecta cada normal con el componente siguiente;
6. divide el desplazamiento defendible por el intervalo temporal.

La correspondencia por centroides es conservadora y no resuelve fusiones o
divisiones complejas. Los componentes nuevos o desaparecidos quedan sin
emparejar y se reportan.

## Gates de calidad

Una estimación local se abstiene cuando:

- no existe intersección normal hacia delante;
- el movimiento no supera la incertidumbre combinada;
- la curvatura local es demasiado alta;
- la intersección normal contradice fuertemente la distancia mínima al borde;
- el componente no alcanza una fracción mínima de intersecciones válidas.

La incertidumbre combina el error declarado de ambas observaciones y una
contribución de discretización raster. Los parámetros se exponen en la CLI y
deben justificarse para cada sensor y escala.

## QA de datos

La ingesta registra SHA-256, dimensiones, dtype, CRS, resolución, timestamp,
método de máscara y fracción de píxeles positivos. Audita duplicados, cambios
de CRS o resolución, timestamps repetidos, máscaras vacías y máscaras casi
completas.

Además del umbral absoluto, el baseline MAD permite segmentación adaptativa
robusta. Ninguno de ambos métodos sustituye una segmentación calibrada.

## Métricas

Con referencia independiente, el sistema calcula distancia simétrica media,
P95 y Hausdorff entre frentes. Para la velocidad sintética calcula MAE. En datos
sin ground truth sólo reporta cobertura observable, mediana, P95, incertidumbre
y motivos de abstención; no reporta exactitud.

## Límites actuales

- No existe validación contra una secuencia real con anotaciones independientes.
- La expansión hacia dentro y los retrocesos no se modelan como velocidad
  negativa: la ausencia de intersección exterior produce abstención.
- Fusiones, divisiones y oclusiones requieren un modelo de asociación temporal
  más rico.
- El borde de una máscara depende del método de segmentación y del sensor.
- No hay predicción ni modelo físico del combustible, viento o pendiente.

## Próximo dato prioritario

El siguiente avance debe usar una secuencia ortorrectificada de quema controlada
o FLAME 3 con timestamps, CRS proyectado, resolución conocida y anotaciones de
frente realizadas independientemente de la segmentación evaluada. Debe separar
calibración y evaluación por evento para evitar fuga de información.
