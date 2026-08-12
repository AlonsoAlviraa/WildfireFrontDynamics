# ML LEAP — E1b selective risk–coverage + FNR@budget

> **As of:** 2026-08-12  
> **Plan:** `docs/PLAN_ML_LEAP_2026-08-12.md` (pack E1b)  
> **Product:** `clm_ensemble_v34` · protocol `clm_holdout_test_seed42_v1`  
> **Rails:** FREEZE_ML · fusion OFF · IoU ≠ ROS · no despacho táctico  
> **Claims:** `docs/CLAIM_BOARD_ML_LEAP_2026-08-12.md` (L1–L8)  
> **Sealed card:** `docs/ML_PRODUCT_SCORECARD.json`  
> **Helpers:** `patch_miss_rate_at_coverage` · `fnr_proxy_at_budget` in `wildfire_front/ml/reliability_metrics.py`

Nota de **método** (0 GPU). No retrain. No scorecard nuevo. No flip de gates.

---

## Qué es (y qué no)

Selective risk–coverage = ranking skill: si el Decision Card **se calla** en la cola de baja confianza, ¿sube el IoU de lo que queda?  
FNR@budget aquí es un **proxy de laboratorio a nivel parche** (miss rate en el conjunto llamado). **No** es FNR píxel de mapas peer, **no** es ROS, **no** es despacho.

El Card puede **GO / HOLD / ABSTAIN**. Ninguno de esos actos es orden táctica.

---

## Claim board (enforce L1–L8)

| ID | En esta nota | Sell |
|----|--------------|------|
| **L1** | Selective@80 sealed beats shuffle-conf; ECE~0.15 → ABSTAIN when weak | YES-with-scorecard (honesty) |
| **L2** | Peer next-day = multi-day + LOYO/LOFO + AP/growth | **NO** as WFD SOTA |
| **L3** | CRC/FNR control exists in literature; arch ≠ safety | **NO** (method only) |
| **L4** | Catalog 0.8963 / IoU~0.86 = live or ROS | **contradicted — NO** |
| **L5** | Transformer/FireCast = LEAP under FREEZE | **contradicted — NO** |
| **L6** | WFD meets peer FNR≤α or ROS-class ±35% | **NO** until dedicated scorecard |
| **L7** | Multi-CCAA / all-year from current LOFO | **NO** until scorecard |
| **L8** | field_ops fusion ON / GO_MES+ from U1 lab | **NO** |

---

## Grid de cobertura @50 / @80 / @90

Usar `selective_iou_at_coverage` + `selective_beats_random` (`null_kind=shuffle_conf`) + `patch_miss_rate_at_coverage` (`tau=0.5`).

| Coverage | Selective IoU | Δ vs shuffle-conf | beats_random (δ=0.01) | miss_rate (IoU&lt;0.5) |
|----------|---------------|-------------------|-----------------------|------------------------|
| **50%** | **not run** | **not run** | **not run** | **not run** |
| **80%** | **~0.903** (sealed) | **~0.047** | **true** | **not in sealed card** |
| **90%** | **not run** | **not run** | **not run** | **not run** |

Sealed @80 (n=200 TEST, cal VAL-frozen):

- `uncertainty.selective_iou_at_80pct_coverage` ≈ **0.903**
- `uncertainty.selective_iou_random_baseline_80` ≈ **0.857** (shuffle-conf mean)
- `uncertainty.delta_vs_random` ≈ **0.047**
- `uncertainty.ece_patch_conf` ≈ **0.153**
- `primary.model_iou` ≈ **0.857** (full coverage)

`uncertainty.abstain_rate == 0.0` en la card **no** es el 20% de cola; no confundir con budget=0.20.

**Prohibido** rellenar @50/@90 o FNR numérico sin un run E1 TEST (`docs/ML_LEAP_EVAL_ONESHOT.md`) + drift note. SKIP sin weights ≠ curva verde.

---

## Cómo computar (0 GPU; arrays U1)

Tras E1 con weights (o en unit test sintético):

```python
from wildfire_front.ml.reliability_metrics import (
    selective_iou_at_coverage,
    selective_beats_random,
    patch_miss_rate_at_coverage,
    fnr_proxy_at_budget,
)

COVERAGES = (0.50, 0.80, 0.90)
for c in COVERAGES:
    sel = selective_iou_at_coverage(ious, confs, coverage=c)
    util = selective_beats_random(ious, confs, coverage=c, n_trials=50, seed=42)
    miss = patch_miss_rate_at_coverage(ious, confs, coverage=c, tau=0.5)
    # record sel["selective_iou"], util["delta_vs_random"], util["beats_random"], miss["miss_rate"]
    # do not overwrite docs/ML_PRODUCT_SCORECARD.json
```

Null por defecto = **shuffle de confidences** (U1b). No uses el subset aleatorio como claim sellable salvo nota.

---

## FNR@budget (proxy lab)

| Símbolo | Definición honesta |
|---------|-------------------|
| **budget b** | Fracción ABSTAIN = cola de **menor** confianza |
| **coverage c = 1 − b** | Parches que el Card **puede** llamar (GO/HOLD candidatos) |
| **fnr_proxy** | `mean(IoU < 0.5)` en el conjunto llamado = `fnr_proxy_at_budget(..., budget=b, tau=0.5)` |

Ejemplos de budget (método; números **not run** salvo que E1 los mida):

| budget b | coverage | Acto de cola | FNR proxy |
|----------|----------|--------------|-----------|
| 0.50 | 50% | ABSTAIN 50% más débil | **not run** |
| 0.20 | 80% | ABSTAIN 20% más débil | **not run** (sel IoU @80 sealed; miss_rate no está en la card) |
| 0.10 | 90% | ABSTAIN 10% más débil | **not run** |

Esto **no** es:

- FNR píxel (fuego presente predicho como no-fuego)
- CRC peer / FNR≤α (L6)
- “si abstienes 20% del incendio el frente es 0.90”

L1 solo autoriza: *ranking @80 gana al azar en TEST sellado; si la cola es débil, cállate*.

---

## Mapa → GO / HOLD / ABSTAIN (no despacho)

Reglas **cualitativas** (no son gates de producto; no flipan GO_Q / fusion / GO_MES+):

| Condición lab (TEST + cal frozen) | Decision Card | Nunca |
|-----------------------------------|---------------|-------|
| No `beats_random` **o** ECE alto y miss_rate no medido / alto **o** identity cal | **ABSTAIN** | Inventar GO |
| `beats_random` pero miss_rate alto o fuentes débiles | **HOLD** | Despacho / ROS |
| `beats_random` y miss_rate aceptable **y** política lo permite | **GO** = apoyo a decisión | field_ops fusion ON · táctico |

`field_ops` sigue **más estricto** (`config/decision_policies.json`). Lab `research_open` no es sala.

IoU / selective / FNR_proxy **≠** Vp / ROS / ha.

---

## Vanity kill (esta nota)

- Catalog **0.8963** como certeza live o ROS (L4)
- Inventar @50/@90 o FNR peer (L6)
- “Transformer = leap” bajo FREEZE (L5)
- Fusion ON / GO_MES+ desde U1 (L8)
- Nested VAL ECE ~0.058 como cal de campo
- Rellenar Hellín `confirmed`

---

## Tras un E1 TEST real (no este PR)

Plantilla ( commitear bajo `outputs/ml_eval/` o cuerpo de PR; **no** pisa el scorecard sellado):

```
E1b <date>: cov50 IoU=… Δ=… miss=… | cov80 IoU=… Δ=… miss=… | cov90 IoU=… Δ=…
fnr_proxy@b0.50=… @b0.20=… @b0.10=…  vs sealed sel@80=0.903 Δ=0.047
(no L6; no ROS; no stamp overwrite)
```

Si no hay weights/NPZ: `E1b SKIP: no weights — not honesty green`.

---

## Non-goals

- Retrain / v35 / Swin / FireCast  
- Refit cal en TEST  
- P1 latencia (pack aparte; no inventar p95)  
- M1 / lift FREEZE  
- Promote Hellín  

---

## Verificación E1b (eng)

```bash
python scripts/check_release_flags.py
# expect PASS; GO_Q partial; fusion OFF
pytest tests/test_ml_leap_e1b.py tests/test_ml_leap_request_data.py tests/test_data_anchor_honesty.py -q
```
