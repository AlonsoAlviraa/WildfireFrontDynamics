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

### 3.3. Fine-tuning (smoke test primero, luego run completo)

**Smoke test rápido (CPU, ~15s):**

```bash
set PYTHONPATH=. && python scripts\smoke_test_finetune.py ^
    --images-dir artifacts\<fire_name>_reprojected_lwir ^
    --masks-dir artifacts\<fire_name>_lwir_masks ^
    --epochs 1 ^
    --max-patches 30
```

**Run completo (GPU o CPU paciente):**

```bash
set PYTHONPATH=. && python scripts\smoke_test_finetune.py ^
    --images-dir artifacts\<fire_name>_reprojected_lwir ^
    --masks-dir artifacts\<fire_name>_lwir_masks ^
    --epochs 10 ^
    --max-patches 0 ^
    --output models\<fire_name>_finetuned.pt
```

> `--max-patches 0` desactiva el límite (usa todos los patches con fuego).

### 3.4. Validación cualitativa

```bash
set PYTHONPATH=. && python scripts\compare_base_vs_finetuned.py
```

Comparar `BASE acc` vs `FINE-TUNED acc`. El fine-tuned debe ser >= base y
`target_spread > 0` confirma que hay transiciones reales.

## 4. Incorporar múltiples incendios

Para combinar varios incendios en un único dataset:

1. Concatenar los directorios reproyectados en uno solo (o usar symlinks).
2. Re-ejecutar la materialización de máscaras sobre el directorio combinado.
3. Fine-tuning sobre el directorio combinado.

> **Nota**: el `WildfireDataset` asume que todos los frames de un directorio
> pertenecen a la misma secuencia temporal. Para múltiples incendios,
> mantener directorios separados y crear un `ConcatDataset` de PyTorch.

## 5. Checklist de calidad

- [ ] Todas las imágenes tienen CRS proyectado (no 4326).
- [ ] Las máscaras contienen píxeles > 0 (ver audit script).
- [ ] `target_spread > 0` en la comparación (hay transiciones reales).
- [ ] `FINE-TUNED acc >= BASE acc`.
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