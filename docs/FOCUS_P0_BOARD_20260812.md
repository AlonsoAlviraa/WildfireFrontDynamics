# P0 focus board — 2026-08-12

> **Scope:** solo estos 6 hilos. No thrash ML · no merge ruidoso · no outbound hasta Claims clear.  
> **Gates:** GO_Q **partial** · fusion **OFF** · eng no inventa GO_Q.

---

## Board

| # | Item | Owner | Status | Action now |
|---|------|-------|--------|------------|
| **1** | **PR #10 SPA** — hold hasta path de merge limpio | eng | **HOLD** | No merge a `main` mientras la base lleve secretos en **historia** git. Ver §1. |
| **2** | **Rotar tokens** históricos fuera de git | humano + eng | **OPEN** | Tokens/OAuth vistos en commits antiguos siguen en historia aunque el tree esté limpio. Ver §2. |
| **3** | **H1** tercero + acta | humano | **OPEN** (eng ready) | GO_Q partial hasta demo+acta firmada. Ver §3. |
| **4** | **Borrar “New Bot” vacío** (sidebar Grok Bot) | humano (UI Grok) | **OPEN** | App Grok Bot · hide/delete empty New Bot. Ver §4. |
| **5** | **Outbound marketing** embargado | Claims + humano | **EMBARGO** | Docs higienizados; **no send** hasta clear Claims Guardian. Ver §5. |
| **6** | **Hellín** — no promover sin cite | eng + humano | **SSOT promote = pending** | No grade A / O5 / pitch. Cite UNAP documentada; promote formal **pending**. Ver §6. |

---

## 1. PR #10 SPA — HOLD (merge path limpio)

| | |
|--|--|
| **PR** | https://github.com/AlonsoAlviraa/WildfireFrontDynamics/pull/10 |
| **Base actual** | `fix/b2-b3-flags-noise-20260810` (no `main`) |
| **Por qué hold** | Historia de la base incluye `1a709a3` (añadió dumps Gmail/outreach) y solo **después** `53ca905` (scrub del tree). El **tree tip está limpio**; la **historia del branch aún contiene blobs sensibles**. Mergear a `main` sin reescritura/squash controlado reintroduce secretos en el grafo de `main`. |
| **Qué sí se hizo en tip** | Live Ops 501 → copy-CLI fallback · scrub tree + `.gitignore` patrones |
| **Path limpio (cuando toque)** | 1) Rotar tokens (§2) · 2) Opción A: squash + filter-repo de la línea Live Ops **sin** dumps, rebasar sobre `main` actual (#9+#11) · Opción B: cherry-pick solo commits “code/docs limpios” a rama nueva desde `main` · 3) PR nuevo a `main` con CI verde · 4) Cerrar #10 como superseded |
| **No hacer** | Force-push a `main` · merge #10 “tal cual” · confiar solo en “deleted in tip” |

**Estado operativo:** **hold de merge** hasta path limpio + rotación tokens.

---

## 2. Rotar tokens históricos (fuera de git)

| Hecho | Detalle |
|-------|---------|
| Tree tip (rama SPA) | Scrub en `53ca905`: GMAIL audit bodies, outreach CSV/drafts/send logs, FOI rellena, etc. |
| Historia | Commits anteriores (p.ej. `1a709a3`) **siguen** en el objeto store de esa rama / forks / clones que ya pushearon |

### Checklist humano (obligatorio si hubo OAuth/activation en dumps)

- [ ] **Google / Gmail OAuth** usados con MCP Gmail: revocar en [Google Account → Security → Third-party access](https://myaccount.google.com/permissions) y re-auth limpio  
- [ ] Cualquier **API key / activation token** que apareciera en `GMAIL_*` audits → rotar en el proveedor  
- [ ] **GitHub PAT** si alguna vez se pegó en doc/log → revoke + nuevo  
- [ ] Confirmar clones locales/CI no re-suben archivos ignorados  
- [ ] (Opcional eng) `git filter-repo` / BFG sobre la rama Live Ops **antes** de merge a main — solo tras rotación  

**Eng no puede “borrar de internet” un push ya hecho sin rewrite + force coordinado.** Prioridad: **rotar secretos**, luego history rewrite si se mergea.

---

## 3. H1 tercero + acta (GO_Q partial)

| | |
|--|--|
| **Gate** | GO_Q = **partial** · `go_q_met=false` forever from eng |
| **Eng ready** | Sí (prep scripts, runbook, cheatsheet, Live Ops surface) |
| **Cierra GO_Q** | Solo: demo con **tercero externo** + **acta firmada real** (no `ACTA_DEMO_PENDING_HUMAN`) + `record_h1_demo_complete.py --acta <firmada>` exit 0 |

### Presentador (humano)

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front app --demo-day          # preferred
# fallback: python -m wildfire_front app --fire _sla_measure --serve
```

- Cheatsheet: `docs/CHEATSHEET_DEMO_12MIN.md`  
- Runbook: `docs/H1_GO_Q_RUNBOOK.md`  
- Invite: `docs/H1_CALENDAR_INVITE.md`  
- Acta plantilla: `docs/actas/ACTA_DEMO_PENDING_HUMAN.md` → copiar a `ACTA_DEMO_YYYYMMDD_<org>.md` y rellenar  

### Human next

1. Agendar tercero (no eng solo)  
2. Demo 12 min (kill list: no fusion · no ROS invent · no “IA apaga incendios”)  
3. Acta firmada  
4. `python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_….md`  

**No:** inventar GO_Q · firmar PENDING · saltar tercero.

---

## 4. Borrar “New Bot” vacío (sidebar Grok Bot)

| | |
|--|--|
| **Dónde** | App **Grok Bot** (producto xAI/Cursor), no el repo WFD |
| **Qué** | Placeholder / bot vacío **New Bot** en sidebar |
| **Acción** | UI: open bot → **Hide** o **Delete** · no crear otro vacío  
| **Roster canónico** | `docs/EMPRESA_BOTS_ROSTER_LEAN_2026-08-12.md` (15 bots con job) |
| **Deferred** | Field Ops, Weather, Funding — no re-crear como “New Bot” vacío |

Esto **no se arregla con merge git**; es higiene de la app Grok Bot.

---

## 5. Outbound marketing — EMBARGO

| | |
|--|--|
| **Estado** | **Embargado** hasta **Claims clear** (Claims Guardian / Honesty) |
| **Docs** | Higienizados en tree (no dumps de envío en tip SPA; outreach sensibles scrubbed) |
| **Permitido** | Redactar drafts **locales** · one-pager review · guion demo **sin publicar** |
| **Prohibido** | Send email/LinkedIn/campaña · publicar one-pager como “cerrado” · claim GO_Q complete / fusion ON / IoU=ROS / Tobarra LOFO como producto campo |

**Clear Claims =** review explícito de `docs/ONEPAGER_COMERCIAL_ES.md` (+ guion si se usa) con lista supported/invent, rails OK, humano aprueba envío.

Bot: **Claims Guardian** / **Marketing** solo draft (ver `docs/EMPRESA_BOTS_TRABAJADORES.md`).

---

## 6. Hellín — no promover sin cite (SSOT promote = **pending**)

| Campo | Valor honesto |
|-------|----------------|
| **Ancla en `data/infocam_anchors.json`** | `hellin_2024` tiene `status: confirmed` **con cite** UNAP boletín 2024-07-20 (Vp=50; ha 100\* *estimada no oficial*) |
| **Promote producto / O5 / grade A** | **PENDING** — no promover |
| **Ops grade** | Hellín track A → **B** estructural (`docs/GO_MES_VERDICT.md`, `docs/P1_HELLIN_ENG_STATUS.md`) |
| **O5 2º grade A** | **OPEN** — solo Tobarra es structural A |
| **Pitch / one-pager** | No vender Hellín como grade A ni ha oficial sin re-citar fuente y pie de página |

### Reglas

1. **No** reclamar GO_MES+ por Hellín.  
2. **No** k-fit silencioso para forzar grade A.  
3. **No** promover `area_ha=100` como EGIF/oficial (nota boletín: estimada).  
4. Re-promote solo con: cite verificable en disco/PDF + scorecard A real + decisión humana.  
5. SSOT de **promote** = **pending** aunque el campo `status` del ancla diga `confirmed` para O1 multi-ancla.

---

## Weekly check (solo este board)

```text
[ ] #10 still HOLD / tokens rotated?
[ ] H1: fecha tercero? acta path?
[ ] New Bot vacío eliminado en Grok Bot UI?
[ ] Marketing still embargo / Claims clear?
[ ] Hellín still no-promote?
```

---

## Non-goals this board

- Merge Dependabot / PR #12 operator conflicts  
- Tobarra KEEP reopen / ML thrash  
- Force-push secrets away without rotation  
- Outbound “por urgencia”  

---

*Board vivo. Actualizar status in-place; no crear paralelo de gates.*
