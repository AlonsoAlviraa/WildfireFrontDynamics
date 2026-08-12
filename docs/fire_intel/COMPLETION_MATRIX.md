# Completion matrix — fire intel max (2026-07-29)

## Qué significa “todo”

| Capa | Definición de “completo” | Estado |
|------|--------------------------|--------|
| **A. Open intel** | Inventario mega-IF ES/FR con fuentes, ha press/EFFIS, CEMS codes | **MAXED** este ciclo |
| **B. Agency open** | MITECO avance + CEMS activations + EFFIS cites | **MAXED** |
| **C. Open packs GIS** | EMSR packs en `outputs/open_if` | **GO_PROXY** — 896/898/899/900/902/905 vía RM API light |
| **D. Ops gold (Tobarra-class)** | Vp+ha official + LWIR≥3 + masks | **BLOCKED externo** (solo Tobarra) |
| **E. O1 multi-ancla** | ≥2 confirmed en `infocam_anchors.json` | **BLOCKED** (1 confirmed) |

**No se puede “iterar hasta D/E” solo con scrape.** Requiere parte INFOCAM/CMA/CyL/SDIS + material térmico.

---

## Logrado esta sesión (iteración 2)

1. Graph v3 + `wfd-fire-intel-scrape` (+ re-lanzado)  
2. Inventory 14 fires + CEMS 899/900/902/905  
3. **MITECO Avance 1-ene → 19-jul 2026 PDF** en `data/fire_intel/raw/`  
   - 65 753,71 ha forestales comunicadas CCAA  
   - 21 GIF  
   - EFFIS al 27-jul en nota: **172 396 ha** (incluye no extinguidos)  
4. EFFIS complex Ávila–Madrid ~**63–70k ha** (X analistas 28-jul)  
5. Gironde **42k ha** estabilizado 29-jul (press/X)  
6. Anchors stubs: La Mierla, Burgohondo, Sierra Oeste  
7. Plan cycle + 38 tests pilot/ML/confidence OK  
8. Workflows lanzados (límite 4 concurrentes en sesión)  
9. **`build_open_if_from_rm_api.py`** + 6 packs 2026 (ha CEMS stats) · open index **11 packs**

### CEMS light packs (burnt ha from product stats)

| Code | max ha | Pack |
|------|-------:|------|
| EMSR898 La Mierla | 27213 | `outputs/open_if/emsr898` |
| EMSR900 Central ES | 44377 | `outputs/open_if/emsr900` |
| EMSR899 Saumos/Gironde | 26065 | `outputs/open_if/emsr899` |
| EMSR902 Biscarrosse | 2682 | `outputs/open_if/emsr902` |
| EMSR905 Plana Baixa | 7266 | `outputs/open_if/emsr905` |
| EMSR896 Asín/Aragón | 12133 | `outputs/open_if/emsr896` |

---

## Bloqueos honestos (no se resuelven iterando scrape)

| Dato | Cómo se obtiene | Acción |
|------|-----------------|--------|
| Vp m/min Cardoso / Mierla / Burgohondo | Parte ops | Email humano / transparencia |
| ha EGIF por IF 2026 | Post-extinción CCAA→MITECO | Esperar avance semanal + partes |
| LWIR multi-frame | CMA / Heligrafics / partner | Outreach (ya en CONTACTOS) |
| Perímetro nacional | CCAA cartografía / EGIF | Solicitud formal |
| CEMS zip auto | Script download EMSR products | **siguiente código** (no bloqueado por política) |

---

## Hecho: CEMS light packs (2026-07-29)

| Code | max burnt ha (CEMS stats) | Pack |
|------|--------------------------:|------|
| EMSR898 La Mierla | **27 213** | `outputs/open_if/emsr898` |
| EMSR900 Central ES | **44 377** | `outputs/open_if/emsr900` |
| EMSR899 Saumos/Gironde | **26 065** | `outputs/open_if/emsr899` |
| EMSR902 Biscarrosse | **2 682** | `outputs/open_if/emsr902` |
| EMSR905 Plana Baixa | **7 266** | `outputs/open_if/emsr905` |
| EMSR896 Asín/Aragón | **12 133** | `outputs/open_if/emsr896` |

Builder: `python scripts/build_open_if_from_rm_api.py --activation EMSR898`  
`n_packs` open index: **11** (histórico + 2026).

## Siguiente

```text
1) human: Cardoso Vp/ha (O1)
2) wfd-fire-intel-scrape daily in season
3) optional: heavy observedEventA simplify for full Hausdorff proxy
```

Hasta (1), **GO_MES sigue false**.
