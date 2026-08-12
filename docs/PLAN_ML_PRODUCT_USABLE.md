# Plan — ML product usable (lab surface)

> **Scope:** 100% ML lab product surface. **Not** field_ops fusion, not ops ROS, not Hellín track.  
> **As of:** 2026-08-05  
> **Status machine:** [`docs/PLAN_ML_PRODUCT_STATUS.json`](PLAN_ML_PRODUCT_STATUS.json)  
> **Snapshot:** [`docs/CURRENT_STATE.md`](CURRENT_STATE.md) · **Goals:** [`docs/goals/README.md`](goals/README.md)  
> **Rails:** `field_ops.allow_ml_live_in_fusion=false` · `ml_product_go=false` until human promote · **IoU ≠ ROS** · catalog **0.8963** = provenance only  
> **Mega closed:** W3 **MET** · Tobarra KEEP-or-KILL **KILL** (fresh IoU 0.4776) — lab idle unless new signal; product residual = **H1**

---

## 1p. Cierre mega goals 2026-08-05 (iter 15–17)

| Goal | Process | Science | Board |
|------|---------|---------|-------|
| W3 multi-fire + protocol | **MET** | Hellín/Brazatortas/Retuerta Head A thr frozen | `iter_w3_mega_goal_latest.md` |
| Tobarra fresh LOFO KEEP-or-KILL | **MET** | **KILL** — IoU 0.4776 · K1 fail · leak 0 | `iter_tobarra_keep_or_kill_latest.md` |

**Next ML:** optional only with new patches/features/pre-registered kill bar. **Do not** re-open Tobarra KEEP same recipe.  
Product primary outside this plan: **H1 GO_Q** (`docs/H1_GO_Q_RUNBOOK.md`).

---

## 1. Estado actual de productos ML

| Product ID | Rol | Métrica honesta | Notas |
|------------|-----|-----------------|-------|
| **`clm_ensemble_v34`** | **Default / emergency ML** | U1 TEST mean IoU ~**0.86** · sel@80 ~**0.90** · ECE ~**0.15** | Soft-vote ensemble (v28 + EMA + multi-IF); VAL temp-cal. Catalog holdout IoU **0.8963** = **provenance only** (no live certainty). |
| **`clm_v28`** | Fallback single-model | Holdout IoU ~**0.838** · Δ copy +0.196 | Specialist CLM Spain; usar si ensemble weights incompletos. |
| **`ndws_v21`** | Research / G1 KILL primary | IoU **0.226** · Δ +0.076 | Baseline NDWS global. **No** primary de emergencia España. G1 features KILL — no reabrir como primary sin datos. |
| Ops (no ML) | `front_dynamics_v1` | ROS observado LWIR | **Separado** — nunca mezclar IoU ML con ROS. |

**Gates (lab claim surface):**

| Gate | Value | Meaning |
|------|-------|---------|
| `u1_test_honest` | **true** | U1 on TEST with frozen VAL-fit calibrator |
| `ml_product_go` | **false** | No promote humano completo a producto campo |
| `field_ops.allow_ml_live_in_fusion` | **false** | Fusion táctica OFF siempre en este plan |
| `research_open.allow_ml_live_in_fusion` | **true** (experimental) | Solo lab demos; no dispatch |

Fuentes: `docs/ML_PRODUCT_SCORECARD.json`, `docs/ML_U1_PROMOTE_RECORD.json`, `models/catalog.json`, `config/decision_policies.json`.

---

## 1o. Loop lab 2026-08-05 — W3 expert path (iteración 14)

**Fricción:** Hellín/Brazatortas BLOCKED en unaligned multi-frame; Tobarra hard; pack cerrado.

**Control:** ¿alinear por cadenas de solape → patches → Head A frozen + receta Tobarra LOFO con kill y zero leak, sin retunear ECE/thr en holdout TEST? **SÍ.**

| Entrega | Resultado |
|---------|-----------|
| Align Hellín | **OK** chain-local common grid (`align_geotiff_stack`) · 4 chains |
| Align Brazatortas | **OK** |
| Patches (min_change≥0.02) | Hellín **320** · Brazatortas **80** (static dropped) |
| Head A Hellín (n=60) | IoU **~0.79** · copy **~0.68** · **Δ+0.11** · ECE ~0.08 · thr frozen |
| Head A Brazatortas (n=60) | IoU **~0.54** · copy **~0.54** · **Δ~0** · ECE ~0.22 · hard transfer |
| Tobarra recipe | **OPTIONAL_lofo_finetune_with_kill** · leak audit **OK** · K1–K5 |
| Rails | `ml_product_go=false` · field_ops fusion **OFF** · no ECE thrash TEST |

**Honestidad:** no vender IoU sin Δ vs copy (short-Δt drone). Brazatortas no es GO de transfer.

Artefactos:
- `wildfire_front/ml/align_geotiff_stack.py` · `scripts/align_lwir_common_grid.py`
- `scripts/run_lab_ml_loop_v34_w3_expert.py`
- `outputs/ml_eval/w3/{hellin_2024,brazatortas_2025}/`
- `outputs/ml_eval/lab_loop/lab_loop_v34_w3_expert_latest.json`
- `outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json`
- `docs/ML_LOOP_ITERATIONS/iter_20260805_w3_expert.md`

**Next:** Tobarra LOFO finetune solo si K1–K5; W4 human promote. **No** ECE post-hoc U1.

---

## 1n. Loop lab 2026-08-05 — W3 señal nueva (iteración 13)

**Fricción:** pack CLM cerrado (4 sources); Tobarra hard; need fires/features nuevas.

**Control:** ¿instrumentar inventario + diagnóstico Tobarra sin ECE thrash? **SÍ.**

| Entrega | Resultado |
|---------|-----------|
| In-pack sources | 4 (CARDOSO, ESTRELLA×2, Tobarra) |
| External READY | hellin, brazatortas, retuerta, cardoso_2025_lwir (**P0=hellin**) |
| Tobarra mean IoU | **0.489** · bimodal **true** · frac IoU&lt;0.1 high |
| Reject thr helps Tobarra | yes (IoU acc ~0.84 @ abs~0.68) |
| Hellín patches dry-run | **BLOCKED** unaligned frames (H/W span thousands of px) → **unblocked in iter 14** |

Artefactos: `w3_fire_inventory.json` · `tobarra_head_a_diagnose.json` · `lab_loop_v34_w3_signal_latest.json` · `iter_20260805_w3_signal.md`

**Next:** alinear Hellín → NPZ → Head A; o finetune Tobarra con kill. **No** ECE post-hoc U1.

---

## 1m. Loop lab 2026-08-05 — LOFO Head A + Tobarra (iteración 12)

**Fricción:** multi-fuego Head A incompleto (faltaba Tobarra en W1/W2).

**Control:** ¿añadir Tobarra y re-evaluar thr/ECE frozen? **SÍ.**

| Fold | n | mean IoU | ECE | abstain@0.795 | IoU acc@lock |
|------|--:|---------:|----:|--------------:|-------------:|
| CARDOSO | 200 | 0.857 | 0.153 | 0.515 | 0.949 |
| LA_ESTRELLA_ACOM1 | 200 | 0.783 | 0.125 | 0.210 | 0.851 |
| LA_ESTRELLA_ACOM2 | 190 | 0.691 | 0.073 | 0.689 | 0.844 |
| **tobarra_20240802** | **300** | **0.489** | **0.342** | **0.680** | **0.841** |
| **mean (n=4)** | **890** | **0.705** | **0.173** | **0.524** | **0.871** |
| Holdout U1 | 200 | 0.857 | 0.153 | 0.515 | 0.949 |

**Hallazgos (actualizados):**
- Tobarra es el **fuego duro**: IoU full ~0.49 · ECE ~0.34 · abstain ~68%.
- Aun así thr~0.80 sube IoU accepted a **~0.84** (reject sigue útil).
- Mean ECE 4-fuegos **0.173 > holdout 0.153** (`worse_ece_than_holdout=true`) — no vender calibración multi-fuego como mejor.
- Superficie lab: **iter1 reject only** · field OFF · ml_product_go false.

**Next:** W3 features/datos nuevos o fine-tune-aware eval; no thrash ECE same-TEST.

---

## 1l. Loop lab 2026-08-04 — LOFO Head A W1/W2 (iteración 11)

**Fricción:** W1 BLOCKED (0 Head A caches por fuego).

**Control:** ¿build caches + ECE/reject multi-fuego frozen? **SÍ** (3 folds; expandido en 1m).

| Fold | n | mean IoU | ECE | abstain@0.795 | IoU acc@lock |
|------|--:|---------:|----:|--------------:|-------------:|
| CARDOSO | 200 | 0.857 | 0.153 | 0.515 | 0.949 |
| LA_ESTRELLA_ACOM1 | 200 | 0.783 | 0.125 | 0.210 | 0.851 |
| LA_ESTRELLA_ACOM2 | 190 | 0.691 | 0.073 | 0.679 | 0.843 |
| **mean (3)** | 590 | **0.777** | **0.117** | **0.471** | **0.881** |

Ver iter 12 para board de 4 fuegos + Tobarra.

---

## 1k. Loop lab 2026-08-04 — next-signal readiness gate (iteración 10)

**Fricción:** loop producto cerrado, pero el camino métrico siguiente (Head A LOFO) no estaba instrumentado como READY/BLOCKED.

**Control:** ¿instrumentar next sin retunear ECE ni auto-unfreeze? **SÍ.**

| Work item | Status | Nota |
|-----------|--------|------|
| **W1** per-fire Head A caches | **BLOCKED** | 0/3 caches; 3/3 LOFO weights; data hints OK |
| W2 LOFO ECE/reject eval | BLOCKED | depende W1 |
| W3 multi-fire Head A | **DONE MET** | Hellín/Brazatortas/Retuerta |
| Tobarra fresh KEEP-or-KILL | **DONE KILL** | no re-open same recipe |
| W4 / new features | OPEN optional | only with new signal · no thrash same-TEST |
| W4 human ml_product_go | BLOCKED | lab_usable ≠ promote |
| W5 H1 third-party | OUT_OF_SCOPE ML lab | |

CLI: `python -m wildfire_front ml next`  
Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_next_gate_latest.json`  
**recommended_next:** `W1_lofo_head_a_caches` · **auto_unfreeze:** false

---

## 1j. Loop lab 2026-08-04 — LOFO multi-fire scoreboard (iteración 9)

**Fricción:** LOFO existía como tabla fina (iter4); faltaba scoreboard de producto con fold débil, changed IoU y gap U1.

**Control:** ¿productizar board multi-fuego sin ECE same-TEST? **SÍ.**

| Fold | IoU | Δ copy | changed |
|------|----:|-------:|--------:|
| CARDOSO | 0.798 | +0.156 | 0.928 |
| LA_ESTRELLA_ACOM1 | 0.783 | +0.424 | 0.882 |
| **LA_ESTRELLA_ACOM2 (weakest)** | **0.693** | +0.323 | 0.881 |
| **mean / spread** | **0.758 / 0.105** | — | — |
| U1 holdout | 0.857 | gap +0.099 | (protocolo distinto) |

CLI: `python -m wildfire_front ml lofo`  
Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_lofo_board_latest.json`  
**Blocked still:** LOFO Head A ECE/reject (needs per-fire feature caches).

---

## 1i. Loop lab 2026-08-04 — post-freeze smoke (iteración 8)

**Fricción:** freeze sin gate de regresión re-ejecutable (riesgo de drift silencioso).

**Control:** ¿sigue verde freeze + CLI offline + rails? **SÍ** (`smoke_pass=true`).

| Check | Resultado |
|-------|-----------|
| freeze usable | OK |
| field_ops OFF / ml_product_go false | OK |
| CLI list/show/doctor/cases/curve/freeze/card | OK |
| show --json rails | OK |

CLI: `python -m wildfire_front ml smoke` · `make ml-lab-smoke`  
Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_smoke_latest.json`  
Report: `docs/ML_LOOP_ITERATIONS/iter_20260804_post_freeze_smoke.md`

**No** es retune de métricas. Superficie sigue **iter1 reject only**.

---

## 1h. Loop lab 2026-08-04 — freeze / handoff (iteración 7)

**Fricción:** evidencia de iters 1–6 dispersa; falta una tarjeta única de handoff que diga qué está usable y qué **no** se puede reclamar.

**Control:** ¿congelar lab usable sin campo y sin retunear ECE? **SÍ** (`lab_usable_freeze=true`).

| Claim | Valor |
|-------|-------|
| lab_usable_freeze | **true** |
| field_product / ml_product_go | **false** |
| ece_fixed | **false** |
| recommended surface | **iter1_reject_only** thr~0.80 |
| U1 IoU universal | **false** (LOFO ~0.76) |

CLI: `python -m wildfire_front ml freeze` · Runner: `scripts/run_lab_ml_loop_v34_freeze.py`  
Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_freeze_latest.json`  
Report: `docs/ML_LOOP_ITERATIONS/iter_20260804_lab_freeze.md`

**Next métrica:** solo con datos/features nuevas o LOFO Head A por fuego. El loop de producto lab queda **congelado** en esta superficie.

---

## 1g. Loop lab 2026-08-04 — risk–coverage curve (iteración 6)

**Fricción:** un solo thr no enseña el trade-off cobertura→IoU; el ranking conf existe en scorecard pero no como curva de producto.

**Control:** ¿productizar curva selectiva + thr map sin retunear ECE? **SÍ.**

| Punto TEST | Valor |
|------------|------:|
| full mean IoU | **0.857** |
| selective IoU @80% | **0.903** (lift **+0.047**) |
| ranking useful @80 | **true** |
| thr default 0.35 abstain | **~0** (nunca rechaza) |
| thr locked ~0.80 abstain | **0.515** · IoU acc **0.949** |

Conf band TEST: confidences ~0.74–0.81 (thr=0.35 vacío; thr lab dentro de la banda).

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_risk_curve.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_risk_curve_latest.json`
- CLI: `python -m wildfire_front ml curve`
- Runner: `python scripts/run_lab_ml_loop_v34_risk_curve.py`

**Superficie:** sigue **iter1 reject only**. Curva = mapa de operación, no nuevo thr.

---

## 1f. Loop lab 2026-08-04 — teach-cases productization (iteración 5)

**Fricción:** fail_cases + LOFO + reject existían en JSON pero no como superficie CLI/curso de 1 comando.

**Control:** ¿productizar enseñanza sin re-tunear ECE ni abrir field_ops? **SÍ.**

| Entrega | Evidencia |
|---------|-----------|
| CLI `ml cases` | offline board: reject thr, LOFO, buckets, talking points |
| Pack machine | `outputs/ml_eval/lab_loop/lab_loop_v34_teach_cases_latest.json` |
| Curso m6 | `ml cases` + buckets + LOFO vs U1 |
| Superficie | sigue **iter1 reject only** |

Buckets de enseñanza (TEST Head A indices):

| Bucket | n | Mensaje |
|--------|--:|---------|
| `accepted_low_iou` | 5 | conf alta, IoU flojo → overconfianza residual |
| `rejected_high_iou` | 5 | conf < thr, IoU alto → coste del reject thr~0.80 |

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_teach_cases.md`
- `wildfire_front/ml/lab_teach_cases.py`
- `scripts/run_lab_ml_loop_v34_teach_cases.py`
- Runner: `python scripts/run_lab_ml_loop_v34_teach_cases.py`
- CLI: `python -m wildfire_front ml cases`

**Next (solo señal nueva):** LOFO ECE con caches por fuego; o datos/features nuevas. No thrash ECE same-TEST.

---

## 1e. Loop lab 2026-08-04 — generalización LOFO + teach lock (iteración 4)

**Fricción elegida:** tras 2 ECE fails en el mismo holdout, **no** re-tunear ECE; medir **generalización multi-fuego** y **fijar superficie de enseñanza**.

**Control:** ¿tabla LOFO + recipe teach sin producto de campo? **SÍ.**

| Fuente | model_iou | vs copy Δ |
|--------|----------:|----------:|
| LOFO CARDOSO | **0.798** | +0.156 |
| LOFO LA_ESTRELLA_ACOM1 | **0.783** | +0.424 |
| LOFO LA_ESTRELLA_ACOM2 | **0.693** | +0.323 |
| **LOFO mean ± std** | **0.758 ± 0.046** | mean Δ +0.30 |
| U1 TEST mean IoU (lab holdout) | **0.857** | — (protocolo distinto) |

**Nota de generalización:** `holdout_u1_higher_than_lofo_mean` — **no** vender IoU U1 ~0.86 como universal multi-fuego. Spread LOFO ~0.10 (material).  
**Honestidad:** LOFO = leave-one-fire **mask IoU** de evals existentes; **≠** protocolo U1 Head A ECE.

**Superficie lab locked (sin cambio):** iter1 reject thr ~**0.80** · abstain ~0.52 · IoU accepted ~0.95.  
**ECE holdout:** sigue ~0.15 · stop thrash same-TEST.

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_generalization_teach.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_generalization_latest.json`
- `outputs/ml_eval/lab_loop/lab_loop_v34_latest.json` (iters 1–4)
- Runner: `python scripts/run_lab_ml_loop_v34_generalization.py`
- CLI: `python -m wildfire_front ml show` (sección LOFO)

**Next (solo si hay señal nueva):** caches Head A por fuego para LOFO ECE/reject; o features/datos nuevos. **No** más post-hoc ECE en el mismo TEST.

---

## 1d. Loop lab 2026-08-04 — re-fit logistic (iteración 3)

**Fricción residual:** ECE ~0.15 tras fallar post-hoc conf (iter2).

**Control:** re-fit logistic Head A completo en VAL + second stage VAL-outer — **SÍ intentado**.

| Metric TEST | Prod cal | Refit |
|-------------|----------:|------:|
| ECE full | **0.153** | **0.178** (Δ **+0.025** — **no mejora**) |
| reject thr (VAL) | — | ~0.78 |
| abstain @ reject | — | ~0.53 |
| IoU accepted @ reject | — | ~0.95 |

**Veredicto:** `lab_refit_recommended = **false**` · `ece_improved_on_test = false`.  
**Superficie lab recomendada sigue siendo iter1 reject** sobre calibrador de producción (no sustituir prod cal).

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_refit_logistic.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_refit_latest.json`
- `outputs/ml_eval/lab_loop/lab_loop_v34_fail_cases_test.json` (enseñanza)
- `models/clm_ensemble/uncertainty_calibration_v1_lab_refit.json` (lab only, **not recommended**)

**Conclusión de 3 iters (pre-iter4):** el gancho usable de lab es **reject thr ~0.80**; recalibrar/re-fit **no** baja ECE TEST. Iter4 cambió fricción a LOFO/teach (arriba).

---

## 1c. Loop lab 2026-08-04 — ECE recalibration (iteración 2)

**Fricción residual (Alta):** ECE full ~0.15 tras iter1 (overconfianza en banda alta).

**Control:** ¿post-hoc VAL-only sin campo? **SÍ.**

**Cambio:** temperature vs Platt vs none sobre *logits de confianza* (VAL fit); TEST frozen.

| Metric TEST | Baseline | Tuned (method=temperature) |
|-------------|----------:|---------------------------:|
| ECE full | **0.153** | **0.174** (Δ **+0.021** — **no mejora**) |
| mean conf | 0.782 | (ver JSON) |

**Veredicto honesto:** `ece_improved_on_test = **false**`.  
VAL eligió temperature que **no generaliza** a TEST ECE. **No se promueve** la etapa ECE como mejora de calibración global.

**Sí se mantiene de iter1:** reject surface (abstain ~0.5, IoU aceptados ~0.95).  
Combinado post-ECE: abstain ~0.53, IoU aceptados ~0.95, ECE full no mejor.

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_ece_recalibration.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_ece_latest.json`
- `outputs/ml_eval/lab_loop/lab_loop_v34_latest.json` (puntero combinado)
- `models/clm_ensemble/uncertainty_calibration_v1_lab_ece.json` (lab only; ECE stage **not** claimed better on TEST)

**Next loop:** LOFO ECE/reject (generalización) o re-fit logistic Head A en VAL (más pesado).

---

## 1b. Loop lab 2026-08-04 — reject surface (iteración 1)

**Fricción elegida (Alta):** ECE ~0.15 + `abstain_rate≈0` con thr=0.35 (rechazo de máscara invisible).

**Control question:** ¿mejorable con métricas honestas sin producto de campo? **SÍ.**

**Cambio mínimo (VAL-only):** grid de `abstain_threshold` en banda real de confianza (~0.74–0.81) + temperatura post-hoc de confidencia.

| Metric (TEST frozen) | Baseline thr=0.35 | Lab reject thr≈0.795 |
|----------------------|-------------------:|---------------------:|
| abstain_rate | **0.00** | **0.515** |
| mean_iou_accepted | 0.857 | **0.949** (+0.09) |
| ECE full | 0.153 | 0.153 (sin cambio) |
| ECE accepted | — | puede **empeorar** (banda alta sigue overconfident) — **honesto** |

**Veredicto:** `lab_reject_surface_improved=true` para research_open/lab (ABSTAIN de máscara visible + IoU en aceptados).  
**No es promote de campo.** `ml_product_go=false` · field_ops fusion **OFF**.

Artefactos:

- `docs/ML_LOOP_ITERATIONS/iter_20260804_reject_calibration.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_reject_latest.json`
- `models/clm_ensemble/uncertainty_calibration_v1_lab_reject.json` (lab only)
- CLI: `python -m wildfire_front ml show` (sección lab loop)
- Runner: `python scripts/run_lab_ml_loop_v34_reject.py --write-lab-calibrator`

**Hallazgo de producto:** las confidencias Head A están en un rango estrecho (~0.74–0.81); thr=0.35 **nunca** rechaza. El “ABSTAIN de máscara” requiere thr en esa banda.

---

## 2. Objetivos de producto (“usable lab product”)

**Sí (lab product usable):**

1. Superficie CLI única: `wildfire-front ml …` (list / show / predict / card / doctor).
2. Scorecard y rails legibles offline sin pesos `.pt`.
3. Camino 5 minutos: list → show → card offline → contrast `research_open` vs `field_ops`.
4. Predict/card con mensaje claro (exit 1) si faltan pesos — sin traceback.
5. Docs de entrada + cheatsheet + tests de contrato CLI.
6. Honestidad dual-product en todo banner/help: **lab · not field_ops fusion · IoU ≠ ROS**.

**No (fuera de scope):**

- Fusión `field_ops` ON  
- Reclamar `ml_product_go=true` sin promote + evidencia  
- Retrain Kaggle / reabrir G1 NDWS como primary  
- Hellín ops / H1 demo tercero  
- Inventar métricas o IoU como ROS  

---

## 3. Roadmap 2 semanas (IDs M-P0 … M-P5)

| ID | Entrega | Done when |
|----|---------|-----------|
| **M-P0** | Plan + status JSON + rails documentados | Este doc + `PLAN_ML_PRODUCT_STATUS.json` |
| **M-P1** | CLI `wildfire-front ml` (list/show/predict/card/doctor) | Help + offline list/show/doctor; predict/card fail clean |
| **M-P2** | Scorecard productization (`ml show` + `--json`) | Lee scorecard + promote + catalog + field_ops flag |
| **M-P3** | Docs entry (START_HERE ML, CURSO m6, cheatsheet) | 5-min path copy-paste |
| **M-P4** | Tests `tests/test_cli_ml_product.py` | list/show/doctor/card offline; never fusion ON |
| **M-P5** | Hygiene (PROJECT_STATUS, CHANGELOG, plan graph link) | Unreleased bullet + status link |

Cadencia sugerida: M-P0–P2 día 1–3 · M-P3–P4 día 3–7 · M-P5 + polish día 7–14.

---

## 4. Kill list (no negociable)

| Prohibido | Por qué |
|-----------|---------|
| `field_ops.allow_ml_live_in_fusion = true` | Tactical fusion no es claim lab; rail de producto |
| IoU como ROS / Vp / m·min⁻¹ | Dual product: máscara lab ≠ frente térmico |
| Catalog **0.8963** como certeza live | Provenance holdout only |
| `ml_product_go=true` sin promote humano | Checklist + script; nunca auto-flip |
| Retrain / G1 reopen sin datos nuevos | No horas de retrain en este mes sin señal |
| Mezclar Tobarra ROS con scorecard U1 | Claims distintos, docs distintos |

---

## 5. Acceptance — “ML product usable”

Checklist (todas deben ser **true** para declarar usable lab product).
Aligned with `docs/PLAN_ML_PRODUCT_STATUS.json` → `acceptance_ml_product_usable` (2026-08-04):

- [x] `wildfire-front ml list` exit 0; muestra `clm_ensemble_v34` default + `not_for`
- [x] `wildfire-front ml show` / `--json`: `ml_product_go=false`, field_ops fusion **OFF**, U1 IoU/ECE visibles
- [x] `wildfire-front ml doctor` exit 0; reporta MISSING weights honestamente si faltan
- [x] `wildfire-front ml card --mode offline --scenario hold` produce card (o skip graceful)
- [x] `wildfire-front ml predict` sin pesos → exit 1 + mensaje, no traceback
- [x] Help/epilog: **lab product · not field_ops fusion · IoU ≠ ROS**
- [x] `tests/test_cli_ml_product.py` verde; **nunca** assert fusion ON en field_ops
- [x] Docs: `ML_PRODUCT_START_HERE.md` + link en START_HERE + CURSO m6

**No** forma parte del acceptance: `ml_product_go=true`, field_ops fusion ON, retrain.

---

## 6. Commands cheatsheet

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# Offline (sin pesos)
python -m wildfire_front ml list
python -m wildfire_front ml show
python -m wildfire_front ml show --json
python -m wildfire_front ml doctor
python -m wildfire_front ml card --mode offline --scenario hold
python -m wildfire_front ml card --mode offline --scenario abstain

# Con pesos (si models/**/*.pt presentes)
python -m wildfire_front ml predict --list-products
python -m wildfire_front ml predict --product clm_ensemble_v34 --npz path\to\patch.npz

# Contraste políticas (no fusion field_ops)
python -m wildfire_front decide --policy research_open --explain
python -m wildfire_front decide --policy field_ops --explain

# Scripts legacy (siguen válidos)
python scripts\predict_spread.py --list-products
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold

# Tests
pytest tests\test_cli_ml_product.py -q
```

Entrada 5 min: [`docs/ML_PRODUCT_START_HERE.md`](ML_PRODUCT_START_HERE.md)  
Cheatsheet 1 página: [`docs/CHEATSHEET_ML_LAB.md`](CHEATSHEET_ML_LAB.md)

---

## 7. Enlaces

| Asset | Path |
|-------|------|
| Scorecard lab | `docs/ML_PRODUCT_SCORECARD.json` |
| Promote record | `docs/ML_U1_PROMOTE_RECORD.json` |
| Catalog | `models/catalog.json` |
| Policies | `config/decision_policies.json` |
| IoU ≠ ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| ML rails loop | `docs/ML_LOOP_RAILS.md` |
| Project status | `docs/PROJECT_STATUS.md` |
| Plan graph v6 | `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` |
