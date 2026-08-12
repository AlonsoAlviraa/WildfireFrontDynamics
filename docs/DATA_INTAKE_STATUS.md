# Estado de Ingesta — Material Real de Incendios

> Última actualización: **2026-08-03**  
> Fuentes: GEA CyL + CLM + Dropbox real_if + open REDIAM/RAI/CEMS + **Pablo/GEACAM Tobarra + pack 0308 (Hellín/Estrella/Cardoso)**  
> Pipeline: `scripts/batch_process_fires.py`, `materialize_lwir_masks.py`, `scripts/eval_tobarra_pablo_perimeters.py`, `scripts/build_cardoso_timeline.py`  
> Snapshot: `docs/PROJECT_STATUS.md` · O1 recompute: `docs/O1_GOMES_RECOMPUTE_20260803.json`

---

## Resumen ejecutivo

| Estado | Cantidad |
|--------|----------|
| Completos (reproy + máscaras) | 6 IF (Tobarra, Cardoso, LA ACOM1/2, Hellín, Brazatortas, Retuerta) |
| Parcial | Polán (1 LWIR reproy, 0 máscaras) |
| Anclas INFOCAM **confirmed** | **2** (Tobarra Vp=7 + **Hellín** Vp=50 boletín UNAP) — **O1 multi-ancla PASS** |
| **O2 Tobarra ops (Pablo KMZ)** | **PARTIAL_GO** — 2 perímetros activos multi-hora (no catastro nacional) |
| **O2 multi-IF ops (Pablo 0308)** | Hellín KMZ + La Estrella KMZ + Cardoso multi-día — no EGIF |
| Open multi-CCAA demo | Tobarra OPS + Níjar AND + Caminomorisco EXT |
| QA flags | Retuerta (ver `RETUERTA_QA_FLAG.md`) |

---

## Inventario por incendio (artifacts/)

| Incendio | Reproy LWIR | Máscaras | QA / notas | Listo ops | Listo ML parches |
|----------|------------:|---------:|------------|-----------|------------------|
| `tobarra` | 35 | 35 | Grado A con ancla Vp=7, ha=39 | sí | holdout train |
| `hellin_2024` | 16 | 16 | **Ancla confirmed** Vp=50, ha=100* (boletín UNAP); KMZ ~93.7 ha; front_dynamics grade A **pendiente** | parcial ops | masks ok |
| `cardoso_2025` | 85 | 79 | Ancla Vp pendiente; **timeline KMZ multi-día** (proxy Δha) | sí | holdout test / LOFO |
| `la_estrella_acom1_2024` | 199 | 181 | Ancla pendiente | sí | LOFO / holdout val |
| `la_estrella_acom2_2024` | 67 | 17 | Máscaras << frames | parcial | parcial |
| `hellin_2024` | 36 | 16 | Ancla pendiente | parcial | no en holdout_v1 |
| `retuerta_2025` | 10 | 8 | **QA flag** área/FOV | flag | no confiar sin clean |
| `brazatortas_2025` | 16 | 8 | Sin ancla | parcial | candidato LOFO futuro |
| `polan_2025` | 1 | 0 | Material insuficiente | no | no |

### Open / no-LWIR

| Pack / evento | Tipo | Ancla | Notas |
|---------------|------|-------|-------|
| CEMS EMSR* | open perimeter | n/a | Pista B proxy O2 |
| REDIAM Andalucía / Níjar | open industrial | no Vp ops | O2 AND |
| RAI Extremadura 2025 (3 SHP) | open industrial | no Vp ops | Caminomorisco gold demo |
| La Mierla 2026-07 | open scrape | pending_external | press ~30–32k ha **≠ EGIF** |
| **Pablo/GEACAM Tobarra 2026-07-30** | ops perímetro activo KMZ | Tobarra confirmed (Vp/ha aparte) | 18:30→21.49 ha, 21:43→37.08 ha; O2 ops **PARTIAL** |
| **Pablo/GEACAM pack 0308 2026-08-03** | Hellín+Estrella+Cardoso | Hellín **confirmed** | Boletín Vp=50; Estrella mapas Vp 20–25 (no confirmed); Cardoso Δha timeline |

### Drop Pablo/GEACAM (2026-07-30)

| Ruta | Contenido | Uso en repo |
|------|-----------|-------------|
| `data/real_if/pablo_geacam_20260730_tobarra/` | 2 KMZ + KML + 7 JPG mapas + inventory | Parser `wildfire_front/ops_perimeter.py` |
| Eval | `scripts/eval_tobarra_pablo_perimeters.py` | Report `outputs/tobarra_pablo_perimeters/eval_report.json` + GeoJSON |
| Ancla pointer | `data/infocam_anchors.json` → `perimeter_drop_pablo_20260730` | No cambia status `confirmed` ni inventa Vp |

**Honestidad:** perímetro ops ≠ cadastre nacional; Δha/h ≠ Vp m/min. O2 nacional sigue **BLOCKED** (`docs/O2_HAUSDORFF_BLOCKED.md`).

### Parches CLM (`artifacts/clm_ndws_patches/`)

| Split set | Uso | Fuentes |
|-----------|-----|---------|
| `holdout_v1` | train Tobarra / val LA / test Cardoso | Protocolo seed42 |
| `lofo_v1` | folds CARDOSO, LA_ACOM1/2, tobarra | multi_if train sin Cardoso |

---

## Anclas (O1 / O5)

Fuente: `data/infocam_anchors.json` (protocolo v1).

| fire_id | status | Vp | ha | Acción |
|---------|--------|----|----|--------|
| tobarra_20240802 | **confirmed** | 7.0 | 39 | Mantener |
| cardoso_2025 | pending_external | — | — | **Prioridad #1** — solicitar INFOCAM/CMA |
| hellin_2024 | pending_external | — | — | Solicitar |
| la_estrella_acom1_2024 | pending_external | — | — | Solicitar |
| retuerta_2025 | pending_external | — | — | Solo tras QA clean |
| guadalajara_la_mierla_20260717 | pending_external | — | press only | LWIR+EGIF+perímetro si liberable |

**O1 bloqueado** hasta ≥1 ancla confirmed adicional (no inventar Vp).

---

## Outreach / email (estado 2026-07-30)

| Canal | Estado | Acción |
|-------|--------|--------|
| REDIAM AND | GO datos públicos | Packs en casa |
| RAI EXT | GO 3 SHP + form | Packs en casa |
| CyL 4082/2026 | Acuse 17-jul; **silence ~17 ago** (as of 2026-08-04) | **WAIT** — no re-spam; post-silence: one follow-up or close — `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md` |
| Galicia Extinción | Traslado 22-jul | Follow-up ~**1 ago** si silencio |
| USC | Cerrado para datos | No insistir |
| INIA | Solo contrato pago | No gratis |
| **CMA/Pablo** | **2026-07-30:** muestra Tobarra KMZ + mapas; **Cardoso sin extra** | Agradecer; pedir multi-IF perímetros (Cardoso/Hellín/Estrella) + vectorial; O1 sigue bloqueado |
| Gmail MCP | OAuth expired | Re-auth Testing app |

Detalle histórico: `docs/PLAN_PROGRAMACION_EMAILS_20260724_POST_S1.md`, `docs/CONTACTOS_OUTREACH.csv`.

---

## Prioridades de datos

1. Conseguir Vp/ha **Cardoso** (máximo impacto O1 + narrativa multi-IF).  
2. **Mega-IF 2026 (open intel):** Burgohondo/Ávila, La Mierla, Sierra Oeste, Gironde — ver `docs/fire_intel/MEGA_FIRES_2026_ES_FR.md` (press only; graph `wfd-fire-intel-scrape`).  
3. Completar máscaras **LA ACOM2** y **Polán** o marcar NO_USE.  
4. CyL 4082 cuando resuelva; GAL Extinción si envía SHP.  
5. Si hay LWIR+máscara nuevo no-Cardoso → LOFO v2 + multi_if retrain (pista ML).  

### Stubs ancla 2026 (pending_external, ha press ≠ EGIF)

| fire_id | ha press prov. | Vp |
|---------|----------------:|----|
| guadalajara_la_mierla_20260717 | ~32k | null |
| avila_burgohondo_202607 | ~50k | null |
| madrid_sierra_oeste_202607 | ~19k | null |

---

## Comandos útiles

```bash
python scripts/build_if_inventory.py
python scripts/batch_process_fires.py
python scripts/materialize_lwir_masks.py --help
python scripts/eval_tobarra_pablo_perimeters.py
python scripts/run_plan_cycle.py --execute-m1
```
