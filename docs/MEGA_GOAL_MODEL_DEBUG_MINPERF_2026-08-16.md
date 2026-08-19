# MEGA-GOAL — depurar cada `.py` del modelo y extraer el mínimo rendimiento honesto

**ID:** `MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16`  
**Escrito:** 2026-08-16  
**Rama de trabajo:** `wip/latam-au-campaign` (rebasear sobre `origin/main` antes de ejecutar)  
**Cómo lanzarlo después:**

```
/goal checker lee docs/MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16.md sección 0 y confirma MET con artefactos :: ejecutar fases 1–6 de ese documento; no parar hasta el criterio
```

Este archivo **es** el mega-goal. No es un plan de SPA, ni de H1, ni de GO_Q. Es el contrato para que un agente recorra el código del modelo, lo depure, y saque **hasta el último punto de IoU honesto**. Si no cabe en la sección 0, no está hecho.

---

## 0. Hecho cuando (criterio duro)

El checker marca **MET** solo si **todas** estas frases son verdaderas y hay fichero que lo prueba. Si una es falsa, **NO MET**.

1. Existe `outputs/ml_eval/mega_goal_model/INVENTORY.json` con **cada** `.py` de la sección 3 (olas 1–5). Cada fila tiene `status ∈ {audited_ok, bug_fixed, out_of_perf, blocked}` y `note` de una línea. Cero filas `pending`.
2. Existe `outputs/ml_eval/mega_goal_model/BUGLOG.md` con todo bug encontrado (archivo:línea, síntoma, fix o `wontfix` + por qué). Si no hubo bugs, el log lo dice explícitamente y el inventario lo respalda.
3. Se re-ejecutó `python scripts/run_latam_au_complete_model_iou.py` **después** de los fixes. El JSON nuevo está en `outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json`.
4. El JSON nuevo usa el **mismo** protocolo de pares: excluye `too_short_delta` (<12 h), `static_label_copy` (label IoU > 0.98), `incompatible_product_kind` (FEP/GRA ≠ DEL/MONIT). No se reintroduce el 0.088 de EMSR715 FEP→DEL.
5. Sobre los pares `usable` del run nuevo:
   - `n_pairs_used ≥ 4` (hoy: 1 Nacimiento + 3 NSW).
   - **Mínimo de rendimiento (cierra el goal):** `mean(delta_vs_copy) > 0`. El modelo **gana a copy** en media. Copy = máscara t0 vs label t1.
   - **Suelo por par:** ningún par `usable` con `delta_vs_copy < -0.05` sin una entrada en BUGLOG que nombre la causa (fuga, canal mal alineado, threshold, tile mix). “Hace falta más datos” no vale si el par ya es usable.
6. Existe `outputs/ml_eval/mega_goal_model/SCORECARD.md` con la tabla de la sección 5 rellenada **antes / después**, y un bloque `not_claims` idéntico al de abajo.
7. Tests: `python -m pytest tests/test_latam_au_code_improve.py tests/test_latam_au_product_e2e.py tests/test_unet_model.py tests/test_u1_honest_eval.py tests/test_ndws_metrics.py -q` en verde.
8. `python scripts/check_release_flags.py` sigue **PASS**. Nadie ha puesto `GO_Q=complete`, `lab_ok_conaf=true`, ni ha vestido catalog 0.8963 como certeza live.

**No es MET** si el mean IoU sube porque se han metido pares estáticos, FEP/GRA, o se ha dropeado el par de Nacimiento donde el modelo pierde (−0.088).

### `not_claims` (copiar tal cual al SCORECARD)

- `complete_proxy_model_iou` **no** es transfer IoU sellado.
- **No** es U1 TEST CLM (0.857).
- **No** es catalog 0.8963.
- **No** es ROS. IoU ≠ ROS.
- **No** es GO_Q complete. **No** es GO_TOTAL.
- **No** es FREEZE lift de producto hasta que un humano promocione pesos. Un retrain de laboratorio se etiqueta `lab_scratch`, no `clm_ensemble_v34`.
- EMSR715 `n_pairs_used=0` se queda en 0 salvo que aparezca un par DEL→DEL/MONIT real. El 0.088 viejo **no se maquilla**.
- `lab_ok_conaf` sigue false.

---

## 1. Línea de base (2026-08-16T13:30Z) — no tocar estos números

Fuente: `outputs/ml_eval/latam_au_complete_iou/complete_proxy_model_iou.json`.

| Evento | n_pairs | n_used | pair_class del resto | model IoU | copy IoU | Δ vs copy |
|---|---:|---:|---|---:|---:|---:|
| `AU_EMSR500_PERTH` | 2 | 0 | static_label_copy + incompatible_product_kind | — | — | — |
| `CL_EMSR647_NACIMIENTO` | 2 | 1 | 1× too_short_delta (2.3 h) | **0.673** | **0.761** | **−0.088** |
| `AU_EMSR408_NSW` | 3 | 3 | — | 0.857 / 0.669 / 0.880 | 0.918 / 0.695 / 0.949 | −0.061 / −0.026 / −0.068 |
| `CL_EMSR715_VALPARAISO` | 2 | 0 | FEP/GRA ≠ growth | — | — | — |
| **Media usable** | | **4** | | **0.737** | copy gana | **todos Δ < 0** |

CLM sellado (otra cosa): U1 TEST IoU **0.857** · sel@80 **0.903** · ECE **0.153** · n=200. Provenance only en producto. No se usa como cifra LATAM.

**Diagnóstico de partida (hipótesis, no hecho hasta que la ola 2 lo mate o lo confirme):**

- El UNet CLM en delta, con `real_proxy_fill` (meteo punto + DEM + NBR), **copia peor que copiar la máscara**.
- Posibles causas en código, no en “más GPU”: canales `legacy17` mal ordenados vs pesos; `prev_fire` / delta invertido; threshold 0.5; tiles interior vs borde; veg NBR post-fuego en vez de pre-fuego; meteo constante espacial; `prepare_input` asume 17 y se le pasan 18.
- Hasta que cada `.py` de las olas 1–3 tenga fila en INVENTORY, no se declara “el modelo es malo”. Puede ser un bug de ensamblado.

---

## 2. Rails (romper uno = fallar el goal)

- No inventar IoU. No alimentar 1 banda al UNet v34 y reportar transfer.
- No levantar FREEZE de producto. Retrain = `lab_scratch_*` + manifiesto aparte.
- No mezclar ROS y IoU.
- No reclamar GO_Q / GO_TOTAL / `lab_ok_conaf`.
- No commitear pesos `.pt` si `.gitignore` los excluye; sí el JSON de eval.
- Rebase sobre `origin/main` (`f623eca` + #51–#54) **antes** de tocar código. LATAM va 5 commits detrás.
- Un PR (o un commit) por ola. No un dump de 80 archivos.

---

## 3. Cada `.py` — inventario obligatorio

Hay ~739 `.py` en el árbol. **Este goal no depura la SPA.** Depura el camino que mueve IoU. El inventario debe listar **todos** los de abajo. Los demás (`product/`, `cli_*.py`, `map_status/`) van como `out_of_perf` en bloque, no uno a uno.

### Ola 0 — generador de inventario (hacer primero)

Escribir `scripts/inventory_model_py.py` que recorra las rutas de esta sección y emita `INVENTORY.json`. Sin este script no hay MET.

### Ola 1 — pares, labels, schema (aquí se esconde el 0.088 y el copy)

| Archivo | Qué buscar |
|---|---|
| `wildfire_front/open_if/latam_au.py` | `classify_temporal_pair`, `GROWTH_LABEL_KINDS`, `hours_between`, `mean_usable_pair_ious`, `pick_pre_s2_path`. Fugas: FEP/GRA como growth; Δt; copia estática. |
| `scripts/run_latam_au_complete_model_iou.py` | `cov_at_label`, tiles 64, threshold 0.5, `delta_vs_copy`, `in_channels`. ¿18 vs 17? |
| `scripts/run_latam_au_experimental_model_iou.py` | No debe reportarse como complete. |
| `wildfire_front/ml/feature_schema.py` | `build_legacy17_channels`, `schema_channel_count`. Orden de canales = orden de `weights_multi_if.pt`. |
| `wildfire_front/ml/dataset.py` | Lookahead, split leak, label copy. |
| `wildfire_front/ml/normalization.py` | FFMC / stats de CLM aplicadas a LATAM sin clip. |
| `wildfire_front/ml/types.py` | Contratos de tensor. |

### Ola 2 — forward del modelo (aquí se pierde contra copy)

| Archivo | Qué buscar |
|---|---|
| `wildfire_front/ml/unet_train.py` | `build_model`, `prepare_input`, delta mode, sigmoid vs logits, threshold. |
| `wildfire_front/ml/train.py` | pos_weight, loss, val metric ≠ test leak. |
| `wildfire_front/ml/spread_predictor.py` | Quién llama al UNet en producto vs eval. |
| `wildfire_front/ml/physics.py` | Canales físicos denorm / invertidos. |
| `wildfire_front/ml/weights.py` | Path, schema id, `in_channels` del ckpt. |
| `wildfire_front/ml/export_torchscript.py` | Solo si el eval usa TS. |
| `wildfire_front/models.py` | Fachada vieja vs `ml/`. |

### Ola 3 — métricas (aquí se miente sin querer)

| Archivo | Qué buscar |
|---|---|
| `wildfire_front/ml/clm_eval.py` | Split TEST vs LATAM. |
| `wildfire_front/ml/u1_eval.py` | U1 sellado. No mezclar con complete_proxy. |
| `wildfire_front/ml/ndws_metrics.py` | IoU / ECE definición. |
| `wildfire_front/ml/reliability_metrics.py` | ECE. |
| `wildfire_front/ml/nested_cv.py` | No usar LATAM como fold CLM. |
| `wildfire_front/ml/scorecard_schema.py` | Campos `not_claims`. |
| `wildfire_front/ml/protocol_rails.py` | FREEZE / promote. |
| `wildfire_front/evaluation.py` | Ops vs ML. |
| `wildfire_front/metrics_protocol.py` | Nombres de métrica. |

### Ola 4 — datos que alimentan el forward

| Archivo | Qué buscar |
|---|---|
| `scripts/fill_latam_au_ndws_covariates.py` | Meteo en **timestamp del label**; DEM fallback silencioso prohibido. |
| `scripts/warp_latam_au_s2_to_cems.py` | Solo S2→CEMS; no `*_to_cems_to_cems`. |
| `scripts/adapt_latam_au_to_ndws_patches.py` | NPZ 17ch. Si el schema no cierra, `model_iou=null`. |
| `scripts/export_latam_au_ml_patches.py` | Tiles, no pack entero. |
| `scripts/align_latam_au_era5.py` | Alineación temporal. |
| `scripts/build_latam_au_lofo_folds.py` | Held-out ≠ train. |
| `scripts/eval_latam_au_domain_gap.py` | `model_iou=null` si schema incompatible. |
| `scripts/geotiff_to_training_patches.py` | Grid / CRS. |
| `scripts/preprocess_clm_to_ndws_npz.py` | Referencia de schema CLM. |
| `wildfire_front/open_if/stac_s2.py` | Pre-fire vs post-fire. |
| `wildfire_front/open_if/dnbr.py` | NBR pre. |
| `wildfire_front/ml/cloud_train.py` | Solo si se lanza retrain `lab_scratch`. |

### Ola 5 — tests que clavan el suelo

| Archivo | Qué debe seguir siendo cierto |
|---|---|
| `tests/test_latam_au_code_improve.py` | FEP≠growth; Δt; no 0.088 en la media. |
| `tests/test_latam_au_product_e2e.py` | Rails de producto. |
| `tests/test_latam_au_campaign.py` | Packs / rights. |
| `tests/test_latam_au_p1_p2.py` | P1/P2. |
| `tests/test_latam_au_residual_backlog.py` | Residual. |
| `tests/test_unet_model.py` | Shapes / forward. |
| `tests/test_u1_honest_eval.py` | U1 no se viste de LATAM. |
| `tests/test_ndws_metrics.py` | IoU binario. |
| `tests/test_ml_pipeline.py` | Pipeline CLM. |
| `tests/test_ml_focus_protocol.py` | Protocolo. |

### Fuera de rendimiento (marcar `out_of_perf` en bloque)

`wildfire_front/product/*.py`, `cli.py`, `cli_app.py`, `cli_operator.py`, `cli_incident.py`, `cli_report.py`, `map_status/*`, `incident/*`, `progressive_burn/*` (salvo que el eval los llame), scripts CONAF/H1/SPA, tests de decide/SPA.

---

## 4. Fases de ejecución (orden fijo)

### Fase 1 — Rebase + inventario

1. `git fetch origin` y rebase `wip/latam-au-campaign` sobre `origin/main`.
2. Correr `scripts/inventory_model_py.py` → `INVENTORY.json` con todo `pending`.
3. Commit: `chore(ml): inventory every model-path .py for mega-goal`.

### Fase 2 — Depurar olas 1–3 (sin retrain)

Por cada archivo de las olas 1–3:

1. Leer el forward real (quién llama a quién con qué shape).
2. Añadir o ejecutar un test mínimo si el archivo mueve IoU.
3. Si hay bug: fix + test + fila `bug_fixed`.
4. Si está limpio: `audited_ok` + nota (“orden canales = ckpt”, etc.).

**Parada obligatoria de fase 2:** un diagrama de 15 líneas en `outputs/ml_eval/mega_goal_model/FORWARD.md`:

```
label_t0 tif → mask
cov_at_label → meteo/DEM/NBR
build_legacy17_channels → (C,H,W)
prepare_input → tensor
UNet → logits → threshold
vs label_t1  y  vs copy(mask_t0)
```

Si C ≠ `in_channels` del ckpt, **eso se arregla antes de retrain**.

### Fase 3 — Re-eval zero-shot (mismos pesos)

```
python scripts/run_latam_au_complete_model_iou.py
```

Copiar JSON a `outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json`.  
Rellenar SCORECARD columna “después de debug, mismos pesos”.

Si ya `mean(delta_vs_copy) > 0` → ir a fase 6 (el mínimo está sacado **sin** GPU).  
Si sigue Δ < 0 → fase 4.

### Fase 4 — Un solo retrain `lab_scratch` (opcional, solo si fase 3 falla)

- Pesos nuevos **no** sustituyen `models/clm_ensemble/weights_multi_if.pt` en producto.
- Datos: solo pares `usable` + CLM holdout. **Cero** FEP/GRA, **cero** static copy, **cero** annual L1 como next-mask.
- 1 seed, 1 config. No barrido de 20 runs.
- GPU: crédito RunPod 100 $ / Community 4090. Apagar el pod.
- Eval con el **mismo** runner complete_proxy.
- Si el scratch gana a copy y el v34 no: SCORECARD lo dice. FREEZE de producto **sigue**.

### Fase 5 — Ablations mínimas (solo si fase 4 corre)

Como mucho **tres**, cada una un commit:

1. Quitar meteo punto (canales a 0) — ¿el Δ mejora? Entonces el fill miente.
2. Solo tiles `edge` — si el modelo solo gana en borde, el mean global no se vende.
3. Threshold {0.4, 0.5, 0.6} en **eval**, no en train. El mejor threshold de eval se reporta como `eval_threshold_sweep`, no como U1.

### Fase 6 — Cierre

- SCORECARD.md completo.
- BUGLOG.md cerrado.
- INVENTORY sin `pending`.
- Tests de la sección 0.7 verdes.
- `check_release_flags.py` PASS.
- Parar. No abrir SPA. No tocar GO_Q.

---

## 5. Tabla que el SCORECARD debe copiar

| Métrica | Antes (2026-08-16 13:30Z) | Después debug (mismos pesos) | Después lab_scratch (si hubo) | ¿MET? |
|---|---|---|---|---|
| n_pairs_used | 4 | | | ≥ 4 |
| mean complete_proxy IoU | 0.737 | | | informativa |
| mean Δ vs copy | **negativa en 4/4** | | | **> 0** |
| Nacimiento Δ | −0.088 | | | ≥ −0.05 o RCA |
| NSW mean Δ | −0.052 | | | ≥ −0.05 o RCA |
| EMSR715 n_used | 0 | | | 0 salvo par DEL real |
| Perth n_used | 0 | | | 0 si sigue copia |
| transfer IoU sellado | no | no | no | debe seguir **no** |
| GO_Q | partial | partial | partial | no complete |

---

## 6. Qué no entra en este mega-goal

- Reservar H1, acta, Mihura, Pablo, CONAF, Jorge.
- PRs de stamp fusion ON (#51–#54) salvo el rebase.
- SPA, decision-log, V&V sidecar.
- Vestir 0.857 / 0.8963 como LATAM.
- “Mejorar el modelo” con más markdown en `docs/`.

Si un agente escribe un PLAN_*.md nuevo en vez de INVENTORY + BUGLOG + SCORECARD + JSON de eval, ha fallado el goal.

---

## 7. Checker (texto para `/goal`)

```
MET iff:
- outputs/ml_eval/mega_goal_model/INVENTORY.json exists and has zero status=pending
  for every path listed in docs/MEGA_GOAL_MODEL_DEBUG_MINPERF_2026-08-16.md section 3 olas 1–5
- outputs/ml_eval/mega_goal_model/BUGLOG.md exists
- outputs/ml_eval/mega_goal_model/FORWARD.md exists
- outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json exists, schema
  wfd_latam_au_complete_proxy_model_iou_v1, as_of_utc after the inventory commit
- usable pairs: n_pairs_used >= 4
- mean(delta_vs_copy) over usable pairs > 0
- no usable pair with delta_vs_copy < -0.05 unless BUGLOG names file:line cause
- EMSR715 n_pairs_used == 0 unless pair_class is usable DEL/MONIT (not FEP/GRA)
- SCORECARD.md repeats the not_claims block verbatim
- listed pytest files pass
- scripts/check_release_flags.py PASS
- GO_Q is not complete; lab_ok_conaf is not true; no claim of sealed transfer IoU
```
