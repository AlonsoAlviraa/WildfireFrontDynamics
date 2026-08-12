# Mega auditoría — qué falta para **venderlo**

> **As of:** 2026-08-05  
> **Producto:** WildfireFrontDynamics  
> **Verdad de una línea:** el eng ya es demoable; **no es vendible como “producto de campo con ML GO”** hasta **H1 (demo + acta con tercero)** y un pitch honesto de **Decision Card / ops dual**, no de IoU mágico.  
> **Canónico vivo:** `docs/CURRENT_STATE.md` · `docs/GO_MES_VERDICT.md` · `docs/ONEPAGER_COMERCIAL_ES.md`

---

## 0. Veredicto comercial (honesto)

| Pregunta | Respuesta |
|----------|-----------|
| ¿Se puede **mostrar** a un tercero mañana? | **Sí** — operator UX + pack third-party + Reliability Report + Tobarra multipass S4 + piloto honesty |
| ¿Se puede **facturar** un piloto de decisión/auditoría? | **Sí, con contrato honesto** (ABSTAIN, dual ops/open, sin `ml_product_go`) |
| ¿Se puede vender **despacho táctico ML** / “apagamos incendios con IA”? | **No** — fusion OFF · `ml_product_go=false` · Tobarra LOFO KEEP **KILL** · Hellín grade **B** |
| ¿Qué bloquea “producto listo de mercado”? | **H1 humano** (demo + acta externa) · opcional 2º grade A / O2 · packaging comercial fino |

**Score de madurez comercial (0–100, juicio eng):**

| Eje | Score | Nota |
|-----|------:|------|
| Ingeniería / demo eng | **82** | GO_ENG + GO_MES mín · CLI · packs · S4 multipass |
| Honestidad / rails | **90** | kill list fuerte; no silent GO |
| Evidencia externa (acta) | **25** | H1 TODO · M3.2 PENDING |
| Datos multi-IF (ops) | **55** | 2 anclas; 1 grade A; O2 nacional blocked |
| ML como producto campo | **20** | lab only; multi-fire Tobarra hard; KEEP kill |
| Empaque comercial (precio/SLA) | **40** | one-pager existe; no SLA firmado ni pricing cerrado |
| **Global “listo para vender”** | **~48** | Vende **piloto de decisión**; no vende **IA táctica** |

---

## 1. Qué **sí** se vende (encaje one-pager)

| Entregable | Estado eng | ¿Listo en demo? |
|------------|------------|-----------------|
| **Fire Decision Card** GO/HOLD/**ABSTAIN** + audit trail | Hecho | Sí |
| Dual **ops LWIR** + **open CEMS/AND/EXT** | Hecho | Sí |
| Reliability gate (no silent GO) | Hecho (suite + report terceros) | Sí |
| Metrics Hub / commander / portal | Hecho | Sí (opcional eng) |
| Operator UX 4 actos | Plateau eng | Sí — `python -m wildfire_front operator` |
| Tobarra multipass ROS geometry (S4) | **OK** ~6.14 m/min vs Vp 7 | Sí — reforzar pitch ops |
| Piloto honesty 3 sitios | Hecho | Sí |
| ML lab show/freeze/reject | Congelado iter1 | Solo como **lab**, no producto campo |

**Frase de venta correcta:**

> “Sistema de apoyo a la decisión con abstención auditada: ROS desde térmica multi-pasada cuando hay dron; perímetros open cuando no; **nunca** inventa GO silencioso ni confunde IoU con ROS.”

**Frase prohibida:**

> “IA que predice el frente al 90% y dirige el ataque.”

---

## 2. Scorecard de gates (vender vs no vender)

| Gate | Valor | Implicación comercial |
|------|--------|----------------------|
| **GO_ENG** | true | Podéis enseñar código y demos estables |
| **GO_MES** (mínimo) | **true** | Mes eng cerrado; no es “producto vendido” |
| **GO_MES+** | false | Falta 2º grade A / O2 nacional / demo formal |
| **GO_Q** | **partial** | **Bloqueo de credibilidad B2G** sin H1 |
| **M3.2 / H1** | PENDING / TODO | Sin acta de tercero no hay cierre de trimestre de producto |
| **M3.4 informe** | ENG_FILLED | Usable en dossier; sello humano opcional |
| **ml_product_go** | **false** | No vender ML live en sala de mando field_ops |
| **field_ops fusion** | **OFF** | Correcto para no mentir en piloto |
| **O2 nacional** | BLOCKED | No vender “cadastre oficial” |
| **O5 2º grade A** | OPEN | Hellín B; solo Tobarra A fuerte |
| **S4 multipass** | **OK** | Argumento ops fuerte (nuevo 2026-08-05) |
| **Tobarra LOFO KEEP** | **KILL** | No vender transfer ML a Tobarra como resuelto |

> Nota: `docs/INDUSTRIAL_READINESS_STATUS.json` está **stale** (GO_MES false, O1 OPEN). **No usarlo** como verdad comercial; usar `GO_MES_VERDICT` + `CURRENT_STATE`.

---

## 3. Cadena de valor: eng listo vs humano pendiente

```
[ENG LISTO]                    [HUMANO / EXTERNO]              [VENTA]
operator + card + packs   →    H1 demo + acta tercero    →    piloto firmado
S4 multipass Tobarra      →    (calendario)              →    “ops medido”
Reliability Report        →    lectura 1 página          →    confianza auditor
Contactos outreach        →    1 mail personalizado      →    datos / 2ª ancla
                          →    O2 / CyL wait             →    GO_MES+ opcional
```

**Conclusión:** el cuello **no es más retrain**. Es **calendario + narrativa + un tercero que firme el acta**.

---

## 4. Ruta de 30 días para poder **vender un piloto**

### Semana 0–1 (esta semana) — **cerrar H1**

| # | Acción | Owner | Done cuando |
|---|--------|-------|-------------|
| 1 | Agendar **1 persona externa** (GEACAM/uni/partner) 30 min | humano | fecha en calendario |
| 2 | Ensayo: `operator` + cheatsheet 12 min + `demo-third-party` | humano+eng | 1 dry-run sin fallos |
| 3 | Abrir call con kill list verbal (no ROS inventado, no ml_product_go) | presentador | checklist H1 |
| 4 | Rellenar acta real + `record_h1_demo_complete.py` | humano | exit 0 · M3.2 met |

**Artefactos ya listos:**

- `docs/H1_GO_Q_RUNBOOK.md`
- `docs/CHEATSHEET_DEMO_12MIN.md`
- `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md`
- `outputs/demo_third_party/`
- `scripts/prepare_h1_acta_draft.py` / `record_h1_demo_complete.py`
- `outputs/tobarra_multipass_s4/` (S4 **OK**)

### Semana 1–2 — **paquete de venta**

| # | Acción | Owner | Done cuando |
|---|--------|-------|-------------|
| 5 | One-pager + precio piloto (setup + 3 IF open + 1 térmica cliente) | comercial | PDF 1 página |
| 6 | Demo script 12 min fijando **Decision Card + S4 ROS + ABSTAIN** | presentador | guion memorizado |
| 7 | Dossier: informe trimestre + Reliability Report + GO_MES verdict | eng | zip “trust pack” |
| 8 | Outreach 3 contactos (Pablo GEACAM, Heligrafics, 1 uni) — no spam | humano | 3 mails enviados |

### Semana 2–4 — **fortalecer oferta (no thrash ML)**

| # | Acción | Prioridad | Nota |
|---|--------|-----------|------|
| 9 | 2º grade A (O5) si llega ancla/perímetro | P1 | desbloquea GO_MES+ pitch |
| 10 | O2 nacional si llega vector | P1 | no inventar |
| 11 | Piloto con **datos del cliente** (1 secuencia LWIR) | P0 venta | prueba de integración |
| 12 | API `serve-decide` en red demo controlada | P2 | solo si piden integración |

**No hacer en el mes de venta:** retrain Tobarra KEEP · ECE thrash · flip fusion · GFM full train.

---

## 5. Matriz de riesgo de venta (qué te tumba en la reunión)

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Prometer ML táctico / fusión ON | alta si se improvisa | crítico | field_ops demo = ABSTAIN con ML-only |
| Confundir IoU 0.89 con ROS | alta | crítico | slide dual producto + S4 geometry |
| “GO_Q complete” sin acta | media | alto | semáforo AMARILLO hasta H1 |
| Un solo IF grade A | media | medio | honestidad Hellín B + roadmap O5 |
| INDUSTRIAL_READINESS stale | baja | medio | no enseñar ese JSON |
| Cliente pide perímetro cadastre | media | medio | open proxy + O2 blocked explícito |
| Cliente pide SLA 99% acierto frente | media | alto | five-nines = no silent GO only |

---

## 6. Inventario eng “listo para demo” (checklist)

### Debe estar verde (eng)

- [x] GO_MES mínimo true  
- [x] Operator UX / ensayo  
- [x] Decision Card field_ops fail-closed  
- [x] Pack third-party + replay  
- [x] Reliability Report terceros  
- [x] Piloto honesty multi-sitio  
- [x] S4 multipass Tobarra OK (~6.14 m/min)  
- [x] Cheatsheet 12 min + H1 runbook  
- [x] Kill list en docs  

### Debe estar verde (humano) — **bloqueantes de venta formal**

- [ ] Fecha con **tercero externo**  
- [ ] Demo ejecutada  
- [ ] Acta con nombre + fecha + firmas  
- [ ] `record_h1_demo_complete.py` → GO_Q path  
- [ ] Precio/alcance piloto escrito  
- [ ] (Opcional) 1 secuencia LWIR del cliente  

---

## 7. Oferta comercial recomendada (plantilla)

### Producto A — **Piloto Decision Card (recomendado ahora)**

| | |
|--|--|
| **Qué** | 1 sala: Decision Card + audit trail + 3 IF open + 1 térmica (suya o Tobarra demo) |
| **Entregables** | outbox cards · informe abstenciones · replay hash · 1 formación 90 min |
| **No incluye** | ML live field fusion · cadastre nacional · despacho táctico |
| **Precio (plantilla)** | setup + 4–8 semanas · (definir €) |
| **Gate de éxito** | acta H1 + ≥1 decisión ABSTAIN/HOLD/GO con fuentes reales del cliente |

### Producto B — **Ops térmico multi-pasada (si tienen dron/Heligrafics)**

| | |
|--|--|
| **Qué** | pipeline S4-like: arrival + ROS structural + brief |
| **Evidencia** | Tobarra multipass OK · grade A · ratio Vp |
| **No incluye** | predicción next-day ML como ROS |

### Producto C — **ML lab (no vender como campo)**

| | |
|--|--|
| **Qué** | evaluación multi-fuego, reject surface, teach cases |
| **Estado** | lab freeze · Tobarra hard · KEEP kill |
| **Pitch** | I+D / validación, **no** GO de producto |

---

## 8. Prioridad absoluta (orden de impacto en ventas)

1. **H1 demo + acta** — sin esto no hay GO_Q ni “caso de uso validado por tercero”.  
2. **Pitch dual + kill list** ensayado (12 min) — evita suicidio comercial por hype.  
3. **Trust pack** (Reliability + GO_MES + S4 + informe trimestre) en un zip.  
4. **1 outreach de datos** (Pablo / Heligrafics) — refuerza O5/O2, no bloquea piloto A.  
5. **Precio y contrato de piloto** (alcance / no-claims).  
6. Todo lo demás (ML, GFM, retrain) es **ruido** hasta 1–5.

---

## 9. Señales de que **ya se puede vender** (criterio de salida)

Declarar “piloto comercial abierto” solo si:

| ID | Criterio |
|----|----------|
| V1 | H1 acta registrada (M3.2 met) |
| V2 | Demo reproducible en &lt;15 min en máquina limpia con cheatsheet |
| V3 | One-pager + precio + no-claims firmables |
| V4 | Rails intactos en la demo (fusion OFF, ml_product_go false) |
| V5 | Al menos 1 decisión field_ops **ABSTAIN** mostrada como feature |

Hasta V1–V5: se puede **pre-vender conversación** y **mostrar**, no cerrar “producto maduro de campo con ML”.

---

## 10. Lo que **no** es el siguiente paso

| Tentación | Por qué no |
|-----------|------------|
| Otro retrain Tobarra KEEP | Ya **KILL**; no vende |
| ECE thrash U1 TEST | Ya falló; no vende |
| Flip `ml_product_go` | Mentira contractual |
| Más papers sin H1 | No cierra GO_Q |
| Scraping emails masivo | Ilegal/inútil vs 3 mails buenos |
| Confundir GO_MES con “vendido” | GO_MES = eng mínimo mes |

---

## 11. Comandos de demo comercial (copiar)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# 1) Puerta de entrada
python -m wildfire_front operator
python -m wildfire_front ensayo

# 2) Contraste políticas (ABSTAIN feature)
python -m wildfire_front decide --policy field_ops --explain
python -m wildfire_front decide --policy research_open --explain

# 3) Pack terceros + replay
python -m wildfire_front demo-third-party

# 4) Ops multipass Tobarra (S4)
python scripts/run_tobarra_multipass_s4.py --mode reuse
# ver outputs/tobarra_multipass_s4/S4_NOTE.md

# 5) ML lab (solo si preguntan; no como producto campo)
python -m wildfire_front ml freeze
python -m wildfire_front ml show
```

---

## 12. Resumen ejecutivo (10 líneas)

1. **Producto vendible hoy:** apoyo a la decisión auditado (card + dual ops/open + abstención).  
2. **No vendible hoy:** ML táctico live ni “predicción de frente garantizada”.  
3. **Eng está por delante del go-to-market:** falta **H1** y packaging de precio.  
4. **GO_MES true** da credibilidad de mes de ingeniería, no de cierre comercial.  
5. **S4 multipass** refuerza el pitch **ops térmico real** (usar en demo).  
6. **ML lab** es honestidad multi-fuego (Tobarra hard / KEEP kill) — fuerza anti-hype.  
7. **Siguiente acción única:** agendar tercero + ejecutar H1 runbook.  
8. **Después:** trust pack + 3 outreach + precio piloto.  
9. **No reabrir** thrash ML ni fusion.  
10. Criterio de “ya se vende piloto”: **V1–V5** de la sección 9.

---

## Referencias canónicas

| Doc | Uso |
|-----|-----|
| `docs/CURRENT_STATE.md` | Snapshot gates |
| `docs/GO_MES_VERDICT.md` | GO_MES mínimo |
| `docs/H1_GO_Q_RUNBOOK.md` | Cierre GO_Q |
| `docs/ONEPAGER_COMERCIAL_ES.md` | Qué se vende |
| `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` | Confianza auditor |
| `docs/PILOT_HONESTY_CARD.md` | Dual policy live |
| `docs/CONTACTOS_EMERGENCIAS_DATOS.md` | Outreach |
| `outputs/tobarra_multipass_s4/` | Ops S4 |
| `docs/goals/README.md` | Mega goals ML cerrados |
