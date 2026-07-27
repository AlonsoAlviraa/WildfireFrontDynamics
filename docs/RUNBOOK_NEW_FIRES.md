# Runbook: Incorporar nuevos incendios al pipeline de fine-tuning

Este documento describe el flujo end-to-end para añadir un nuevo incendio al
dataset de fine-tuning del modelo A3C-LSTM de WildfireFrontDynamics.

## 1. Requisitos de datos de entrada

Para cada nuevo incendio se necesitan:

- **Imágenes térmicas (LWIR)**: secuencia temporal de GeoTIFFs (uno por timestep).
  - Banda 1 = radiancia térmica (Kelvin o unidad comparable).
  - Sistema de referencia proyectado (UTM recomendado; el pipeline reprojecta).
  - Nombres ordenables cronológicamente (ej: `frame_001.tif`, `frame_002.tif`).
- **Polígonos de área quemada** (opcional pero recomendado):
  - Shapefile/GeoJSON con campo de timestamp o nombre que permita emparejar
    cada polígono con su frame térmico.
  - Si no hay polígonos, el script de máscaras usará umbralización térmica.

## 2. Estructura de directorios esperada

```
artifacts/
  <fire_name>_reprojected_lwir/     # imágenes térmicas reproyectadas
    frame_001.tif
    frame_002.tif
    ...
  <fire_name>_lwir_masks/           # máscaras binarias (0/1) generadas
    frame_001_mask.tif
    frame_002_mask.tif
    ...
```

## 3. Pasos del pipeline

### 3.1. Reproyectar y alinear las imágenes térmicas

Si las imágenes vienen en EPSG geográfico (4326) o con resoluciones mixtas:

```bash
set PYTHONPATH=. && python scripts\prepare_real_if_geotiffs.py ^
    --input artifacts\<fire_name>_raw_lwir ^
    --output artifacts\<fire_name>_reprojected_lwir ^
    --target-crs EPSG:32630
```

> El CRS `32630` (UTM 30N) es el usado para Tobarra. Ajustar según la zona.

### 3.2. Materializar máscaras binarias a partir de los térmicos

```bash
set PYTHONPATH=. && python scripts\materialize_lwir_masks.py ^
    --images-dir artifacts\<fire_name>_reprojected_lwir ^
    --output-dir artifacts\<fire_name>_lwir_masks ^
    --threshold 2.0
```

- `--threshold` = sigma z-score sobre el que se considera "fuego activo".
  - 2.0 es conservador (false positives bajos).
  - 1.5 es más sensible (recall más alto).
- Si se dispone de polígonos vectoriales, usar `--vectors <path>`.

Verificar el resultado:

```bash
set PYTHONPATH=. && python scripts\audit_dataset_candidate.py ^
    --images-dir artifacts\<fire_name>_reprojected_lwir ^
    --masks-dir artifacts\<fire_name>_lwir_masks
```

### 3.3. Fine-tuning (legacy A3C — archived)

> **Product path is U-Net / CLM**, not A3C-LSTM. The old smoke finetune lives under
> `scripts/archive/smoke_test_finetune.py` for forensic replay only.

```bash
# Forensic only (A3C-LSTM, not product weights)
set PYTHONPATH=. && python scripts\archive\smoke_test_finetune.py ^
    --images-dir artifacts\<fire_name>_reprojected_lwir ^
    --masks-dir artifacts\<fire_name>_lwir_masks ^
    --epochs 1 ^
    --max-patches 30
```

**Product ML validation (preferred):**

```bash
python scripts\predict_spread.py --list-products
python scripts\predict_spread.py --product clm_ensemble_v34 --help
```

### 3.4. Validación de producto (U-Net / CLM)

```bash
# Listar productos ML y smoke holdout
python scripts\predict_spread.py --list-products
set PYTHONPATH=. && python scripts\smoke_production_products.py --products clm_v28,clm_ensemble_v34 --max-patches 12

# Ops / incidente sintético
set PYTHONPATH=. && python scripts\smoke_incident_runtime.py
```

Legacy A3C qualitative compare (forensic only):

```bash
set PYTHONPATH=. && python scripts\archive\compare_base_vs_finetuned.py
```

## 4. Incorporar múltiples incendios

**Ops / packs (producto):**

1. Procesar cada incendio con el pipeline de ingest (`scripts/batch_process_fires.py` o per-fire).
2. Materializar máscaras LWIR y auditar (`materialize_lwir_masks.py` + `audit_dataset_candidate.py`).
3. Para open CEMS multi-día: `scripts/build_open_if_pack.py` / La Mierla week scripts.

**ML holdout / patches (CLM España):**

1. Mantener directorios por incendio; no mezclar secuencias en un solo folder.
2. Generar patches con el protocolo holdout documentado (`build_clm_holdout_splits.py`, `preprocess_clm_to_ndws_npz.py`).
3. Evaluar con `smoke_production_products.py` o scorecards CLM — **no** A3C fine-tune.

> **Nota histórica (A3C):** `WildfireDataset` legacy asumía una secuencia por
> directorio; el path de producto es Residual U-Net / ensemble CLM v34.

## 5. Checklist de calidad

- [ ] Todas las imágenes tienen CRS proyectado (no 4326).
- [ ] Las máscaras contienen píxeles > 0 (ver audit script).
- [ ] Producto ML: `clm_ensemble_v34` / `clm_v28` listados y smoke holdout OK.
- [ ] Ops: incident doctor / smoke-incident sin errores en fixture.
- [ ] `pred_spread > 0` (el modelo no colapsa a predecir "no propagación").
- [ ] Los pesos fine-tuned se guardan en `models/`.

## 6. Troubleshooting

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| `ValueError: insufficient valid sequences` | <4 frames emparejados | Verificar nombres de archivos y `_find_mask` |
| `target_spread = 0` | Máscaras vacías o sin propagación | Bajar `--threshold` en materialización |
| Loss no disminuye | LR muy alto / datos ruidosos | Probar `--lr 5e-5`, más epochs |
| OOM en GPU | batch_size=1 ya es mínimo | Reducir `patch_size` o `sequence_length` |
| `shape-mismatched keys` warning | Cambios de arquitectura | Normal: capas nuevas se inicializan random |