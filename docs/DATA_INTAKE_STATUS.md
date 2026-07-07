# Estado de Ingesta — Material Real de Incendios

> Última actualización: 2026-07-07  
> Fuente: GEA CyL + Castilla-La Mancha  
> Pipeline: `scripts/batch_process_fires.py`

---

## Resumen Ejecutivo

| Estado | Cantidad |
|--------|----------|
| ✅ **Incendios con datos crudos** | 7 incendios + Tobarra (751 + 67 TIFs) |
| ✅ **Incendios reproyectados** | 4 completos (Tobarra, Cardoso, La Estrella ACOM1/2) |
| ⏳ **Incendios pendientes** | 3 (Hellín, Retuerta, Brazatortas, Polán) |
| ✅ **Máscaras materializadas** | 312+ (acumulando) |

---

## Estado por Incendio

| Incendio | TIFs Crudos | Reproyectados | Máscaras | Estado |
|----------|------------|---------------|----------|--------|
| `tobarra_lwir` (2024) | 67 | 35 | 35 | ✅ Completo |
| `cardoso_2025` | 146 | 85 | 79 | ✅ Completo |
| `la_estrella_acom1_2024` | 361 | 199 | 181 | ✅ Completo |
| `la_estrella_acom2_2024` | 126 | 67 | 🔄 Procesando | ⚠️ En curso |
| `hellin_2024` | 70 | — | — | ⏳ Pendiente |
| `retuerta_2025` | 16 | — | — | ⏳ Pendiente |
| `brazatortas_2025` | 19 | — | — | ⏳ Pendiente |
| `polan_2025` | 13 | — | — | ⏳ Pendiente |
| **TOTAL** | **818** | **386** | **312+** | |

> **Nota**: Los TIFs crudos incluyen múltiples bandas (LWIR + HD-EO).  
> Los TIFs reproyectados son solo LWIR (`*_LWIR.tif`).

---

## Datos Crudos Disponibles

### `data/real_if/raw_dropbox/organized/`

Estructura organizada por incendio:

```
organized/
├── CARDOSO/                    # 146 TIFs (Guadalajara, 2025)
├── HELLIN20240719/             # 70 TIFs (Albacete, 2024-07-19)
├── LA_ESTRELLA_ACOM1/          # 361 TIFs (C-LM, 2024)
├── LA_ESTRELLA_ACOM2/          # 126 TIFs (C-LM, 2024)
├── 04_09_2025_IF.RETUERTA/     # 16 TIFs (2025-09-04)
├── 05_10_2025_IF.BRAZATORTAS/  # 19 TIFs (2025-10-05)
└── 13_09_2025_IF.POLAN/        # 13 TIFs (2025-09-13)
```

---

## Pipeline de Ingesta

### Script: `scripts/batch_process_fires.py`

Procesa los 7 incendios automáticamente:

1. **Reproyección**: EPSG:32630 (UTM 30N), resolución 0.5m
2. **Ingesta**: Binarización adaptativa MAD (z=3.5) + fast marching
3. **Persistencia**: Máscaras binarias + manifest con SHA-256

### Ejecución

```bash
set PYTHONPATH=. && python scripts\batch_process_fires.py
```

**Características**:
- `skip_if_done=True`: Omite incendios ya procesados (reanudable)
- Reporte JSON final en `outputs/batch_processing_report.json`
- Manejo de errores por incendio (continúa si uno falla)

---

## Tobarra (referencia)

### `data/real_if/raw_dropbox/20260707_transfer_01/` — TOBARRA-AB-20240802

| Tipo | Cantidad | Formatos |
|------|----------|----------|
| **Fotos** | 205 archivos | `.jpg`, `.tif` |
| **KMZ/KML** | 172 archivos | Georreferenciación por frame |
| **ZIP original** | 1 archivo (138.8 MB) | `TOBARRA-AB-20240802.zip` |

**Frames LWIR procesados**: 35 máscaras en `artifacts/tobarra_lwir_masks/`

---

## Notas Operativas

### Salto temporal en datos de campaña

> "habrá saltos en el comportamiento del incendio porque la campaña pasada solo contamos con una cámara. El avión hizo dos periodos por lo general, pero encontrarás saltos temporales."

⚠️ El pipeline **infiere dt del timestamp EXIF/KMZ**, no asume intervalo fijo.

### Próximos pasos

1. **Completar batch actual** (ACOM2 + Hellín + Retuerta + Brazatortas + Polán)
2. Generar manifiesto consolidado de todos los incendios
3. Preparar dataset de evaluación con los 8 incendios
4. Entrenar/validar modelo con datos reales multi-incendio