# Estado de Ingesta — Material Real de Incendios

> Última actualización: **2026-08-12** (honesty patch) · histórico 2026-07-17  
> Fuentes: GEA CyL + Castilla-La Mancha + Dropbox real_if  
> Pipeline: `scripts/batch_process_fires.py`, `materialize_lwir_masks.py`

---

## Banner de honestidad (2026-08-12)

1. **Anclas SSOT** = solo `data/infocam_anchors.json` → ver `docs/DATA_ANCHOR_SSOT.md`.  
   Hoy: **1 confirmed (Tobarra)**. Hellín / Cardoso / … = `pending_external`.
2. **Cite → promote** (Hellín u otra ancla): checklist en `docs/DATA_ANCHOR_SSOT.md` — **humano Alonso**; agentes no promueven sin cite literal. Tests: `tests/test_data_anchor_honesty.py`.
3. La tabla “✅ Completos” de abajo es un **inventario histórico** (2026-07-17).  
   **No** garantiza que este clone tenga stacks LWIR bajo `artifacts/`. Verificar on-disk (`build_if_inventory` / listar `.tif`) antes de vender “6 IF completos”.
4. **O2 nacional** sigue BLOCKED_EXTERNAL; CEMS/REDIAM/RAI = **proxy ≠ cadastro**.
5. No inventar Vp/ha. FREEZE_ML → pedir datos, no reentrenar.

---

## Resumen ejecutivo

| Estado | Cantidad |
|--------|----------|
| ✅ Completos (reproy + máscaras) *histórico 2026-07-17* | 6 IF nombrados (Tobarra, Cardoso, LA ACOM1/2, Hellín, Brazatortas, Retuerta) — **verify on-disk** |
| ⚠️ Parcial | Polán (1 LWIR reproy, 0 máscaras) |
| ⏳ Anclas INFOCAM confirmed | **1** (Tobarra) — Hellín **pending_external** (SSOT) |
| 🚩 QA flags | Retuerta (ver `RETUERTA_QA_FLAG.md`) |

---

## Inventario por incendio (artifacts/) — histórico

| Incendio | Reproy LWIR | Máscaras | QA / notas | Listo ops | Listo ML parches |
|----------|------------:|---------:|------------|-----------|------------------|
| `tobarra` | 35 | 35 | Grado A con ancla Vp=7, ha=39 **confirmed** | ✅ | ✅ holdout train |
| `cardoso_2025` | 85 | 79 | Ancla **pending_external** | ✅* | ✅ holdout test / LOFO |
| `la_estrella_acom1_2024` | 199 | 181 | Ancla pendiente | ✅* | ✅ LOFO / holdout val |
| `la_estrella_acom2_2024` | 67 | 17 | Máscaras << frames | ⚠️ | ⚠️ parcial |
| `hellin_2024` | 36 | 16 | Ancla **pending_external** (no SSOT confirmed) | ⚠️ | no en holdout_v1 |
| `retuerta_2025` | 10 | 8 | **QA flag** área/FOV | 🚩 | no confiar sin clean |
| `brazatortas_2025` | 16 | 8 | Sin ancla | ⚠️ | candidato LOFO futuro |
| `polan_2025` | 1 | 0 | Material insuficiente | ❌ | ❌ |

\* “Listo ops” aquí = material histórico declarado; no sustituye ancla confirmed ni grade A.

### Parches CLM (`artifacts/clm_ndws_patches/`)

| Split set | Uso | Fuentes |
|-----------|-----|---------|
| `holdout_v1` | train Tobarra / val LA / test Cardoso | Protocolo seed42 |
| `lofo_v1` | folds CARDOSO, LA_ACOM1/2, tobarra | multi_if train sin Cardoso |

---

## Anclas (O1 / O5)

Fuente canónica: `data/infocam_anchors.json` + `docs/DATA_ANCHOR_SSOT.md`.

| fire_id | status | Vp | ha | Acción |
|---------|--------|----|----|--------|
| tobarra_20240802 | **confirmed** | 7.0 | 39 | Mantener |
| cardoso_2025 | pending_external | — | — | **Candidato 2ª ancla** — solicitar INFOCAM |
| hellin_2024 | pending_external | — | — | **No promover** sin cite; ignorar “Vp=50 confirmed” fuera de este JSON |
| la_estrella_acom1_2024 | pending_external | — | — | Solicitar |
| retuerta_2025 | pending_external | — | — | Solo tras QA clean |

**O1 / GO_MES+:** 2ª ancla grade A sigue **OPEN** (no inventar).

---

## Prioridades de datos

1. Conseguir Vp/ha **Cardoso** (máximo impacto O1 + narrativa multi-IF) si el hilo vivo lo permite.  
2. Decidir Hellín: promote con cite literal **o** dejar pending (default).  
3. Completar máscaras **LA ACOM2** y **Polán** o marcar NO_USE.  
4. CyL silencio: respetar hold (no chase agresivo).  
5. ML: FREEZE — no retrain Tobarra KEEP.

---

## Comandos útiles

```bash
python scripts/build_if_inventory.py
python scripts/batch_process_fires.py
python scripts/materialize_lwir_masks.py --help
```
