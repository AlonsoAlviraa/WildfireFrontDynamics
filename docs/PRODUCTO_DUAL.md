# Producto dual — Ops + ML

## Qué hay

| Producto | ID CLI | Dominio | Métricas clave |
|----------|--------|---------|----------------|
| **NDWS global** | `ndws_v21` | Next-day patches Google NDWS | IoU **0.226**, Δ copy **+0.076** |
| **CLM España** | `clm_v28` | Holdout incendios CLM | IoU **0.838**, Δ copy **+0.196** |
| **CLM ensemble** | **`clm_ensemble_v34`** | Soft-vote v28+EMA+multi_if + temps VAL | U1 TEST honest ~**0.86** IoU / ECE ~**0.15** (lab pitch); catalog holdout **0.8963** provenance only — not live certainty · not ROS |
| **Ops frente** | (no ML) | Secuencias LWIR reales | ROS multi-estimador (`front_dynamics_v1`) |
| **Incident live** | `incident_*` | Inbox LWIR → outbox | `incident_runtime_v1` |

**Alias:** `clm_ensemble_v30` apunta al mismo manifest/pesos que v34 (compat CLI).

**No mezclar:** ROS de dron ≠ predicción NDWS/CLM.

## CLI

```bash
python scripts/predict_spread.py --list-products

python scripts/install_dual_weights.py

# Champion ML (v34)
python scripts/predict_spread.py --product clm_ensemble_v34 \
  --npz artifacts/clm_ndws_patches/holdout_v1/test \
  --eval --max-patches 50

# Single specialist
python scripts/predict_spread.py --product clm_v28 \
  --npz artifacts/clm_ndws_patches/holdout_v1/test \
  --eval --max-patches 50

# Demo one-shot ops + ML
python scripts/demo_dual_product.py
```

## Rutas

| | NDWS | CLM single | CLM ensemble |
|--|------|------------|--------------|
| Manifest | `models/production/manifest.json` | `models/clm_specialist/manifest.json` | `models/clm_ensemble/manifest.json` |
| Catálogo | `models/catalog.json` | | |
| Código | `wildfire_front/ml/product_catalog.py` | | |

## Gates

| Gate | Producto | Estado |
|------|----------|--------|
| G0 | ndws_v21 | GO |
| G1 | NDWS ≥0.25 / +0.09 | **KILL** (features/temporal) |
| G2 | clm_v28 holdout | GO |
| G2e | clm_ensemble_v34 | **GO** (temps VAL; no Cardoso leakage) |

Field kit ops: `docs/FIELD_KIT_INCIDENT.md`.
