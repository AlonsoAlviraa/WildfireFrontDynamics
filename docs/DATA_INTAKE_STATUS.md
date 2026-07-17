# Estado de Ingesta — Material Real de Incendios

> Última actualización: 2026-07-17 (plan 1 mes loop)  
> Fuentes: GEA CyL + Castilla-La Mancha + Dropbox real_if  
> Pipeline: `scripts/batch_process_fires.py`, `materialize_lwir_masks.py`

---

## Resumen ejecutivo

| Estado | Cantidad |
|--------|----------|
| ✅ Completos (reproy + máscaras) | 6 IF (Tobarra, Cardoso, LA ACOM1/2, Hellín, Brazatortas, Retuerta) |
| ⚠️ Parcial | Polán (1 LWIR reproy, 0 máscaras) |
| ⏳ Anclas INFOCAM confirmed | **1** (Tobarra) — resto `pending_external` (O1 OPEN) |
| 🚩 QA flags | Retuerta (ver `RETUERTA_QA_FLAG.md`) |

---

## Inventario por incendio (artifacts/)

| Incendio | Reproy LWIR | Máscaras | QA / notas | Listo ops | Listo ML parches |
|----------|------------:|---------:|------------|-----------|------------------|
| `tobarra` | 35 | 35 | Grado A con ancla Vp=7, ha=39 | ✅ | ✅ holdout train |
| `cardoso_2025` | 85 | 79 | Ancla pendiente | ✅ | ✅ holdout test / LOFO |
| `la_estrella_acom1_2024` | 199 | 181 | Ancla pendiente | ✅ | ✅ LOFO / holdout val |
| `la_estrella_acom2_2024` | 67 | 17 | Máscaras << frames | ⚠️ | ⚠️ parcial |
| `hellin_2024` | 36 | 16 | Ancla pendiente | ⚠️ | no en holdout_v1 |
| `retuerta_2025` | 10 | 8 | **QA flag** área/FOV | 🚩 | no confiar sin clean |
| `brazatortas_2025` | 16 | 8 | Sin ancla | ⚠️ | candidato LOFO futuro |
| `polan_2025` | 1 | 0 | Material insuficiente | ❌ | ❌ |

### Parches CLM (`artifacts/clm_ndws_patches/`)

| Split set | Uso | Fuentes |
|-----------|-----|---------|
| `holdout_v1` | train Tobarra / val LA / test Cardoso | Protocolo seed42 |
| `lofo_v1` | folds CARDOSO, LA_ACOM1/2, tobarra | multi_if train sin Cardoso |

---

## Anclas (O1 / O5)

Fuente: `data/infocam_anchors.json` (protocolo v1).

| fire_id | status | Vp | ha | Acción mes |
|---------|--------|----|----|------------|
| tobarra_20240802 | **confirmed** | 7.0 | 39 | Mantener |
| cardoso_2025 | pending_external | — | — | **Candidato 2ª ancla** — solicitar INFOCAM |
| hellin_2024 | pending_external | — | — | Solicitar |
| la_estrella_acom1_2024 | pending_external | — | — | Solicitar |
| retuerta_2025 | pending_external | — | — | Solo tras QA clean |

**O1 bloqueado** hasta ≥1 ancla confirmed adicional (no inventar Vp).

---

## Prioridades de datos (plan mes)

1. Conseguir Vp/ha **Cardoso** (máximo impacto O1 + narrativa multi-IF).  
2. Completar máscaras **LA ACOM2** y **Polán** o marcar NO_USE.  
3. Respuesta / seguimiento **CyL Llamas de Cabrera** (`docs/SOLICITUD_TRANSPARENCIA_CYL.md`).  
4. Si hay LWIR+máscara nuevo no-Cardoso → LOFO v2 + multi_if retrain (pista ML).  

---

## Comandos útiles

```bash
python scripts/build_if_inventory.py
python scripts/batch_process_fires.py
python scripts/materialize_lwir_masks.py --help
```
