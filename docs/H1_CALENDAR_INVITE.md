# Invitación calendario — Demo WFD 12 min (H1 / GO_Q)

> **Copia/pega a Google Calendar / Outlook.**  
> **Eng no cierra GO_Q** — al terminar, rellenar acta real y:

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

## Título
WildfireFrontDynamics — demo decisión 12 min (HITL, fusion OFF)

## Cuándo (propuesta)
**Propuesta eng:** 2026-08-13 10:00–10:15 (UTC) — reprogramar con el tercero. Prepared UTC: 2026-08-10T13:42:31.496441+00:00

## Duración
12–15 min (+ 5 min Q&A opcional)

## Asistentes
- **Presentador (repo):** _rellenar nombre_
- **Tercero externo (obligatorio):** _emergencias / uni / partner_ — **sin tercero no hay H1**

## Agenda (cheatsheet)

| Min | Bloque |
|----:|--------|
| 0–1 | Rails en voz alta: GO_MES true · GO_Q partial · fusion **OFF** · ml_product_go **lab only** · ABSTAIN = feature |
| 1–4 | Ver multi-CCAA (3 contratos) |
| 4–6 | Callarse (pilot honesty / field_ops se calla) |
| 6–9 | Decision Card + explain |
| 9–11 | Pack third-party + replay |
| 11–12 | Límites + ask · acta |

Detalle: `docs/CHEATSHEET_DEMO_12MIN.md`  
Runbook: `docs/H1_GO_Q_RUNBOOK.md`

## Setup 30 s (presentador)

```powershell
cd <repo_WFD>
$env:PYTHONPATH = "."
python -m wildfire_front operator checklist
```

## Kill list verbal (obligatorio)
- No ROS inventado  
- No field_ops ML live fusion ON  
- No vender Tobarra LOFO ~0.48 como producto de campo  
- No “apagamos incendios con IA”

## Después de la call
1. Acta firmada: `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` (no PENDING)  
2. `python scripts/record_h1_demo_complete.py --acta <acta>` → exit 0 cierra M3.2/GO_Q en status JSON  
3. Si exit 2: campos vacíos / placeholder — **no se muta status** (correcto)

## Estado eng pre-call
Ver `docs/H1_DEMO_SESSION_READY.json` (este prepare).
