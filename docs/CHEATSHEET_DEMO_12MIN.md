# Cheatsheet demo 12 min — WFD

## Rails (decir en voz alta)

GO_MES **true** (mínimo) · GO_Q **partial** (H1 demo) · field_ops ML fusion **ON** · ml_product_go **true** (lab) · Tobarra LOFO **KILL** (lab) · **ABSTAIN = feature** · fusion ON ≠ despacho

> **Dry-run ≠ acta.** Un ensayo eng / `scripts/dry_run_h1.py` **no** cierra GO_Q y **no** es acta H1 de tercero.

## KILL LIST VERBAL (obligatorio — decir en voz alta)

Operadores **deben** decir:

1. **No inventar ROS / Vp** — si no hay cite, el número no existe.
2. **fusion ON ≠ GO_Q complete ≠ despacho táctico.**
3. **No** «apagamos incendios con IA».
4. **Sealed LOFO ~0.79 no es certeza de campo.**
5. **Catalog 0.8963 es provenance only; IoU ≠ ROS.**
6. **ABSTAIN / HOLD son features**, no fallos.
7. **Solo 1 ancla grade-A (Tobarra).** Hellín sigue `pending_external`.

## Setup

```powershell
cd <repo>
$env:PYTHONPATH = "."
```

**Modo operario (preferido):** `python -m wildfire_front operator`  
**Ensayo 4 actos:** `python -m wildfire_front operator do --all` · `make operator-path`  
CLI teach path: `python -m wildfire_front teach` · gates: `python -m wildfire_front show`  
**Mapa de comandos:** `python -m wildfire_front commands` (aliases `spa` / `console` → `app`)  
**Checklist QA (CLI + SPA, todo lo clicable):** `docs/CHECKLIST_CLI_SPA_QA.md`

### SPA Live Ops (Estado → Decidir → Acta)

Con **serve** (loopback; Live Ops POST `/live/v1/*`):

```powershell
python -m wildfire_front app --fire _sla_measure --serve
# aliases: spa · console ·  --demo-day  (H1 presentador, no inventa GO_Q)
# abre http://127.0.0.1:8766/  →  pulse Estado · Decidir · Acta en la SPA
```

Sin serve (estático / file://): **no** HTTP 501 desnudo — la UI usa `liveUnavailableFallback`:
copia el CLI al portapapeles y deja el comando en **Último acto** (copy-CLI).

```powershell
python -m wildfire_front app --fire _sla_measure --open   # sin --serve
# En UI: Estado / Decidir / Acta → toast «CLI copiado · sin serve»
```

Rails SPA: field_ops ML fusion **ON** · conf. predicción **no es ROS** · IoU ≠ ROS · GO_Q partial.

### Ensayo eng en SPA (A6) — no es H1 tercero

En la consola (rail derecho) el bloque **Ensayo H1 eng** marca siempre `go_q_met=false`.
Escala **SR** = soporte/recomendación (S0–S3) — **no** vender field GO / fusion ON.

### E2E eng (W1-A) — V&V sidecar lectura

Panel **V&V eng** (`data-marker="vv-scorecard"`): si `work_dir` tiene `vv_scorecard.json` (#34, lo escribe `decide` / `run_vv_sidecar`), la SPA **solo lee**. Sin archivo → «sin sidecar». Field IoU/ROS/grade siempre **—**. No es score de campo ni GO_Q.

```powershell
python scripts/run_vv_sidecar.py --work-dir outputs/incidents/_sla_measure
python -m wildfire_front app --fire _sla_measure --open
# UI: panel V&V eng · eng_stub · fusion ON (cap 0.20 / abstain 0.45) · go_q_met=false · ≠ despacho
```

```powershell
# Preferido loopback:
python -m wildfire_front app --fire _sla_measure --serve
# o demo-day (sigue sin inventar GO_Q):
python -m wildfire_front app --demo-day
```

## Timeline 12 min

| Min | Acto | Qué haces | Comando / path |
|----:|------|-----------|----------------|
| 0–1 | Gancho | Rails en voz alta + ABSTAIN | (sin comando) |
| 1–4 | 1 Ver | multi-CCAA HTML (3 contratos) | `python scripts\build_demo_multi_ccaa.py` → `outputs\demo_multi_ccaa\index.html` |
| 4–6 | 2 Callarse | pilot honesty (field_ops se calla) | `python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot` |
| 6–9 | 3 Decidir | Decision Card + explain | `python -m wildfire_front decide --policy field_ops --explain` |
| 9–11 | 4 Probar | pack + replay_ok | `python -m wildfire_front demo-third-party` |
| 11–12 | Límites | H1/M3.2 cierra GO_Q; eng no | `docs\ACTA_DEMO_TERCERO_TEMPLATE.md` |

## 4 actos (copy-paste)

### Acto 1 — Ver (multi-CCAA)

```powershell
python -m wildfire_front operator do --act 1 --open
# equiv: python scripts\build_demo_multi_ccaa.py
```

Mensaje: mismos gates, 3 contratos (Tobarra OPS · Níjar AND · Caminomorisco EXT).

### Acto 2 — Callarse (pilot honesty)

```powershell
python -m wildfire_front operator do --act 2 --open
# equiv: python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot
```

Mensaje: field_ops puede ABSTAIN mientras research_open es más permisivo — **no es un bug**.

### Acto 3 — Decidir (Decision Card)

```powershell
python -m wildfire_front operator do --act 3
# equiv: python -m wildfire_front decide --policy field_ops --explain
```

Mensaje: fuentes vacías → ABSTAIN es correcto (lenguaje normal en pantalla).

### Acto 4 — Probar (pack + replay)

```powershell
python -m wildfire_front operator do --act 4
# equiv: python -m wildfire_front demo-third-party
```

Mensaje: `replay_ok` = consistencia forense offline, **no** autenticidad criptográfica.

## Kill list (5+)

1. fusion ON ≠ GO_Q complete ≠ despacho táctico  
2. No vender `ml_product_go` lab como field GO / despacho  
3. No inventar Vp/ha  
4. No IoU = ROS  
5. No GO_Q sin M3.2 / acta humana H1  
6. No `replay_ok` = firma de tercero  

## Pre-call (30 s)

```powershell
python -m wildfire_front show
# si pack MISSING:
python -m wildfire_front demo-third-party
```

## Después de la call

| Qué | Path |
|-----|------|
| Acta H1 | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` |
| Reliability report | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| Curso completo | `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` |
| START_HERE | `docs/START_HERE.md` |
| Checklist QA CLI + SPA | `docs/CHECKLIST_CLI_SPA_QA.md` |

**No marcar GO_Q sin H1 firmada.** Eng (teach-cli / pack / replay) no cierra GO_Q.

## Product CLI (v7 teach)

```text
wildfire-front teach [--act N] [--json]
wildfire-front show [--open] [--json]
wildfire-front demo-third-party [--no-replay] [--skip-build] [--no-zip]
wildfire-front decide --policy field_ops --explain
```
