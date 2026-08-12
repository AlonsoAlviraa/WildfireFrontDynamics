# Cheatsheet demo 12 min — WFD

## Rails (decir en voz alta)

GO_MES **true** (mínimo) · GO_Q **partial** (H1 demo) · field_ops ML fusion **OFF** · ml_product_go **true** (lab only) · Tobarra LOFO **KILL** (lab) · **ABSTAIN = feature**

## Setup

```powershell
cd <repo>
$env:PYTHONPATH = "."
```

**Modo operario (preferido):** `python -m wildfire_front operator`  
**Ensayo 4 actos:** `python -m wildfire_front operator do --all` · `make operator-path`  
CLI teach path: `python -m wildfire_front teach` · gates: `python -m wildfire_front show`

## Primary surface (third party)

```powershell
# One-shot presentador (Live Ops + pack/reliability check + serve loopback)
python -m wildfire_front app --demo-day

# Alternativas
python -m wildfire_front app --fire _sla_measure --serve
python -m wildfire_front app --fire _sla_measure --open   # file:// estático (copia CLI)
# artefacto: outputs/app/index.html
```

En la SPA C2: **Estado · Decidir · Acta** (Live Ops con `--serve` / `--demo-day`) · Fácil|Pro · Fusion OFF · GO_Q partial.

## Timeline 12 min

| Min | Acto | Qué haces | Comando / path |
|----:|------|-----------|----------------|
| 0–1 | Gancho | Rails en voz alta + ABSTAIN | (sin comando) |
| 1–3 | SPA C2 | Abrir consola industrial (primary, live) | `python -m wildfire_front app --demo-day` → click Estado/Decidir/Acta |
| 3–5 | 1 Ver | multi-CCAA HTML (3 contratos) | `python scripts\build_demo_multi_ccaa.py` → `outputs\demo_multi_ccaa\index.html` |
| 5–7 | 2 Callarse | pilot honesty (field_ops se calla) | `python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot` |
| 7–9 | 3 Decidir | Decision Card + explain | `python -m wildfire_front decide --policy field_ops --explain` |
| 9–11 | 4 Probar | pack + replay_ok | `python -m wildfire_front demo-third-party` |
| 11–12 | Límites | H1 cierra GO_Q; eng no | `docs\ACTA_DEMO_TERCERO_TEMPLATE.md` |

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

1. No field_ops ML live fusion ON  
2. No ml_product_go true  
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

**No marcar GO_Q sin H1 firmada.** Eng (teach-cli / pack / replay) no cierra GO_Q.

## Product CLI (v7 teach)

```text
wildfire-front teach [--act N] [--json]
wildfire-front show [--open] [--json]
wildfire-front demo-third-party [--no-replay] [--skip-build] [--no-zip]
wildfire-front decide --policy field_ops --explain
```
