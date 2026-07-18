# Models

## Production (use these)

| Path | Role |
|------|------|
| `unet_model.py` | U-Net architecture for next-day spread |
| `catalog.json` | Product catalog (v21 production, CLM specialist, ensemble) |
| `production/` | v21 weights manifest / export metadata |
| `clm_specialist/` | CLM specialist manifest |
| `clm_ensemble/` | Loop champion ensemble recipe + manifest |

Weights (`.pt`) are gitignored; install via `scripts/install_production_weights.py`
or `scripts/install_dual_weights.py` when available.

## Legacy (do not use for product)

| Path | Role |
|------|------|
| `model.py` | **LEGACY A3C-LSTM** — kept for old tests / fine-tune path only |
| `config.json` | A3C hyperparams |

Predict with: `python scripts/predict_spread.py --list-products`
