# Metrics Hub — todas las métricas

_UTC: 2026-07-21T10:57:40.724454+00:00_ · git `29fb877` · hash `a3e8ac658fae…`

## Decision Card (fusión)

- **decision:** `GO`
- **confidence_pred:** 0.7559999999999999 (HIGH)
- **system_reliability_pass:** False
- **reasons:** ml_clm_ensemble:holdout_quality=1.000:not_fused, ops_thermal_front:conf=0.980:w=0.40, open_cems_perimeter:conf=0.500:w=0.35, policy:default, ops_confidence_ok

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

**ML-first honesty:** catalog holdout TEST IoU **0.8963** is research quality only (not live certainty, not ROS, not Tobarra/REDIAM O2). Live confidence uses ensemble disagreement + **VAL-fit** calibrator (Card may HOLD/ABSTAIN). Fusion live weight OFF until **U1 on TEST** with frozen calibrator (`u1_test_honest`); VAL-only U1 is lab/optimistic and must not promote fusion.

## Ops (Tobarra representativo)

| Métrica | Valor |
|---------|------:|
| grade | A |
| ROS m/min | 5.71 |
| frames | 35 |
| area_ha | 39.0 |
| ratio vs Vp | 0.8157142857142857 |

## Open CEMS packs

n_packs = **5**

| Pack | max_ha | steps | O2_cems |
|------|-------:|------:|---------|
| EMSR578 | 2693.5 | 5 | GO |
| EMSR581 | 2209.8 | 4 | GO |
| EMSR583 | 1790.6 | 5 | GO |
| EMSR632 | 5319.5 | 4 | GO |
| guadalajara_la_mierla_20260717 | 29000.0 | 1 | NOT_ACTIVATED_OR_UNKNOWN |

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

- decision audit: `2543d49d5593ff8f…`
- hub hash: `a3e8ac658fae1b2e629082e1e53a6090f0f7cc233001013a0b8db0278b293fa5`
