# 🏗️ ARCHITECTURE — WildfireFrontDynamics

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                │
│  NDWS TFRecords (train/val/test) → NpzWildfireDataset       │
│  Real GeoTIFF (Tobarra) → WildfireDataset (30×30 patches)   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    MODEL LAYER                               │
│                                                              │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │ A3C_PerCellModel    │    │ WildfireUNetSmall (NEW)     │ │
│  │ (legacy, bs=1)      │    │ batch_size=32, 4.3M params  │ │
│  │ models/model.py     │    │ models/unet_model.py        │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    TRAINING LAYER                            │
│  wildfire_front/ml/train.py     → Loss functions (focal BCE)│
│  wildfire_front/ml/dataset.py   → Data loading + augment    │
│  wildfire_front/ml/physics.py   → Rothermel ROS physics loss│
│  kaggle_job/run_mega_training.py → A3C pipeline (Kaggle GPU)│
│  kaggle_job/run_unet_training_v13.py → U-Net pipeline       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    EVALUATION LAYER                          │
│  wildfire_front/evaluation.py  → IoU, Recall, Precision     │
│  wildfire_front/quality.py     → Quality checks             │
│  scripts/archive/analyze_training_curves.py → Legacy plots  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    INFERENCE LAYER                           │
│  wildfire_front/cli.py         → Command-line interface     │
│  wildfire_front/real_if.py     → Real fire ingestion        │
│  wildfire_front/ingestion/     → GeoTIFF pipeline           │
│  wildfire_front/geometry_speed.py → Fire front geometry     │
└─────────────────────────────────────────────────────────────┘
```

## Key Directory Structure

```
WildfireFrontDynamics/
├── wildfire_front/          # Python package (core logic)
│   ├── ml/                  # ML pipeline (train, dataset, physics, meta-labeler)
│   └── ingestion/           # GeoTIFF ingestion
├── models/                  # Model definitions
│   ├── model.py             # A3C_PerCellModel_LSTM (legacy)
│   └── unet_model.py        # WildfireUNet (new, industry standard)
├── kaggle_job/              # Kaggle training scripts
│   ├── run_mega_training.py     # A3C training (v10-v12)
│   └── run_unet_training_v13.py # U-Net training (v13+)
├── scripts/                 # Utility scripts
├── tests/                   # Test suite (38 tests)
├── docs/                    # Documentation + experiment logs
├── research/                # Academic references
├── data/                    # Real fire data (Tobarra, semireal)
└── pyproject.toml           # Python project config
```

## Data Pipeline

### Training Data (NDWS Benchmark)
```
NDWS TFRecords (15 shards)
  → preprocess_ndws.py splits: train[0-11], val[12-13], test[14]
  → NpzWildfireDataset loads .npz patches (30×30 or 64×64)
  → DataLoader with batch_size=1 (A3C) or 32 (U-Net)
```

### Real Data (Castilla-La Mancha)
```
GeoTIFF images (Tobarra LWIR)
  → prepare_real_if_geotiffs.py
  → WildfireDataset (patches of 30×30)
  → Fine-tuning on best NDWS checkpoint
```

## Model Comparison

| Aspect | A3C-LSTM (v10-v12) | U-Net (v13+) |
|---|---|---|
| Architecture | Per-cell iteration | Encoder-decoder |
| Batch size | **1** (forced) | **32** (native) |
| Parameters | ~2.5M | 4.3M |
| Patch size | 30×30 | 30×30 (64×64 planned) |
| Forward pass | Cell-by-cell loop | Single convolution |
| Best IoU achieved | 0.035 (v11) | Pending (v13b) |
| Industry standard | ❌ | ✅ (NDWS paper) |

## Kaggle Training Infrastructure

- **Account:** `alonsoalviraaaa` (university)
- **GPU:** Tesla P100 16GB (sm_60 — needs PyTorch ≤2.1.x)
- **Dataset:** `fantineh/next-day-wildfire-spread` (public)
- **Budget:** 30 GPU-hours/week
- **Typical run:** ~2-4 hours per experiment

## Evaluation Protocol (Leak-Free)

```
1. Train on NDWS train shards [0-11]
2. Validate on NDWS val shards [12-13] → model selection
3. Test on NDWS test shard [14] → ONE evaluation (honest metrics)
4. Meta-labeler: trained on VAL predictions, evaluated on TEST
```

## Dependencies

- **Python 3.11+**
- **PyTorch** (≤2.1.x for P100 compatibility)
- **NumPy, rasterio, scikit-learn, matplotlib**
- **Kaggle CLI** (for remote training)