# Empieza aquí (2 minutos)

## Qué es esto (1 frase)

**Apoyo a la decisión en incendios** con tres piezas claras:

1. **Ops térmico** (si hay dron/LWIR) → ROS y brief  
2. **Open CEMS** (si no hay dron) → perímetros públicos multi-día  
3. **Decision Card** → GO / HOLD / **ABSTAIN** + métricas + auditoría  

No es “otro mapa de Copernicus”. Es **cuándo confiar y cuándo callarse**.

## Abre esto

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"
python scripts\show_all.py
```

Se abre el **portal** (`docs/PORTAL.html`) con números, trabajo hecho y enlaces.

## Tres números para enseñar

| Qué | Valor |
|-----|------:|
| ML v34 IoU holdout | **0.8963** |
| Packs open CEMS | **4** (hasta ~5320 ha) |
| Decisión ejemplo | **GO** (conf 0.89) |

## Solo 5 documentos (ignora el resto al principio)

| Doc | Para qué |
|------|----------|
| `docs/PORTAL.html` | **Ver todo** |
| `docs/START_HERE.md` | Este resumen |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Comandos largos |
| `docs/PLAN_3_MESES.md` | Roadmap |

El resto de `docs/` es archivo técnico / scorecards — no hace falta para la primera demo.

## Qué está hecho vs bloqueado

| Hecho | Bloqueado (externo) |
|-------|---------------------|
| ML v34, ops incident, 4 packs CEMS | 2ª ancla INFOCAM |
| Decision Card + Metrics Hub | Perímetro nacional oficial |
| **FDC en cada `incident update`** (outbox) | Piloto con cliente real |
| Portal + demo 1 comando | |

## Comando mínimo de decisión

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front decide                    # vacío → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\open_if\emsr578 --require-ops-for-go
```

Tras un incidente (demo o real), la decisión también sale **en el outbox**:

`outputs/incidents/<IF>/outbox/fire_decision_card.json`
