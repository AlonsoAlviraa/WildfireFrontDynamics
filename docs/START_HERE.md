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
| ML U1 TEST honest (lab) | mean IoU ~**0.86** · sel@80 ~**0.90** · ECE ~**0.15** |
| Catalog holdout IoU (provenance only) | **0.8963** — not live certainty |
| Packs open CEMS | **5** (hasta ~29000 ha) |

## ML-first (honest bullets)

1. **Pitch with U1 TEST honest** metrics (mean IoU eval ~**0.86**, selective@80 ~**0.90**, ECE ~**0.15**) from `docs/ML_PRODUCT_SCORECARD.json` / `docs/ML_U1_PROMOTE_RECORD.json`. Catalog holdout **0.8963** is **provenance only** — protocol-clean next-day **mask** research quality; **not** live fire certainty, **not** ops ROS, **not** Tobarra tactical speed, **not** REDIAM O2 perimeter truth.
2. **Live confidence** comes from ensemble disagreement + **VAL-fit** Head A calibrator (frozen JSON); the Decision Card can **HOLD** or **ABSTAIN** when patch reliability is low (ML-only / research paths). Demo: `python scripts/run_ml_live_card_demo.py --mode offline`.
3. **`research_open` live fusion is experimental** after U1 TEST honest promote; **`field_ops.allow_ml_live_in_fusion` remains false**. VAL-only U1 is a **lab** diagnostic and does not alone promote fusion.
4. Dual product: ML mask product ≠ ops `front_dynamics_v1`. Promote checklist: `scripts/promote_ml_live_fusion.py` (never flips policy without `--apply-policy`, and only `research_open`).
5. **Lab claim surface** (not tactical): scorecard + abstain/ECE note `docs/ML_LIVE_ABSTAIN_ECE_NOTE.md` — research quality only; no ROS / no field_ops.

## Documentos clave

| Doc | Para qué |
|------|----------|
| **`docs/CURSO_WFD_PARA_DESCONOCIDOS.md`** | **Curso completo** (qué es cada cosa, cómo usarlo) |
| `docs/PORTAL.html` | **Ver todo** |
| `docs/ML_PRODUCT_SCORECARD.json` | **Lab claim surface** (ML product; not tactical) |
| `docs/START_HERE.md` | Este resumen |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Venta |
| **`docs/funding/README.md`** | **Sin empresa → partners y ayudas UE/ES (playbook)** |
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Comandos largos |
| `docs/PLAN_3_MESES.md` | Roadmap realista |
| `docs/SUENOS_MAXIMOS.md` | Techo de resultados y funciones |

## Qué está hecho vs bloqueado

| Hecho | Bloqueado (externo / humano) |
|-------|---------------------|
| ML v34 U1 honest + ops Tobarra A | **2ª ancla INFOCAM (O1)** — Cardoso |
| Decision Card + Metrics Hub + policies | Perímetro nacional oficial (O2) |
| Piloto honesty multi-pack + demo multi-CCAA | **Demo con tercero** + acta 1 pág |
| FDC en incident + API `/v1/decide` | Auth / 99.9% uptime (sueño) |
| Acta forense + radio + replay | PDF firmado (sueño) |
| Graph v2 external-unblock ready | Gmail MCP re-auth (token Testing) |

**Estado canónico:** [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) · scorecard mes: [`SCORECARD_MES_1.md`](SCORECARD_MES_1.md)

## Fuel stack + AEMET Tobarra (PR-α / PR-β)

```powershell
# PR-α core physics tests
pytest tests/test_fuel_rothermel_lite.py tests/test_fuel_dem.py tests/test_fuel_map.py `
  tests/test_fuel_calibration.py tests/test_fuel_sector_weather.py tests/test_fuel_sector_slope_aemet.py -q

# PR-β envelope + AEMET (offline fixtures + optional live key in .env)
pytest tests/test_aemet_weather.py tests/test_fuel_envelope.py `
  tests/test_fuel_envelope_scorecard.py tests/test_pr_beta_envelope_aemet.py -q
python scripts/run_tobarra_aemet_pipeline.py
```

Plan de aterrizaje: `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md`.

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
