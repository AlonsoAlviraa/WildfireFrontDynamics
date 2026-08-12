# Honestidad de métricas — **IoU ≠ ROS**

**1 página · Graph v6.1 E9**  
**As of:** 2026-08-04

## Mensaje único

| Métrica | Qué mide | Qué **no** es |
|---------|----------|----------------|
| **IoU** (máscara next-day / holdout) | Solapamiento de **máscaras** de quemado o crecimiento en eval lab | Velocidad de frente, ROS táctico, certeza live de sala |
| **ROS** (m/min) | Tasa de propagación **geométrica** entre frentes LWIR multi-pasada | IoU, mAP de detector, peligro next-day Orion |
| **Holdout catalog IoU ~0.8963** | Proveniencia del ensemble CLM v34 en protocolo limpio | Live fire certainty · ops Tobarra · perímetro nacional O2 |
| **U1 TEST honest IoU ~0.86** | Lab pitch (selective@80, ECE) | Despacho táctico · `ml_product_go` |

## Capas que no se mezclan en demo

```text
LWIR multi-pasada  →  ROS / grade / envelope     = capa Ops (field_ops)
CEMS / open        →  ha / timeline perímetro   = monitorización
ML máscaras        →  IoU / ECE / abstain lab   = research / research_open
Decision Card      →  GO | HOLD | ABSTAIN       = fusión con rails
```

## Rails

- `ml_product_go` = **false**
- `field_ops.allow_ml_live_in_fusion` = **false**
- Catalog IoU: **provenance only** (reason `holdout_quality=…:not_fused`)
- v34 / U1: **lab only** en claims comerciales de frente
- Lampman MAE: **método**, no SLA mediterráneo

## Frases prohibidas en pitch

- “IoU 0.90 ⇒ el fuego avanza X m/min”
- “El modelo predice el perímetro táctico en vivo”
- “Holdout = certeza en el incendio de hoy”

## Frases permitidas

- “Máscaras de research con IoU holdout de proveniencia; el ROS de sala sale del LWIR medido.”
- “Si solo hay ML o la incertidumbre es alta, la card **ABSTAIN**.”
- “Tobarra: ROS ~5.7 m/min vs Vp 7 (grade A); Hellín grade B honest.”

## Ver también

- `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`
- `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md`
- `docs/DATA_PROXY_HONESTY.md`
- `docs/PILOT_HONESTY_CARD.md`
