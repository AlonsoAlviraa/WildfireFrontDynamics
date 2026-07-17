# WildfireFrontDynamics — One-pager comercial

## El problema

En incendios grandes, los mandos necesitan **saber dónde avanza el frente y a qué ritmo**,  
pero suelen tener **o** datos de dron (escasos, NDA) **o** mapas satelitales (públicos, lentos de integrar).

## La solución (producto dual)

| Módulo | Qué entrega | Cuándo |
|--------|-------------|--------|
| **A · Thermal Front Ops** | ROS local, sectores, envelope, brief desde LWIR | Hay cámara / Heligrafics / campo |
| **B · Open Perimeter Intelligence** | Perímetros CEMS multi-día, ha, crecimiento, mapa, brief | **Sin NDA**, IF grandes Europa/ES |

**ML (CLM ensemble v34):** máscara next-day en parches España — IoU holdout **0.896** — producto separado, no se confunde con ROS de dron.

## Por qué es mejor que “solo CLM”

| | Solo CLM | Dual (lo que vendemos) |
|--|----------|-------------------------|
| Demo en 10 min a un cliente | Difícil (datos privados) | **Sí** (descarga CEMS) |
| IF de miles de ha | Raro en vuestro Dropbox | **CEMS 1–3k ha** |
| Perímetro multi-temporal | No | **FEP→DEL→MONIT→GRA** |
| Dependencia de un proveedor | Alta | Baja en pista B |
| ML transfer CLM | Sí (v34) | **Se mantiene** |

## Demo (1 comando)

```bash
python scripts/demo_sellable_product.py
```

Abre: packs open_if, scorecard dual vs CLM-solo, mapas HTML.

## Oferta piloto (plantilla)

| Item | Contenido |
|------|-----------|
| Duración | 4–6 semanas |
| Entregable 1 | 3 packs open CEMS de IF a elegir (España/PT) |
| Entregable 2 | Integración 1 secuencia térmica (si el cliente aporta LWIR) |
| Entregable 3 | Brief operativo + formación 2 h |
| Precio | _definir con Alonso_ |
| No incluido | Despacho táctico, promesa de extinción, perímetro catastral nacional |

## Disclaimers (legales / venta honesta)

- CEMS = mapeo de emergencia satelital Copernicus, **no** cadastro nacional.  
- ROS proxy open = crecimiento entre productos CEMS (Δt a menudo 24 h).  
- ML IoU ≠ velocidad de frente en campo.

## Contacto / siguientes pasos

1. Demo en vivo 20 min  
2. Elegir 1 IF open + 1 IF con dron  
3. Carta de interés / piloto  

Repo: WildfireFrontDynamics · Scorecard: `docs/COMPARE_CLM_VS_OPEN.md` · Plan: `docs/PLAN_COMERCIAL_SUPERA_CLM.md`
