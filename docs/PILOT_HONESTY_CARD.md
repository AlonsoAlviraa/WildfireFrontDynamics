# Piloto honesty — Decision Card multi-fuente
Tobarra · Níjar · Caminomorisco
Generated: 2026-07-24T00:00:00+00:00 · policy primary: research_open · product: clm_ensemble_v34

## 0. Banner de honestidad (dual product)
- Ops (front_dynamics_v1) ≠ ML (máscara + fiabilidad de parche)
- Fusión solo en Decision Card; field_ops live fusion = OFF
- No es orden táctica de despacho
- U1 TEST honest (scorecard): IoU eval ≈ 0.857 · sel@80 ≈ 0.903 · ECE ≈ 0.153
- Catalog holdout 0.8963 = provenance only (not live certainty)

## 1. Tabla de hechos (auto from facts_table.json)
| Site | Track | Sources | Decision (research_open) | conf | live_ok | Decision (field_ops) | Key number | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tobarra | OPS | ops+ml_live | GO | 0.672 | True | ABSTAIN | primary_ros_m_min=6.752 | No tactical Vp |
| Níjar | OPEN_AND | open+ml_live | HOLD | 0.610 | True | HOLD | area_ha=2169.340 | No tactical Vp; open HOLD |
| Caminomorisco | OPEN_EXT | open+ml_live | HOLD | 0.500 | False | HOLD | area_ha=2679.140 | No tactical Vp; open HOLD |

## 2. Lectura por incendio
### Tobarra (OPS)
- Key number: primary_ros_m_min = 6.7521 (source: operational_metrics.speed_median_m_min)
- Card research_open: GO · conf=0.672 · live_ok=True
- field_ops contrast: ABSTAIN (no fake R1–R4; fusion OFF)
- Honesty: vp_invented=False; firms_hull≠burned; sources_incomplete=False

### Níjar (OPEN_AND)
- Key number: area_ha = 2169.3400 (source: metrics_o2.area_rediam_ha)
- Card research_open: HOLD · conf=0.610 · live_ok=True
- field_ops contrast: HOLD (no fake R1–R4; fusion OFF)
- Honesty: vp_invented=False; firms_hull≠burned; sources_incomplete=False

### Caminomorisco (OPEN_EXT)
- Key number: area_ha = 2679.1400 (source: metrics_o2.area_rai_ha)
- Card research_open: HOLD · conf=0.500 · live_ok=False
- field_ops contrast: HOLD (no fake R1–R4; fusion OFF)
- Honesty: vp_invented=False; firms_hull≠burned; sources_incomplete=False

## 3. Contraste de políticas
- research_open: lab / open-friendly HOLD; experimental live fusion
- field_ops: require_ops_for_go; live fusion OFF; fail-closed ABSTAIN if GO without verified reliability (reason field_ops_fail_closed_reliability_unverified) — pilot does not invent gates

## 4. Límites y no-claims
- Not multi-CCAA “works across all Spain”
- FIRMS hull ≠ official burned area
- No retrain in this pilot
- ml_product_go remains false until product gates

## 5. Artefactos
- Pilot root: `outputs/pilot_honesty_card`
- Per site: `decision_card.json`, `decision_card_field_ops.json`, `site_summary.json`
- `facts_table.json` · `pilot_summary.json` · this report

