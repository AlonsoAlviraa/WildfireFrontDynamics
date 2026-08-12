# Metrics Hub — todas las métricas

_UTC: 2026-08-04T14:44:28.330203+00:00_ · git `eb95049` · hash `1c4be67a850b…`

## Decision Card (fusión)

- **decision:** `GO`
- **confidence_pred:** 0.8586666666666667 (HIGH)
- **system_reliability_pass:** False
- **reasons:** ml_clm_ensemble:holdout_quality=0.750:not_fused, ops_thermal_front:conf=0.980:w=0.40, open_cems_perimeter:conf=0.720:w=0.35, policy:default, ops_confidence_ok

> Fire prediction is **not** 99.9999% accurate. Five-nines bound = no silent GO without gates under automation.

## ML (CLM ensemble)

| Métrica | Valor |
|---------|------:|
| product | clm_ensemble_v34 |
| **U1 TEST honest mean IoU (lab pitch)** | 0.8568865373678947 |
| **ECE patch conf (lab)** | 0.15280955026564416 |
| selective@80 IoU | 0.903428533834858 |
| u1_test_honest | True |
| ml_product_go | False |
| catalog holdout test_iou (provenance only) | 0.8963 |
| catalog Δ copy (provenance) | 0.2545 |
| catalog growth (provenance) | 0.9071 |
| manifest_verdict | GO_RESEARCH_HOLDOUT |
| temps | [0.7, 0.7, 1.3] |
| mix | [0.28, 0.32, 0.4] |

> Catalog holdout IoU is **provenance only** — not live certainty, not ROS, not `ml_product_go`.

## Ops (Tobarra representativo)

| Métrica | Valor |
|---------|------:|
| grade | A |
| ROS m/min | 5.71 |
| frames | 35 |
| area_ha | 39.0 |
| ratio vs Vp | 0.8157142857142857 |

## Open CEMS packs

n_packs = **11**

| Pack | max_ha | steps | O2_cems |
|------|-------:|------:|---------|
| EMSR578 | 2693.5 | 5 | GO |
| EMSR581 | 2209.8 | 4 | GO |
| EMSR583 | 1790.6 | 5 | GO |
| EMSR632 | 5319.5 | 4 | GO |
| EMSR896 | 12133.4 | 4 | GO |
| EMSR898 | 27213.2 | 8 | GO |
| EMSR899 | 26064.7 | 2 | GO |
| EMSR900 | 44376.7 | 10 | GO |
| EMSR902 | 2682.2 | 3 | GO |
| EMSR905 | 7265.8 | 3 | GO |
| guadalajara_la_mierla_20260717 | 32000.0 | 1 | NOT_ACTIVATED_OR_UNKNOWN |

## Abstention slice (E7)

- **n_cards:** 18 · unknown=False
- **abstain_rate:** 0.2777777777777778 (ABSTAIN=5 · HOLD=7 · GO=6)
- **source_coverage_mean:** 0.5231481481481481
- **R3_abstention_enforced:** True
- **ml_live_fusion:** OFF
- population: `artifact_cards_plus_suite_samples_not_fleet_telemetry`

> abstain_rate = fraction of sampled Decision Cards with decision=ABSTAIN (suite + on-disk artifacts). NOT live fire accuracy, NOT field fleet rate. source_coverage_mean = mean fraction of sources[] marked available per card. ml_live fusion remains OFF (weight 0 / not fused).

### Source coverage by id

| Source | n_seen | n_available | available_rate |
|--------|-------:|------------:|---------------:|
| envelope_v3_hybrid | 1 | 1 | 1.0 |
| ml | 1 | 0 | 0.0 |
| ml_clm_ensemble | 17 | 6 | 0.35294117647058826 |
| ml_live_reliability | 9 | 9 | 1.0 |
| open_cems | 8 | 0 | 0.0 |
| open_cems_perimeter | 10 | 10 | 1.0 |
| ops | 11 | 0 | 0.0 |
| ops_thermal_front | 7 | 7 | 1.0 |

## Gates industriales

```json
{
  "G0_ndws": "GO",
  "G1_ndws": "KILL",
  "G2_clm_v28": "GO",
  "G2e_ensemble_v34": "GO_RESEARCH_HOLDOUT",
  "O1_multi_anchor": "OPEN",
  "O2_hausdorff_official": "BLOCKED",
  "O2_cems_open_proxy": "GO_PROXY",
  "O3_temporal": "PARTIAL",
  "O4_brief": "GO_ENG",
  "O5_second_grade_a": "OPEN",
  "P1_incident_2if": "PARTIAL",
  "E1_ci_smokes": "GO_ENG",
  "D1_cyl": "FOLLOW_UP",
  "M2_v34_hold": "GO",
  "M5_v35": "NO_DATA",
  "pilot_honesty_pack": "GO_ENG",
  "demo_multi_ccaa": "GO_ENG",
  "third_party_demo": "PENDING"
}
```

## Comercial (dual vs CLM-solo)

- score_dual: 95.0
- score_clm_only: 39.0
- VENTA_GO: True

## Audit

- decision audit: `10213ee47bff8496…`
- hub hash: `1c4be67a850b903dfa24beccc6b68378d8087ce69af0278808cddceb90aec1a1`
