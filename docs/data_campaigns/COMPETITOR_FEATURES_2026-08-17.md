# Competencia wildfire-ops (público) vs lo que WFD envía hoy

**Fecha:** 2026-08-17  
**Método:** páginas comerciales e institucionales públicas (no memoria).  
**Uso:** mapa de huecos de producto y de outreach. No es un plan de implementación.

## Lo que WFD envía hoy (límite honesto)

Fuente: `docs/PILOT_HONESTY_CARD.md` (2026-08-17) y `docs/ONEPAGER_COMERCIAL_ES.md`.

| Superficie WFD | Qué es | Qué no es |
|---|---|---|
| Fire Decision Card | GO / HOLD / ABSTAIN con confianza 0–1 y motivos | Orden táctica de despacho |
| Audit trail | hash de inputs/outputs, versión, UTC, fuente | Acta firmada por tercero |
| Fusión field_ops | ON, cap 0.20 / abstain 0.45 | GO_Q complete; despacho |
| Reliability gate | fail-closed: GO sin fiabilidad verificada → ABSTAIN | Stamp contractual de residual |
| Dual field | LWIR si hay dron + open CEMS si no | Red de cámaras o constelación propia |
| Decide API / CLI / app | POST `/v1/decide`, replay forense, flags/catalog/card | CAD, tracking de recursos, ICS |
| ML catálogo | `ml_product_go` lab only; FREEZE_ML | RCDA IoU 0.308 ni Caldor como producto |

No se reclama: GO_Q complete, acta H1 firmada, cita operativa Hellín/Cardoso, O2 España, cesión CONAF escrita, scores RCDA/Caldor de producto.

## Productos nombrados

### 1. Technosylva — Tactical Analyst™, fiResponse™, Wildfire Analyst / FireSight / FireRisk

| Función pública | Fuente | WFD hoy |
|---|---|---|
| Common operating picture: integra simulación Wildfire Analyst + despacho fiResponse | https://technosylva.com/products/tactical-analyst/ | No. WFD no integra CAD ni COP multi-agencia. |
| Predicción de propagación on-demand por incidente; informes de simulación web/móvil | https://technosylva.com/products/tactical-analyst/ | No como producto operativo. La tarjeta no es un simulador táctico. |
| Tracking de recursos (IRWIN/CAD, AVL/GPS), incluso offline | https://technosylva.com/products/tactical-analyst/ · https://technosylva.com/products/firesponse/ | No. |
| CAD multi-agencia: declaración de incidente, ICS, burn permits, facturación | https://technosylva.com/products/firesponse/ | No. WFD es apoyo a decisión, no mando. |
| Planificación de riesgo de activo (FireSight) y riesgo operativo (FireRisk) para utilities | https://technosylva.com/ | No. No hay PSPS ni hardening de red. |
| Clientes públicos citados en home (CAL FIRE, INFOCA, Junta CyL, UME logo) | https://technosylva.com/ | WFD no tiene despliegue de agencia. |

### 2. Pano AI — Pano Rapid Detect + Pano 360

| Función pública | Fuente | WFD hoy |
|---|---|---|
| Estaciones de cámara 24/7, 360°, 6 MP, zoom 30×, panorama cada minuto | https://www.pano.ai/solution | No hay red de cámaras. |
| Detección de humo por IA + revisión humana en Pano Intelligence Center | https://www.pano.ai/solution | No hay detector de ignición. |
| Alertas verificadas email/SMS a partners; acceso gratis a first responders de la zona | https://www.pano.ai/solution | No hay canal de alerta. |
| Triangulación GPS del incidente + capas meteo/perímetros/red flag | https://www.pano.ai/solution | WFD consume perímetros/ops si el operador los aporta; no detecta. |
| Posicionamiento: “detect early, notify, visual intelligence” | https://www.pano.ai/ | WFD entra **después** de que exista una observación georreferenciada. |

### 3. OroraTech — Wildfire Solution (+ constelación propia)

| Función pública | Fuente | WFD hoy |
|---|---|---|
| Fusión de 35+ satélites; detección de focos (claims de 4×4 m / 10×10 m) | https://ororatech.com/all-products/wildfire-solution | No hay sensor espacial propio ni alerta de hotspot. |
| Alertas email / WhatsApp / SMS / in-app en minutos | https://ororatech.com/all-products/wildfire-solution | No. |
| Fire confidence para filtrar falsos positivos | https://ororatech.com/all-products/wildfire-solution | WFD tiene abstención por falta de evidencia, no un score de hotspot. |
| Simulación de propagación + seguimiento del frente activo | https://ororatech.com/all-products/wildfire-solution | No como producto. |
| Índice de peligro a 9 días, fuel moisture, burnt area post-fuego | https://ororatech.com/all-products/wildfire-solution | No. CEMS abierto se usa como fuente, no como producto revendible. |
| Grecia: Hellenic Fire System (4 satélites + plataforma a servicios griegos) | https://ororatech.com/resources/news-blog/greece-launches-world-s-first-national-wildfire-satellite-system | Irrelevante para WFD: no competimos en detección espacial. Sí implica que el outreach GR debe pedir **casos históricos**, no “mejor detección”. |

### 4. Dryad — Silvanet Wildfire Sensor

| Función pública | Fuente | WFD hoy |
|---|---|---|
| Sensor solar en árbol; detecta pirólisis (CO / VOC / PM) en minutos | https://www.dryad.net/wildfiresensor | No hay hardware de campo. |
| Microclima (T, HR, presión, CO, VOC, PM2.5) | https://www.dryad.net/wildfiresensor | No. |
| Malla LoRaWAN + satélite; 10–15 años sin batería de litio | https://www.dryad.net/wildfiresensor | No. |
| Plataforma cloud / API de alerta | https://www.dryad.net/wildfiresensor | Decide API es tarjeta de decisión, no ingestión de sensores de gas. |

### 5. Overstory — vegetation intelligence para utilities

| Función pública | Fuente | WFD hoy |
|---|---|---|
| Riesgo de vegetación árbol a árbol (satélite + IA) para recorte y hazard trees | https://www.overstory.com/ | No. |
| Overlay de encroachment / species sobre mapas de wildfire para planes de mitigación | https://www.overstory.com/solutions | No hay producto de vegetation management. |
| High-Reliability Zone desde subestación al primer dispositivo de protección | https://www.overstory.com/solutions | Fuera de scope. WFD no es un WMP de utility. |

## Lectura para producto (no implementar en esta tanda)

La competencia se concentra en **detectar** (cámaras, satélite, gas) o en **despachar/simular** (CAD, COP, spread). WFD ocupa un hueco más estrecho: **decidir si hay evidencia bastante para hablar del frente**, y callarse (ABSTAIN/HOLD) si no la hay.

Huecos reales si un organismo compara:

1. No detectamos ignición.
2. No despachamos medios.
3. No vendemos simulación táctica validada por agencia.
4. GO_Q sigue partial hasta demo tercero + acta.

Eso no se tapa con marketing. Se tapa con un caso histórico multi-observación y, más adelante, un firmante humano.

## Anti-claims (esta nota no afirma)

- GO_Q complete / field sell-ready
- Acta H1 firmada
- Cita operativa Hellín / Cardoso / La Estrella
- RCDA IoU 0.308 ni Caldor (1 fuego / 15 pares) como score de producto
- Fusion ON = despacho
