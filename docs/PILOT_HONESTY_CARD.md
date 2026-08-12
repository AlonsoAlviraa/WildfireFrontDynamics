# Piloto de honestidad — tarjeta de decisión multi-fuente
Tobarra · Níjar · Caminomorisco
Generado: 2026-08-04T14:12:17.319132+00:00 · política: research_open · producto: clm_ensemble_v34

## 0. Banner de honestidad (producto dual)
- Ops (front_dynamics_v1) ≠ ML (máscara + fiabilidad de parche)
- Fusión solo en tarjeta de decisión; field_ops fusión live = OFF
- No es orden táctica de despacho
- U1 TEST honest (scorecard): IoU eval ≈ 0.857 · sel@80 ≈ 0.903 · ECE ≈ 0.153
- Catalog holdout 0.8963 = provenance only (no es certeza en vivo)

## 1. Tabla de hechos
| Sitio | Pista | Fuentes | Decisión (research_open) | confianza | ML live | Decisión (field_ops) | Cifra clave | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tobarra | OPS | ops+ml_live | GO | 0.672 | sí | ABSTAIN | ROS primario (m/min)=6.752 | Sin Vp táctica |
| Níjar | OPEN_AND | open+ml_live | HOLD | 0.610 | sí | HOLD | área (ha)=2169.340 | Sin Vp táctica; open HOLD |
| Caminomorisco | OPEN_EXT | open+ml_live | HOLD | 0.500 | no | HOLD | área (ha)=2679.140 | Sin Vp táctica; open HOLD |

## 2. Lectura por incendio
### Tobarra (OPS)
- Cifra clave: ROS primario (m/min) = 6.7521 (fuente: operational_metrics.speed_median_m_min; clave: primary_ros_m_min)
- Tarjeta research_open: GO · confianza=0.672 · ML live=sí
- Contraste field_ops: ABSTAIN (sin R1–R4 inventados; fusión OFF)
- Honestidad: Vp inventada=no; casco FIRMS≠quemado; fuentes incompletas=no

### Níjar (OPEN_AND)
- Cifra clave: área (ha) = 2169.3400 (fuente: metrics_o2.area_rediam_ha; clave: area_ha)
- Tarjeta research_open: HOLD · confianza=0.610 · ML live=sí
- Contraste field_ops: HOLD (sin R1–R4 inventados; fusión OFF)
- Honestidad: Vp inventada=no; casco FIRMS≠quemado; fuentes incompletas=no

### Caminomorisco (OPEN_EXT)
- Cifra clave: área (ha) = 2679.1400 (fuente: metrics_o2.area_rai_ha; clave: area_ha)
- Tarjeta research_open: HOLD · confianza=0.500 · ML live=no
- Contraste field_ops: HOLD (sin R1–R4 inventados; fusión OFF)
- Honestidad: Vp inventada=no; casco FIRMS≠quemado; fuentes incompletas=no

## 3. Contraste de políticas
- research_open: laboratorio / amigable con open (HOLD); fusión live experimental
- field_ops: require_ops_for_go; fusión live OFF; ABSTAIN fail-closed (cierre seguro) si GO sin fiabilidad verificada (reason field_ops_fail_closed_reliability_unverified) — el piloto no inventa gates

## 4. Límites y no-claims
- No es multi-CCAA «funciona en toda España»
- Casco FIRMS ≠ área quemada oficial
- Sin reentrenamiento en este piloto
- ml_product_go sigue en false hasta gates de producto

## 5. Modo presentación (1 página)
- Tres sitios · un criterio: GO / HOLD / ABSTAIN con audit trail
- research_open puede ir a GO experimental; field_ops se calla (ABSTAIN/HOLD) — fusión OFF
- Cifras solo de OPS (ROS) u open (ha); sin Vp táctica inventada
- Holdout catálogo 0.8963 = provenance only, no certeza del incendio

## 6. Artefactos
- Raíz piloto: `outputs/pilot_honesty_card`
- Por sitio: `decision_card.json`, `decision_card_field_ops.json`, `site_summary.json`
- `facts_table.json` · `pilot_summary.json` · `index.html` · este informe

