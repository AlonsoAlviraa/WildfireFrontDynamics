# Empieza aquí (2 minutos)

## Qué es esto (1 frase)

**Apoyo a la decisión en incendios** con tres piezas claras:

1. **Ops térmico** (si hay dron/LWIR) → ROS y brief
2. **Open CEMS** (si no hay dron) → perímetros públicos multi-día
3. **Decision Card** → GO / HOLD / **ABSTAIN** + métricas + auditoría

No es “otro mapa de Copernicus”. Es **cuándo confiar y cuándo callarse**.

## Abre esto

### Demo multi-CCAA vendible (recomendado para calls)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
.\scripts\open_demo_multi_ccaa.ps1
# o: python scripts\build_demo_multi_ccaa.py ; start outputs\demo_multi_ccaa\index.html
```

Portal: `outputs/demo_multi_ccaa/index.html` — Tobarra OPS + Níjar AND + Caminomorisco EXT, KPIs, gates, guion 12 min, pitch.

### Portal repo completo

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
| Packs open CEMS | **5** (hasta ~29000 ha) |
| Decisión ejemplo | **GO** (conf 0.76) |

## ML-first (honest bullets)

1. **Holdout IoU research quality** (v34 ~**0.8963**) — protocol-clean next-day mask metric; **not** live fire certainty and **not** ops ROS.
2. **Live confidence** comes from ensemble disagreement + VAL-fit Head A calibrator; the Decision Card can **HOLD** or **ABSTAIN** when patch reliability is low (ML-only / research paths).
3. **Fusion live weight stays OFF** until **U1** selective@80% beats random on VAL (`allow_ml_live_in_fusion_recommended`); production dual-product fuse does not promote ML into field fusion silently.

## Documentos clave

| Doc | Para qué |
|------|----------|
| `docs/PORTAL.html` | **Ver todo** |
| `docs/START_HERE.md` | Este resumen |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| **`docs/funding/README.md`** | **Sin empresa → partners y ayudas UE/ES (playbook)** |
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

## App de sala de mando (espectacular)

```powershell
python scripts\build_commander_app.py
start docs\commander\index.html
```

Teclas: **1–4** packs · **R** copiar radio · **F** fullscreen.

## Demo multi-CCAA (Tobarra · Níjar · Caminomorisco)

```powershell
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html
```

OPS gold CLM + O2 REDIAM AND + O2 RAI EXT · mismos gates · HOLD sin ancla.

## API + acta + políticas

```powershell
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --use-ml-v34 --policy field_ops
python -m wildfire_front serve-decide --port 8765
```
