# Gold IF — verificación E2E (loop-engineering)

_UTC: 2026-07-21T11:06:25.260815+00:00_ · verdict **GO_GOLD_STACK**

## Hallazgo honesto del scrape mundial

No existe un incendio público en el mundo que reúna a la vez:

1. Secuencia LWIR GeoTIFF multi-frame (contrato Heligrafics)
2. Ancla operativa confirmed Vp/ha (INFOCAM-class)
3. Perímetro CEMS multi-día del **mismo** evento
4. Perímetro catastral/nacional oficial (O2 real)

Por diseño del producto, la **fusión** ocurre en la Decision Card entre
fuentes heterogéneas. El stack oro verificable es dual:

- **OPS:** `tobarra_20240802` — LWIR=35, masks=35, anchor=confirmed, Vp=7.0, ha=39.0
- **OPEN:** `EMSR578` — vectors=7, timeline=5, O2_cems=GO, dnbr=GO, max_ha=2693.4837707192946
- **ML:** `clm_ensemble_v34`

## Capas del contrato (pass/fail)

| Capa | Pass |
|------|------|
| `ops_lwir` | ✅ |
| `ops_masks` | ✅ |
| `ops_anchor` | ✅ |
| `ops_pack` | ✅ |
| `open_multi` | ✅ |
| `open_o2` | ✅ |
| `open_dnbr` | ✅ |
| `open_firms` | ✅ |
| `decide_ok` | ✅ |

**Capas:** 9/9

## Decision Card (fusión)

- decision: **GO**
- confidence_pred: 0.8586666666666667
- system_reliability_pass: False
- sources: [{"id": "ml_clm_ensemble", "available": true, "confidence": 0.75}, {"id": "ops_thermal_front", "available": true, "confidence": 0.98}, {"id": "open_cems_perimeter", "available": true, "confidence": 0.72}]

## Pasos ejecutados

| Step | OK |
|------|----|
| open_emsr578_artifacts | ✅ |
| ops_tobarra_pack | ✅ |
| decide_fusion | ✅ |
| decide_empty_abstain | ✅ |
| smoke_incident_runtime | ✅ |
| smoke_ml_v34 | ✅ |
| reliability_gate | ✅ |
| pytest_product_core | ✅ |

## Candidatos externos (web) — no sustituyen Tobarra

- **FLAME3_NADIR_Hanna_Hammock** · `RESEARCH_ONLY_NOT_GOLD` — UAV radiometric thermal NADIR georeferenced + masks (prescribed burn US)
- **NIROPS_US_multi_day_IR_perimeters** · `OPEN_PROXY_US_ONLY` — 12k+ multi-day IR-interpreted perimeters (NIFC) — excellent O2-proxy timeline
- **CALFIRE_historic_perimeters** · `OUT_OF_DOMAIN` — Official state perimeters (closest to O2 official, but California)
- **EMSR896_Aragon_2026** · `PROBE_ON_DEMAND` — Live Spanish CEMS wildfire activation (Jul 2026)
- **EMSR578_Catalonia_2022** · `OPEN_GOLD_IN_REPO` — Already in-repo: FEP+DEL+MONIT×2+GRA, dNBR STAC GO, FIRMS overlay
- **Tobarra_AB_20240802** · `OPS_GOLD_IN_REPO` — Only fire with confirmed Vp/ha + full LWIR sequence + grade A pack

## Cómo re-ejecutar

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python scripts\verify_gold_if_e2e.py
```

JSON: `docs/GOLD_IF_E2E_VERIFICATION.json`

