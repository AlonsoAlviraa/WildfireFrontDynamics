# Metrics Hub — todas las métricas

_UTC: 2026-07-17T18:55:52.951370+00:00_ · git `046226f` · hash `9e69e7a6fa39…`

## Decision Card (fusión)

- **decision:** `GO`
- **confidence_pred:** 0.894 (HIGH)
- **system_reliability_pass:** True
- **reasons:** ml_clm_ensemble:conf=1.000:w=0.25, ops_thermal_front:conf=0.980:w=0.40, open_cems_perimeter:conf=0.720:w=0.35, ops_confidence_ok

> Fire prediction is **not** 99.9999% accurate. Five-nines bound = no silent GO without gates under automation.

## ML (CLM ensemble)

| Métrica | Valor |
|---------|------:|
| product | clm_ensemble_v34 |
| test_iou | 0.8963 |
| improvement_vs_copy_iou | 0.2545 |
| model_iou_growth | 0.9071 |
| temps | [0.7, 0.7, 1.3] |
| mix | [0.28, 0.32, 0.4] |

## Ops (Tobarra representativo)

| Métrica | Valor |
|---------|------:|
| grade | A |
| ROS m/min | 5.71 |
| frames | 35 |
| area_ha | 39.0 |
| ratio vs Vp | 0.8157142857142857 |

## Open CEMS packs

n_packs = **4**

| Pack | max_ha | steps | O2_cems |
|------|-------:|------:|---------|
| EMSR578 | 2693.5 | 5 | GO |
| EMSR581 | 2209.8 | 4 | GO |
| EMSR583 | 1790.6 | 5 | GO |
| EMSR632 | 5319.5 | 4 | GO |

## Gates industriales

```json
{
  "G0_ndws": "GO",
  "G1_ndws": "KILL",
  "G2_clm_v28": "GO",
  "G2e_ensemble_v34": "GO",
  "O1_multi_anchor": "OPEN",
  "O2_hausdorff_official": "BLOCKED",
  "O3_temporal": "PARTIAL",
  "O4_brief": "GO_ENG",
  "O5_second_grade_a": "OPEN",
  "P1_incident_2if": "PARTIAL",
  "E1_ci_smokes": "GO_ENG",
  "D1_cyl": "FOLLOW_UP",
  "M2_v34_hold": "GO",
  "M5_v35": "NO_DATA"
}
```

## Comercial (dual vs CLM-solo)

- score_dual: 95.0
- score_clm_only: 39.0
- VENTA_GO: True

## Audit

- decision audit: `90ef8eb2c0497382…`
- hub hash: `9e69e7a6fa39ca24f1c860a549b6c9cc6cccc2e1d419166fa16482c26c0b070d`
