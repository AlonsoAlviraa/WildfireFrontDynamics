# ML lab — qué está probado y cómo

> **Cierre formal:** 2026-08-10 · `FREEZE_ML_AND_REQUEST_DATA`  
> **Rails:** lab only · `ml_product_go` true · **field fusion OFF** · residual-small · IoU ≠ ROS  

Este directorio documenta el **camino probado**. Los números canónicos viven en  
`outputs/ml_eval/canonical/` (local) y en los boards citados.

---

## 1. Tres tracks (no mezclar)

| Track | Qué es | Campeón congelado |
|-------|--------|-------------------|
| **A. Sealed LOFO** | legacy17, recipe `exact_force_ema_long`, residual-small | mean **0.7878** · min **0.7071** |
| **B. Spatial weather** | spatial_v1 + ERA5-Land + bridge init | **era5_long** mean **0.5762** (Δ vs W0 **+0.019**) |
| **C. Schema bridge** | physics14 proyectado (pack pequeño) | research only (~0.68); **no product** |

Un IoU de schema o spatial **no** sustituye sealed product LOFO.

---

## 2. Cómo se probó (método)

1. **LOFO residual-small** en Kaggle (T4), recipe sellada o spatial bridge.  
2. **Leak audit** = 0 en packs de datos (p.ej. LOFO v4).  
3. **Ablaciones weather** vs baseline spatial W0 (mean 0.5576):
   - Open-Meteo → **REGRESSION** (−0.024)
   - ERA5 short → NULL débil (+0.008)
   - ERA5 long → **LIFT** (+0.019)
   - Multi-fire spatial fill → REGRESSION
   - Finetune from long → peor que long (−0.014)
4. **Data levers** (v3 hellin, v4 Cardoso extra): Hellín held ayuda; core3 sealed **no** mejoró con v4.  
5. **Cierre:** thrash de recipe en corpus actual **congelado**; siguiente EV = datos chain_honest.

Criterio de cierre: `docs/GOAL_ML_CLOSEOUT.md`  
Decisión: `outputs/ml_eval/canonical/ML_CLOSEOUT_DECISION.json`  
Auditoría: `outputs/ml_eval/canonical/AUDIT_GOAL_ML_SESSION_2026_08.md`

---

## 3. Qué NO reabrir (kill list)

- Open-Meteo como weather principal  
- Multi-fire spatial (hellin+braz) sin runner limpio + QA  
- Finetune full core3 desde long sin kill de no-regresión  
- ECE/logistic same-holdout thrash  
- Tobarra KEEP reopen  
- Larger U-Net thrash  
- Hparam grid sealed sin datos nuevos  
- Goal “+0.05 mean” thrash en corpus actual  

---

## 4. Archivos canónicos (local)

```text
outputs/ml_eval/canonical/
  ML_CLOSEOUT_DECISION.json
  ML_CLOSEOUT_CHECKER.json
  CHAMPION_SEALED_exact_force_ema_long.json
  CHAMPION_WEATHER_era5_long_board.json
  weather_era5_status.json          # ERA5_READY 7/7
  tobarra_keep_or_kill_scorecard.json
  AUDIT_GOAL_ML_SESSION_2026_08.md
```

Boards Kaggle completos (descargas): `outputs/kaggle_exact_force_ema/`, `outputs/kaggle_spatial_era5_long/`, etc.

---

## 5. CLI lab

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front ml list
python -m wildfire_front ml doctor
python -m wildfire_front ml freeze
```

Documentación CLI: `docs/ML_PRODUCT_START_HERE.md` (si existe) / `docs/GUIA_COMANDOS_RECREAR_TODO.md`.

---

## 6. Siguiente cola (post-freeze)

| Prioridad | Acción |
|-----------|--------|
| **Datos** | IF multi-día chain_honest, FOV alineado, timestamps para ERA5 |
| **No** | Otro kernel sealed hparam en el mismo corpus |
| **Producto** | H1 demo humano (GO_Q); fusion field solo con promote |
