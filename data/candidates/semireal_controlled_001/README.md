# semireal_controlled_001

Small reproducible semireal candidate for the data-validation milestone.

## Purpose

This dataset is not a real fire. It is a controlled stand-in that exercises the
same contract expected from a real sequence:

- projected GeoTIFF imagery;
- one observed mask per timestamp;
- one independent annotation mask per timestamp;
- temporal expansion and translation of the candidate front;
- known CRS, affine transform and resolution.

It exists to validate the data-audit and reference-metric workflow before a
FLAME 3, WIT-UAS or field sequence is available.

## Generation

```powershell
python scripts\generate_semireal_candidate.py
```

The script writes:

```text
data/candidates/semireal_controlled_001/
  images/
  masks/
  annotations/
```

## Spatial Contract

- CRS: `EPSG:32630`
- Resolution: `2.0 m`
- Raster shape: `96 x 128`
- Timestamps: four frames from `20260610_120000` to `20260610_120230`

## Scientific Status

The masks are observed candidates. The `annotations/` masks are independent only
within this generated fixture, not human or field truth. Metrics computed from
this package prove the pipeline mechanics, not wildfire accuracy.

## Recommended Audit

```powershell
python scripts\audit_dataset_candidate.py `
  --images data\candidates\semireal_controlled_001\images `
  --masks data\candidates\semireal_controlled_001\masks `
  --annotations data\candidates\semireal_controlled_001\annotations `
  --output outputs\semireal_controlled_001-audit `
  --event-id semireal_controlled_001 `
  --sensor-id thermal_semireal `
  --estimated-error-m 2.0
```
