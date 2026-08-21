# Mega-auditoría y evolución ML — WildfireFrontDynamics

**Periodo cubierto:** 2026-08-18 → 2026-08-21  
**Corte:** 2026-08-21, durante la cosecha WFIGS grande de TRAIN/DEV  
**Estado científico:** desarrollo reproducible; la confirmación no está abierta y no hay todavía una mejora estable que autorice una afirmación confirmatoria.

## 1. Resumen ejecutivo

Durante estos dos días se convirtió un prototipo de predicción de dinámica de
incendios en un flujo auditable: cosecha histórica, pares temporales, filtros de
calidad, enriquecimiento EO/meteorológico, derechos, splits por incendio,
protocolos preregistrados, adaptaciones RCDA→WFIGS y una cadena de PRs
reproducible.

La conclusión actual es deliberadamente honesta:

- El mejor control estable sigue siendo el ensemble híbrido residual de tres
  semillas, con **0.136178 event-macro IoU** en DEV.
- Las características combinadas de geometría de frente + residuales EO por
  tesela llegaron a **0.141378** en una corrida de una semilla, pero esa corrida
  usaba una augmentación físicamente inconsistente para los vectores normales.
  Tras corregirla, la réplica de tres semillas quedó en **0.138085**, y el
  ensemble con fuente RCDA fija en **0.140044** (la rejilla fija llegó a
  **0.140719**). Ninguno supera de forma estable el gate preregistrado de
  `+0.005` sobre el control (`0.141178` mínimo).
- La única evaluación de confirmación ya realizada permanece en
  **0.067115 vs 0.055010**, con IC bootstrap 95 % `[-0.001563, 0.029216]`;
  por eso el gate confirmatorio sigue cerrado.
- La cohorte histórica grande se está materializando únicamente para TRAIN y
  DEV. La validación de la campaña empezó después de cerrar TRAIN y no se ha
  creado ningún `test.json`.

La lectura correcta para un paper es: ya existe una metodología y una
auditoría defendibles; todavía falta demostrar generalización estable en una
cohorte ampliada y, sólo después, abrir una evaluación confirmatoria separada.

## 2. Qué se auditó y qué queda fuera

Se auditó la cadena completa, no sólo el modelo:

1. procedencia y descarga de WFIGS/NIFC;
2. agrupación por `event_id` y construcción de pares temporales;
3. rechazo de scars finales, M3, hotspots, timestamps ambiguos y geometrías
   truncadas;
4. disponibilidad de Sentinel-2/Landsat antes de `t0` y HRRR antes de `t0`;
5. validez de píxeles, resolución, rejilla fija y geometría rasterizada;
6. separación por incendio (nunca por tesela) y sellado de confirmación;
7. selección de época/umbral sólo sobre DEV;
8. derechos de uso y frontera de publicación;
9. reproducibilidad de cada candidato mediante PR + protocolo + resultado.

No se cargaron para tuning los artefactos `confirmation`/`prospective` ni se
publican geometrías, teselas EO, tensores, checkpoints o predicciones por
píxel. La regla es especialmente importante aunque los datos sean públicos:
acceso público no equivale a licencia afirmativa de redistribución.

## 3. Datos y derechos: resultados comprobados

### 3.1 Cosecha histórica WFIGS

Fuente de evidencia: `data/open_if/wfigs_history_2020_2026/HARVEST_REPORT.json`.

| Campo | Resultado comprobado |
|---|---:|
| Particiones solicitadas | 70 |
| Particiones completas | 70 |
| Particiones fallidas | 0 |
| Observaciones normalizadas | 35.562 |
| Eventos únicos | 15.661 |
| Bytes descargados | 2.322.055.826 (~2,32 GB decimal) |

La cosecha quedó organizada por año y región GACC. No se subieron esos datos al
repositorio público; el repo sólo contiene código, contratos, inventarios y
metodología.

### 3.2 Pares y enriquecimiento

Fuente: `data/open_if/wfigs_history_2020_2026/enrichment/INVENTORY.json`.

| Campo | Resultado comprobado |
|---|---:|
| Pares temporales auditados | 3.439 |
| Eventos consultados | 842 |
| Consultas completas | 842 |
| Pares con Sentinel-2 pre-`t0` | 3.439 |
| Pares con Landsat pre-`t0` | 3.439 |
| Pares con ambos EO pre-`t0` | 3.439 |
| Sentinel-2 top candidate creado antes de `t0` | 2.877 |
| Landsat top candidate creado antes de `t0` | 1.377 |
| Ambos top candidates creados antes de `t0` | 1.163 |
| HRRR disponible por `t0` y ventana completa | 2.530 |
| HRRR sin resolver | 909 |
| Fuera del dominio HRRR CONUS | 673 |
| URLs de archivo HRRR sondeadas | 7.367 |

La selección de la campaña no usa crecimiento, área `t1` ni solapamiento como
ranking de entrada; esas cantidades sólo se usan en la validación posterior y
en el objetivo. Así se evita seleccionar ejemplos con información del futuro.

### 3.3 Política de derechos resuelta

La política interna está materializada por `wfigs_rights_summary()` y por los
inventarios. El resultado no es “todo se puede publicar”:

- permitido: investigación interna no comercial y entrenamiento interno;
- publicable: código, configuración, metodología, plots y métricas agregadas;
- bloqueado: datos crudos, geometrías, dataset derivado, tensores, teselas,
  checkpoints y predicciones por píxel;
- uso comercial: no autorizado por la evidencia disponible;
- la licencia explícita de redistribución no fue encontrada.

Evidencia de procedencia: el ítem público NIFC/WFIGS y su disclaimer científico;
la política está fechada en 2026-08-19 y marcada como “no es asesoría legal”.

## 4. Splits y cohortes

### 4.1 Cohorte congelada de desarrollo

La expansión que sustentó todas las ablaciones comparables tuvo:

- 184 incendios en TRAIN;
- 42 incendios en DEV/VALIDATION;
- 16 incendios de confirmación, abiertos una sola vez;
- 16 incendios prospectivos, nunca cargados;
- un par por evento y splits disjuntos por `event_id`.

El baseline de referencia de las ablationes es el control de semilla 47
(`0.131902` **DEV** event-macro IoU sobre los 42 incendios DEV, no TRAIN) y,
para decisiones de estabilidad, el ensemble congelado de tres semillas
(`0.136178`).

### 4.2 Campaña grande cerrada

El PR [#152](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/152)
añade una campaña reanudable con hasta 50 eventos por región GACC
(`events_per_region=50`; el año solo agrupa la materialización, no el tope), rejilla
`256×256`, resolución 60 m y fracción mínima válida 0,70. El script:

```text
scripts/run_wfigs_large_dev_campaign.py
```

Sólo acepta los assignments `train` y `validation`, materializa por grupos,
escribe `STATE.json`, falla si aparece un `test.json` y construye después el
dataset de adaptación. El informe final `LARGE_DEV_CAMPAIGN_REPORT.json` fue
revisado y deja este corte reproducible:

| Split | Seleccionados | Materializados | Rechazados | Tensores | Principales motivos |
|---|---:|---:|---:|---:|---|
| TRAIN | 287 | 235 | 52 | 235 | 25 píxeles válidos insuficientes; 3 geometrías fuera de la rejilla; 24 geometrías `t1` truncadas |
| VALIDATION | 87 | 76 | 11 | 76 | 5 píxeles válidos insuficientes; 6 geometrías `t1` truncadas |
| **Total** | **374** | **311** | **63** | **311** | **0 fallos de escritura** |

La configuración fue `events_per_region=50`, `256×256`, 60 m y fracción mínima
válida 0,70. Los 311 pares elegibles se materializaron sin fallos, los splits
son disjuntos por evento y `test.json` no existe ni fue usado para selección.
El dataset resultante es sólo TRAIN/VALIDATION; todavía no es evidencia de
confirmación y aún no se ha publicado ningún tensor, geometría ni checkpoint.

## 5. Protocolo ML congelado

### 5.1 Fuente y objetivo

- arquitectura: residual U-Net híbrida;
- fuente: checkpoint RCDA seleccionado en RCDA VAL;
- target: híbrido extent/growth;
- pesos del objetivo: extensión 0,35, crecimiento 0,65;
- Tversky: `alpha=0.3`, `beta=0.7`, `gamma=0.75`;
- adaptación habitual: decoder + proyecciones de entrada residuales;
- deeper encoder/context congelados en los experimentos de baja muestra;
- AdamW, `lr=1e-4`, batch 4; receta de las ablaciones DEV de esta campaña:
  máximo 18 épocas, paciencia 5. El default del adapter en código
  (`WFIGSAdaptConfig` y el protocolo 2026-08-19) es 30 épocas y paciencia 7;
- front-ring BCE `0.05` cuando lo indica el protocolo.

### 5.2 Features que se probaron

1. puente RCDA de 16 canales;
2. máscara `valid_data` aprendida;
3. geometría explícita del frente: distancia firmada y normales;
4. residuales EO robustos por tesela (azul/verde/rojo/NDVI, mediana/IQR);
5. combinación geometría + EO;
6. variantes de normalización y scopes de encoder;
7. decodificadores espaciales, caps de distancia, rejillas de pesos y reglas
   por tamaño del incendio.

### 5.3 Métricas y gate

La métrica primaria es **event-macro growth IoU**: se calcula por evento y se
promedia para no dejar que los incendios grandes dominen. También se guardan
pooled IoU, precisión, recall, F1, recall/IoU lejano y métricas por evento.

El gate de promoción de desarrollo exige una mejora mínima de `+0.005` sobre el
ensemble congelado: `0.136178 + 0.005 = 0.141178`. Época y umbral se eligen
exclusivamente en DEV. Si una idea no supera el gate en réplica de semillas,
queda registrada como rechazo, no se rescata con TEST.

## 6. Resultados comprobados y cómo cambiaron las decisiones

Todas las filas siguientes proceden de los `*_RESULT_*.md` y de los JSON de
adaptación locales; son métricas agregadas, no una nueva evaluación externa.

### 6.1 Controles de objetivo, transferencia y arquitectura

| Experimento | DEV event-macro IoU | Pooled IoU | Precisión | Recall | Decisión |
|---|---:|---:|---:|---:|---|
| Control decoder-only, seed 47 | 0.131902 | — | 0.217028 | 0.307855 | referencia de una semilla |
| Ensemble híbrido congelado, 3 seeds | **0.136178** | **0.149627** | 0.226176 | 0.306567 | control científico DEV |
| Growth-only + augment | 0.083614 | — | — | — | rechazado |
| Growth-only sin augment | 0.082554 | — | — | — | rechazado |
| Multitask transfer | 0.112394 | — | — | — | rechazado |
| ASPP-U-Net | 0.122170 | — | 0.209034 | 0.300170 | rechazado |
| All-parameter `lr=1e-5` | 0.123372 | — | 0.237014 | 0.248286 | rechazado |
| Scratch residual U-Net | 0.129120 | — | 0.215094 | 0.265312 | rechazado |
| Precision-oriented source | 0.111499 | — | 0.210362 | 0.257742 | rechazado |

**Interpretación:** el híbrido transferido conserva mejor el recall y la
estabilidad. Entrenar desde cero, cambiar a multitarea o forzar precisión
produce pérdidas de generalización o de recall.

### 6.2 Losses y normalización

| Experimento | DEV event-macro IoU | Pooled IoU | Precisión | Recall | Decisión |
|---|---:|---:|---:|---:|---|
| Negative-background BCE | 0.131685 | — | 0.218800 | 0.304634 | rechazado |
| Far-background BCE | 0.131897 | — | 0.217157 | 0.307464 | rechazado |
| Balanced-growth BCE | 0.129834 | — | 0.228356 | 0.283420 | rechazado |
| WFIGS converted normalization | 0.130501 | — | 0.224243 | 0.280337 | rechazado |
| RCDA TRAIN normalization | 0.131902 | — | 0.217028 | 0.307855 | conservar |

**Interpretación:** la normalización de RCDA TRAIN se mantuvo congelada para
evitar una segunda fuente de fuga/variabilidad. Las pequeñas ganancias de
precisión no compensaron la pérdida de recall ni el gate de IoU.

### 6.3 Decodificación y calibración

| Decoder | Event-macro IoU | Pooled IoU | Precisión | Recall | Decisión |
|---|---:|---:|---:|---:|---|
| Ensemble sin regla espacial | 0.136178 | 0.149627 | 0.226176 | 0.306567 | control |
| Cap de distancia 12 px | 0.136554 | 0.149155 | 0.225898 | 0.305094 | sensibilidad menor |
| Pesos `[.25,.25,.50]` + cap | 0.136771 | 0.147781 | 0.214854 | 0.321292 | no estable |
| Regla por tamaño de evento | 0.137478 | 0.147594 | 0.246673 | 0.268718 | no supera gate |

La regla por tamaño mejoró la precisión a costa del recall y sólo aportó
`+0.001299`; se conserva como análisis de sensibilidad, no como receta final.

### 6.4 Representaciones WFIGS

| Features / scope | Event-macro IoU | Pooled IoU | Precisión | Recall | Decisión |
|---|---:|---:|---:|---:|---|
| Máscara `valid_data` | 0.134848 | 0.149817 | 0.223636 | 0.312181 | rechazado |
| Geometría explícita, seed 47 | 0.136740 | 0.148653 | 0.255060 | 0.262712 | near miss |
| Geometría, ensemble 3 seeds | 0.134268 | 0.150103 | 0.258579 | 0.263518 | rechazado |
| Geometría + `enc1` completo | 0.133599 | 0.140359 | 0.266418 | 0.228775 | rechazado |
| EO tile-standardized, global | 0.135831 | 0.154225 | 0.240225 | 0.301091 | rechazado |
| EO + decoder por tamaño | 0.136407 | 0.149237 | 0.270176 | 0.250035 | sensibilidad |
| Combinado geometry + EO, seed 47 (bug) | 0.141378 | 0.154920 | 0.238660 | 0.306291 | no promover |
| Combinado, ensemble (bug) | 0.138581 | 0.152349 | 0.262019 | 0.266854 | no promover |

**Interpretación:** los residuales EO sí capturan cambio de dominio y mejoran
pooled IoU, pero la señal no fue suficientemente estable a nivel de evento.
Exponer la validez como un canal aislado no resolvió el problema.

### 6.5 Corrección física de la augmentación y replicación

La corrida de `0.141378` reveló una inconsistencia: al voltear o rotar una
tesela se transformaban viento y canales espaciales, pero no los índices de los
vectores normales del frente. El PR
[#146](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/146)
introdujo la transformación ortogonal/sign-correcta y añadió tests.

Después de corregir:

| Receta corregida | Event-macro IoU | Pooled IoU | Precisión | Recall | Decisión |
|---|---:|---:|---:|---:|---|
| Seed 47, combined features | 0.138828 | 0.151691 | 0.235699 | 0.298537 | near miss de una semilla |
| Ensemble 3 seeds | 0.138085 | 0.151251 | 0.253519 | 0.272698 | rechazado por estabilidad |
| Fuente RCDA seed 47 fija + adapt seeds | 0.140044 | 0.156678 | 0.240205 | 0.310616 | mejor evidencia estable hasta aquí |
| Misma fuente + rejilla fija (equal weights, cap 12) | **0.140719** | 0.152906 | 0.238705 | 0.298445 | aún bajo `0.141178` |

Las semillas de adaptación en la corrida de fuente fija obtuvieron
`0.140309`, `0.138084` y `0.138828`. La fuente fija reduce parte de la
variancia, pero no convierte el resultado en confirmatorio.

## 7. Confirmación: qué se puede afirmar y qué no

La confirmación de 16 eventos se abrió una sola vez antes de esta ronda de
ablaciones. El resultado registrado es:

| Métrica | Candidato | Baseline |
|---|---:|---:|
| Event-macro IoU | 0.067115 | 0.055010 |

La diferencia es `+0.012105`, pero el bootstrap pareado de 10.000 réplicas da
IC 95 % `[-0.001563, 0.029216]`; como incluye cero, el gate sigue **false**.
El candidato ganó en 56,25 % de los eventos. El prospectivo de 16 eventos
permanece sellado y nunca se cargó.

Por tanto, los resultados DEV no deben presentarse como “mejoró en el mundo
real” ni como una comparación confirmatoria. La afirmación defendible es que
el pipeline detecta una señal de transferencia, pero aún requiere más datos y
una réplica bloqueada.

## 8. Iteración: por qué se tomó cada siguiente paso

1. **Primero se congeló el control.** Sin un ensemble RCDA reproducible no había
   una referencia científica; se fijaron semillas, normalización y selección en
   VAL.
2. **Se probaron objetivos y arquitecturas.** Growth-only, multitarea, ASPP,
   scratch y pérdidas BCE quedaron por debajo; se evitó seguir gastando TEST en
   ideas que ya perdían en DEV.
3. **Se separó precisión de calidad geométrica.** Las reglas espaciales y por
   tamaño subían precisión, pero bajaban recall/pooled IoU; se conservaron como
   sensibilidad.
4. **Se auditó el dominio EO.** La máscara válida no bastó; los residuales
   robustos por tesela mejoraron pooled IoU, motivando combinar EO con geometría.
5. **Se corrigió una violación física.** El resultado de una semilla se invalidó
   como receta de promoción porque los normales no seguían la augmentación.
6. **Se rehicieron las réplicas.** El ensemble corregido y la fuente fija no
   superaron `+0.005`; se cerró esa familia en la cohorte pequeña.
7. **Se amplió TRAIN/DEV.** La siguiente acción racional es aumentar potencia y
   reducir varianza antes de abrir cualquier confirmación nueva.

Este orden evita seleccionar el modelo por el mejor número aislado y deja
registrados también los caminos que no funcionaron.

## 9. Código y salvaguardas implementadas

Componentes principales:

- `wildfire_front/ml/wfigs_external_eval.py`: dataset externo, máscara válida,
  geometría de frente y residuales EO robustos;
- `wildfire_front/ml/wfigs_domain_adapt.py`: adaptación RCDA→WFIGS, expansión
  de canales, scopes entrenables, selección sólo en DEV y asserts anti-TEST;
- `wildfire_front/ml/rcda_sealed.py`: fuente sellada, normalización TRAIN-only,
  métricas event-macro y ensembles;
- `wildfire_front/open_if/regional/wfigs_campaign.py`: selección por evento,
  grupos reanudables e inventarios;
- `scripts/run_wfigs_large_dev_campaign.py`: campaña grande TRAIN/DEV;
- tests WFIGS de materialización, derechos, geometría, adaptación y campaña.

Guardrails que se ejecutan en código:

- rechazo de roots con `confirm`, `test` o `prospective` en los runners;
- comprobación de que el source checkpoint se seleccionó en RCDA VAL;
- comprobación de TRAIN/DEV disjuntos por evento;
- `wfigs_test_loaded == false` y `test_used_for_selection == false`;
- fallo explícito si se crea `dataset/test.json`;
- rechazo de geometrías fuera de rejilla, truncadas o con validez insuficiente;
- escritura atómica de inventarios/estado;
- checkpoints y tensores sólo locales.

Verificación ejecutada en el PR de campaña:

```text
python -m pytest tests/test_wfigs_campaign.py tests/test_wfigs_domain_adapt.py -q
12 passed

ruff check scripts/run_wfigs_large_dev_campaign.py \
  wildfire_front/ml/wfigs_domain_adapt.py \
  wildfire_front/ml/wfigs_external_eval.py \
  tests/test_wfigs_campaign.py tests/test_wfigs_domain_adapt.py
All checks passed!
```

## 10. Cadena de PRs publicada

La cadena está apilada; cada PR nuevo usa como base el anterior y permanece
abierto/mergeable para revisión ordenada. Los PRs de resultados contienen sólo
metodología y métricas agregadas.

| Bloque | PRs | Qué contiene |
|---|---|---|
| Auditoría y controles | [#80](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/80)–[#87](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/87) | auditoría limpia, UI de conteos, réplicas RCDA, fuente congelada |
| Sellado y primeros pilotos | [#88](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/88)–[#99](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/99) | ensembles, front-ring, prospectivo sellado, expansión de confirmación |
| Confirmación y controles DEV | [#100](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/100)–[#110](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/110) | telemetría, gate, follow-up, decoder espacial y multitarea |
| Objetivos y arquitectura | [#111](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/111)–[#131](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/131) | BCE, far-background, pesos, normalización, tamaño, ASPP, all-low, source precision, scratch |
| Features WFIGS | [#132](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/132)–[#145](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/145) | máscara válida, geometría, enc1, EO tile, combinación y réplicas |
| Corrección y fuente fija | [#146](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/146)–[#151](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/151) | augmentación física correcta, réplica corregida, fuente RCDA fija |
| Cohorte grande | [#152](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/152)–[#153](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/153) | campaña TRAIN/DEV reanudable y protocolo de adaptación grande |

Los títulos individuales y sus ramas quedan verificables en GitHub; no se
deben mezclar PRs de código con PRs de resultados al hacer merge.

## 11. Archivos de evidencia

- Harvest: `data/open_if/wfigs_history_2020_2026/HARVEST_REPORT.json`.
- Enriquecimiento: `data/open_if/wfigs_history_2020_2026/enrichment/INVENTORY.json`.
- Protocolo de derechos: `docs/WFIGS_DOMAIN_ADAPTATION_PROTOCOL_2026.md` y
  `wildfire_front/open_if/regional/wfigs_rights.py`.
- Confirmación: `docs/WFIGS_EXPANSION_CONFIRMATION_20260820.md`.
- Control DEV: `docs/WFIGS_FOLLOWUP_DEV_RESULT_20260820.md`.
- Resultados por experimento: todos los `docs/WFIGS_*_RESULT_*.md`.
- Corrección física: `docs/WFIGS_GEOMETRY_AUGMENTATION_FIX_PROTOCOL_20260821.md`.
- Fuente fija: `docs/WFIGS_FIXED_SOURCE_ENSEMBLE_DEV_RESULT_20260821.md`.
- Campaña grande: `docs/WFIGS_LARGE_DEV_CAMPAIGN_PROTOCOL_20260821.md` y
  `docs/WFIGS_LARGE_DEV_ADAPTATION_PROTOCOL_20260821.md`.

Los JSON de adaptación contienen el detalle por semilla y por evento, pero
permanecen locales porque incluirían rutas, IDs y artefactos derivados sujetos
a la política de derechos.

## 12. Siguiente decisión científica

Cuando termine la campaña grande:

1. auditar `LARGE_DEV_CAMPAIGN_REPORT.json` y los dos inventarios;
2. confirmar conteos, regiones, rechazos, derechos y ausencia de TEST;
3. correr la receta corregida de fuente fija en las tres semillas;
4. comparar contra el control congelado en el **nuevo DEV**, sin tocar
   confirmación/prospectivo;
5. repetir sólo si una mejora supera `+0.005` y mantiene recall/pooled IoU;
6. abrir una nueva confirmación únicamente mediante un protocolo separado y
   aprobado, con un split event-disjoint completamente nuevo.

Hasta que esos seis puntos se cumplan, el modelo no debe etiquetarse como
“listo para paper confirmatorio”. Sí está listo para una sección metodológica y
para un informe de auditoría reproducible: las decisiones, los rechazos y la
frontera de derechos están documentados y comprobados.

## 13. Corrección post deep-verify (2026-08-21)

Verificación claim-a-claim de los PRs `#56`–`#155`: 322 claims, 314 supported,
4 contradicted, 4 unverifiable en el checkout `wip/latam-au-campaign`.

- `#107` IoU 0.131902 / 0.083614 / 0.082554 es **DEV**, no TRAIN. TRAIN=184 es
  el tamaño de la cohorte de entrenamiento, no el split de la métrica.
- El tope de la campaña grande es **50 eventos por región GACC**, no por
  región/año. El año solo agrupa la materialización.
- `wfigs_rights_summary()` ahora lista `per_pixel_prediction` en
  `publication_blocked`, alineado con la prosa de esta auditoría.
- Conteos de `#155` comprobados en GitHub (el archivo no estaba en el checkout
  local): TRAIN 235/52, VAL 76/11, total 311, `samples_failed=0`, 6 rechazos
  VAL `t1_geometry_truncated`.
