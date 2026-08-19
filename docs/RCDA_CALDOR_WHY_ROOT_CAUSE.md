# Por qué RCDA se queda en IoU 0,31 y Caldor no tiene inferencia

Fecha: 2026-08-16  
Tipo: auditoría de causa raíz (no es otro recuento de métricas)  
Companion: `docs/RCDA_CALDOR_WHY_ROOT_CAUSE.json`  
Datos de partida: `docs/RCDA_CALDOR_RESULTS_AUDIT.md` + barrido TEST 1.630/1.630

## Veredicto

El 0,308 no es un modelo roto ni un umbral mal puesto. Es el techo de un
**predictor de anillo local** al que se le pidió crecimiento diario con:

- meteorología de escena (MERRA-2 ~50 km sobre un parche de 7,7 km);
- óptica Landsat **estática** entre días consecutivos;
- un solo perímetro previo, sin horizonte ni historia;
- Dice suave sobre un 1,02 % de positivos.

RCDA **sí extrae señal**: IoU 0,308 frente a 0,111 de la mejor dilatación
geométrica en el mismo TEST. Esa diferencia vive casi toda a ≤5,5 px del
frente (≤165 m). El 42 % de los píxeles de crecimiento están a más de
10,5 px (315 m); ahí el recall cae a 0,15 porque **los inputs no
explican dónde ocurre esa masa**.

La contaminación de protocolo (TEST para checkpoint/threshold/norma,
`UID_FIRE_656` cruzado) es real y prohíbe tratar 0,308 como cifra
independiente. **No es lo que produce el 0,31.** Quitar 656 mueve el IoU
de 0,3083 a 0,3081. Cambiar el threshold de 0,2 a 0,6 mueve F1 en
0,000095.

Caldor no tiene un IoU pobre: tiene un contrato temporal que **nosotros**
rompimos al materializar clean17, más un zoo de schemas incompatible con
cualquier checkpoint. No hay tensor ni modelo nativo.

---

## 1. Qué está haciendo realmente el modelo

El checkpoint publicado no estima un campo de probabilidad de
propagación. Emite un **anillo duro alrededor de la máscara t0**.

| Hecho medido en el TEST oficial | Valor | Qué implica |
|---|---:|---|
| Píxeles con p ≤ 0,01 | 98,99 % | Casi todo el mapa es “no fuego” seguro |
| Píxeles con p ≥ 0,99 | 0,93 % | El resto es “sí” seguro |
| Píxeles con 0,2 ≤ p < 0,6 | 0,015 % | No existe zona gris |
| ΔF1 al pasar el umbral de 0,2 a 0,6 | 0,000095 | El threshold search es teatro |
| Distancia media del crecimiento (mediana de escenas) | 2,57 px | El target típico ya es un anillo corto |
| Distancia media de la predicción | 2,63 px | El modelo copia esa escala |
| p90 de la distancia media del crecimiento | 13,0 px | Hay colas largas |
| p90 de la distancia media predicha | 6,91 px | El modelo **nunca** llega tan lejos |
| Fracción de masa de crecimiento >10,5 px | **42,1 %** | Casi la mitad del IoU se juega fuera del anillo |
| Fracción de píxeles predichos >10,5 px (media escena) | 5,6 % | Subpredice sistemáticamente lo lejano |
| Masa predicha / masa verdadera | 1.035.312 / 1.091.109 | El volumen total es razonable; la **ubicación** no |

La calibración lo confirma. En los bins 0,05–0,95 la frecuencia empírica
está clavada en ~0,22–0,25 **da igual la probabilidad predicha**. El
modelo no rankea; solo pinta un anillo. En 0,95–1,00 hay 1.011.452
píxeles con p media 0,9995 y frecuencia 0,490: sobreconfianza masiva.
El Brier de RCDA (0,01046) es **peor** que predecir siempre cero
(0,01021). Los FP seguros del anillo cuestan más error cuadrático que
lo que aportan los TP.

Accuracy 0,9895 < accuracy del predictor nulo 0,9898. Accuracy no mide
esta tarea.

### 1.1 Los 154 IoU = 0 no son spotting

De 154 escenas con IoU cero, **133 tienen menos de 100 píxeles** de
crecimiento. Solo 6 tienen distancia mediana de crecimiento >10,5 px.

En el bin 1–99 px: recall 0,62 y precisión 0,14. El modelo pinta el
anillo típico sobre días casi quietos y se come el IoU con FP.

2017 (32 % del TEST oficial, 528/1.630) es el dominio peor porque los
incendios son más pequeños, no porque el año sea “más difícil” en
sentido físico:

| Año | n TEST | crecimiento mediano (px) | perímetro t0 mediano | precisión | recall | IoU |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 227 | 266 | 3.580 | 0,561 | 0,469 | 0,343 |
| 2016 | 269 | 277 | 5.188 | 0,481 | 0,455 | 0,305 |
| **2017** | **528** | **102** | **1.440** | **0,351** | **0,532** | **0,268** |
| 2018 | 355 | 223 | 1.513 | 0,584 | 0,426 | 0,327 |
| 2019 | 251 | 254 | 1.682 | 0,497 | 0,435 | 0,302 |

2017 tiene el **mejor recall y la peor precisión**. El modelo no deja de
ver fuego: **sobrepredice** el anillo medio sobre fuegos chicos.

Simétrico en el otro extremo: crecimientos ≥2.000 px tienen precisión
0,68 y recall 0,41. Regresión a la escala media. No hay un “modo
corrida” ni un “modo spotting”.

---

## 2. Por qué el modelo solo puede aprender ese anillo

Hay cinco cuellos de información. Juntos cierran el 0,31.

### Causa 1 — La meteorología no es un campo a 30 m

El README de RCDA declara MERRA-2 a **0,5° × 0,625°** (~55 km) sobre
parches 256×256 a 30 m = **7,68 km**. Un parche cabe en una celda
MERRA-2, a veces en el blend de 2–4.

Medido en las 1.630 escenas TEST:

| Canal | Rango espacial mediano | Fracción de escenas con rango 0 |
|---|---:|---:|
| viento (m/s) | 0,038 | 46,9 % |
| dirección (rad) | 0,012 | 47,0 % |
| temperatura (K) | 0,051 | 46,9 % |
| precipitación | ~0 | 47,1 % |
| humedad | 2,9e-5 | 46,9 % |
| densidad del aire | 3,0e-4 | 46,9 % |

El protocolo global ya había contado ~3.184/8.131 muestras con los seis
canales meteorológicos espacialmente constantes. El TEST lo confirma:
casi la mitad son un escalar de escena, y el resto tiene un gradiente
cosmético de interpolación, no meteorología a 30 m.

Consecuencia: el viento **no puede orientar el frente**. Solo puede
empujar un sesgo global del tipo “hoy crece más / hoy crece menos”.
El “dónde” lo deciden la máscara previa, el DEM y Landsat.

El DEM sí varía: rango mediano 128 m, **cero** escenas constantes.
Eso explica por qué RCDA gana a la dilatación isótropa: recorta el
anillo con pendiente y cubierta, no porque “entienda” el viento.

### Causa 2 — Landsat no es diario

El propio README marca B/G/R/NDVI como resolución temporal
**Constant**. En TEST, de 1.446 pares de días consecutivos del mismo
incendio, **1.395 (96,47 %) tienen RGB+NDVI byte-a-byte idénticos**.
Mediana del |Δ| máximo = 0. El combustible óptico es una foto fija.
No hay humedad de combustible espacial del día, ni cambio de dosel.

### Causa 3 — El tensor no contiene la pregunta física

Canales RCDA (12): máscara t0, DEM, B, G, R, NDVI, 6 escalares MERRA-2.

Falta, y no es opinable:

- pendiente y aspecto explícitos (solo DEM; el modelo tendría que
  inventar gradientes);
- seno/coseno de viento y aspecto (el ángulo está en [−π, π],
  discontinuo en ±π, y la augmentación lo rota a mano);
- distancia al frente;
- horizonte en horas;
- perímetros t−2, t−3 o mapa de llegada;
- secuencia meteorológica (un solo resumen, a menudo constante).

Sin historia no hay velocidad ni aceleración. Sin horizonte el mismo
anillo tiene que servir para cualquier Δt. Caldor, de hecho, oscila
entre 18,75 h y 28,38 h y **tampoco** mete Δt como canal.

### Causa 4 — Dice suave + 1 % de positivos produce 0/1

`LossFunction.DiceLoss` hace

```text
dice = 2·⟨p,y⟩ / (⟨p⟩ + ⟨y⟩ + ε)
loss = 1 − dice
```

sobre el batch aplanado, con `p` ya pasado por sigmoid en
`Models/RCDA.py`. Con ȳ ≈ 0,01, cualquier p intermedia empeora a la
vez numerador y denominador. El óptimo de Dice suave en este régimen
es un mapa casi binario del solapamiento típico: el anillo de ~2–6 px.

El comando documentado es `python train.py --loss_function DiceLoss`.
El default del argparse es FocalLoss; el paper/README publican Dice.
No hay Tversky (no se puede cargar FN lejanos), no hay loss de
frontera, no hay muestreo por incendio ni por tamaño de crecimiento.
Los días se barajan. Un día de 100 px cuenta igual que uno de 8.000.

CAA, la atención espacial, usa kernels 11×1 y 1×11 más un pool 7×7.
Está **diseñada** para contexto local de ~11–15 px. Coincide con el
rango donde el modelo funciona (IoU 0,58 a 0–1,5 px, 0,38 a 3,5–5,5,
0,12 a >10,5). El receptive field teórico del U-Net es grande; la
atención y la loss no premian usarlo para spotting.

### Causa 5 — El target es intrínsecamente de cola pesada

1,02 % de positivos. 635/1.630 escenas tienen 1–99 px de crecimiento.
144 tienen ≥2.000. El 42 % de la **masa** de crecimiento (no de las
escenas) está a >315 m del perímetro t0.

Un estimador que maximiza Dice/IoU micro se especializa en el modo
(anillo corto) y sacrifica la cola (corridas, spotting, saltos de
escala). Eso no se arregla con más épocas del mismo tensor.

---

## 3. La contaminación de protocolo: grave, pero no es el 0,31

### Qué está roto en el código upstream (no es hipótesis)

`data/external/rcda_net_full/upstream/train.py`:

```python
fire_eval_data = Fire('test', augmentation=False)
...
if test_f1 >= best_f1:
    torch.save(net, WEIGHT_SAVE_PATH)
```

No existe split VAL. Cada época mira TEST. El checkpoint es el de
mejor F1 TEST. Early stopping también mira TEST.

`eval.py` vuelve a elegir threshold ∈ {0,2 … 0,6} sobre TEST.

`dataset.py` hardcodea `band_info` con máximos que **coinciden con
TEST y no con TRAIN original**:

| Canal | max TRAIN original | max TEST = max publicado |
|---|---:|---:|
| viento | 12,9921875 | 13,046875 |
| precipitación | 0,00068099 | 0,00128398 |

No hay seed, ni `deterministic`, ni época del `.pth`, ni estado del
AdamW. El `.pth` es `torch.save(net)` (pickle del módulo), no
`state_dict`.

### `UID_FIRE_656` es fuga temporal adyacente, no un incendio al azar

- TRAIN: 2018-08-11 … 2018-08-31 (21 días, el fuego crece de 2 a 8.289 px).
- TEST: 2018-09-01 … 2018-09-07 (7 días, crecimiento 131 → 6 px, fase
  final).

Mismo UID, días pegados, mismo DEM, misma Landsat, misma celda MERRA-2.
El modelo ya vio tres semanas de ese paisaje. Aun así, **excluir las
7 escenas deja IoU 0,3081**. La fuga es inaceptable como protocolo;
no explica el número.

### Labels: el README miente, el loader acierta

Zenodo/README dicen `increment_mask`. Los `.npy` de label son la
extensión **acumulada** de t1. El loader hace `label - input[0]`.
Sobre 8.131 pares: 0 píxeles de crecimiento negativo, retención del
perímetro previo = 1,0. El target de entrenamiento es crecimiento
binario correcto **si** se usa su loader. Cualquiera que tome los
labels al pie de la letra entrena otra tarea.

### Qué se puede afirmar y qué no

| Afirmación | ¿Sostenible? |
|---|---|
| El checkpoint publicado produce IoU 0,3083 / F1 0,4713 en su TEST | Sí, reproducido |
| Esa cifra es una estimación independiente de generalización | No |
| Quitar 656 o retocar el threshold cambia el diagnóstico | No |
| Un retrain sellado va a saltar a 0,5+ con la misma receta | Muy improbable |
| Prior razonable post-retrain sellado, misma receta | **0,26–0,32** micro IoU |

El split sellado ya está materializado (`protocol/train.json` 5.552 /
`val.json` 928 / `test.json` 1.651, eventos disjuntos, norma solo
TRAIN). `sealed_retraining_completed` sigue en `false`. El siguiente
experimento no es otra auditoría de protocolo: es entrenar.

---

## 4. Caldor: el bloqueo lo escribimos nosotros

El paquete espacial está bien. 171 GeoTIFF, EPSG:32610, 30 m,
2.199×1.302, hashes, LF2020 pre-Caldor, ciclos HRRR inicializados
≥1 h antes de t0, sin MTBS/RAVG como input. Eso **no** autoriza
inferencia.

### 4.1 HRRR: leads fijos 0–24 desde el ciclo, no la ventana [t0, t1]

En `scripts/acquire_caldor_clean17.py`:

```python
HRRR_LEADS = tuple(range(0, 25, 3))  # siempre f00,f03,...,f24

def choose_hrrr_cycle(t0, availability_lag_hours=1):
    available = t0 - 1 h
    cycle_hour = (available.hour // 6) * 6   # 00/06/12/18Z
```

Los sobrevuelos NIROPS de Caldor caen ~03–07 UTC. Para t0=03:20Z el
ciclo es 00Z. Se promedian leads 0…24 → valid times 00Z del día D
hasta 00Z del día D+1.

La ventana real [03:20, 03:30 del día siguiente] entonces:

- mete 3,33 h **anteriores** a t0;
- deja 3,50 h del target **sin cubrir**.

En el par largo 2021-08-25T05:07 → 08-26T09:30 (28,38 h) se pierden
**9,5 h**. Media del paquete: 4,60 h pre-t0 mezcladas, 4,94 h de
target descubiertas. 0/15 ventanas exactas.

Además el resumen destruye el ciclo diurno: U/V, T, RH, etc. se
promedian en los 9 leads. `precipitation_mm_24h` no es la lluvia de
[t0, t1]: es el APCP del **último** lead (f24 desde 00Z).

Los ciclos 00/06/12/18Z de HRRR llegan a 48 h. El código podía pedir
leads = `ceil((t0−cycle)/3) … ceil((t1−cycle)/3)`. No lo hace. El
contrato del pack (`covariate_contract.json`) exige “preserve cycle
and lead time” y valid time de la ventana. La adquisición viola el
contrato que ella misma declara.

### 4.2 ERC: usamos el día que todavía no existía en t0

`build_gridmet_erc(..., date=t0)` indexa el NetCDF por
`t0.date()`. El propio registro escribe

```text
day_definition = "calendar day ending 07:00 UTC next day"
```

Para t0 = 2021-08-18T03:20Z el ERC de “18 de agosto” incluye horas
hasta el 19 a las 07:00 UTC: **~28 h de meteorología futura**.

El contrato del pack dice otra cosa: *“use only the latest daily
value that would have been published by t0”*. Lo correcto es el
último día gridMET **completo** antes de t0 (el 17). 15/15 pares
fallan.

Esto no es un detalle de auditoría permisiva. Es lookahead de
peligro de incendio.

### 4.3 `clean17_ready: true` es un conteo de ficheros

```python
"clean17_ready": len(dynamic) == len(selected)
```

15 pares escritos = “ready”. El contrato posterior ya lo corrige
(`temporal_availability_ready: false`, `clean17_covariates_ready:
false`, `model_iou_allowed: false`). Dos documentos del mismo día se
contradicen. Quien lea solo el JSON de adquisición cree que puede
entrenar.

### 4.4 No hay tensor, y ningún checkpoint encaja

| Schema | Canales | Estado |
|---|---|---|
| RCDA upstream | 12 (máscara + DEM + Landsat + MERRA-2) | checkpoint `rcda.pth` |
| `legacy17` + prev_fire | 18, con huecos constantes (presión, nubes, vis, rocío, 4 veg) | `clm_ensemble_v34` |
| `clean12` / `physics14` / `physics15` | 12–15, viento/aspecto en sin-cos | trainers WFD |
| `clean17_physical_v1` | 17 físicos reales (HRRR + canopy + ERC) | GeoTIFF sí, NPZ **0** |

legacy17 aprendió slots constantes. Meterle presión/nubes/dosel
reales de Caldor es otro modelo. RCDA 12 no es clean17. No existe
normalización TRAIN, ni política de imputación del 11,19 % nodata de
canopy, ni máscara de missingness, ni encoding circular.

### 4.5 Un incendio, 15 pares correlacionados

Caldor es holdout externo. No es corpus de entrenamiento ni de
selección de checkpoint. Entrenar clean17 **en Caldor** y reportar
IoU Caldor sería la versión estadounidense de seleccionar en TEST.

Los labels NIROPS sí sirven hoy para un baseline de dilatación /
copy. Eso no es model IoU.

---

## 5. Por qué nos pasa *a nosotros* (fallo de proceso)

No es solo el paper chino. El repo repite el mismo patrón.

1. **Zoo de schemas sin un contrato de entrenamiento único.**
   legacy17, clean12, physics14, physics15, clean17, RCDA-12. Cada
   pack nuevo inventa un orden de canales. Los pesos no se pueden
   transferir. La tentación es “lanzar el checkpoint que ya tenemos”.

2. **Las adquisiciones optimizan existencia espacial.** Hash, CRS,
   GSD, nodata, 171 ficheros → `status: complete`. La validez
   temporal (valid time, disponibilidad en t0) entra después, como
   auditoría, no como invariante de construcción. `HRRR_LEADS =
   range(0, 25, 3)` fue la implementación barata de “un día de
   meteo”.

3. **Diagnosticamos más de lo que entrenamos.** En un día:
   `RCDA_NET_PROTOCOL_AUDIT`, `RCDA_CALDOR_RESULTS_AUDIT`,
   `CALDOR_CLEAN17_AUDIT`, `EXTERNAL_ML_COMPATIBILITY_AUDIT`,
   `FIREBENCH_CALDOR_CHANNEL_AUDIT`. El split sellado existe.
   `sealed_retraining_completed` es false. El número 0,308 se ha
   explicado tres veces; no se ha sustituido.

4. **El mismo cuello de información aparece en LATAM/AU.** El proxy
   complete pierde frente a copy (Δ = −0,070). El audit de
   compatibilidad lo dice: *“weather is a point-derived spatially
   constant field”*. RCDA al menos gana a la dilatación porque
   ABoVE+DEM+Landsat es una tarea real de anillo. Nuestro proxy, con
   meteo de punto, ni eso.

5. **Un parser ya nos había mentido en el tiempo.** Los KML FireBench
   `...T20_20_07_00` son `20:20-07:00`; el parser viejo leía `07`
   como segundos. Misma clase de error que ERC/HRRR: el reloj se
   trata como etiqueta, no como disponibilidad.

---

## 6. Hipótesis que no sobreviven

| Hipótesis | Veredicto | Evidencia |
|---|---|---|
| “El modelo es malo / hay que cambiar a ViT” | Rechazada como causa primera | Gana 0,308 vs 0,111 a dilatación; no hay U-Net sellado contra el que compararlo |
| “Falta ajustar el threshold” | Muerta | ΔF1 9,5×10⁻⁵; 98,99 % de p fuera de (0,01, 0,99) |
| “656 infla el 0,31” | Muerta como explicación del número | IoU 0,3083 → 0,3081 |
| “Caldor tiene un IoU malo” | Categoría errónea | No hay inferencia válida |
| “Hay que reutilizar `legacy17` / `rcda.pth` en Caldor” | Prohibido | Schemas distintos; legacy17 vio constantes |
| “Más épocas / más GPU con el mismo tensor” | Improbable | El modelo ya está saturado y sobreconfiado |
| “Accuracy o ECE global demuestran calibración” | Muerta | Accuracy < nulo; ECE lo dominan los negativos fáciles |
| “2017 es un dominio meteorológico imposible” | Débil | Fuegos más chicos + sobrepredicción de anillo; recall 2017 es el más alto |

---

## 7. Qué movería de verdad el IoU (orden causal)

Cada ítem mata o confirma una causa. Si no la mata, no es la
prioridad.

### P0 — Dejar de mentirnos con el número

1. Entrenar RCDA (y U-Net, y dilated-copy) en el split sellado.
   Norma solo TRAIN. Checkpoint y threshold solo VAL. TEST una vez.
   Tres seeds. Gate: manifests hasheados + cero uso de TEST.
2. Reparar Caldor **antes** de cualquier model IoU:
   - ERC = último día gridMET cuya ventana termina ≤ t0;
   - HRRR leads con valid time en [t0, t1], extendiendo >24 h si
     hace falta (los ciclos 00/06/12/18Z lo permiten);
   - no promediar horas anteriores a t0;
   - gate: 15/15 ERC disponibles y 15/15 ventanas exactas.
3. No aceptar una cifra nueva que no gane a U-Net y a dilated-copy
   **en el mismo TEST** en IoU micro, IoU macro por incendio, AP y
   recall >10,5 px.

### P0/P1 — Meter la información que el 0,31 no tiene

4. Distancia al frente + viento/aspecto en seno/coseno + Δt en horas.
   Experimento barato. Si el IoU sellado no sube, el cuello no era
   representación angular/geométrica.
5. Historia de perímetros o arrival time. Sin esto no hay ROS ni
   aceleración.
6. Secuencia HRRR/MERRA por valid time, no un escalar de escena.
   En RCDA esto choca con la resolución nativa (~50 km): el primer
   sitio donde la secuencia espacial importa de verdad es Caldor
   (HRRR ~3 km), **después** de arreglar la ventana.
7. Loss: focal-Tversky (cargar FN lejanos) + frontera/SDF.
   Muestrear por incendio y por tamaño de crecimiento, no por día.
   Tratar explícitamente los targets vacíos y los de 1–99 px.

### P1 — No entrenar Caldor en silencio

8. Corpus clean17 de **varios** incendios CONUS. Caldor holdout.
9. Tensor NPZ + imputación de canopy + máscara de missingness.
   Nunca reutilizar `legacy17` ni `rcda.pth` sobre clean17.

### Lo que no hay que hacer

- Otro paper-audit del 0,308 sin retrain sellado.
- Reportar IoU Caldor con el checkpoint actual.
- Optimizar threshold sobre TEST “porque total casi no cambia”
  (el gesto contamina el protocolo aunque el número no se mueva).
- Promediar HRRR 0–24 “para tener un mapa diario” y llamarlo
  nowcast de [t0, t1].

---

## 8. Lectura operativa de una línea

RCDA aprendió a **engrosar el perímetro con DEM y Landsat**. Eso es
todo lo que el tensor permite, y lo hace mejor que un círculo. El
42 % del crecimiento real está fuera de ese truco. Caldor podría
ser el primer sitio donde el viento espacial cuenta, pero hoy el
viento que le dimos incluye el pasado inmediato, excluye parte del
futuro de la ventana, y el ERC incluye el día siguiente. Por eso
“nos pasa esto”: no por falta de arquitectura, sino porque le
estamos preguntando spotting y corridas a un anillo, y le estamos
dando a Caldor el tiempo equivocado.

---

## Fuentes reproducibles

- Auditor de resultados: `scripts/audit_rcda_caldor_results.py`
- Protocolo sellado: `docs/RCDA_NET_FULL_PROTOCOL.json`
- Código upstream: `data/external/rcda_net_full/upstream/{train,eval,dataset,LossFunction}.py`
- Adquisición Caldor: `scripts/acquire_caldor_clean17.py` (`HRRR_LEADS`, `choose_hrrr_cycle`, `build_gridmet_erc`)
- Contrato del pack: `data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021/covariate_contract.json`
- Predicciones cacheadas: `outputs/ml_eval/rcda_full_upstream/predictions/`
- Barrido causal TEST (óptica, meteo, distancias, 656, 2017): 2026-08-16, 1.630/1.630 escenas
