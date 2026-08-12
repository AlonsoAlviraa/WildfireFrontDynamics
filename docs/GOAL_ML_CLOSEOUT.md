# Goal: cierre de ML lab (freeze / más datos / techo)

**Schema:** `wfd_goal_ml_closeout_v1`  
**Rails:** lab only · `ml_product_go` true · field fusion OFF · residual-small · IoU ≠ ROS · no Tobarra KEEP thrash · no larger-UNet thrash  

## Objetivo

Producir **una decisión de cierre verificable** entre tres salidas (no “seguir iterando sin techo”):

| Código | Significado |
|--------|-------------|
| **FREEZE_ML** | Se congela entrenamiento/recipe en el corpus actual; champions sellados; no thrash. |
| **REQUEST_MORE_DATA** | El techo de *train thrash* está; el único EV residual es **datos nuevos honestos**. |
| **CEILING_REACHED** | Techo de performance en el board comparable: ni recipe ni datos plausibles en el horizonte actual suben mean de forma honesta. |

La decisión puede ser **compuesta** (recomendado):

- `FREEZE_ML` + `REQUEST_MORE_DATA` → “paramos thrash; pedimos fuegos”
- `FREEZE_ML` + `CEILING_REACHED` → “paramos thrash y no esperamos lift mean sin cambio de clase de problema”
- Nunca: thrash + “más datos” sin freeze (doble gasto)

## Criterio hard (goal met)

El goal está **met** cuando existe un stamp JSON:

`outputs/ml_eval/lab_loop/ML_CLOSEOUT_DECISION.json`

con:

1. `decision` ∈ {`FREEZE_ML_AND_REQUEST_DATA`, `FREEZE_ML_CEILING`, `FREEZE_ML_ONLY`}  
2. `evidence` con boards citados (paths + means)  
3. `kill_list` de runs/paths sellados (no reabrir)  
4. `champions` freeze (sealed + weather spatial)  
5. `rails` fusion OFF  
6. Checker: no claim de sealed mean +0.05 sin board; no mezclar tracks  

## Reglas de decisión (deterministas)

### A) ¿FREEZE_ML training?

**TRUE** si **todas** se cumplen:

1. Campeón sealed documentado (`exact_force_ema_long` o sucesor con mean/min en stamp).  
2. ≥ 2 levers no thrash fallaron o flat en sealed/data (p.ej. LOFO v3/v4 data, recover, specialist sin batir sealed min).  
3. Weather ablation honest: best Δmean vs W0 conocido; thrash weather muertos (Open-Meteo REG, MF REG, finetune &lt; parent).  
4. No hay lever abierto de **recipe residual-small** con kill criterion no ejecutado.

### B) ¿REQUEST_MORE_DATA?

**TRUE** si FREEZE_ML y **alguna**:

1. Hellín-style: un held geográfico nuevo mejoró held IoU de forma grande (evidencia v3 hellin lift).  
2. Corpus core3 sigue siendo 3 fuegos familiares + externos limitados.  
3. Existe backlog de IF multi-día **chain_honest** no ingeridos (no FOV thrash, no press-only).  

**FALSE** (no pedir datos genéricos) si el único backlog es Tobarra KEEP, FOV basura, o weather parcial.

### C) ¿CEILING_REACHED (mean product path)?

**TRUE** si FREEZE_ML y:

1. Goal mean +0.05 en sealed es irreal en residual-small (headroom teórico pero historial de meseta).  
2. Best weather lift << +0.05 (p.ej. +0.019).  
3. Data lever en corpus actual no subió sealed mean.  

**Nota:** CEILING no niega `ml_product_go` lab ni el valor de ERA5; niega “otro kernel nos da +0.05 mean sealed”.

## Champions a congelar (si FREEZE_ML)

| Rol | Config | Mean | Min | Board |
|-----|--------|------|-----|-------|
| Product LOFO sealed | `exact_force_ema_long` residual-small multi_if | 0.7878 | 0.7071 | `HISTORIC_CHAMPION_exact_force_ema_long.json` |
| Weather spatial lab | `era5_long` residual-small bridge init | 0.5762 | 0.5260 | `spatial_v1_era5_long_board.json` |

**No freeze / no promote:** openmeteo, era5_mf, era5_finetune, lofo_v4 como “mejor que sealed”.

## Kill list (no reabrir sin new evidence class)

- Open-Meteo weather as primary path  
- Multi-fire spatial pack (hellin+braz) sin runner limpio + QA  
- Finetune full-core3 from long without non-regression kill  
- Same-holdout ECE / logistic refit thrash  
- Tobarra KEEP reopen  
- Larger U-Net default thrash  
- Hparam grid on sealed residual-small without new data  

## Salidas del checker

```
met = true  iff ML_CLOSEOUT_DECISION.json exists and is consistent with rules A–C
```

Si `decision = FREEZE_ML_AND_REQUEST_DATA`, el “trabajo ML thrash” está finalizado; el proyecto no está “muerto”, solo cambia de cola a **intake de datos**.
