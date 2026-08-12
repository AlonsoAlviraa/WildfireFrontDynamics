# Guion demo 30 min — post O1 unlock

**Audiencia:** end-user (INFOCAM/CMA/GEACAM), universidad/TFG, partner datos o UE.  
**Producto real (2026-08):** Tobarra ops grade A · Hellín 2ª ancla confirmed (ops grade **B**) · ML lab v34 · Decision Card · open multi-CCAA · fuel/envelope **contexto**.  
**Acta post-demo:** `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` (M3.2).  
**Regla de oro:** enseñar **cuándo el sistema se calla** (HOLD/ABSTAIN). HOLD es feature, no fallo.

---

## 0. Mensaje en una frase

> “Apoyo a la decisión con **audit trail**: velocidad de frente donde hay LWIR + ancla, perímetro institucional donde hay Junta, y **abstención** cuando no se puede mentir. Ops y ML son productos **separados**; en sala, la fusión ML live de `field_ops` está **OFF**.”

---

## 1. Kill list explícita (leer antes de la call)

| # | NO hacer / NO decir |
|---|---------------------|
| K1 | **No inventar ROS, Vp ni ha** sin fuente en `infocam_anchors` / pack / Junta |
| K2 | **No afirmar fusión ML live en `field_ops`** (`allow_ml_live_in_fusion` = OFF) |
| K3 | **No flipar ni implicar `ml_product_go=true`** — ML es lab hasta gates de producto |
| K4 | **No calibrar k único** Tobarra (Vp 7) + Hellín (Vp 50) “para que cuadre” |
| K5 | **No reescalar ROS a Vp en silencio** — ratio crudo, grade honesto |
| K6 | **No presentar Cardoso ha/h ni Estrella SITAC** como ancla **confirmed** |
| K7 | **No** hull FIRMS = área quemada oficial |
| K8 | **No** “99 % precisión del fuego” / “apagamos incendios con IA” / sustituimos al mando |
| K9 | **No** GO_MES solo porque O1 PASS — P1/O5 siguen abiertos (Hellín grade B) |
| K10 | **No** envelope/fuel como orden táctica de despacho (peso 0 en Decision Card) |

---

## 2. Claims permitidos (frases seguras)

| Tema | Frase OK |
|------|----------|
| Dual product | Ops (`front_dynamics`) ≠ ML (máscara/IoU); no se mezclan como un solo número |
| Tobarra | ROS ops vs Vp **7** m/min (INFOCAM confirmed); grade **A** documentado |
| Hellín | 2ª ancla Vp **50** (boletín UNAP); ROS ~**28** m/min, ratio ~**0.56** in-band, grade **B** — no es grade A |
| O1 | Multi-ancla **PASS** (Tobarra + Hellín); O5/P1 **no** cerrados |
| Decision Card | GO / HOLD / **ABSTAIN** con motivos; `research_open` más permisivo, `field_ops` fail-closed |
| Open multi-CCAA | Níjar REDIAM + Caminomorisco RAI: mismos gates de honestidad |
| ML | U1 honest lab (IoU/ECE); catalog holdout = **provenance**, no certeza en vivo |
| Fuel | AEMET + envelope v3 en pipeline Tobarra; **no** claim táctico en Card |
| Venta | Audit + abstención + dual field; no mapitas CEMS como producto |

---

## 3. Material a tener abierto (pre-call, 5 min)

| Prioridad | Artefacto | Path |
|-----------|-----------|------|
| **P0** | **Modo operario (tablero + 4 actos)** | `python -m wildfire_front operator` |
| P0 | Cheatsheet 12 min | `docs/CHEATSHEET_DEMO_12MIN.md` |
| P0 | Runbook H1 / GO_Q | `docs/H1_GO_Q_RUNBOOK.md` |
| P0 | Portal demo multi-CCAA | `outputs/demo_multi_ccaa/index.html` |
| P0 | Honesty card | `docs/PILOT_HONESTY_CARD.md` |
| P0 | Hellín scorecard | `docs/HELLIN_TRACK_A_SCORECARD.md` |
| P0 | Scorecard mes / O1 | `docs/SCORECARD_MES_1.md` · `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| P0 | P1 eng BLOCKED (por qué no GO_MES) | `docs/P1_HELLIN_ENG_STATUS.md` |
| P1 | Figs Tobarra | `docs/entrega_cma/fig_tobarra_ros.png` · `fig_tobarra_area.png` |
| P1 | Commander (opcional) | `docs/commander/index.html` |
| P1 | Anclas | `data/infocam_anchors.json` (solo `confirmed`) |
| P1 | Proxy vs confirmed | `docs/DATA_PROXY_HONESTY.md` |
| P2 | Producto dual | `docs/PRODUCTO_DUAL.md` |
| P2 | One-pager | `docs/ONEPAGER_COMERCIAL_ES.md` |
| P2 | Fuel design (si preguntan) | `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` |

**Arranque rápido (operario primero):**

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front operator
python -m wildfire_front operator do --all    # ensayo 4 actos + sello
python -m wildfire_front operator checklist   # 7/7 eng; GO_Q sigue partial
# HTML multi-CCAA (si hace falta abrir a mano):
# start outputs\demo_multi_ccaa\index.html
# opcional eng: start docs\commander\index.html
```

---

## 4. Timeline 30 minutos

### 0:00–2:00 — Gancho y dual product

**Objetivo:** fijar marco mental.

1. Frase de apertura (§0).  
2. Diagrama verbal:

| Capa | Qué es | Qué no es |
|------|--------|-----------|
| **Ops** | LWIR + `front_dynamics_v1` → ROS / grade | No es IoU ML |
| **ML lab** | `clm_ensemble_v34` máscaras/fiabilidad | No es orden de sala |
| **Decision Card** | Une señales con **política**; puede **ABSTAIN** | No es despacho táctico automático |

3. Decir en voz alta: **`field_ops` fusión ML live = OFF** · **`ml_product_go` = false**.

---

### 2:00–9:00 — Tobarra OPS (ancla 1, grade A)

**Objetivo:** producto diferencial con datos reales.

1. Mostrar figs ROS/área Tobarra o card Tobarra en portal (`?panel=tobarra`).  
2. Hechos a citar (sin inventar decimales nuevos en caliente; preferir scorecard):
   - Fecha IF **2024-08-02**, LWIR multi-frame.
   - Ancla INFOCAM **confirmed**: Vp **7** m/min, **~39 ha**.
   - Ops grade **A**; ratio ROS/Vp en banda documentada (orden ~0.8–1.2 según pack/scorecard).
3. Frase clave:
   > “Aquí sí hay **velocidad de frente validable**. Sin termografía + parte, **no inventamos el número**.”
4. Límite:
   > “Depende de partner de datos térmicos. No es open data genérico de toda España.”

---

### 9:00–15:00 — Hellín 2ª ancla (honestidad post-O1)

**Objetivo:** O1 multi-ancla PASS sin inflar P1/GO_MES.

1. Abrir `docs/HELLIN_TRACK_A_SCORECARD.md`.  
2. Hechos:
   - Ancla **confirmed**: Vp **50** m/min (boletín UNAP); ha 100\* estimada.
   - ROS primaria ops ~**27.9** m/min · ratio ~**0.56** ∈ [0.5, 2.0].
   - Grade estructural **B** → **no** es segundo grade A → **P1 parcial / NO_GO_MES**.
3. Frases obligatorias:
   > “O1 **sí** (dos anclas confirmed + ratios en banda). O5/P1 **no**: solo Tobarra es grade A.”
   > “**No** ajustamos un k conjunto 7↔50 m/min. Reportamos crudo.”
4. Si preguntan “¿está listo para sala en Hellín?”:
   > “Útil como contraste y validación multi-IF; **no** lo vendemos como grade A operativo.”

---

### 15:00–20:00 — Open multi-CCAA (Níjar · Caminomorisco)

**Objetivo:** mismos gates, otra pista de datos.

1. Portal: teclas `2` / `3` o `?panel=nijar` / `camino`.  
2. Mensaje:
   - **Níjar (AND):** perímetro REDIAM ~miles de ha; O2 institucional; **sin** Vp táctica inventada.
   - **Caminomorisco (EXT):** perímetro RAI/INFOEX; ventana det–ext; FIRMS puede ir SKIP honesto.
3. Frase:
   > “Tres CCAA, **un contrato de honestidad**: si falta ancla u ops, el sistema no finge un GO de sala.”
4. Opcional 30 s: La Mierla open HOLD (crisis real) — solo si no diluye el pitch.

---

### 20:00–25:00 — Decision Card + políticas

**Objetivo:** el entregable de pago.

1. Honesty card: Tobarra `research_open` puede ir **GO** experimental; `field_ops` a menudo **ABSTAIN** (fail-closed).  
2. Mostrar reasons: missing reliability, open_only, fusion OFF — **sin inventar R1–R4**.  
3. Opcional live CLI (si hay tiempo y entorno):

```bash
python -m wildfire_front decide --use-ml-v34 --policy field_ops
python -m wildfire_front decide --use-ml-v34 --policy research_open
```

4. Frase de valor:
   > “Lo que se factura es **confianza operativa y auditoría**, no otro GIS.”

**Fuel / envelope (60–90 s, solo si útil o preguntan):**

- Pipeline AEMET Tobarra + envelope v3 existen y tienen scorecard eng.
- En Decision Card el envelope lleva **peso 0 táctico** — contexto, no despacho.
- No enlazar fuel a un ROS inventado en la demo.

---

### 25:00–28:00 — Límites abiertos y roadmap honesto

| Abierto | Estado actual | No prometer |
|---------|---------------|-------------|
| GO_MES | **NO_GO_MES** (P1: falta 2º grade A) | “Mes cerrado” |
| O2 Hausdorff nacional | **BLOCKED** sin perímetro oficial multi-hora nacional | “Ya medimos Hausdorff oficial en todos los IF” |
| ML producto campo | `ml_product_go=false` | “ML en vivo manda en sala” |
| 3ª ancla | Cardoso/Estrella **no confirmed** | “Ya hay 3 anclas INFOCAM” |
| CyL | follow-up calendario | “Ya tenemos CyL completo” |

---

### 28:00–30:00 — Ask y cierre

**A end-user / CMA:**  
> “¿Feedback 15 min por escrito o segunda sesión? Si encaja: **carta de interés** y, cuando confíen, **un IF con material térmico** o Vp formal de un 3er incendio.”

**A universidad / TFG:**  
> “¿Encaja como capítulo de producto / work package software? El esqueleto de memoria está en `docs/INFORME_TRIMESTRE_ESQUELETO.md`.”

**A partner UE:**  
> “One-pager EN + demo reproducible; seat en consorcio sin inflar claims de campo.”

**Cierre:**  
> “Resumen: Tobarra A, Hellín ancla B honesta, open multi-CCAA, Decision Card que sabe callarse. Acta de esta sesión en una página.”

→ Rellenar `docs/ACTA_DEMO_TERCERO_TEMPLATE.md` el mismo día.

---

## 5. Q&A difícil (respuestas cortas)

| Pregunta | Respuesta |
|----------|-----------|
| ¿Precisión 99 %? | No la reclamamos. Confianza del fenómeno ≠ gates de sistema. |
| ¿Sustituís al mando? | No. Apoyo + abstención auditada. |
| ¿Por qué field_ops se calla? | Política estricta de sala; fusión ML live OFF a propósito. |
| ¿Hellín no cuadra al 50? | Ratio 0.56 es mismo orden; FOV/máscara incompleta probable; no reescalamos. |
| ¿Cuándo GO_MES? | Cuando **P1 cierre**: 2º IF ops grade A usable (u otra IF grade A si Hellín queda eng BLOCKED). **Hellín eng BLOCKED** (`docs/P1_HELLIN_ENG_STATUS.md`) documenta que **no** se cierra P1 por este pack — **no es GO_MES por sí solo**. Fórmula: `O1∧O4∧P1∧M2∧E1`; hoy **NO_GO_MES**. |
| ¿Empresa / CIF? | En formación; el software y el piloto no esperan al CIF para demo honesta. |
| ¿CEMS = ha oficiales? | No; open institucional y CEMS son pistas distintas; se etiquetan. |

---

## 6. Variantes de duración

| Tiempo | Recorte |
|--------|---------|
| **12 min** | Gancho + Tobarra + Decision Card HOLD + 1 open + ask (omitir Hellín detalle / fuel) |
| **20 min** | + Hellín scorecard 3 min; open en 1 solo sitio |
| **30 min** | Este guion completo |
| **+10 Q&A** | Solo kill list + límites; no abrir más packs |

Guion corto histórico (otra narrativa La Mierla): `docs/funding/04_GUION_DEMO_10MIN.md`.  
Handoff portal 12 min: `docs/design/DEMO_FRONT_SALES_HANDOFF.md`.

---

## 7. Checklist pre-call (2 min)

- [ ] Portal multi-CCAA abre local sin error  
- [ ] Hellín scorecard y SCORECARD_MES_1 a mano  
- [ ] Anclas confirmed: solo Tobarra + Hellín  
- [ ] No demos con `ml_product_go` o fusion ON “para quedar bien”  
- [ ] Acta template impresa o en 2ª pantalla  
- [ ] Email CTA listo (si aplica)

---

## 8. Evidencia canónica (paths)

| Qué | Path |
|-----|------|
| Overlay plan activo | `docs/PLAN_1_MES_POST_O1_UNLOCK.md` |
| O1 recompute | `docs/O1_GOMES_RECOMPUTE_20260803.json` |
| P1 Hellín eng BLOCKED | `docs/P1_HELLIN_ENG_STATUS.md` |
| Proxy vs confirmed | `docs/DATA_PROXY_HONESTY.md` |
| Pack Hellín | `outputs/observatorio/hellin_2024/` |
| Pack Tobarra / observatorio | `outputs/observatorio/` (refs en SCORECARD) |
| Pilot outputs | `outputs/pilot_honesty_card/` |
| Demo builder | `python scripts/build_demo_multi_ccaa.py` |
