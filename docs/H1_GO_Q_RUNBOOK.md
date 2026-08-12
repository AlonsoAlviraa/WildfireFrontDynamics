# H1 / GO_Q runbook — demo tercero + acta

> **Gate:** M3.2 → cierra el bloqueante humano de **GO_Q** (junto con M3.4 eng-filled).  
> **Eng no cierra GO_Q.** Este runbook es para el presentador humano.  
> **As of:** 2026-08-11 · Graph v6.1 · GO_MES **true** · GO_Q **partial** · SPA industrial C2 primary

---

## Antes (prep, ~15 min)

1. **Rails** (no negociables en la call):
   - `GO_MES=true` · `GO_Q=partial` hasta firma  
   - `field_ops` ML fusion **OFF** · `ml_product_go=true` (**lab only**, ≠ field fusion)  
   - ABSTAIN / HOLD = feature, no fallo · **no inventar GO_Q true**  
2. **Prep one-shot eng (recomendado):**
   ```powershell
   python scripts/prepare_h1_demo_session.py
   # → docs/H1_DEMO_SESSION_READY.json + docs/H1_CALENDAR_INVITE.md
   # rails: go_q_met=false · field_ops_fusion=OFF · demo_entry=app SPA C2
   ```
3. **SPA industrial C2 (superficie third-party primaria — Live Ops):**
   ```powershell
   $env:PYTHONPATH="."
   python -m wildfire_front app --demo-day
   # o: python -m wildfire_front app --fire _sla_measure --serve
   # file:// estático: python -m wildfire_front app --fire _sla_measure --open
   ```
   En UI: **Estado · Decidir · Acta** (live con `--serve`/`--demo-day`) · Fácil|Pro · Fusion OFF · GO_Q partial.  
4. **Modo operario** (30 s — tablero + 4 actos):
   ```powershell
   python -m wildfire_front operator
   python -m wildfire_front operator checklist
   ```
   Esperado: semáforo **AMARILLO** (GO_Q partial) · checklist eng 7/7 · **no** reclamar GO_Q complete.  
5. **Ensayo eng path H3** (una vez, más pesado):
   ```powershell
   python scripts/run_h3_dry_run_path.py
   ```
   Esperado: `h3_eng_path_ok=true`, `h3_human_attestation_pending=true`, `go_q_met=false`.
6. **Cheatsheet 12 min:** `docs/CHEATSHEET_DEMO_12MIN.md`  
7. **Acta borrador:**
   ```powershell
   python scripts/prepare_h1_acta_draft.py
   ```
   → `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` (blanks para tercero).  
8. **Pack listo:** `outputs/demo_third_party/` + Reliability Report  
   `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`  
9. **Agendar** persona **externa** al repo (emergencias / uni / partner).  
   Sin tercero real **no hay H1**.

---

## Durante (~12–30 min)

| Min | Bloque | Artefacto |
|-----|--------|-----------|
| 0–2 | Gancho: rails + SPA C2 Live Ops | `python -m wildfire_front app --demo-day` → click Decidir |
| 2–5 | Dual: ops ≠ ML lab | `docs/PRODUCTO_DUAL.md` |
| 5–8 | Tobarra / Hellín honestidad | Honesty / scorecard |
| 8–10 | Multi-CCAA o portal (si hay tiempo) | `outputs/demo_multi_ccaa/` |
| 10–12 | Pack + replay en vivo | `python -m wildfire_front operator do --act 4` |
| cierre | Límites + ask | kill list verbal · GO_Q = falta acta |

**Kill list verbal (obligatorio):**  
no ROS inventado · no fusión ML live en field_ops · no vender lab `ml_product_go` como field GO · no “apagamos incendios con IA” · no Tobarra LOFO ~0.48 como producto.

---

## Después (cierre GO_Q)

1. **Rellenar acta real** (no el PENDING): copiar borrador a  
   `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md`  
   Campos **obligatorios** (sin placeholders):
   - **Fecha** `YYYY-MM-DD`  
   - **Presentador** (nombre)  
   - **Tercero (externo)** (nombre)  
   - Checklists §3–§4 + firmas §7  
2. **Registrar en plan** (script estricto):
   ```powershell
   python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
   ```
   - Exit **0** → actualiza M3.2 / H1 / GO_Q en `docs/PLAN_1_MES_GRAPH_V6_STATUS.json`  
   - Exit **2** → campos vacíos o placeholder; **no** muta status  
3. **No** pasar el draft `ACTA_DEMO_PENDING_HUMAN.md` al record script.  
4. Opcional: sello humano en informe M3.4  
   `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md`.

---

## Checklist rápido

- [ ] H3 eng dry-run verde  
- [ ] Cheatsheet ensayado  
- [ ] Tercero externo confirmado  
- [ ] Demo hecha en fecha real  
- [ ] Acta con nombre tercero + fecha + presentador  
- [ ] `record_h1_demo_complete.py` exit 0  
- [ ] Status: H1 DONE · M3.2 met · GO_Q complete  

---

## Paths canónicos

| Qué | Path |
|-----|------|
| **Modo operario** | `python -m wildfire_front operator` |
| UX loop log | `docs/OPERATOR_UX_LOOP_LOG.md` |
| Plantilla | `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` |
| Borrador eng | `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` |
| Guion 30 min | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| Cheatsheet 12 min | `docs/CHEATSHEET_DEMO_12MIN.md` |
| H3 dry-run report | `outputs/demo_third_party/H3_DRY_RUN_REPORT.md` |
| Status plan | `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` |
| Record H1 | `scripts/record_h1_demo_complete.py` |

**Honestidad:** inventar un tercero o firmar en vacío **rompe** el gate. El eng path solo prepara el escenario.
