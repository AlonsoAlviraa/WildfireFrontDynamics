# Curso WildfireFrontDynamics — dominio completo (para ti)

**Para:** aprender el proyecto de punta a punta y poder **enseñarlo** sin overclaim  
**Nivel:** de cero a dominio operativo (producto + CLI + rails + evidencia)  
**Estado de referencia:** 2026-08 · Graph **v6.1** · **GO_MES = true** · **GO_Q = partial** (falta demo+acta humana)

| Ruta | Tiempo | Qué cubres |
|------|--------|------------|
| **Exprés** | 45–60 min | Módulos 0–2 + flashcards del Módulo 14 |
| **Estándar** | 1 día | Módulos 0–8 + ejercicios prácticos |
| **Dominio** | 5–7 días | Todo el curso + autoexamen + ensayo de demo 12 min |

**Regla de este curso:** cada módulo tiene **leer → hacer → comprobar → no decir**.  
Si solo lees, no lo dominas. Si solo corres comandos sin el “no decir”, enseñas mal.

---

# Cómo usar este documento

1. Marca la casilla **✓** al final de cada módulo cuando pases el mini-examen.  
2. Los comandos asumen PowerShell en la raíz del repo.  
3. Cifras: **cita la fuente** (ops / lab / open / catalog). No mezcles.  
4. El bloqueante de producto **no es código**: es **H1** (demo + acta con tercero). El eng ya está listo para enseñar.  
5. **Empieza siempre por modo operario** (no por `show_all.py`).

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front operator
python -m wildfire_front operator checklist
```

> Semáforo + 4 actos + qué falta para GO_Q. Log UX: `docs/OPERATOR_UX_LOOP_LOG.md` · cheatsheet: `docs/CHEATSHEET_DEMO_12MIN.md`

---

# Módulo 0 — El problema y la promesa (15 min)

## 0.1 Qué problema ataca

En un incendio, sala e investigación quieren:

- ¿Hacia dónde avanza el frente?  
- ¿A qué velocidad (orden de magnitud)?  
- ¿Qué perímetro de referencia hay?  
- **¿Puedo confiar o debo callarme?**

La tentación tech es **siempre un mapa bonito**.  
WFD prefiere **HOLD / ABSTAIN** cuando faltan datos o la fiabilidad es baja.

## 0.2 Frase de producto (memoriza esta)

> **Apoyo a la decisión en incendios:** mido el frente cuando hay LWIR real, uso perímetros open cuando no hay dron, y emito **GO / HOLD / ABSTAIN** con auditoría. El ML de máscaras es **laboratorio**, no despacho táctico. En campo, la fusión ML live está **OFF**.

## 0.3 Qué NO es

| No es | Por qué |
|-------|---------|
| Sistema de extinción con IA | No manda medios |
| GPS táctico ROS garantizado | Sin térmico no inventa Vp |
| “Copernicus más guapo” | El valor es **postura + honestidad** |
| GO de campo con ML fusionado | `field_ops` fusion **OFF** |
| Predicción nacional next-day operativa | ML = protocol patches lab |

## 0.4 Foto de gates (hoy)

| Gate | Estado | Qué significa para ti |
|------|--------|------------------------|
| **GO_ENG** | true | CI / producto eng verde |
| **GO_MES** | **true** | Mínimo del mes (O1∧O4∧P1∧M2∧E1) |
| **GO_Q** | **partial** | Falta **demo tercero + acta (M3.2)** |
| **GO_MES+** | false | O2 oficial, O5 2º grade A, etc. |
| **ml_product_go** | true (lab) | Lab product GO · **≠** field fusion (OFF) |
| **field_ops ML fusion** | **OFF** | Rail no negociable en demos serias |

**Ejercicio 0:** explica en voz alta, sin papel:  
*“GO_MES true no implica GO_Q; GO_Q necesita un humano y un acta.”*

### Mini-examen 0

- [ ] Puedo decir la frase de producto sin “IA apaga incendios”  
- [ ] Sé que GO_MES ≠ GO_Q  
- [ ] Sé que ABSTAIN es feature  

---

# Módulo 1 — Mapa mental del repositorio (20 min)

## 1.1 Casa del proyecto

```
WildfireFrontDynamics/
├── wildfire_front/   ← biblioteca producto (CLI, Decision Card, ops, ML, open)
├── scripts/          ← demos, packs, hubs, third-party, open builders
├── config/           ← decision_policies.json
├── models/           ← catálogo ML (+ pesos locales a menudo gitignored)
├── data/             ← anchors, open_if crudos, fire_intel
├── outputs/          ← regenerable (demos, packs, incidents)
├── docs/             ← curso, portal, scorecards, informes, design
├── tests/            ← red de seguridad
├── artifacts/        ← LWIR/masks/patches (pesados, locales)
└── dist/             ← zips demo terceros
```

## 1.2 Tres capas de producto (no las mezcles)

| Capa | ID / pista | Produce | Analogía |
|------|------------|---------|----------|
| **Ops térmico** | `front_dynamics_v1` / incident | ROS, grade, brief, sectores | Reloj de sala **con dron** |
| **Open** | packs `open_if` / CEMS / Junta | ha, timeline, map, scorecard | Mapa multi-día **sin NDA** |
| **ML lab** | `clm_ensemble_v34` | máscara + conf de parche | Investigación con termómetro de duda |
| **Decision Card** | `decide` | GO/HOLD/**ABSTAIN** + reasons + audit | El árbitro que junta fuentes **sin entrenar** con la fusión |

## 1.3 Políticas

| Política | Uso mental | ML live en fusión |
|----------|------------|-------------------|
| **`field_ops`** | Sala / demo seria | **OFF** |
| **`research_open`** | Lab / experimentos | experimental |
| `default` | Intermedio | normalmente OFF |

**Regla de oro:** si dudas, enseña **`field_ops`**.

### Mini-examen 1

- [ ] Dibujas de memoria ops / open / ML / Card  
- [ ] Sabes qué carpeta es código vs scripts vs docs  
- [ ] field_ops = no ML live  

---

# Módulo 2 — Tour guiado: ver el producto (45–60 min)

Haz **en orden**. Objetivo: ver, no hackear.

## 2.0 Setup

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
```

## 2.1 Demo multi-CCAA (cara comercial)

```powershell
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html
```

| Sitio | Pista | Mensaje |
|-------|-------|---------|
| Tobarra (CLM) | **OPS** | ROS con térmico + ancla |
| Níjar (AND) | **OPEN** | perímetro Junta / REDIAM |
| Caminomorisco (EXT) | **OPEN** | otro contrato open |

**Pitch:** mismos **gates de honestidad**, tres contratos de datos.

## 2.2 Piloto honesty (la lección ABSTAIN)

```powershell
python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot
start outputs\pilot_honesty_card\index.html
```

Lee también: `docs/PILOT_HONESTY_CARD.md`

**Qué debes ver:**  
`research_open` a menudo más permisivo que `field_ops`.  
Si field_ops **ABSTAIN** y research_open **GO** → **no es bug**; es el producto.

## 2.3 Pack terceros + replay (evidencia eng)

```powershell
python scripts\build_demo_third_party_pack.py
python scripts\run_third_party_replay.py --bundle outputs\demo_third_party
# exit 0 ⇔ replay_ok
# o: make dry-run-demo-third-party
```

| Asset | Path |
|-------|------|
| Pack | `outputs/demo_third_party/` |
| Zip | `dist/demo_third_party_*.zip` |
| Reliability Report | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| IoU ≠ ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` |

**Enseña:** “validáis offline sin nosotros” · **No digas:** “replay_ok = anti-hackeable criptográfico”.  
Replay = **consistencia forense** del pack emitido.

## 2.4 Decision CLI desnuda

```powershell
python -m wildfire_front --help
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --policy field_ops
# sin fuentes ricas → ABSTAIN (bien)
```

## 2.5 ML offline → Card (lab)

```powershell
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold
python scripts\run_ml_live_card_demo.py --mode offline --scenario abstain
```

## 2.6 Portal + commander (opcional)

```powershell
python scripts\show_all.py
python scripts\build_commander_app.py
start docs\commander\index.html
```

### Mini-examen 2

- [ ] Abrí multi-CCAA y expliqué 3 pistas  
- [ ] Abrí piloto y expliqué por qué field_ops se calla  
- [ ] Corrí pack + replay y vi exit 0  
- [ ] Vi un ABSTAIN de `decide` sin inventar datos  

---

# Módulo 3 — Glosario operativo (consulta)

| Término | Significado | Trampa al enseñar |
|---------|-------------|-------------------|
| **ROS** | Velocidad de frente (m/min) | No = IoU |
| **Vp** | Velocidad de parte/ancla | **No inventar** sin fuente confirmed |
| **Grade A/B/C** | Calidad ops de la secuencia | Hellín **B** ≠ fallo de CI |
| **LWIR** | Térmico dron | Base del track ops |
| **Ancla confirmed** | Vp/ha con protocolo en `infocam_anchors.json` | Press/SITAC/Δha **no** son confirmed |
| **Pack open_if** | Carpeta industrial open | CEMS ≠ perímetro nacional O2 |
| **FIRMS** | Hotspots NASA | Hull ≠ área oficial |
| **IoU** | Solape de máscaras 0–1 | Solo lab/máscara |
| **ECE** | Calibración de confianza | ~0.15 lab; no “99% fuego” |
| **U1** | Gate incertidumbre ML | Lab promote rails |
| **Catalog 0.8963** | Holdout publicado | **Provenance only** |
| **GO / HOLD / ABSTAIN** | Posturas de la Card | ABSTAIN = valor |
| **GO_MES / GO_Q** | Gates de plan | MES true; Q partial |
| **field_ops** | Política sala | ML live OFF |
| **replay_ok** | Hashes/consistencia forense | No = autenticidad crypto |
| **Envelope 15/30/60** | Extrapolación geométrica corta | **No** despacho táctico |

---

# Módulo 4 — Carril OPS (térmico) (30–45 min)

## 4.1 Idea

Con **secuencia LWIR georreferenciada + timestamps**, se estima **ROS observado**, no “el fuego futuro de España”.

## 4.2 Anclas que debes saber de memoria

| IF | Vp ancla | ROS típico pack | Ratio | Grade |
|----|----------|-----------------|-------|-------|
| **Tobarra** | 7 m/min | ~5.71 | ~0.82 | **A** |
| **Hellín** | 50 m/min | ~27.9 | ~0.56 | **B** (honesto) |

- O1 multi-ancla: **PASS** (2 confirmed).  
- **No** calibrar un solo k Tobarra(7)↔Hellín(50).  
- O5 (2º grade A): **OPEN** / eng blocked sin datos nuevos.

## 4.3 CLI incident (campo mental)

```powershell
python -m wildfire_front incident --help
# doctor / update / watch / status
```

Conceptos: inbox de GeoTIFF, work-dir, outbox con Decision Card.

## 4.4 Lecturas cortas

- `docs/INCIDENT_RUNTIME_V1.md`  
- `docs/GEOTIFF_INPUT_CONTRACT.md`  
- `docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md` (sectores head/flank/rear)

## 4.5 Research que refuerza (no inventa SLA)

- **Lampman 2026:** repeat-pass TIR → ROS es **método** SOTA; sus MAE **no** son SLA de Tobarra Med.  
  (en Reliability Report §1)

### Mini-examen 4

- [ ] Tobarra A / Hellín B sin mirar tabla  
- [ ] “Sin térmico → no invento ROS táctico”  
- [ ] Sé qué es grade vs ratio vs Vp  

---

# Módulo 5 — Carril OPEN (30 min)

## 5.1 Idea

Sin dron: **perímetros y ha públicas** (CEMS, REDIAM, RAI…) con scorecard y honesty flags.

## 5.2 Qué hay en un pack

Típico bajo `outputs/open_if/<pack>/`:

- mapa / geo  
- métricas ha / timeline  
- scorecard / brief  
- a veces freshness (`content_checksum`, `freshness_score`)

```powershell
python scripts\audit_open_pack_freshness.py --pack outputs\open_if\emsr578 --write
python scripts\summarize_open_perimeter_attempt.py --help
```

## 5.3 No-claims open

| Decir | No decir |
|-------|----------|
| “Pack CEMS con ha de producto” | “Perímetro nacional EGIF desbloqueado” (**O2 BLOCKED**) |
| “Open multi-CCAA demoable” | “Sustituye al cadastro oficial” |
| “FIRMS da dirección/proxy” | “FIRMS = área quemada oficial” |

## 5.4 Lecturas

- `docs/design/DEMO_MULTI_CCAA_*.md`  
- `docs/O2_HAUSDORFF_BLOCKED.md` (si existe)  
- Open catalog / fire_intel completion matrix  

### Mini-examen 5

- [ ] Diferencio open pack vs O2 nacional  
- [ ] Sé que CEMS no cierra GO_MES+  

---

# Módulo 6 — Carril ML lab (30–40 min)

## 6.1 Idea

Ensemble España **`clm_ensemble_v34`**: predice **máscaras** en protocolo de patches + incertidumbre.  
**No** predice ROS de frente LWIR.

## 6.2 CLI producto ML (`wildfire-front ml`)

Superficie lab usable (offline list/show/doctor sin pesos):

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front ml list              # catálogo + default + not_for
python -m wildfire_front ml show              # U1 IoU, ECE, ml_product_go, fusion OFF
python -m wildfire_front ml show --json
python -m wildfire_front ml cases             # fail buckets + LOFO + reject teach board
python -m wildfire_front ml cases --bucket accepted_low_iou
python -m wildfire_front ml curve             # cobertura→IoU + thr map (no retune ECE)
python -m wildfire_front ml freeze            # handoff lab_usable ≠ campo
python -m wildfire_front ml doctor            # pesos MISSING = informe, no crash
python -m wildfire_front ml card --mode offline --scenario hold
python -m wildfire_front ml card --mode offline --scenario abstain
python -m wildfire_front ml predict --list-products
```

**Banner de honestidad:** lab product · not field_ops fusion · IoU ≠ ROS  

Entrada 5 min: `docs/ML_PRODUCT_START_HERE.md` · cheatsheet: `docs/CHEATSHEET_ML_LAB.md` · plan: `docs/PLAN_ML_PRODUCT_USABLE.md`

## 6.3 Números de pitch (lab)

| Métrica | ~Valor | Etiqueta al enseñar |
|---------|--------|---------------------|
| U1 TEST mean IoU | ~**0.86** | lab holdout (no universal) |
| LOFO mean IoU | ~**0.76** (n=3) | multi-fuego; protocolo distinto |
| Selective@80 IoU | ~**0.90** | lab |
| ECE | ~**0.15** | calibración imperfecta (post-hoc no arregló) |
| Lab reject thr | ~**0.80** | ABSTAIN de máscara; IoU acc ~0.95 |
| Catalog holdout IoU | **0.8963** | **provenance only** |
| `ml_product_go` | **true (lab)** | lab only · field fusion OFF |
| NDWS v21 / G1 | KILL features | no reabrir como primary |

## 6.3b Fail cases al enseñar (`ml cases`)

| Bucket | Qué cuenta |
|--------|------------|
| `accepted_low_iou` | Conf alta + IoU flojo → overconfianza residual |
| `rejected_high_iou` | Conf < thr pero IoU alto → coste del reject thr~0.80 |

Superficie lab locked: **iter1 reject only**. No re-tunear ECE en el mismo TEST sin datos nuevos.

## 6.3c Curva cobertura→IoU (`ml curve`)

| coverage | ~selective IoU TEST |
|---------:|--------------------:|
| 100% | ~0.86 (full) |
| 80% | ~0.90 (ranking conf útil) |
| thr~0.80 reject | keep ~0.49 · IoU acc ~0.95 |

Selective ranking **≠** thr-based reject. Enseña ambos.

## 6.3d Freeze handoff (`ml freeze`)

| Claim | Valor al enseñar |
|-------|------------------|
| lab_usable_freeze | true (CLI + evidencia completa) |
| ml_product_go / field fusion | **true (lab)** / **OFF** |
| ece_fixed | **false** |
| surface | iter1 reject thr ~0.80 |

Freeze **≠** promote a campo.

## 6.4 Fuentes

- `docs/ML_PRODUCT_SCORECARD.json`  
- `docs/ML_U1_PROMOTE_RECORD.json`  
- `docs/METRICS_HONESTY_IOU_NE_ROS.md`  
- `models/catalog.json`  
- `docs/ML_PRODUCT_START_HERE.md`  
- `docs/design/DESIGN_ML_LAB_LOOP_CONTINUOUS.md`  
- `outputs/ml_eval/lab_loop/lab_loop_v34_fail_cases_test.json`  

## 6.5 Frase anti-error

> “El IoU mide solape de **máscara lab**, no metros por minuto del frente en Tobarra.”

### Mini-examen 6

- [ ] 0.86 vs 0.8963 en una frase cada uno  
- [ ] LOFO ~0.76 ≠ U1 ~0.86 (protocolos distintos)  
- [ ] Nunca digas IoU = velocidad  
- [ ] ml_product_go true (lab) · fusion OFF  
- [ ] Sé lanzar `wildfire-front ml show` y `ml cases`; fusion OFF  

---

# Módulo 7 — Decision Card a fondo (45 min)

## 7.1 Flujo

```
ops_metrics ──┐
open_metrics ─┼──► política (field_ops / research_open)
ml_live ──────┘         │
                        ▼
              GO | HOLD | ABSTAIN
              + reasons + sources + hashes
```

## 7.2 CLI esencial

```powershell
python -m wildfire_front decide --help
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --policy field_ops
python -m wildfire_front decide --use-ml-v34 --policy field_ops
python -m wildfire_front decide --use-ml-v34 --policy research_open

python -m wildfire_front export-acta --help
python -m wildfire_front replay-decide --help
python -m wildfire_front serve-decide --port 8765
```

## 7.3 Cómo leer una Card (JSON o MD)

1. `decision`  
2. `confidence` / `confidence_pred`  
3. Fuentes: available / weight / fused?  
4. `reasons` (legibles)  
5. `disclaimers`  
6. reliability / system gates si existen  

## 7.4 Mapeo UQ (Orion-style rails, no pesos Orion)

| Señal | Postura típica |
|-------|----------------|
| Fuentes fuertes + conf alta | GO (según política) |
| Señal media / parcial | HOLD |
| Falta ops en field_ops, conf baja, etc. | **ABSTAIN** |

No renombres a SAFE/EVACUATE en producto ES.

## 7.5 Forense

- `export-acta` → acta + radio-bridge  
- `replay-decide` / `run_third_party_replay.py` → verifica hashes  

### Mini-examen 7

- [ ] Corrí decide vacía → ABSTAIN y lo celebré  
- [ ] Expliqué field_ops vs research_open  
- [ ] Sé que replay no es “certificado crypto”  

---

# Módulo 8 — CLI de producto completa (30 min)

## 8.1 Mapa de comandos raíz

```text
wildfire-front / python -m wildfire_front
├── demo              demo sintético con ground truth
├── ingest-geotiff    batch LWIR → productos ops
├── incident          doctor | update | watch | status
├── decide            Fire Decision Card
├── serve-decide      HTTP POST /v1/decide
├── export-acta       forense + radio
└── replay-decide     re-verifica hashes
```

## 8.2 Scripts “producto” que debes saber (además de CLI)

| Script / make | Rol en la historia |
|---------------|-------------------|
| `build_demo_multi_ccaa.py` | Acto venta multi-pista |
| `run_pilot_honesty_card.py` | Acto ABSTAIN |
| `build_demo_third_party_pack.py` | Acto evidencia externa |
| `run_third_party_replay.py` | Acto replay |
| `make dry-run-demo-third-party` | Ensayo pre-demo humana |
| `run_ml_live_card_demo.py` | Acto ML lab |
| `show_all.py` / PORTAL | Mapa del repo |
| `build_metrics_hub.py` | Hub métricas + abstention |

## 8.3 Ruta de aprendizaje en 4 actos (memoriza)

> **Modo operario (preferido):** `python -m wildfire_front operator`  
> **Ejecutar acto N:** `python -m wildfire_front operator do --act N`  
> **CLI teach (detalle):** `python -m wildfire_front teach`  
> **Cheatsheet 12 min:** `docs/CHEATSHEET_DEMO_12MIN.md`  
> **Gates snapshot:** `python -m wildfire_front show`  
> **ABSTAIN plain:** `python -m wildfire_front operator explain-abstain`

| Acto | Comando operario | Mensaje |
|------|------------------|---------|
| 1 Ver | `operator do --act 1` | mismos gates, 3 contratos |
| 2 Callarse | `operator do --act 2` | field_ops se calla — ABSTAIN ≠ bug |
| 3 Decidir | `operator do --act 3` | GO/HOLD/ABSTAIN en lenguaje normal |
| 4 Probar | `operator do --act 4` | pack + replay_ok (no firma cripto) |

Scripts sueltos (`build_demo_multi_ccaa.py`, …) siguen existiendo; el operario **no** los necesita.

### Mini-examen 8

- [ ] Listas de memoria los 4 actos  
- [ ] Sabes el comando único `operator` + `do --act N` sin abrir el curso  
- [ ] Sabes qué falta para GO_Q (H1 humano, no más eng)  

---

# Módulo 9 — Honestidad y kill list (15 min, memorizar)

## 9.1 Diez mandamientos

1. No inventes ROS/Vp sin térmico o ancla confirmed.  
2. FIRMS hull ≠ quemado oficial.  
3. Ops ≠ ML en la cabeza y en el pitch.  
4. **ABSTAIN es feature.**  
5. 0.8963 = provenance, no certeza en vivo.  
6. U1 ~0.86 = lab, no “Níjar mañana”.  
7. field_ops no fusiona ML live.  
8. O2 nacional sigue BLOCKED aunque tengas CEMS.  
9. Replay_ok ≠ autenticidad criptográfica.  
10. Un email de CCAA no inventa ancla.

## 9.2 Frases prohibidas en demo

| Prohibido | Sustituto |
|-----------|-----------|
| “99.9999% de acierto del fuego” | “Gates anti-GO silencioso en tests; el fuego no se predice al 99%” |
| “El modelo dice evacuar” | “Card de monitoreo/apoyo; el mando decide” |
| “Hellín es A con nuestro k único” | “Hellín B; no unificamos k con Tobarra” |
| “Open = oficial nacional” | “Open proxy; O2 nacional blocked” |
| “IoU 0.89 = ROS fiable” | “IoU es máscara lab; ROS es ops térmico” |

### Mini-examen 9

- [ ] Recitas 5 mandamientos  
- [ ] Detectas un overclaim en un pitch inventado  

---

# Módulo 10 — Estado del proyecto y bloqueantes (20 min)

## 10.1 Hecho (eng)

- Pack terceros, Reliability Report, replay, contrato GeoTIFF, open freshness, hub abstention  
- Informe trimestre eng-filled: `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md`  
- CyL silence note (wait ~2026-08-17)  
- Research map / industry notes  

## 10.2 Bloqueantes que te faltan (honestos)

| Prioridad | ID | Qué | Dueño |
|-----------|-----|-----|--------|
| **P0** | **H1 / M3.2** | Demo + **acta firmada** | Humano → **GO_Q** |
| **P0** | **H3** | Dry-run operador del pack | Humano (eng ready) |
| P1 | H4 | Shadow 1 organismo | Humano |
| P2 | O2 | Perímetro nacional | Externo |
| P2 | O5 | 2º grade A | Datos/policy |
| P2 | 3ª ancla | Cardoso Vp formal etc. | Externo |

Lectura: `docs/GO_MES_VERDICT.md`, `docs/PLAN_1_MES_GRAPH_V6_STATUS.json`.

### Mini-examen 10

- [ ] “El bloqueo de GO_Q es humano H1, no falta de U-Net”  
- [ ] Listas O2 y O5 como stretch, no como “está roto el CI”  

---

# Módulo 11 — Cómo enseñar a otros (30 min + ensayo)

## 11.1 Guion 12 minutos (estructura)

| Min | Qué | Material |
|-----|-----|----------|
| 0–1 | Problema + frase producto | Módulo 0 |
| 1–4 | Multi-CCAA 3 pistas | portal |
| 4–7 | Piloto honesty / se calla | field_ops vs research |
| 7–10 | Pack + replay o Decision Card | evidencia |
| 10–12 | Límites + “qué falta (demo humana)” | no overclaim |

Guion formal: `docs/GUION_DEMO_30MIN_POST_O1.md` (versión larga).  
Acta: `docs/ACTA_DEMO_TERCERO_TEMPLATE.md`.

## 11.2 Ejercicio de dominio (obligatorio para “ya lo sé”)

1. Grábate o habla 8–12 min.  
2. Checklist anti-overclaim (Módulo 9).  
3. Si dices “IA predice el frente en vivo con ML en field_ops”, **repite**.

## 11.3 Preguntas que te van a hacer (y respuestas cortas)

| Pregunta | Respuesta corta |
|----------|-----------------|
| ¿Sustituye a Technosylva/CAL FIRE sim? | No. Ellos simulan spread a escala agencia; nosotros **medimos frente LWIR** y **nos callamos** sin datos. |
| ¿Funciona sin dron? | Sí, open packs; sin ROS táctico térmico. |
| ¿Cuál es la precisión? | No hay un % del fuego. Hay gates, ROS vs ancla, IoU lab etiquetado. |
| ¿Está listo para comprar? | Eng+evidencia listos; falta validación con tercero (acta) y anclas extra para stretch. |

### Mini-examen 11

- [ ] Ensayé 12 min una vez  
- [ ] Respondí las 4 preguntas sin inventar  

---

# Módulo 12 — Código: orientación (opcional, 45 min)

No memorices archivos; memoriza **dónde vive cada capa**.

| Necesitas | Mira |
|-----------|------|
| Decision Card / políticas | `wildfire_front/product/` |
| CLI | `wildfire_front/cli.py`, `cli_incident.py` |
| ROS ops | `front_dynamics`, scientific ops, incident pipeline |
| Open packs | `wildfire_front/open_if/`, `scripts/build_*_if_pack*` |
| ML | `wildfire_front/ml/`, `models/` |
| Forense | `wildfire_front/product/forensics.py` |
| Fuel/hybrid | `wildfire_front/fuel/` |

Tests de humo útiles:

```powershell
python -m pytest tests/test_demo_third_party_pack.py tests/test_pilot_honesty_card.py -q
python -m pytest tests/ -q -m "not slow and not requires_weights"
```

### Mini-examen 12

- [ ] Sabes en qué paquete está la Card  
- [ ] Sabes dónde está el CLI  

---

# Módulo 13 — Mapa de lecturas (cuándo abrir cada doc)

| Si quieres… | Abre |
|-------------|------|
| 2 minutos | `docs/START_HERE.md` |
| **Este curso** | `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` |
| Gates mes | `docs/GO_MES_VERDICT.md` · `PROJECT_STATUS.md` |
| Plan implement | `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` · STATUS json |
| Informe relleno | `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` |
| Reliability terceros | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| IoU ≠ ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` |
| Pitch comercial | `docs/ONEPAGER_COMERCIAL_ES.md` |
| Políticas | `docs/design/DECISION_POLICY.md` · `config/decision_policies.json` |
| Research→IDs | `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` |
| SOTA stack | `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` |
| Industria ferias | `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_…` |
| Graph state | `.grok/graph_engineering/STATE.md` |

---

# Módulo 14 — Flashcards (repaso diario 10 min)

Cubre la carta y di la respuesta.

1. **¿Producto en una frase?** → Apoyo a decisión: ops + open + Card con ABSTAIN; ML lab.  
2. **¿Tres capas?** → Ops térmico · Open · ML lab · (Card fusiona).  
3. **¿field_ops y ML?** → Fusion live **OFF**.  
4. **¿GO_MES vs GO_Q?** → MES true (mínimo); Q partial (falta acta demo).  
5. **¿Tobarra / Hellín?** → A ~5.71/7 · B ~28/50.  
6. **¿0.86 vs 0.8963?** → U1 lab · catalog provenance.  
7. **¿IoU = ROS?** → **No.**  
8. **¿ABSTAIN?** → Feature de honestidad.  
9. **¿O2?** → Perímetro nacional BLOCKED; CEMS es proxy.  
10. **¿replay_ok?** → Consistencia forense del pack, no crypto-auth.  
11. **¿Qué bloquea GO_Q?** → H1 demo + acta humana.  
12. **¿Qué no reentrenas este mes?** → Ensemble / WFTS por moda.  

---

# Módulo 15 — Plan de 7 días (dominio)

| Día | Objetivo | Hacer |
|-----|----------|--------|
| **1** | Producto | M0–2: demos + pack replay |
| **2** | Idioma | M3–4 + flashcards 1–6 |
| **3** | Open + ML | M5–6 + scorecards |
| **4** | Card + CLI | M7–8 todos los comandos |
| **5** | Honestidad + bloqueos | M9–10 |
| **6** | Enseñar | M11 ensayo 12 min |
| **7** | Cierre | Autoexamen M16 + dry-run H3 |

---

# Módulo 16 — Autoexamen final

Marca solo si puedes **explicar en voz alta sin el PDF**:

### Producto
- [ ] Frase de producto  
- [ ] Dual/triple capa + Card  
- [ ] GO / HOLD / ABSTAIN con ejemplo  
- [ ] field_ops vs research_open  

### Datos
- [ ] Tobarra A y Hellín B con orden de magnitud  
- [ ] Open vs O2 nacional  
- [ ] FIRMS ≠ ha oficial  

### ML
- [ ] U1 ~0.86 y catalog 0.8963 etiquetados  
- [ ] IoU ≠ ROS  
- [ ] ml_product_go true (lab) · fusion OFF  

### Evidencia y gates
- [ ] Cómo construir pack y qué es replay_ok  
- [ ] GO_MES true / GO_Q partial / por qué  
- [ ] Bloqueante H1  

### Enseñar
- [ ] Guion 12 min ensayado  
- [ ] 3 overclaims que no cometerás  

**Umbral dominio:** ≥ 14/16.  
**Umbral “puedo dar una call corta”:** ≥ 10/16 + ensayo 12 min.

---

# Apéndice A — Cheatsheet de comandos

> **Operario (preferido):** `python -m wildfire_front operator` · 12 min: `docs/CHEATSHEET_DEMO_12MIN.md`  
> Teach detalle: `python -m wildfire_front teach`

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# --- Modo operario (única puerta) ---
python -m wildfire_front operator
python -m wildfire_front operator do --act 1   # Ver
python -m wildfire_front operator do --act 2   # Callarse
python -m wildfire_front operator do --act 3   # Decidir
python -m wildfire_front operator do --act 4   # Probar
python -m wildfire_front operator checklist
python -m wildfire_front operator explain-abstain

# --- Product teach surface (v7, detalle) ---
python -m wildfire_front teach
python -m wildfire_front show
python -m wildfire_front demo-third-party

# --- Acto 1 equiv. scripts (opcional) ---
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html

# --- Acto 2 equiv. scripts (opcional) ---
python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot
start outputs\pilot_honesty_card\index.html

# --- Acto 3 equiv. decide ---
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --policy field_ops
python -m wildfire_front decide --policy field_ops --explain

# --- Acto 4: evidencia terceros ---
python -m wildfire_front demo-third-party
# equiv: python scripts\build_demo_third_party_pack.py
#        python scripts\run_third_party_replay.py --bundle outputs\demo_third_party
# make dry-run-demo-third-party

# --- ML lab ---
python -m wildfire_front ml list
python -m wildfire_front ml show
python -m wildfire_front ml card --mode offline --scenario hold
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold

# --- Portal ---
python scripts\show_all.py

# --- Tests offline ---
python -m pytest tests\test_demo_third_party_pack.py tests\test_pilot_honesty_card.py -q
```

---

# Apéndice B — Números “de pizarra” (solo con etiqueta)

| Número | Etiqueta obligatoria |
|--------|----------------------|
| ROS Tobarra ~5.7 m/min | ops · vs Vp 7 · grade A |
| ROS Hellín ~28 m/min | ops · vs Vp 50 · grade B |
| U1 IoU ~0.86 | **lab** |
| Catalog IoU 0.8963 | **provenance only** |
| ECE ~0.15 | **lab calibración** |
| GO_MES | **true** (mínimo plan) |
| GO_Q | **partial** (falta M3.2) |

---

# Apéndice C — Checklist pre-demo humana (H3 → H1)

- [ ] `PYTHONPATH=.`  
- [ ] multi-CCAA HTML abre  
- [ ] pilot honesty abre  
- [ ] pack rebuild + replay exit 0  
- [ ] Frase producto ensayada  
- [ ] Overclaim list repasada (M9)  
- [ ] Guion 12 o 30 min impreso/abierto  
- [ ] Acta template lista para rellenar **el mismo día**  
- [ ] No prometo O2/O5/ml fusion en la demo  

---

# Apéndice D — Historial del curso

| Versión | Cambio |
|---------|--------|
| 2026-07-ish | Curso original “desconocidos” |
| **2026-08** | Dominio completo: gates GO_MES/Q, pack terceros, flashcards, 7 días, autoexamen, teach path, bloqueantes H1 |

---

*Cuando marques el autoexamen ≥14/16 y hayas ensayado 12 min, el siguiente paso del plan de producto no es otro doc: es **H3 dry-run + H1 demo con acta**.*
