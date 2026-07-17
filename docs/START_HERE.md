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

## Documentos clave

| Doc | Para qué |
|------|----------|
| `docs/PORTAL.html` | **Ver todo** |
| `docs/START_HERE.md` | Este resumen |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Comandos largos |
| `docs/PLAN_3_MESES.md` | Roadmap realista |
| `docs/SUENOS_MAXIMOS.md` | Techo de resultados y funciones |

## Qué está hecho vs bloqueado

| Hecho | Bloqueado (externo) |
|-------|---------------------|
| ML v34, ops, 4 packs CEMS | 2ª ancla INFOCAM |
| Decision Card + Metrics Hub | Perímetro nacional oficial |
| FDC en incident update | Piloto con cliente real |
| API mínima POST /v1/decide | Auth / 99.9% uptime (sueño) |
| **Acta forense + radio + replay** | PDF firmado (sueño) |

## Comando mínimo de decisión

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front decide                    # vacío → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\open_if\emsr578 --require-ops-for-go
```

## API + acta + políticas (filas del sueño en el plan)

```powershell
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --use-ml-v34 --policy field_ops   # estricto: ML-only → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --policy research_open
python -m wildfire_front serve-decide --port 8765
python -m wildfire_front export-acta --work-dir outputs\incidents\tobarra_demo
python -m wildfire_front replay-decide --work-dir outputs\incidents\tobarra_demo
```

Outbox tras `incident update` (policy default **field_ops**): card + radio + acta + replay_sources.
