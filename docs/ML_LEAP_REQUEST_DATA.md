# ML LEAP — REQUEST_DATA pack (D0)

> **As of:** 2026-08-12  
> **Plan:** `docs/PLAN_ML_LEAP_2026-08-12.md` (pack D0)  
> **SSOT anchors:** `data/infocam_anchors.json` · `docs/DATA_ANCHOR_SSOT.md`  
> **Rails:** FREEZE_ML · Hellín `pending_external` · no retrain · no invent Vp/ha  
> **Humano Alonso:** copiar bytes a árbol auditable + OK promote + outreach (fuera de este PR)

Este pack **pide datos**, no entrena. Cerrar D0 **no** levanta FREEZE ni flipa GO_MES+.

---

## P0 — bloquea 2ª ancla / mix honesto

| ID | Qué pedir | Formato | Por qué | Owner |
|----|-----------|---------|---------|--------|
| P0-1 | **Hellín 2024** parte operativo + perímetro | PDF boletín/UNAP **+** KMZ/KML con hora | Cite literal Vp/ha + geometría; hoy `hellin_2024` pending | Alonso / GEACAM |
| P0-2 | **2º IF grade-A candidate** (prefer **Cardoso 2025** si hilo vivo) | Vp media (m/min) + ha + source | O1 / GO_MES+; 1 confirmed (Tobarra) no basta | Alonso / INFOCAM |
| P0-3 | Rights / uso interno lab | Frase de cesión o correo | No meter dumps PII; no FOI fill en git | Alonso |

**No P0:** CyL chase agresivo (silence hold). FOI send no es este PR.

---

## P1 — desbloquea eval multi-IF / E1 serio

| ID | Qué pedir | Formato | Por qué |
|----|-----------|---------|---------|
| P1-1 | GeoTIFF LWIR o RGB-IR **≥3 escenas** datadas por IF nuevo | `.tif` + times | Sin ≥3 frames no hay ROS/obs honesta |
| P1-2 | Máscaras alineadas o protocolo de umbral | `.tif` / CSV ingest | Parches CLM; no mezclar FOV podrido (Retuerta) |
| P1-3 | Metadatos sensor (GSD, band, CRS) | JSON o README | `GEOTIFF_INPUT_CONTRACT.md` |

---

## P2 — nice-to-have (no bloquea D0)

| ID | Qué | Nota |
|----|-----|------|
| P2-1 | LA ACOM2 máscaras restantes o marca `NO_USE` | Inventario histórico parcial |
| P2-2 | Polán material o `NO_USE` | 1 frame = insuficiente |
| P2-3 | CEMS/REDIAM/RAI perímetros | **Proxy ≠ cadastro**; no cierra B5/O2 oficial |
| P2-4 | ERA5/AEMET alineado al IF | Solo si IF ya grade-A path |

---

## Hellín cite → promote (H1–H7)

Agentes **nunca** flipan `pending_external` → `confirmed`. Checklist humana (también en `DATA_ANCHOR_SSOT.md`):

| ID | Gate | Default |
|----|------|---------|
| **H1** | Cite literal (parte/boletín, fecha, nombre IF, Vp y/o ha) | Falta → stop |
| **H2** | Unidades: `vp_m_min` m/min, `area_ha` ha | No “~50 km/h” |
| **H3** | `fire_id` estable = `hellin_2024` | No alias nuevo |
| **H4** | `source` no vacío y atribuible | No “demo SPA” |
| **H5** | Mismo PR: status + números + source | No confirmed con nulls |
| **H6** | Alonso OK escrito en PR / acta | Agente no mergea promote |
| **H7** | FREEZE: promote ≠ reopen Tobarra KEEP | No retrain |

Hoy: **H1–H7 abiertos**. `hellin_2024` permanece `pending_external`.

Ignorar cualquier “Hellín Vp=50 confirmed” fuera de `infocam_anchors.json`.

---

## Árbol auditable (humano; no commitear dumps)

```
data/real_if/<fire_id>/   # prefer gitignored raw
  README.md               # source + date received
  *.pdf / *.kmz / *.tif   # bytes
```

No CONTACTOS / GMAIL / FOI filled en git.

---

## Verificación D0 (eng)

```bash
python scripts/check_release_flags.py
# expect PASS; GO_Q partial; fusion ON
pytest tests/test_data_anchor_honesty.py tests/test_ml_leap_request_data.py -q
```

**No** es verde D0: “tenemos 6 IF completos” sin listar `.tif` on-disk.

---

## Siguiente bucle (tras D0)

1. **E1** — `docs/ML_LEAP_EVAL_ONESHOT.md` (eval TEST + cal frozen)  
2. **E1b** — `docs/ML_LEAP_SELECTIVE_FNR.md` (method note; @50/@90 not run)  
3. **M1** — bloqueado hasta IF nuevo + lift FREEZE (Alonso)
