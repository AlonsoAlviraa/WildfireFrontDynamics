# Reliability Gate Report — terceros (1–3 pp)

**As of:** 2026-08-04  
**Audience:** demo externa / auditor técnico  
**Machine samples:** `docs/RELIABILITY_GATE_REPORT.json` (suite-only; **no** field unlock) · this-run: `outputs/*/reliability_gate_report.json` o pack `outputs/demo_third_party/`  
**Plan:** Graph v6.1 · E2 + **R-STACK-L** + **R-UQ1**

> Fire prediction is **not** 99.9999% accurate.  
> “Five-nines” en este repo = **no silent GO** sin gates bajo automatización (R1–R4), no acierto de propagación.

---

## 1. Qué medimos (ops TIR multi-pasada) — **R-STACK-L Lampman**

La capa **Ops térmico** estima ROS a partir de secuencias LWIR multi-pasada (geometría de frente, multi-estimador, gates de observabilidad).  
Ese **método** está alineado con literatura reciente de comportamiento del fuego con UAS+TIR.

**Cita metodológica (no SLA):** Lampman et al., *Leveraging drone-based thermal imagery and artificial intelligence to advance wildland fire behavior quantification and prediction*, Int. J. Wildland Fire (2026) — [IJWF WF25133](https://connectsci.au/wf/article/35/5/WF25133/272342/Leveraging-drone-based-thermal-imagery-and).  
Reportan predicciones de corto plazo muy precisas en un **fuego prescrito de pastizal** (un sitio, un combustible) y advierten **generalización limitada**.

| Uso legítimo | Uso ilegítimo |
|--------------|---------------|
| Ancla **metodológica** repeat-pass TIR → ROS (± FI/FRP en paper) | MAE/R² del paper como **SLA de Tobarra/Hellín** |
| Reforzar proceso + abstención + proveniencia (R1–R4) | Desbloquear `field_unlock` o inventar Vp |

**Párrafo demo:** WFD adopta el principio de medición geométrica desde LWIR como capa Ops, **sin** trasladar cifras de error del pastizal prescrito a incendios mediterráneos operativos ni usar ML de máscaras como sustituto del ROS observado.

---

## 2. Dónde el sistema **acierta** (Tobarra)

| Campo | Valor (repo) | Evidencia |
|-------|--------------|-----------|
| IF | Tobarra 2024-08-02 | `data/infocam_anchors.json` · observatorio pack |
| Grade estructural | **A** | multi-frame LWIR + ROS primaria |
| ROS primaria | **~5.71 m/min** | `outputs/observatorio/tobarra_20240802/` |
| Ancla Vp INFOCAM | **7 m/min** | ratio ≈ **0.82** ∈ [0.5, 2] |
| GO_MES (mínimo) | **true** | `docs/GO_MES_VERDICT.md` |

En política **`field_ops`**, con ops multi-frame grade A/B + gate **this-run** PASS, la Decision Card puede emitir **GO** (confianza de producto, **no** orden táctica de despacho).

Sector ROS (orientativo, ya exportado en ops Tobarra): head ≈ 5.99 · flank ≈ 5.71 · rear ≈ 2.78 m/min — ver `docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md`.

---

## 3. Dónde se **abstiene** — **R-UQ1 Orion mapping**

Paper: Kondylatos / Orion-AI-Lab — *Uncertainty-Aware Deep Learning for Wildfire Danger Forecasting* ([arXiv:2509.25017](https://arxiv.org/abs/2509.25017), [código](https://github.com/Orion-AI-Lab/uncertainty-wildfires)).  
Separan incertidumbre **epistémica** (modelo) y **aleatoria** (datos) y usan **rechazo** cuando u es alta.

### Mapeo a Decision Card WFD (nunca labels EVACUATE)

| Orion-style | Definición en WFD | Decisión |
|-------------|-------------------|----------|
| **Aleatoria (u_data)** baja + ops fuerte | grade A/B, n_frames≥2, ROS>0, ratio Vp en banda | **GO** posible (field_ops + gate) |
| **Aleatoria** media / open-only | CEMS perímetro sin LWIR ops | **HOLD** (monitorización) |
| **Epistémica** alta o solo ML lab | holdout IoU / ML-only sin ops; fusión live OFF en field_ops | **ABSTAIN** |
| Fuentes vacías / conf &lt; umbral | sin sources o `confidence_pred` bajo | **ABSTAIN** |
| Gate R1–R4 no verificado | this-run `system_reliability_pass=false` | **ABSTAIN** (fail-closed field_ops: GO→ABSTAIN) |

**field_ops · ML-only:** `allow_ml_only_hold=false` → **ABSTAIN** (no HOLD “suave” de investigación).  
**`field_ops.allow_ml_live_in_fusion` = false** — fusión RGB–TIR de detección ≠ fusión ML en la card; no se reclama ML-live táctico.

---

## 4. Hellín — grade **B** honest

| Campo | Valor |
|-------|-------|
| Vp boletín | **50 m/min** |
| ROS pack best-of-run | **~27.9 m/min** |
| Ratio | **~0.56** (en banda [0.5, 2]) |
| Grade estructural | **B** |
| Grade A eligible | **NO** |
| GO_MES+ / O5 | **false / OPEN** |

No se reescala ROS a Vp en silencio. No joint-k Tobarra(7)↔Hellín(50).  
Detalle: `docs/HELLIN_TRACK_A_SCORECARD.md` · `docs/P1_HELLIN_ENG_STATUS.md`.

---

## 5. Fuel Med corpus / hybrid — **no** despacho táctico

Corpus ~93 estudios Med/ES (`docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md`).  
Hybrid α / Rothermel-lite / envelope 15–60 min son **priors de escenario** (peso 0 en fusión field_ops de la card).  
Sin viento medido o sin ops TIR → **no** vender prior de fuel como ROS de frente validado.

---

## 6. Qué **no** reclamamos

| Claim | Estado |
|-------|--------|
| **GO_MES+** | false |
| **GO_Q** sin acta tercero | partial / no |
| IoU catálogo = ROS táctico | **prohibido** (E9) |
| Lampman MAE = SLA Tobarra | **prohibido** |
| Hellín grade A | no (B honest) |
| Technosylva-class landscape sim como producto sala | no |
| `ml_product_go` / fusion field_ops ON | **false / OFF** |
| EVACUATE/SAFE como renombre de GO/HOLD/ABSTAIN | **nunca** |

---

## 7. Cómo reejecutar (Metrics Hub · gate · E3)

```powershell
cd <repo>
$env:PYTHONPATH = "."

# Metrics Hub + Decision Card agregado
python scripts/build_metrics_hub.py

# Reliability gate (suite → outputs/; docs sample queda suite_only)
python scripts/reliability_gate.py

# Pack terceros (E1) + replay (E3)
python scripts/build_demo_third_party_pack.py
python scripts/run_third_party_replay.py --bundle outputs/demo_third_party
# exit 0 ⇔ replay_ok

# Equivalente CLI
python -m wildfire_front replay-decide --bundle outputs/demo_third_party
```

**Pack offline:** `outputs/demo_third_party/` o zip `dist/demo_third_party_YYYYMMDD.zip`  
README del pack: validación en 5 min sin red (salvo dependencias Python del repo).

### Límites de E3 (no oversell)

| E3 dice | E3 **no** dice |
|---------|----------------|
| `replay_ok` = decisión + `output_hash` reconstruibles desde `replay_sources` | Autenticidad criptográfica del zip |
| Detecta tamper **parcial** (p. ej. solo `expected_decision`) | Anti-forgery si se reescriben métricas + expected_* + gate embebido a la vez |
| Offline consistency del pack emitido | Sustituto de gate this-run en incidente live / HTTP |

El gate embebido en `replay_sources` permite re-verificar un **GO field_ops ya emitido** sin fail-closed a ABSTAIN; **no** re-deriva R2 desde ops en el momento del replay. HTTP sigue rechazando gates inline no confiables.

---

## 8. R1–R4 (recordatorio)

| Check | Significado |
|-------|-------------|
| R1 determinism | Misma entrada → misma decisión/hash |
| R2 gates | Floor ops multi-frame (grade A/B, n≥2, ROS&gt;0) en this-run |
| R3 abstention | ABSTAIN cuando conf/policy lo exigen |
| R4 provenance | schema + input/output hashes |

`docs/RELIABILITY_GATE_REPORT.json` es **suite-only** (`field_unlock=false`).  
Para field_ops GO se exige informe **this-run** (`provenance.kind=this_run`, `event_id` alineado).

---

## Referencias internas

| Doc | Rol |
|-----|-----|
| `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` | Lampman + Orion doctrina |
| `docs/METRICS_HONESTY_IOU_NE_ROS.md` | IoU ≠ ROS |
| `docs/GO_MES_VERDICT.md` | GO_MES true mínimo |
| `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` | Acta humana H1 (fuera de eng) |
| `docs/fire_intel/OSS_DATASETS_CATALOG_2026.md` | OSS/datasets catalog |
