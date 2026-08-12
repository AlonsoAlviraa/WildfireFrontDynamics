# Empieza aquí (2 minutos)

## Qué es esto (1 frase)

**Apoyo a la decisión en incendios** con tres piezas claras:

1. **Ops térmico** (si hay dron/LWIR) → ROS y brief
2. **Open CEMS** (si no hay dron) → perímetros públicos multi-día
3. **Decision Card** → GO / HOLD / **ABSTAIN** + métricas + auditoría

No es “otro mapa de Copernicus”. Es **cuándo confiar y cuándo callarse**.

## Operario (un solo comando)

Si no conoces el código, **solo necesitas esto**:

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front              # sin COMMAND → modo operario
# o: python -m wildfire_front operator | operador | ops
```

Verás un **semáforo** (VERDE / AMARILLO / ROJO), los **4 pasos** y **qué falta para GO_Q**.

```powershell
python -m wildfire_front ensayo              # = operator do --all (compacto)
python -m wildfire_front operator checklist
python -m wildfire_front operator explain-abstain
# make operator · make operator-path · make operator-checklist
```

> **ABSTAIN no es un bug.** **GO_Q** no lo cierra el eng (hace falta H1: demo+acta con tercero).  
> Log UX: `docs/OPERATOR_UX_LOOP_LOG.md`

## Superficie demo terceros (un solo path)

**Abrir esto para terceros:** Live Ops + SPA industrial C2.

```powershell
# Presentador H1 (recomendado): Live Ops + pack/reliability check + serve loopback
python -m wildfire_front app --demo-day

# Alternativas
python -m wildfire_front app --fire _sla_measure --serve   # live acts
python -m wildfire_front app --fire _sla_measure --open    # file:// estático (copia CLI)
python -m wildfire_front app --all-fires --open            # multi-IF pack cliente
```

Artefacto: **`outputs/app/index.html`**. Doc: **[`docs/APP.md`](APP.md)** · design: **`docs/design/LIVE_OPS_DEMO_KERNEL.md`**.  
Primary acts: **Estado · Decidir · Acta** (live con `--serve`/`--demo-day`) · Fácil|Pro · fusion OFF · GO_Q partial (H1 humano).

## Portal / commander (legacy, no primary)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"
python scripts\show_all.py
```

`docs/PORTAL.html` y `docs/commander/` son **legacy / hub eng** — el path de demo terceros es **`app`**, no commander.

## Tres números para enseñar

| Qué | Valor |
|-----|------:|
| ML v34 IoU holdout | **0.8963** (provenance only · not live certainty · **not ROS**) |
| Packs open CEMS (emsr*) | **11** en `outputs/open_if/` (+ AND/EXT/open aparte; no inventar ha en pitch) |
| Decisión ejemplo | **GO/HOLD/ABSTAIN** según fuentes (vacío → **ABSTAIN**) |

## Documentos clave

| Doc | Para qué |
|------|----------|
| `docs/CURRENT_STATE.md` | **Snapshot canónico** (gates + ML freeze) |
| `docs/REPO_MAP.md` | **Mapa profesional** de carpetas |
| `docs/ml/README.md` | **ML probado**: champions, cómo se midió, kill list |
| `docs/GOAL_ML_CLOSEOUT.md` | Cierre ML: freeze / más datos / techo |
| `outputs/ml_eval/canonical/` | Stamps locales de champions (gitignored) |
| `docs/MEGA_AUDIT_SELL_20260805.md` | Qué falta para vender (H1 + pitch) |
| `docs/goals/README.md` | Mega goals cerrados + closeout |
| `docs/OPERATOR_UX_LOOP_LOG.md` | Loop UX operario |
| `docs/APP.md` | **SPA ops** (Leaflet + dashboard) |
| `docs/CHEATSHEET_DEMO_12MIN.md` | Demo 12 min |
| `docs/ML_PRODUCT_START_HERE.md` | ML lab CLI |
| `docs/PORTAL.html` | Ver todo (generado) |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| `docs/H1_GO_Q_RUNBOOK.md` | Cierre GO_Q (humano) |
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Comandos lab |
| `docs/PLAN_3_MESES.md` | Roadmap |

## Qué está hecho vs bloqueado

| Hecho | Bloqueado (externo / humano) |
|-------|------------------------------|
| Operator UX + 4 actos + Decision Card | **H1** demo tercero → GO_Q |
| ML sealed LOFO **0.788** + weather ERA5 long **+0.019** · thrash **FREEZE** | **Más IF chain_honest** (siguiente cola ML) |
| Tobarra KEEP **KILL** · fusion OFF | 3ª ancla / perímetro nacional / O5 grade A |
| Pack third-party + replay | Piloto cliente real |
| API mínima POST /v1/decide | Auth / 99.9% uptime (sueño) |

## Comando mínimo de decisión

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front decide                    # vacío → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\open_if\emsr578 --require-ops-for-go
```

## App de sala de mando (espectacular)

```powershell
python scripts\build_commander_app.py
start docs\commander\index.html
```

Teclas: **1–4** packs · **R** copiar radio · **F** fullscreen.

## API + acta + políticas

```powershell
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --use-ml-v34 --policy field_ops
python -m wildfire_front serve-decide --port 8765
```
