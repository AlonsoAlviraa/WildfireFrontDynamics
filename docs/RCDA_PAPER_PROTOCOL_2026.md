# Protocolo pre-registrado RCDA para modelo de propagación

Fecha de congelación del diseño: 2026-08-19, antes de evaluar las nuevas recetas sobre TEST.

## Pregunta científica

¿La combinación de distancia global al frente, contexto multiescala y condicionamiento explícito por meteorología mejora la predicción del crecimiento diario frente a una dilatación morfológica y frente al U-Net sellado anterior, manteniendo generalización entre incendios?

## Datos y prevención de fuga

- RCDA completo: 8.131 muestras, 886 incendios y años 2015–2019.
- Split por `UID_FIRE`: 596 incendios TRAIN, 106 VALIDATION y 184 TEST.
- Ningún incendio aparece en más de un split y no existen duplicados binarios entre splits.
- Normalización ajustada exclusivamente con TRAIN.
- Arquitectura, objetivo, época y umbral se seleccionan exclusivamente con VALIDATION.
- Los sweeps usan `evaluate_test=False`; TEST se ejecutará solamente después de escribir `FROZEN_RECIPE.json`.

## Hipótesis y ablations pre-registradas

Fase 1:

- Objetivo directo de crecimiento, perímetro acumulado y pérdida híbrida.
- U-Net, U-Net con ASPP y residual U-Net con ASPP.
- Canal de distancia cercana y canal adicional de distancia global no saturada.

Fase 2:

- FiLM con contexto global obtenido al agregar espacialmente meteorología, viento y horizonte —manteniendo a la vez los rásteres completos en la rama profunda—, más un prior residual superficial de distancia–horizonte–meteorología para que la red modele desviaciones espaciales sobre una ley radial aprendida.
- Muestreo ponderado frente a uniforme.
- Tversky con balances precisión/recall `(0.4, 0.6)`, `(0.3, 0.7)` y `(0.2, 0.8)`.
- U-Net ancho y combinaciones adicionales de objetivo/contexto.

Las ocho recetas originales de fase 2 se definieron antes de observar fase 1.
Tras cerrar fase 1 sin evaluar TEST, `resunet_hybrid_v1` ganó VALIDATION con
IoU macro 0,18021 y alcanzó su mejor checkpoint en la época máxima 24. Antes de
abrir TEST se añadieron transparentemente dos continuaciones adaptativas: 40
épocas al mismo LR y 32 épocas a LR reducido. Son decisiones basadas sólo en
VALIDATION y no se presentan como pre-registradas originalmente.
La cuota semanal GPU de Kaggle bloqueó fase 2 antes de su creación. La corrida
CPU Spot de contingencia ejecuta la variante de 40 épocas. El informe ya sellado
de fase 1 mostró además un desequilibrio claro (precisión 0,183 frente a recall
0,377), por lo que, antes de observar fase 2 y aún sin abrir TEST, se registró en
la misma VM Spot, después de verificar y descargar la corrida larga, una
variante ResUNet híbrida de 32 épocas con Tversky `alpha=0.5, beta=0.5`. Se
intentó paralelizarla, pero la cuota global de 32 vCPU rechazó la segunda VM
antes de crearla; por ello ambas corridas son secuenciales. La variante de LR
reducido se ejecutará también, de forma condicional, si tras las dos primeras
continuaciones ninguna candidata alcanza 0,20 de IoU macro en VALIDATION. Las
ocho ablaciones originales quedan diferidas hasta disponer de GPU. Esta
limitación se declara y no autoriza abrir TEST anticipadamente. Por tanto, la
congelación compara las seis recetas terminadas de fase 1 con dos o tres
continuaciones adaptativas (ocho o nueve candidatas efectivamente entrenadas),
no con las recetas que no se ejecutaron. La regla condicional y su umbral se
escribieron antes de observar cualquier resultado de fase 2.

Tras agotar la cuenta principal sus 30 horas GPU semanales, se habilitó una
segunda cuenta Kaggle con cuota independiente. Los dos datasets RCDA privados se
compartieron con permiso de lectura, sin hacerlos públicos ni duplicarlos. La
variante de precisión se reinició desde semilla 0 en una T4 y la corrida GCP
parcial quedó excluida de la selección por migración de backend. Cada kernel de
VALIDATION se ejecuta de forma secuencial, con una sola receta explícita y un
SHA-256 registrado; no se mezclan checkpoints ni métricas de las dos ejecuciones.
Antes de obtener ninguna métrica de fase 2 se eliminó el límite operativo de
ocho horas de la VM Spot, manteniendo la receta de 40 épocas sin cambios. El RAR
verificado por MD5 y su extracción se guardan en el disco persistente de GCP
para que un reinicio no altere datos ni obligue a abrir TEST prematuramente.
El entorno CPU observado para la corrida larga es Python 3.10.12, PyTorch
2.13.0, NumPy 2.2.6, SciPy 1.15.3, oneDNN disponible y 16 hilos PyTorch. Antes
de obtener resultados de fase 2 se habilitó `channels_last` para las corridas
posteriores; una comprobación local dio diferencia máxima de logits de
2,6e-6 y una aceleración de inferencia de 1,17×, sin cambiar el modelo lógico.

La corrida larga alcanzó su último mejor checkpoint finito en la época 13
(`event_macro_iou=0,16766`, umbral 0,20) y en la época 16 produjo una pérdida no
finita. La auditoría posterior recorrió los 13.002 ficheros NPY de TRAIN y no
encontró ningún NaN ni infinito, por lo que el incidente se atribuye a
inestabilidad de optimización, no a corrupción de datos. Se detuvo el modelo
contaminado, se verificó que todos los tensores del checkpoint de la época 13
eran finitos y se reejecutó exclusivamente la evaluación final de VALIDATION.
El artefacto queda marcado `truncated_after_nonfinite_optimization`; TEST no se
materializó ni evaluó. Antes de continuar se registró una enmienda de seguridad:
parada inmediata de la optimización ante loss no finita, conservando sólo un
checkpoint VAL verificado como finito; fallo ante gradientes CPU no finitos,
gestión de los overflows AMP mediante `GradScaler` y clipping de norma global de gradiente a
5,0. Esta enmienda cambia la optimización posterior y se reporta de
forma explícita; no modifica splits, métrica, rejilla de umbral ni reglas de
selección.

También antes de observar fase 2 se evaluó en VALIDATION una rejilla fija de
umbral, dilatación de 0–2 píxeles y filtrado de componentes desconectados de
`t0`. El mejor resultado de fase 1 pasó de 0,18021 a 0,18238, sólo +0,00217, con
el umbral en el borde superior 0,95. Por ser una mejora pequeña y con señal de
inestabilidad, ese posprocesado no se incorpora a la receta final; el artefacto
`PHASE1_POSTPROCESS_VAL.json` se conserva como resultado exploratorio negativo.

## Selección y evaluación final

- Métrica de selección: `event_macro_iou` sobre VALIDATION.
- En fase 1, la época se controla con `event_macro_iou@0.5`. Antes de descargar u observar su resumen, se pre-registró para fase 2 y final una selección de época robusta al umbral: máximo `event_macro_iou` en VALIDATION sobre `0.1, 0.2, …, 0.9` en cada época.
- Umbral seleccionado en una sola pasada de VALIDATION sobre la rejilla `0.05, 0.10, …, 0.95`.
- Ganador: mayor IoU macro entre todas las recetas efectivamente completadas en
  las fases 1 y 2; las recetas diferidas no cuentan como resultados ni como
  candidatas implícitas. No se usa TEST como desempate.
- Evaluación final pre-registrada: semillas `11`, `29` y `47`.
- Cada semilla selecciona época y umbral en VALIDATION y evalúa TEST una vez.
- La contingencia GCP genera el runner final desde el JSON congelado localmente,
  exige igualdad exacta de la receta embebida y de las semillas antes de aceptar
  el resultado, y detiene la VM después de descargar y verificar los artefactos.
- Métrica primaria: media entre semillas del IoU macro de crecimiento por incendio.
- Análisis secundario pre-registrado antes de abrir TEST: promedio de las
  probabilidades de las tres semillas, con un único umbral seleccionado en
  VALIDATION y una sola evaluación en TEST. El ensemble no sustituye la media
  entre semillas como endpoint primario ni modifica el gate.
- Incertidumbre primaria: bootstrap pareado al 95% sobre los 184 incendios.
- Contraste: Wilcoxon unilateral pareado frente al baseline de dilatación seleccionado en VALIDATION.

Enmienda previa al TEST del nuevo modelo: la primera versión del baseline
geométrico había escogido radio por IoU agrupado, aunque el endpoint principal
del paper es IoU macro por incendio. Una recomputación exclusivamente en VAL
seleccionó radio 6 (IoU macro 0,12498) en lugar de radio 3 (0,11707). El
artefacto antiguo se conserva como `dilated_copy_pooled_selection_legacy.json`;
el comparator oficial se regeneró con radio elegido por la métrica primaria.
El baseline corregido obtiene IoU macro TEST 0,12724 (frente a 0,12186 del
legado) e IoU agrupado 0,10709 (frente a 0,11081); por tanto endurece la
comparación macro sin ocultar el intercambio entre endpoints.
El TEST del baseline legado ya era conocido cuando se detectó esta
incoherencia; la enmienda se justifica por alinear selector y endpoint, usa
solo VAL para elegir radio y se cerró antes de evaluar el nuevo modelo final.
No se compararon radios por su resultado TEST.

Métricas secundarias:

- IoU micro de crecimiento.
- Average Precision de crecimiento.
- IoU y calibración dentro de FCER derivado solo de `t0`.
- ECE, error selectivo al 80% y AURC dentro de FCER.
- Cobertura del crecimiento observado por FCER.
- Boundary-F1 simétrico.
- Recall e IoU a más de 10,5 píxeles del frente.

## Gate definido antes de TEST

El resultado podrá llamarse `paper_model_candidate` únicamente si:

1. se completan al menos tres semillas pre-registradas;
2. IoU macro medio por incendio en TEST es al menos `0.20`;
3. el límite inferior del bootstrap pareado de la mejora frente a dilated-copy es mayor que cero;
4. todas las semillas superan el IoU macro del baseline;
5. TEST no participó en ninguna selección.

Además, antes de observar los resultados de las nuevas recetas se endureció el gate: se reconstruyen métricas por incendio de los checkpoints sellados U-Net y RCDA anteriores, y el nuevo modelo debe superar al mejor de ellos en media, en cada semilla y con límite inferior positivo del bootstrap pareado.

Antes de observar resultados de fase 2 también se fijó una regla de parada
adaptativa: tras `resunet_hybrid_long_v2` y la variante de pérdida equilibrada,
se ejecuta la variante de LR bajo si el mejor IoU macro de VAL sigue por debajo
de 0,20. Si después continúa bajo 0,20, se ejecuta `resunet_growth_v1` como
siguiente ablación. La justificación previa es que en fase 1 el objetivo growth-only
superó al hybrid dentro de U-Net, mientras ResUNet fue la arquitectura ganadora.
Ninguna de estas reglas consulta TEST.

La auditoría de TRAIN encontró 596 incendios con 1–61 observaciones. El
sampler original reduce la razón de masa inducida por duración de 61× a 7,8×,
pero no la elimina, mientras el endpoint principal pesa cada incendio por
igual. Por ello, antes de observar resultados finales de fase 2 se registró
`resunet_hybrid_event_balanced_v1`: usa exponente 1,0 para compensar el número
de días por incendio y se ejecuta solo si todas las recetas previas siguen por
debajo de 0,20 en VALIDATION. Conserva el ajuste por tamaño de crecimiento, por
lo que se describe como balance por duración del evento, no como uniformidad
exacta de todas las muestras. TEST no interviene.

Una auditoría TRAIN-only posterior cuantificó la masa completa del sampler:
15/5.552 ejemplos (0,27%) tienen crecimiento cero, por lo que los negativos
vacíos no son el cuello de botella. La estrategia por defecto concentra 49,97%
de su probabilidad en frentes de 1–99 píxeles y deja un coeficiente de variación
de masa por incendio de 0,647. La alternativa `uniform_events` asigna peso
`1 / n_muestras_del_incendio`, obtiene CV aproximadamente cero y alinea el
objetivo de entrenamiento con el endpoint macro por incendio. Por ello se
registró `resunet_hybrid_uniform_events_v1` como ablación VAL condicional,
después del balance por duración y antes de FiLM, sólo si el mejor candidato
sigue bajo 0,20. El diagnóstico no leyó VAL ni TEST.

La misma pasada verificó la semántica acumulativa de TRAIN: las 5.552
transiciones retienen todos los píxeles positivos de t0 (cero muestras con
contracción y cero píxeles perdidos). Por tanto, `growth-only` es una ablación
de objetivo, no una corrección de etiquetas no monótonas.

Si todas las variantes ResUNet anteriores continúan bajo 0,20 en VAL, el último
fallback pre-TEST es `film_growth_v1`, ya incluido en el sweep original. Su
hipótesis es distinta: modulación explícita por meteorología/horizonte y un prior
radial superficial. Tras esta receta se congela el mejor candidato completado;
no se añaden más arquitecturas en esta campaña y TEST sigue sin participar.

El diagnóstico descriptivo posterior en los 106 incendios de VAL del líder de
fase 1 encontró una asociación débil y no significativa entre duración e IoU
(Spearman rho 0,153; p=0,116). Los eventos de 1–2 días obtuvieron 0,1659 y los
de 6–13 días 0,2052. Esto motiva mantener la receta balanceada como contingencia,
pero no permite afirmar que la duración cause el error.

No se afirmará generalización operativa ni superioridad global hasta validar en un segundo dataset temporal, idealmente WFIGS una vez materializados sus rásteres.

## Enmienda previa a resultados de fase 1

El 2026-08-19 se corrigió, antes de descargar u observar `TUNING_SUMMARY.json`, la reflexión vertical del viento en la augmentación: `sin(dirección)` representa este-oeste y `cos(dirección)` norte-sur, por lo que una reflexión vertical debe cambiar el signo del segundo componente. La fase 1 ya estaba ejecutándose con la implementación anterior y se conserva como tal; fase 2 y las corridas finales usan la corrección. En el mismo momento se registró la selección de época robusta al umbral descrita arriba. Ninguno de estos cambios observó TEST ni métricas de fase 1.

## Artefactos auditables

- `TUNING_SUMMARY.json`: ranking de VALIDATION y `test_evaluated=false`.
- `COMBINED_TUNING_SUMMARY.json`: unión de ambas fases.
- `VALIDATION_SCORECARD.json`: ranking con bootstrap pareado descriptivo por
  incendio, calculado exclusivamente en VALIDATION.
- `PHASE1_VAL_STRATA_AUDIT.json`: auditoría descriptiva por duración y soporte
  de crecimiento, sin acceso a TEST.
- `TRAIN_SAMPLER_AUDIT.json`: masa esperada de cinco estrategias calculada sólo
  con TRAIN; `validation_evaluated=false` y `test_evaluated=false`.
- `PHASE1_VAL_ENSEMBLES.json`: cinco combinaciones evaluadas sólo en VAL. El
  mejor ensemble multi-arquitectura quedó 0,00626 por debajo del mejor modelo
  individual y fue descartado antes de TEST.
- `PRETEST_DECISION_LOG.json`: orden condicional, decisiones y SHA-256 del
  código/evidencias registrados antes de cualquier TEST del nuevo candidato.
- `FROZEN_RECIPE.json`: receta, semillas y hashes antes de TEST.
- La receta congelada incluye MD5 del archivo RCDA, semilla de split y SHA-256
  de TRAIN, VAL, TEST y normalización TRAIN-only.
- `FINAL_SUMMARY.json`: tres ejecuciones finales.
- Cada checkpoint final incluye SHA-256 calculado en GCP y verificado de nuevo
  localmente antes de recomputar métricas o iniciar WFIGS.
- `FINAL_SUMMARY_PAPER_METRICS.json`: AP, FCER y boundary metrics reproducidas desde checkpoints.
- `PAPER_SCORECARD.json` y `.md`: bootstrap por incendio, contraste pareado y gate.

## Extensión externa WFIGS (separada del TEST RCDA)

La cosecha histórica contiene 35.562 observaciones, 15.661 incendios y 3.439
pares geométricos aprobados. La materialización externa aplica estas reglas:

- el recorte se centra exclusivamente con el perímetro `t0`; `t1` solo se usa
  como etiqueta y para rechazar truncamientos;
- la escena Sentinel-2 debe haber sido creada en STAC antes de `t0`; se prueban
  candidatos preordenados hasta alcanzar 70% de píxeles limpios;
- DEM Copernicus GLO-30 y ventanas COG se leen por rango, sin descargar mosaicos
  globales;
- HRRR debe pertenecer a una corrida disponible antes de `t0`, cubrir todo el
  horizonte y contener espacialmente el bbox. La auditoría corrigió 673 pares
  que estaban fuera de CONUS; 2.530 quedan válidos espacio-temporalmente;
- TRAIN y VALIDATION se materializan en campañas distintas, con un solo par por
  incendio en el piloto y normalización ajustada solo en TRAIN;
- WFIGS TEST no se materializa ni evalúa durante esta fase;
- por la política de derechos vigente, datos derivados, tensores y checkpoints
  WFIGS son solo para investigación interna no comercial y no se publicarán sin
  una licencia afirmativa de redistribución.

El primer tensor completo aceptado (`wfigs-pair-bfb5f2816dd64e8f2c39`, Arizona)
incluye máscaras `t0/t1`, Sentinel-2, NDVI, máscara de validez, GLO-30 y HRRR.
Este avance demuestra el pipeline, no generalización externa ni rendimiento del
modelo.

Después de congelar receta, pesos y umbrales RCDA, se permite una sola campaña
WFIGS TEST balanceada por región. La evaluación será cero-shot con las tres
semillas y sus umbrales RCDA ya fijados. También se evaluará una vez el ensemble
de probabilidades con su umbral ya fijado en RCDA VALIDATION; se reporta como
análisis secundario y no selecciona nada en WFIGS. El baseline geométrico usa radio elegido
solo en WFIGS VALIDATION. Ningún resultado WFIGS podrá retroalimentar arquitectura,
época, umbral o selección de semillas.

Antes de materializar WFIGS TEST se fijó una señal estadística externa: media
por incendio entre las semillas frente al baseline geométrico, con bootstrap
pareado de 10.000 remuestras. La señal solo pasa si todas las semillas superan
la media del baseline y el límite inferior del IC 95% del delta es positivo.
Se reporta también el contraste del ensemble. Este gate indica transferencia
externa en la cohorte estudiada; no demuestra validez operativa ni autoriza
redistribución de tensores o checkpoints.

Para adaptación de dominio, cada una de las tres semillas se ajusta en WFIGS
TRAIN y selecciona época/umbral sólo en WFIGS VALIDATION. Antes de materializar
WFIGS TEST también se congela un ensemble secundario de esas tres semillas, con
promedio de probabilidades y umbral elegido sólo en WFIGS VALIDATION. Se evalúa
una vez en TEST y no modifica el endpoint ni el gate primario de semillas.
