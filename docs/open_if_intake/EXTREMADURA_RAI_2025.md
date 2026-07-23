# Extremadura RAI — perímetros 2025 (entrega 2026-07-22)

**Fuente:** `rai@juntaex.es` — Registro de Áreas Incendiadas  
**Mail:** “Petición perímetros formato shape” (thread 19f8a37cae9b1dfc)  
**Plan:** `docs/design/EXTREMADURA_RAI_INDUSTRIAL_E2E_PLAN.md`  
**Acta:** `docs/EXT_INDUSTRIAL_E2E_VERIFICATION.md`

## Entregables recibidos

| Zip | Id_incen | det | ext | ha attr | Pack |
|-----|----------|-----|-----|---------|------|
| 20250729_Caminomorisco | 2025100393 | 2025-07-29 | 2025-08-29 | ~2680 | `outputs/open_if/ext_2025100393_20250729` **GOLD** |
| 20250814_Alburquerque | 2025060450 | 2025-08-14 | 2025-08-29 | ~2356 | `outputs/open_if/ext_2025060450_20250814` |
| 20250814_Burguillos del Cerro | 2025060453 | 2025-08-14 | 2025-08-24 | ~561 | `outputs/open_if/ext_2025060453_20250814` |

- CRS: **EPSG:25829**  
- Formulario: `data/open_if/extremadura_rai_2025/Peticion_de_Datos_RELLENADA_Alonso_Alvira.docx`  
  → **Enviar a rai@juntaex.es** (registro obligatorio)

## Pipeline

```powershell
$env:PYTHONPATH = "."
python scripts/inventory_ext_rai.py
python scripts/build_ext_if_pack.py --tier all
python scripts/verify_ext_industrial_e2e.py
```

## Notas honestas

- FIRMS yearly Spain **2025** archive: **404** en NASA (al 2026-07-23) → packs **PARTIAL** con O2 RAI PASS y OPEN_FIRMS SKIP.  
- No inventar Vp.  
- Atribución: RAI / Junta de Extremadura / INFOEX.
