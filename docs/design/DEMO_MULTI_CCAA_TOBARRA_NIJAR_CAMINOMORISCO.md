# Plan demo multi-CCAA  
## Tobarra (OPS) + Níjar AND (REDIAM) + Caminomorisco EXT (RAI)

**Status:** IMPLEMENTED · portal sales v2 (`outputs/demo_multi_ccaa/`)  
**Portal:** `outputs/demo_multi_ccaa/index.html`  
**Builder:** `python scripts/build_demo_multi_ccaa.py` · `make demo-multi-ccaa`  
**Duración:** 10–12 minutos (+ 3 min Q&A)  
**Audiencias:** TFG tribunal · CMA/GEACAM · ASEMA/RAI · uni · partner UE  
**Regla de oro:** tres pistas, **mismos gates**; el sistema **sabe abstenerse** (HOLD). No inventar Vp ni ha desde hull FIRMS.

---

## 1. Mensaje en una frase

> Validamos **frente térmico con ancla operativa** en Castilla-La Mancha (Tobarra) y **perímetros oficiales de Junta** en Andalucía y Extremadura, con el **mismo contrato industrial** de honestidad: sin despacho táctico y sin inventar datos que no existen.

---

## 2. Las tres historias (tabla maestra)

| | **Tobarra** | **Níjar** | **Caminomorisco** |
|--|-------------|-----------|-------------------|
| **CCAA** | Castilla-La Mancha | Andalucía | Extremadura |
| **Año** | 2024-08-02 | 2024-06-06 | 2025-07-29 → 08-29 |
| **Pista** | **A · OPS gold** | **B+ · OPEN O2** | **B+ · OPEN O2** |
| **Dato estrella** | LWIR multi-frame + **Vp 7 m/min** + **39 ha** confirmed | Perímetro **REDIAM** (~**2169 ha**) + FIRMS + dNBR | Perímetro **RAI/INFOEX** (~**2680 ha**) + fechas det/ext |
| **Fuente** | Heligrafics / CMA material + INFOCAM ancla | REDIAM Junta Andalucía | RAI `rai@juntaex.es` |
| **Veredicto pack** | Grade A / OPS gold stack | `GO_OPEN_AND_O2` | `PARTIAL` (O2 PASS; FIRMS 2025 archive N/A) |
| **Qué demuestra** | ROS multi-estimador + ancla real | O2 institucional multi-IF + satélite | O2 CCAA con ventana det–ext |
| **Qué NO dice** | “Funciona en toda España sin datos” | “Vp táctico AND” | “Ha satélite = quemado oficial” |

### Artefactos a abrir (pre-demo)

| Slot | Path | Acción |
|------|------|--------|
| T1 mapa/ops | `docs/entrega_cma/fig_tobarra_ros.png` + `fig_tobarra_area.png` | Pantalla |
| T2 informe | `docs/entrega_cma/Informe_tecnico_dinamica_frente_v1.0.docx` (portada / 1 slide mental) | Opcional |
| T3 ancla | `data/infocam_anchors.json` → `tobarra_20240802` (Vp=7, ha=39, confirmed) | Citar |
| T4 ventanas | `outputs/temporal_windows/tobarra_20240802/` (early/mid/late) | Si hay tiempo |
| A1 mapa | `outputs/open_if/and_2024040053_20240606/map.html` | **Click local** |
| A2 scorecard | `…/scorecard_and_industrial.json` | Gates PASS |
| A3 brief | `…/operator_brief_open_if.md` | 10 s |
| A4 acta | `docs/AND_INDUSTRIAL_E2E_VERIFICATION.md` | Mencionar 10/10 |
| E1 mapa | `outputs/open_if/ext_2025100393_20250729/map.html` | **Click local** |
| E2 scorecard | `…/scorecard_ext_industrial.json` | O2_RAI PASS, FIRMS SKIP |
| E3 brief | `…/operator_brief_open_if.md` | 10 s |
| E4 acta | `docs/EXT_INDUSTRIAL_E2E_VERIFICATION.md` | 10/10 capas |
| G1 gold dual | `docs/GOLD_IF_E2E_VERIFICATION.md` | Tobarra OPS + open CEMS en stack |

**Antes de la call:** abrir 3 pestañas de mapa (Tobarra figs o commander si aplica + Níjar + Caminomorisco) en pantalla completa.

---

## 3. Guion por minutos (12 min)

### 0:00–0:45 — Gancho

> “No enseño tres mapas bonitos. Enseño **tres contratos de datos distintos** y **un solo criterio de calidad**: si falta ancla o el satélite no cuadra, el sistema **no finge un GO de sala**.”

Slide mental: **OPS · O2 AND · O2 EXT**.

---

### 0:45–4:00 — Tobarra (OPS)

**Objetivo:** enseñar el producto diferencial (térmico + ancla).

1. Mostrar **fig ROS / área** Tobarra.  
2. Decir:
   - Secuencia **LWIR** georreferenciada (Heligrafics-class).  
   - Ancla INFOCAM: **Vp ≈ 7 m/min**, **≈ 39 ha**, status **confirmed**.  
   - ROS multi-estimador, sectores, grados de calidad; ratio en banda razonable.  
3. Frase clave:
   > “Aquí sí hay **velocidad de frente** validable. Esto es la **pista A**. Sin este material, no inventamos el número.”

4. Cierre Tobarra:
   > “Limitación honesta: depende de partner de termografía y parte operativo. No es open data genérico.”

**Si preguntan precisión:** orden de magnitud / grade A; no “99 %”.

---

### 4:00–7:30 — Níjar, Andalucía (REDIAM O2)

**Objetivo:** perímetro **oficial de Junta** + pipeline industrial regenerable.

1. Abrir `map.html` Níjar (capa roja = perímetro REDIAM).  
2. Decir:
   - ~**2169 ha** geométricas; municipio Níjar / Almería; 2024-06-06.  
   - Fuente: **REDIAM — Junta de Andalucía** (respuesta institucional + WFS).  
   - Overlay **FIRMS** + **dNBR** Sentinel cuando hay escenas.  
   - Scorecard: **`GO_OPEN_AND_O2`**; decision open **HOLD** (sin ancla ASEMA de Vp).  
3. Frase clave:
   > “Misma fábrica de packs y gates que el resto del repo. Aquí el oro es el **perímetro institucional**, no el térmico.”

4. Contraste con Tobarra (10 s):
   | Tobarra | Níjar |
   |---------|-------|
   | ROS + Vp | O2 vector + satélite |
   | Partner ops | Catálogo / WFS público |

5. Ask implícito (si audiencia ASEMA):
   > “Con ha/Vp de parte de 1 IF, este pack sube de O2 a O1.”

---

### 7:30–10:30 — Caminomorisco, Extremadura (RAI O2)

**Objetivo:** segunda CCAA oficial **por email directo** (RAI), con fechas det/ext.

1. Abrir `map.html` Caminomorisco.  
2. Decir:
   - ~**2680 ha**; det **2025-07-29**, ext **2025-08-29** (ventana 31 días).  
   - Entrega **RAI** (`rai@juntaex.es`) — 3 shapes 2025 (este es el gold).  
   - Scorecard: **O2_RAI PASS**; **FIRMS SKIP** (archivo country Spain 2025 aún no en NASA) → veredicto pack **PARTIAL** (honesto).  
   - Acta industrial EXT: **10/10 capas** de contrato intake→pack→verify.  
3. Frase clave:
   > “Aunque el satélite yearly no esté, **no rellenamos hotspots inventados**. El perímetro oficial ya basta para validación geométrica multi-CCAA.”

4. Mencionar los otros dos EXT (silver) en una línea: Alburquerque ~2356 ha, Burguillos ~561 ha — misma tubería.

---

### 10:30–11:30 — Síntesis dual / multi-CCAA

Dibujar (o verbalizar) el stack:

```
              ┌─────────────────────────────┐
              │  Gates + scorecard + HOLD   │
              └──────────────┬──────────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Tobarra OPS          Níjar AND            Caminomorisco EXT
   LWIR + Vp            REDIAM O2            RAI O2
   CLM                  Junta Andalucía      Junta Extremadura
```

Frases de cierre (elige según audiencia):

| Audiencia | Cierre |
|-----------|--------|
| **Tribunal TFG** | “Metodología dual: validación térmica y validación O2 multi-CCAA documentada.” |
| **CMA / Pablo** | “CLM sigue siendo el núcleo ops; AND/EXT prueban que el open industrial escala sin inventar.” |
| **ASEMA / RAI** | “Ya usamos vuestros perímetros con atribución; pedimos solo anclas de 1–2 IF.” |
| **UE / partner** | “Spain multi-region living evidence for WFRM decision support + abstention.” |

---

### 11:30–12:00 — Ask (1 cosa)

**Una sola petición clara:**

> “¿30 minutos de feedback técnico? Si encaja, **carta de interés** o **ancla Vp/ha de un IF** en vuestra CCAA.”

No pedir 10 cosas.

---

## 4. Checklist pre-demo (T−30 min)

### Técnico
- [ ] Abrir mapas Níjar y Caminomorisco en navegador (file:// o `start map.html`)  
- [ ] Comprobar figuras Tobarra  
- [ ] Scorecards legibles (JSON o 1 screenshot)  
- [ ] Word RAI **enviado** a `rai@juntaex.es` (relación formal EXT)  
- [ ] PYTHONPATH no necesario en demo (solo lectura de artefactos)

### Narrativa
- [ ] 3 números memorizados: **7 m/min · 2169 ha · 2680 ha**  
- [ ] 3 fuentes: **INFOCAM ancla · REDIAM · RAI**  
- [ ] 2 prohibiciones: **no despacho · no hull=quemado**

### Si falla el mapa local
- [ ] Backup: capturas PNG de los tres mapas en `docs/entrega_cma/` o `docs/design/demo_screens/`  
- [ ] Briefs `.md` en editor

---

## 5. One-slide mental (para pantalla compartida)

```
WFD multi-CCAA demo
─────────────────────────────────────────
Tobarra (CLM)     │ Níjar (AND)      │ Caminomorisco (EXT)
OPS térmico       │ O2 REDIAM        │ O2 RAI
Vp 7 m/min · 39ha │ ~2169 ha         │ ~2680 ha
LWIR + ancla      │ FIRMS + dNBR     │ det/ext oficiales
GO OPS gold       │ GO_OPEN_AND_O2   │ PARTIAL (O2 only)
─────────────────────────────────────────
Mismos gates · HOLD sin ancla · sin inventar datos
```

---

## 6. Q&A preparado

| Pregunta | Respuesta |
|----------|-----------|
| ¿Por qué PARTIAL en EXT? | O2 oficial OK; archive FIRMS Spain 2025 no publicado (404). Preferimos SKIP a inventar hotspots. |
| ¿Sustituís INFOCA/INFOEX? | No. Validación y apoyo; decisión de sala es del servicio. |
| ¿Se puede ver ROS en Níjar? | No sin secuencia térmica o ancla Vp. Tenemos perímetro + satélite. |
| ¿Datos personales / confidenciales? | Perímetros institucionales; uso no comercial; atribución Junta; no redistribuir crudos sin acuerdo. |
| ¿Y Galicia / CyL? | Canales abiertos (Defensa Monte → Extinción; CDF transparencia). Multi-CCAA sigue creciendo. |
| ¿ML / deep learning? | Existe pista ML CLM; esta demo es **producto de validación y decisión**, no un modelo opaco. |
| ¿Empresa? | Proyecto propio en marcha; el software no espera al CIF. |

---

## 7. Variantes de duración

| Tiempo | Qué cortar |
|--------|------------|
| **6 min** | Solo 1 mapa AND + 1 frase Tobarra + 1 mapa EXT + ask |
| **10 min** | Guion completo sin temporal_windows Tobarra |
| **20 min** | + scorecards, + actas E2E, + La Mierla open opcional, + funding one-pager |

---

## 8. Post-demo (acciones 48 h)

| Prioridad | Acción | Owner |
|-----------|--------|-------|
| P0 | Enviar Word RAI si no está enviado | Alonso |
| P1 | Si feedback positivo → brief 1 p PDF multi-CCAA | Alonso / repo |
| P2 | ASEMA: pedir ancla Níjar | email |
| P3 | Cuando exista FIRMS 2025 → rebuild packs EXT | `build_ext_if_pack.py` |
| P4 | Portal HTML unificado 3 mapas | **HECHO** · `outputs/demo_multi_ccaa/index.html` |

---

## 9. Entregables de este plan

| Entregable | Path |
|------------|------|
| Este plan | `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md` |
| **Portal demo (1 click)** | `outputs/demo_multi_ccaa/index.html` |
| Builder | `scripts/build_demo_multi_ccaa.py` |
| Manifest | `outputs/demo_multi_ccaa/demo_manifest.json` |
| Tests | `tests/test_demo_multi_ccaa.py` |
| Packs | paths en §2 |
| Actas | GOLD / AND / EXT verification MD |

### Abrir la demo

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python scripts/build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html
# Deep-links: ?panel=tobarra | ?panel=nijar | ?panel=camino
```

---

## 10. Criterio de éxito de la demo

La demo **funciona** si la audiencia repite al menos una de:

1. “Tenéis **térmico validado** y **perímetros de dos Juntas**.”  
2. “No inventáis GO de sala.”  
3. “El siguiente paso son **anclas Vp/ha** o una **carta de interés**.”

No es éxito: “otro visor de incendios más.”

---

## 11. Comandos de refresco (si hay que regenerar la mañana de la demo)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
# AND gold (si hace falta)
# python scripts/build_and_if_pack.py --selection data/open_if/rediam_andalucia/inventory/selection_gold.json --tier gold
# EXT gold
python scripts/build_ext_if_pack.py --id 2025100393
python scripts/verify_ext_industrial_e2e.py --skip-pytest
python scripts/verify_and_industrial_e2e.py --skip-pytest
start outputs\open_if\and_2024040053_20240606\map.html
start outputs\open_if\ext_2025100393_20250729\map.html
```

---

**Implementado:** portal unificado en `outputs/demo_multi_ccaa/index.html` (builder idempotente, deep-links `?panel=`, guion 12 min, stack dual, Q&A, límites honestos).
