# ML product — empieza aquí (5 minutos)

> **Lab product · not field_ops fusion · IoU ≠ ROS**  
> Default: `clm_ensemble_v34` · fallback `clm_v28` · research `ndws_v21` (no primary)  
> `ml_product_go=false` · field_ops fusion **OFF** · catalog **0.8963** = provenance only  
> **As of 2026-08-05:** lab loop freeze **DONE** · W3 multi-fire **MET** · Tobarra KEEP claim **KILL**  
> Snapshot: `docs/CURRENT_STATE.md` · Goals: `docs/goals/README.md`

## Camino 5 minutos

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# 1) Qué productos hay
python -m wildfire_front ml list

# 2) Scorecard U1 + rails (offline, sin pesos)
python -m wildfire_front ml show
python -m wildfire_front ml show --json

# 3) Teach fail buckets + LOFO (offline)
python -m wildfire_front ml cases

# 3b) Risk–coverage curve + thr map (offline)
python -m wildfire_front ml curve

# 3c) Freeze / handoff card (lab_usable ≠ field promote)
python -m wildfire_front ml freeze

# 3d) Post-freeze smoke (regression gate)
python -m wildfire_front ml smoke

# 3e) Multi-fire LOFO board (mask IoU ≠ U1 ECE)
python -m wildfire_front ml lofo

# 3f) Next-signal readiness (W1 Head A LOFO path)
python -m wildfire_front ml next

# 4) Card offline (HOLD / ABSTAIN demos)
python -m wildfire_front ml card --mode offline --scenario hold
python -m wildfire_front ml card --mode offline --scenario abstain

# 5) Contraste políticas (research_open experimental vs field_ops estricto)
python -m wildfire_front decide --policy research_open --explain
python -m wildfire_front decide --policy field_ops --explain

# 6) Doctor (weights MISSING = informe honesto, no crash)
python -m wildfire_front ml doctor
```

## Qué mirar en `ml show`

| Campo | Valor típico | Cómo enseñarlo |
|-------|--------------|----------------|
| U1 mean IoU | ~**0.86** | lab TEST eval |
| Selective@80 | ~**0.90** | lab |
| ECE | ~**0.15** | calibración imperfecta |
| Catalog holdout | **0.8963** | **provenance only** |
| `ml_product_go` | **false** | no producto campo |
| Lab reject thr | ~**0.80** (lab loop) | ABSTAIN de máscara; IoU aceptados ~0.95; **no** es campo |
| LOFO mean IoU | ~**0.76** (n=3) | multi-fuego; **≠** U1 0.86; no universalizar holdout |
| Selective@80 IoU | ~**0.90** | ranking conf; ver `ml curve` |
| field_ops fusion | **OFF** | rail no negociable |

Tras lab loop, `ml show` incluye **Lab loop reject surface** + **LOFO generalization**.  
`ml cases` productiza fail buckets; `ml curve` la curva cobertura→IoU y thr map.  
`ml freeze` consolida handoff: **lab_usable_freeze=true** · **ml_product_go=false** · field OFF.  
Superficie recomendada: **iter1 reject only** (ECE post-hoc/refit no mejoraron TEST).

### Mega goals lab (cerrados)

| Goal | Resultado |
|------|-----------|
| W3 new fires + protocol | **MET** — Hellín/Brazatortas/Retuerta Head A thr=0.795 |
| Tobarra fresh LOFO KEEP-or-KILL | **KILL** — test IoU **0.4776** · K1 fail vs Head A **0.489** · leak 0 |

No reabrir Tobarra KEEP con la misma receta sin señal nueva. Boards: `docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md`.

## Predict (si hay pesos)

```powershell
python -m wildfire_front ml predict --list-products
python -m wildfire_front ml predict --product clm_ensemble_v34 --npz path\to\patch.npz
# sin pesos → exit 1 + mensaje claro (no traceback)
```

Legacy: `python scripts\predict_spread.py --list-products`  
Card script: `python scripts\run_ml_live_card_demo.py --mode offline --scenario hold`

## Frases anti-error

1. **IoU ≠ ROS** — solape de máscara lab, no m/min del frente.  
2. **0.8963** no es certeza live.  
3. **field_ops fusion OFF** aunque research_open sea experimental.  
4. **`ml_product_go` false** hasta promote humano.

## Docs

| Doc | Uso |
|-----|-----|
| [`PLAN_ML_PRODUCT_USABLE.md`](PLAN_ML_PRODUCT_USABLE.md) | Plan 2 semanas M-P0…M-P5 |
| [`CHEATSHEET_ML_LAB.md`](CHEATSHEET_ML_LAB.md) | 1 página comandos |
| [`ML_PRODUCT_SCORECARD.json`](ML_PRODUCT_SCORECARD.json) | Lab claim surface |
| [`METRICS_HONESTY_IOU_NE_ROS.md`](METRICS_HONESTY_IOU_NE_ROS.md) | Dual product |
| [`START_HERE.md`](START_HERE.md) | Repo general |
