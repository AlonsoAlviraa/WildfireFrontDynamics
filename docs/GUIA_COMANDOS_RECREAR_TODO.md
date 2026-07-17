# Guía de comandos — recrear, enseñar y demostrar todo

**Raíz del proyecto (Windows):**

```text
C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
```

**Shell recomendado:** PowerShell o `cmd`.  
**Siempre empieza así:**

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"
```

En `cmd.exe`:

```bat
cd /d C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
set PYTHONPATH=C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
```

Python usado en el desarrollo (ajusta si el tuyo es otro):

```powershell
python --version
# Si hace falta:
# C:\Users\Mariano\AppData\Local\Programs\Python\Python311\python.exe
```

---

## 0. Instalación (una vez por máquina)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics

python -m pip install -e ".[dev]"
python -m pip install shapely pyproj

# Pesos duales (NDWS + CLM) si faltan en models/
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\install_dual_weights.py
```

---

## 1. Productos ML — listar y evaluar

### 1.1 Listar productos (v34, v28, NDWS)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\predict_spread.py --list-products
```

### 1.2 Evaluar ensemble CLM v34 en holdout (muestra)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\predict_spread.py `
  --product clm_ensemble_v34 `
  --npz C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\clm_ndws_patches\holdout_v1\test `
  --eval `
  --max-patches 20
```

### 1.3 Evaluar single CLM v28

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\predict_spread.py `
  --product clm_v28 `
  --npz C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\clm_ndws_patches\holdout_v1\test `
  --eval `
  --max-patches 20
```

### 1.4 Smoke ML producción (v28 + v34)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\smoke_production_products.py `
  --products clm_v28,clm_ensemble_v34 `
  --max-patches 12
```

**Qué enseñar:** IoU holdout v34 ≈ **0.8963**, Δ vs copy ≈ **0.2545** (manifest).

---

## 2. Ops — incident runtime (sin satélite)

### 2.1 Smoke sintético (siempre funciona, sin datos reales)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\smoke_incident_runtime.py
```

### 2.2 Doctor (pre-vuelo) sobre Tobarra

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front incident doctor `
  --inbox C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\tobarra_reprojected_lwir `
  --masks C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\tobarra_lwir_masks `
  --event-id tobarra_20240802
```

### 2.3 Update una vez (Tobarra → outbox)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front incident update `
  --inbox C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\tobarra_reprojected_lwir `
  --masks C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\artifacts\tobarra_lwir_masks `
  --work-dir C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\tobarra_demo `
  --event-id tobarra_20240802 `
  --ref-name "INFOCAM Tobarra" `
  --ref-vp-m-min 7 `
  --ref-area-ha 39 `
  --force
```

Tras el update, el **Decision Card** está en el outbox (unidad de venta):

```
outputs\incidents\tobarra_demo\outbox\fire_decision_card.json
outputs\incidents\tobarra_demo\outbox\fire_decision_card.md
```

Opciones de fusión:

```powershell
# + pack open CEMS en la misma card
python -m wildfire_front incident update `
  --inbox ... --work-dir ... --force `
  --open-pack C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578

# SLA sintético (debe ser << 10 min)
python scripts\measure_incident_sla.py
```

### 2.3b API mínima Decision Card (HTTP local)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front serve-decide --host 127.0.0.1 --port 8765
```

En otra terminal:

```powershell
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/v1/decide `
  -H "Content-Type: application/json" `
  -d "{\"event_id\": \"demo\", \"use_ml_v34\": true, \"open_pack\": \"outputs/open_if/emsr578\", \"require_ops_for_go\": true}"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\measure_decide_api_latency.py
```

### 2.3c Acta forense + radio + replay (M2.9)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front export-acta `
  --work-dir C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\tobarra_demo `
  --operator "sala_demo"

python -m wildfire_front replay-decide `
  --work-dir C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\tobarra_demo
# debe imprimir replay_ok: True
```

### 2.4 Status del incidente

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front incident status `
  --work-dir C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\tobarra_demo
```

### 2.5 Field kit Windows (watch en vivo)

```bat
cd /d C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
scripts\run_incident.cmd D:\drops\inbox C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\IF_DEMO
```

Una sola pasada:

```bat
cd /d C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
scripts\run_incident.cmd D:\drops\inbox C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\IF_DEMO --once
```

Doc: `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\FIELD_KIT_INCIDENT.md`

---

## 3. Pista B — IF open data CEMS (sin Heligrafics)

### 3.1 Construir un pack (ej. EMSR578)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_open_if_pack.py `
  --activation EMSR578
```

### 3.2 Otros packs útiles

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_open_if_pack.py --activation EMSR583
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_open_if_pack.py --activation EMSR581
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_open_if_pack.py --activation EMSR632
```

### 3.3 Índice multi-pack + comparativa dual vs CLM-solo

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_open_if_index.py
```

### 3.4 Overlay FIRMS (hotspots 24h; puede ser 0 en IF históricos)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\overlay_firms_on_open_pack.py `
  --pack C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578
```

### 3.5 Abrir mapas y brief

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics

start C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\index.html
start C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578\map.html
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578\operator_brief_open_if.md
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578\manifest.json
```

Doc: `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PISTA_B_OPEN_IF.md`

---

## 4. Producto de decisión (lo que se vende)

### 4.1 Reliability gate (abstención / “cinco nueves” de sistema)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\reliability_gate.py
```

Enseñar: **no es 99.9999% del fuego**; es riesgo residual de GO silencioso ≤ 1e-6 en tests.

### 4.2 Metrics Hub (todas las métricas)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\build_metrics_hub.py

start C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\METRICS_DASHBOARD.html
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\METRICS_HUB.md
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\FIRE_DECISION_CARD.json
```

### 4.3 Decision Card por CLI

**Vacío → ABSTAIN:**

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front decide --event-id demo_vacio --json
```

**ML + open CEMS → suele HOLD:**

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front decide `
  --event-id demo_open `
  --use-ml-v34 `
  --open-pack C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr578 `
  --require-ops-for-go `
  --output C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\demo_decision_open.json `
  --json
```

**Con incidente Tobarra (si ya corriste update):**

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python -m wildfire_front decide `
  --event-id tobarra_20240802 `
  --use-ml-v34 `
  --work-dir C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\incidents\tobarra_demo `
  --open-pack C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\emsr632 `
  --output C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\demo_decision_full.json `
  --json
```

---

## 5. Demos “para enseñar / vender”

### 5.1 Demo dual (ops smoke + opcional ML)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

# Solo ops (rápido)
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\demo_dual_product.py --skip-ml

# Ops + ML
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\demo_dual_product.py
```

### 5.2 Demo sellable (índice open + smokes)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

# Si los packs ya existen (no re-descarga CEMS)
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\demo_sellable_product.py --skip-build

# Forzar packs (lento; descarga CEMS)
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\demo_sellable_product.py `
  --activations EMSR578,EMSR583,EMSR581,EMSR632
```

### 5.3 Brief de operador (ejemplo)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\generate_operator_brief.py --from-smoke
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\BRIEF_SMOKE_EXAMPLE.md
```

---

## 6. Plan 3 meses — revisar y adaptar

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

# Solo revisar estado
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\run_plan_cycle.py

# Ejecutar gates M1 + revisar
python C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\scripts\run_plan_cycle.py --execute-m1

notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PLAN_3_MESES.md
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PLAN_3_MESES_STATUS.json
notepad C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PLAN_3_MESES_REVIEW_LOG.md
```

---

## 7. Tests (seguridad de producto)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

# Producto decisión + catálogo + open helpers
python -m pytest `
  C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests\test_confidence_product.py `
  C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests\test_decide_cli.py `
  C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests\test_product_catalog.py `
  C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests\test_ensemble_temperatures.py `
  C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests\test_open_if_pack.py `
  -q

# Suite completa (puede fallar tests legacy que piden models\v3.pt)
python -m pytest C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\tests -q
```

### Make (si tienes make en PATH)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
make reliability
make metrics-hub
make product-gate
make smoke-ops
```

---

## 8. Recreación “show completo” (orden de una demo de 15–20 min)

Copia-pega este bloque entero en PowerShell:

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"
$ROOT = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"

Write-Host "`n=== 1) Productos ML ===" -ForegroundColor Cyan
python "$ROOT\scripts\predict_spread.py" --list-products

Write-Host "`n=== 2) Reliability (no silent GO) ===" -ForegroundColor Cyan
python "$ROOT\scripts\reliability_gate.py"

Write-Host "`n=== 3) Metrics Hub ===" -ForegroundColor Cyan
python "$ROOT\scripts\build_metrics_hub.py"

Write-Host "`n=== 4) Ops smoke ===" -ForegroundColor Cyan
python "$ROOT\scripts\smoke_incident_runtime.py"

Write-Host "`n=== 5) Open IF index (packs ya construidos) ===" -ForegroundColor Cyan
python "$ROOT\scripts\build_open_if_index.py"

Write-Host "`n=== 6) Decision Card: vacio = ABSTAIN ===" -ForegroundColor Cyan
python -m wildfire_front decide --event-id show_empty

Write-Host "`n=== 7) Decision Card: ML + open = HOLD ===" -ForegroundColor Cyan
python -m wildfire_front decide --event-id show_open --use-ml-v34 --open-pack "$ROOT\outputs\open_if\emsr578" --require-ops-for-go

Write-Host "`n=== 8) Plan 3 meses cycle ===" -ForegroundColor Cyan
python "$ROOT\scripts\run_plan_cycle.py"

Write-Host "`n=== Abrir dashboard y mapas ===" -ForegroundColor Green
start "$ROOT\docs\METRICS_DASHBOARD.html"
start "$ROOT\outputs\open_if\index.html"
start "$ROOT\outputs\open_if\emsr578\map.html"
start "$ROOT\outputs\open_if\emsr632\map.html"
```

---

## 9. Qué archivo abrir para explicar cada cosa

| Tema | Ruta completa |
|------|----------------|
| Plan 3 meses | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PLAN_3_MESES.md` |
| Estado del plan | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PLAN_3_MESES_STATUS.json` |
| Rediseño de pago | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PRODUCT_REDESIGN_PAID_VALUE.md` |
| One-pager | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\ONEPAGER_COMERCIAL_ES.md` |
| Métricas todas | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\METRICS_HUB.md` |
| Dashboard | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\METRICS_DASHBOARD.html` |
| Decision card JSON | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\FIRE_DECISION_CARD.json` |
| Reliability report | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\RELIABILITY_GATE_REPORT.json` |
| Comparativa dual | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\COMPARE_CLM_VS_OPEN.md` |
| Pista B open | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\PISTA_B_OPEN_IF.md` |
| Field kit | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\FIELD_KIT_INCIDENT.md` |
| FIRE-RES mapa | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\docs\FIRE_RES_DELIVERABLES_MAP.md` |
| Manifest ML v34 | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\models\clm_ensemble\manifest.json` |
| Catalog productos | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\models\catalog.json` |
| Anclas INFOCAM | `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\data\infocam_anchors.json` |

---

## 10. Guion oral corto (2 minutos)

1. **Problema:** o hay dron (CLM) o hay satélite (CEMS); casi nadie une decisión + abstención + auditoría.  
2. **Muestra `decide` vacío → ABSTAIN** (el sistema se calla).  
3. **Muestra Metrics Hub** (todas las cifras).  
4. **Muestra mapa EMSR632** (miles de ha, sin NDA).  
5. **Muestra Tobarra ops** si hay tiempo (ROS local + ancla).  
6. **Cierra:** no vendemos el perímetro gratis de Copernicus; vendemos **cuándo confiar y cuándo no**, con métricas y hash.

---

## 11. Notas para no fallar en la demo

| Riesgo | Qué hacer |
|--------|-----------|
| Sin red | No re-descargar CEMS; usar `--skip-build` y packs ya en `outputs\open_if` |
| FIRMS = 0 puntos | Normal en IF de 2022 con CSV de **últimas 24 h** |
| pytest total falla en `v3.pt` | Usar solo tests de producto (sección 7) |
| PYTHONPATH | Sin él fallan imports de `wildfire_front` |

---

*Documento para enseñanza. Actualizar rutas si mueves el repo.*
