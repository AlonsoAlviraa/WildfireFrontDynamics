# Producto dual — NDWS v21 + CLM v28

## Qué hay

| Producto | ID CLI | Dominio | Métricas clave |
|----------|--------|---------|----------------|
| **NDWS global** | `ndws_v21` | Next-day patches Google NDWS | IoU **0.226**, Δ copy **+0.076** |
| **CLM España** | `clm_v28` | Holdout incendios CLM | IoU **0.838**, Δ copy **+0.196** (test holdout) |
| **CLM ensemble** | `clm_ensemble_v30` | Soft-vote **v28 + EMA + multi-IF** (~0.30/0.27/0.43) | IoU **0.895**, Δ **+0.253** (loop r8 transfer mix; honest) |
| **Ops frente** | (no ML) | Secuencias LWIR reales | ROS multi-estimador (`front_dynamics_v1`) |

**v30 (2026-07-17):** G1 NDWS features/temporal sigue KILL. Nuevo campeón ML CLM = ensemble honesto (`docs/V30_ML_SCORECARD.json`). Inferencia ensemble: `python scripts/eval_clm_ensemble.py`.

**No mezclar:** ROS de dron ≠ predicción NDWS ≠ specialist CLM.

Smoke local (2026-07-15): `clm_v28` en 20 parches holdout test → mean IoU **0.713**, Δ copy **+0.160**.

## CLI

```bash
# Inventario + readiness (manifest + pesos)
python scripts/predict_spread.py --list-products

# Asegurar pesos single-model en models/
python scripts/install_dual_weights.py

# CLM ensemble v30 (default emergency product — soft-vote v28 + LOFO-CARDOSO)
python scripts/predict_spread.py --product clm_ensemble_v30 \
  --npz artifacts/clm_ndws_patches/holdout_v1/test \
  --eval --max-patches 50

# CLM single specialist
python scripts/predict_spread.py --product clm_v28 \
  --npz artifacts/clm_ndws_patches/holdout_v1/test \
  --eval --max-patches 50

# NDWS research
python scripts/predict_spread.py --product ndws_v21 --npz path/patch.npz --output pred.npz
```

## Rutas

| | NDWS | CLM |
|--|------|-----|
| Manifest | `models/production/manifest.json` | `models/clm_specialist/manifest.json` |
| Pesos | `models/production/weights_v21_best.pt` | `models/clm_specialist/weights_v28_clm_ft.pt` |
| Catálogo | `models/catalog.json` | |
| Código catálogo | `wildfire_front/ml/product_catalog.py` | |

## Cuándo usar cada uno

- **ndws_v21:** investigación / parches NDWS-like globales (protocolo any_fire legacy17).
- **clm_v28:** parches schema legacy17 de incendios CLM (mismo preproceso holdout_v1).
- **front_dynamics / observatorio packs:** velocidades y frentes desde GeoTIFF LWIR (ops). **No es un producto ML.**

## Gates

| Gate | Producto | Estado |
|------|----------|--------|
| G0 | ndws_v21 | GO (baseline IoU 0.226 / Δ +0.076) |
| G1 | NDWS ≥0.25 / +0.09 | **OPEN** — v25/v26 features NO_PROMOTE; v27 temporal T=2 en curso |
| G2 | clm_v28 holdout test | **GO** (Δ +0.196) |

**v26 physics15 (cerrado):** IoU 0.221 / Δ +0.071 → no sustituye a `ndws_v21`.