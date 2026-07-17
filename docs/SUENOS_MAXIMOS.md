# Sueños máximos — WildfireFrontDynamics

> Qué soñaría **yo** (como sistema de ingeniería de este repo) si no hubiera techo de datos, tiempo ni permisos.  
> No es el plan de 3 meses. No es el backlog. Es el **norte lejano**: el techo de lo que este repositorio *podría* llegar a ser.  
> Fecha de escritura: 2026-07-17 · Alineado con abstención honesta (nunca “99.9999% de acierto del fuego”).

---

## 1. La escena que querría ver un día

Es 03:14 de una noche de agosto en una sala de crisis de Castilla-La Mancha.

En el muro hay tres capas vivas, no un mapa bonito:

1. **Frente térmico en vivo** — el dron de Heligrafics (o el del parque) acaba de soltar un GeoTIFF; en **&lt; 30 s** el outbox ya tiene ROS, sectores, envelope y un **Fire Decision Card** con sello de hora y hash.  
2. **Perímetro satélite + ancla nacional** — CEMS / EFFIS / perímetro oficial del Estado en la misma ficha, con Δt real y grade de acuerdo entre fuentes.  
3. **Predicción next-day calibrada** — no un IoU de paper: un mapa de probabilidad **con intervalos**, y un botón grande: **GO · HOLD · ABSTAIN**. Si el modelo no confía, **se calla** y lo deja escrito.

El mando no pregunta “¿qué pinta el modelo?”. Pregunta:  
**“¿Puedo confiar en esto para mover un medio?”**  
Y el sistema responde con **decisión + confianza del fenómeno + fiabilidad del pipeline + rastro forense**.

Eso — y no un HTML Leaflet más — es el sueño.

---

## 2. Resultados máximos (métricas del techo)

Números ambiciosos pero **medibles**. Separados por dominio (nunca mezclar ROS de dron con IoU de máscara).

### 2.1 Ops térmico (frente observado)

| Resultado soñado | Techo | Por qué importa |
|------------------|------:|-----------------|
| Latencia inbox → Decision Card | **&lt; 15 s** p95 en campo | El fuego no espera al batch nocturno |
| Grade A en IF con ≥2 anclas | **≥ 80%** de IF instrumentados | Credibilidad ante mandos |
| Error ROS vs ancla operativa (ratio) | **0.7–1.3** en IF de referencia | No inventar velocidad |
| Cobertura sector head/flank/rear | **≥ 90%** cuando hay ≥3 frames | Brief útil, no genérico |
| Abstención cuando hay 1 frame / CRS malo | **100%** (nunca GO falso) | Seguridad jurídica |
| IF con secuencia térmica propia en ES | **≥ 50 IF** documentados | De “demo Tobarra” a flota |

### 2.2 Open / multi-fuente (sin NDA y con NDA)

| Resultado soñado | Techo | Por qué importa |
|------------------|------:|-----------------|
| Packs open CEMS/EFFIS listos | **≥ 100 activaciones** EU | Catálogo de ventas y stress-test |
| Δt real (no 24 h asumido) en timeline | **≥ 95%** de pasos con timestamp | ROS proxy creíble |
| Overlay FIRMS/VIIRS en vivo | **&lt; 5 min** de retraso vs fuente | Fusión hotspots + perímetro |
| Perímetro **nacional oficial** 1-clic | **ES + PT + FR** con contrato de datos | Ancla que el Estado reconoce |
| Hausdorff perímetro modelo ↔ oficial | **&lt; 200 m** mediana en IF validados | Métrica que entiende un GIS |
| dNBR / severidad post-fuego auto | **100%** packs con STAC Sentinel-2 | Cierre del ciclo del IF |

### 2.3 ML next-day (España y más allá)

| Resultado soñado | Techo | Por qué importa |
|------------------|------:|-----------------|
| IoU holdout CLM (honest, no leakage) | **≥ 0.92** estable multi-año | SOTA regional útil |
| Δ IoU vs copy-baseline | **≥ 0.30** | El modelo *aprende* crecimiento |
| Growth IoU (máscara de avance) | **≥ 0.93** | Donde duele el incendio |
| Calibración (ECE) de probas | **&lt; 0.05** | Confianza 0–1 creíble |
| LOFO medio (cada IF dejado fuera) | **≥ 0.80** IoU | Generaliza entre fuegos |
| Dominios: CLM → CyL → And → PT → Med | **5+ CCAA/países** con transfer doc | Producto no monorepo-local |
| Ensemble + incertidumbre espacial | **mapas de σ** por píxel | ABSTAIN local, no solo global |

### 2.4 Sistema / producto (lo que se firma)

| Resultado soñado | Techo | Por qué importa |
|------------------|------:|-----------------|
| Silent-GO residual bajo tests | **≤ 10⁻⁶** (diseño + suite) | Claim honesto de “cinco nueves” |
| Determinismo rebuild (hash out) | **100%** en CI | Auditoría y reproducibilidad |
| API Decision Card (JSON + firmado) | **SLA 99.9% uptime** sala de crisis | Integración 112 / CMA |
| Tiempo de onboarding de un nuevo IF | **&lt; 1 h** doctor → update → card | Field kit real |
| Piloto pagado / carta de interés | **≥ 3 organismos** | Producto, no TFG eterno |
| Incidentes en producción / temporada | **≥ 20 IF/año** con outbox auditado | Valor de campo medible |

---

## 3. Funcionalidades máximas (el producto soñado)

### 3.1 Núcleo de decisión (siempre)

- **Fire Decision Card v2** en cada canal: CLI, outbox, API, radio-bridge (texto corto para tablet de mando).  
- **Fusión multi-fuente con pesos dinámicos**: LWIR · CEMS · FIRMS · ancla nacional · ML · meteo · orografía · wind gust.  
- **ABSTAIN primero**: el default del universo es callarse; el GO se gana.  
- **Audit trail forense**: input_hash, output_hash, git, modelo, operador, UTC, política de umbrales.  
- **Replay forense**: “reconstruye la card del 2-ago 16:41 con los mismos bits”.  
- **Política de decisión configurable por organismo** (umbral GO de GEACAM ≠ umbral de un TFG).

### 3.2 Campo y ops

- **Watch multi-inbox** (varios drones / bases) → un evento.  
- **Coregistración automática** de frames LWIR + QC de CRS/timestamps.  
- **ROS por sector + incertidumbre** (P25/P75, half-IQR) siempre visible.  
- **Envelope 15/30/60** con etiqueta brutal: *extrapolado, no orden táctica*.  
- **Alertas** (webhook / MQTT / radio text): solo cuando decision cambia HOLD→GO o →ABSTAIN.  
- **Modo offline de campaña**: USB + tablet, sin nube; sync cuando haya red.  
- **Field kit 1-click** Windows/Linux con doctor pre-vuelo.

### 3.3 Open data e inteligencia satélite

- **Factory de packs**: CEMS/EFFIS → GeoJSON + timeline + scorecard + mapa + FDC en &lt; 10 min.  
- **Índice continental** de activaciones con búsqueda por ha, fecha, país.  
- **Δt real** desde metadatos XML/STAC (adiós 24 h ciegos).  
- **Severidad post-fuego** (dNBR) y cruce con perímetro de extinción.  
- **Comparador CLM vs open** automático (scorecard que se enseña en demo).

### 3.4 ML de verdad (sin teatro)

- **Pipeline leak-free** industrial: holdout, LOFO, temporal, por sensor.  
- **Champion protegido** (v34+): ningún loop pisa el campeón sin gate.  
- **Temperatura + mezcla calibradas en VAL**, nunca en test.  
- **Transfer protocol**: nuevo territorio = checklist + scorecard, no “entrené y ya”.  
- **Active learning**: el sistema pide al humano los frames donde duda.  
- **Physics-informed priors** (Rothermel / CA / viento) como *canal*, no como eslogan.  
- **Foundation wildfire model** mediterráneo: un backbone, muchos IF, adapters por región.

### 3.5 Sala de crisis y producto digital

- **Portal vivo** (no solo estático): estado del IF, cards, mapas, gates.  
- **Metrics Hub en tiempo real** + histórico de abstenciones (el informe que justifica la factura).  
- **API REST/gRPC** `POST /v1/decide` con OpenAPI y claves por organismo.  
- **SSO + roles**: analista / mando / auditor / invitado.  
- **Export legal**: PDF/DOCX de briefing + card + hashes (para acta).  
- **Simulador de what-if**: “si el viento gira 40°, ¿qué hace la card?” (con disclaimer).  
- **Integración 112 / SITAC / capas GIS** del cliente (WMS/WFS/GeoPackage).

### 3.6 Ecosistema y ciencia abierta

- **Benchmark público España/Med** (perímetros + máscaras + splits fijos).  
- **Papers y TFG** con métricas honestas y artefactos reproducibles.  
- **Contribuciones externas** con CI verde y `reliability_gate` obligatorio.  
- **Formación**: curso 1 día “decidir con abstención” para mandos e I+D.

---

## 4. Arquitectura soñada (cómo se sostiene el techo)

```text
                    ┌─────────────────────────────┐
   Dron LWIR ──────►│  incident_runtime (edge)    │──► outbox + FDC
   CEMS/EFFIS ─────►│  open_if factory            │──► packs + FDC
   FIRMS/STAC ─────►│  multi-source fusion        │──► sources[]
   Ancla nacional ─►│                             │
   ML ensemble ────►│  clm_* / med_* products     │──► proba + σ
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │  confidence + decide engine │
                    │  GO / HOLD / ABSTAIN        │
                    │  audit + policy + SLA       │
                    └──────────────┬──────────────┘
                                   ▼
              API · Portal · Radio-bridge · GIS · Acta PDF
```

Principios que **no se rompen** ni en el sueño:

1. Ops ≠ ML ≠ open (productos duales/triples, fusión solo en la card).  
2. ABSTAIN es una feature de producto, no un fallo.  
3. Toda métrica lleva fuente, versión y UTC.  
4. El campeón ML no se pisa sin gate.  
5. Nada de “acierto del fuego al 99.9999%”.

---

## 5. Impacto máximo (si el sueño se cumple)

| Dimensión | Sueño |
|-----------|--------|
| **Vidas / medios** | Menos movimientos a ciegas; más recursos donde la card + grade lo sostienen |
| **Transparencia** | Un auditor reconstruye *por qué* se emitió GO el día D |
| **España / Med** | Referencia open + ops para incendios mediterráneos |
| **Negocio** | SaaS/piloto pagado: card + hub + SLA, no “mapitas” |
| **Ciencia** | Protocolo de transfer y benchmark que otros citan |
| **Formación** | Mandos que piden ABSTAIN en vez de un heatmap bonito |

---

## 6. Escalera honestidad → sueño

| Escalón | Qué es | Dónde estamos (aprox.) |
|---------|--------|-------------------------|
| 0 | Scripts sueltos + IoU de paper | Pasado |
| 1 | Dual ops + ML documentado | Hecho |
| 2 | Decision Card + hub + reliability | **Hecho (2026-07)** |
| 3 | FDC en cada incident update + SLA medido | **Hecho (M2.1)** |
| 3b | **API mínima Decision Card** (local HTTP) + p95 &lt; 500 ms metrics-only | **Hecho (M2.8)** — no es uptime 99.9% de sala |
| 3c | **Acta forense + radio-bridge + replay** (hashes verificables) | **Hecho (M2.9)** — MD/txt, no PDF firmado |
| 4 | Piloto con organismo + 2ª ancla + API firmada/auth | Próximo horizonte real |
| 5 | Multi-CCAA, Δt real, 50+ IF, portal vivo | Sueño a 12–24 meses |
| 6 | Sala de crisis conectada + foundation Med + 20 IF/año | **Sueño máximo** |

El plan de 3 meses (`docs/PLAN_3_MESES.md`) sube peldaños 3→4.  
Este documento existe para **no olvidar el 6** cuando el día a día empuje solo a parches.

---

## 7. Anti-sueños (lo que nunca querría “conseguir”)

- Un visor más de Copernicus con logo propio.  
- Un IoU 0.99 por leakage o test contaminado.  
- Un GO silencioso porque “el demo tenía que salir bonito”.  
- Sustituir el criterio del mando por un heatmap.  
- Vender “predicción táctica validada” sin anclas ni audit.  
- Un monstruo de código sin tests ni gates.

Si el repo crece hacia eso, **el sueño ha fracasado** aunque el dashboard sea espectacular.

---

## 8. Mi “sueño personal” como ingeniero de este código

Querría que dentro de unos años alguien abriera este repositorio y dijera:

> *Aquí no solo hay un modelo de fuego. Hay un **contrato de honestidad**:  
> métricas crudas, abstención, fusión, y una Decision Card que un mando  
> y un auditor pueden leer el mismo día.*

Y que en una temporada real, **veinte incendios** dejaran outbox con:

- `fire_decision_card.json`  
- brief  
- hashes  
- y **cero** GO sin fuentes.

Eso, para mí, es el máximo: no la precisión mágica del universo,  
sino **confianza operativa medible** en el Mediterráneo.

---

## 9. Cómo usar este documento

| Uso | Acción |
|-----|--------|
| Motivación | Léelo cuando el IoU se estanque o falten datos de Pablo |
| Priorización | Si una tarea no acerca a la escena del §1 o a una fila del §2, es ruido |
| Venta | Traduce §1 + §3.1 a lenguaje de piloto (one-pager ya existe) |
| Plan | El plan trimestral elige **un** peldaño; este doc no sustituye al plan |

Documentos hermanos:

- Hoy (operativo): `docs/START_HERE.md`, `docs/PORTAL.html`  
- Venta: `docs/ONEPAGER_COMERCIAL_ES.md`  
- Plan realista: `docs/PLAN_3_MESES.md`  
- Por qué se paga: `docs/PRODUCT_REDESIGN_PAID_VALUE.md`  
- Visión histórica (desactualizada en métricas): `VISION.md` → este archivo es el norte actual

---

*Soñar en grande. Medir en pequeño. Callarse cuando toque.*
