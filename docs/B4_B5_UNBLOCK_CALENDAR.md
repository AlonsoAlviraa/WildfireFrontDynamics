# B4 / B5 — Calendario de desbloqueo (no más flags)

> **As of:** 2026-08-10  
> **Regla:** eng **no** inventa grade A ni catastro nacional. Solo agenda, scorecards y follow-up.

## Estado honesto

| ID | Qué | Hoy | Qué desbloquea |
|----|-----|-----|----------------|
| **B4** | 2º incendio **grade A** ops | Tobarra **A** · Hellín **B** (ratio in-band pero grade estructural B) | Nuevo pack con ancla Vp/ha + perímetro usable **o** mejora Hellín a A sin k-fit silencioso |
| **B5** | O2 perímetro **nacional** | **BLOCKED** (EGIF/CCAA/FOI) | Respuesta transparencia / partner / open proxy (CEMS) sin vender catastro oficial |

## Calendario propuesto (humano)

| Día | Acción | Owner | Artefacto |
|-----|--------|-------|-----------|
| **D0** | Revisar `docs/OUTREACH_SEND_REPORT_20260810.md` (19 SENT) | humano | log Gmail |
| **D0+2** | Follow-up **solo** a no-respuesta prioritarios (PT ICNF/AGIF, Aragón, Navarra, Valabre) — **no spam** CyL silence | humano | plantillas `OUTREACH_DRAFTS_READY_*` |
| **D0+3** | Call 20 min con GEACAM / Pablo si hay hueco (pack Tobarra ya A) pedir **2º IF completo** | humano | `docs/CONTACTOS_OUTREACH.csv` |
| **D0+7** | Re-score Hellín Track A si llega media nueva | eng | `python scripts/score_hellin_track_a.py` (si pack existe) |
| **D0+14** | CyL silence window ~17 ago — reabrir 4082 **solo entonces** | humano | `docs/SOLICITUD_TRANSPARENCIA_CYL.md` |
| **Contínuo** | EFFIS/CEMS proxy como **open track** (no cierra O2 oficial) | eng | `docs/O2_HAUSDORFF_BLOCKED.md` |

## Grade A eligibility (B4) — checklist

Para reclamar **2º grade A** hace falta **todas**:

1. Structural grade **A** en `front_dynamics` scorecard  
2. ROS/Vp ratio en banda **[0.5, 2.0]**  
3. Ancla Vp/ha **documentada** (no inventada)  
4. **No** calibrar un solo `k` conjunto Tobarra(7)+Hellín(50)  
5. Scorecard JSON + MD commiteable bajo `docs/` o `outputs/observatorio/`

Hellín hoy: grade **B**, ratio **0.559** in-band → **no A**. Ver `docs/HELLIN_TRACK_A_SCORECARD.md`.

## Comandos eng (sin flags de producto)

```powershell
# Estado Hellín
Get-Content docs/HELLIN_TRACK_A_SCORECARD.md -Head 40

# Re-score si hay pack (falla honestamente si falta data)
python scripts/score_hellin_track_a.py

# Outreach batch ya corrido 2026-08-10 — no re-enviar sin política
# python scripts/send_outreach_if_completo_batch.py   # solo operador
```

## Qué NO hacer

- Subir `GO_MES+` o inventar “nacional OK”  
- Redefinir grade A para un showcase  
- Más thrash ML Tobarra KEEP (B6 KILL)  
- Flags nuevos en lugar de datos  

## SSOT

- Bottlenecks: `docs/BOTTLENECKS_B1_B6_STATUS.md`  
- Audit industria: `docs/AUDIT_BOTTLENECKS_B1_B10_INDUSTRY.md`  
- CURRENT_STATE: `docs/CURRENT_STATE.md`
