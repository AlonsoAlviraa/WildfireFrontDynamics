# B4 / B5 — Calendario de desbloqueo (no más flags)

> **As of:** 2026-08-10  
> **Regla:** eng **no** inventa grade A ni catastro nacional. Solo agenda, scorecards y follow-up.  
> **Probe:** `python scripts/b4_b5_status_probe.py` → `docs/B4_B5_STATUS.json` (null grades if scorecards missing).

## Estado honesto

| ID | Qué | Hoy | Qué desbloquea |
|----|-----|-----|----------------|
| **B4** | 2º incendio **grade A** ops | **OPEN** — grades only from in-repo scorecards (`b4_b5_status_probe.py`); do not hardcode A/B without files | Nuevo pack con ancla Vp/ha + perímetro usable **o** scorecard grade A sin k-fit silencioso |
| **B5** | O2 perímetro **nacional** | **BLOCKED** (EGIF/CCAA/FOI) | Respuesta transparencia / partner / open proxy (CEMS) sin vender catastro oficial |

Historical operator context (may live outside this branch): Tobarra was previously scored A and Hellín structural B on other trees — **re-run probe after committing scorecards**; do not treat memory as measured evidence here.

## Calendario propuesto (humano)

| Día | Acción | Owner | Artefacto |
|-----|--------|-------|-----------|
| **D0** | Revisar outreach send log / report if present under `docs/OUTREACH_SEND_REPORT*.md` | humano | Gmail / report (no invented SENT counts) |
| **D0+2** | Follow-up **solo** a no-respuesta prioritarios (PT ICNF/AGIF, Aragón, Navarra, Valabre) — **no spam** CyL silence | humano | plantillas `OUTREACH_DRAFTS_READY_*` when available |
| **D0+3** | Call 20 min con GEACAM / partner si hay hueco; pedir **2º IF completo** | humano | `docs/CONTACTOS_OUTREACH.csv` when present |
| **D0+7** | Re-score Hellín Track A si llega media nueva | eng | `python scripts/score_hellin_track_a.py` (si pack existe) |
| **D0+14** | CyL silence window ~17 ago — reabrir 4082 **solo entonces** | humano | `docs/SOLICITUD_TRANSPARENCIA_CYL.md` when present |
| **Contínuo** | EFFIS/CEMS proxy como **open track** (no cierra O2 oficial) | eng | `docs/O2_HAUSDORFF_BLOCKED.md` when present |

## Grade A eligibility (B4) — checklist

Para reclamar **2º grade A** hace falta **todas**:

1. Structural grade **A** en `front_dynamics` scorecard  
2. ROS/Vp ratio en banda **[0.5, 2.0]**  
3. Ancla Vp/ha **documentada** (no inventada)  
4. **No** calibrar un solo `k` conjunto multi-IF  
5. Scorecard JSON + MD commiteable bajo `docs/` o `outputs/observatorio/`

When `docs/HELLIN_TRACK_A_SCORECARD.md` is missing on this branch, Hellín grade is **unknown** until scored and committed. Probe will set `hellin_structural_grade: null`.

## Comandos eng (sin flags de producto)

```powershell
# Honest B4/B5 snapshot (nulls if sources missing)
python scripts/b4_b5_status_probe.py

# Estado Hellín (if scorecard present)
Get-Content docs/HELLIN_TRACK_A_SCORECARD.md -Head 40

# Re-score si hay pack (falla honestamente si falta data)
python scripts/score_hellin_track_a.py
```

## Qué NO hacer

- Subir `GO_MES+` o inventar “nacional OK”  
- Redefinir grade A para un showcase  
- Hardcode Tobarra A / Hellín B without scorecards in-tree  
- Más thrash ML Tobarra KEEP (B6 KILL)  
- Flags nuevos en lugar de datos  

## SSOT

- Bottlenecks: `docs/BOTTLENECKS_B1_B6_STATUS.md`  
- Probe JSON: `docs/B4_B5_STATUS.json`  
- Audit industria / CURRENT_STATE when present in tree  
