# Research de industria 2024–2026: congresos, ferias, estudios, open source y mejoras para WildfireFrontDynamics

> **Fecha:** 2026-08-04  
> **Enfoque pedido:** China · California · ferias · hasta la novedad mínima · estudios · OSS · producto  
> **Audiencia:** decisión de producto / outreach / engineering prioritization  
> **Relacionado:** `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`, `docs/VENDOR_CN_INVENTORY.md` (si existe)

---

## 0. Mensaje ejecutivo (1 página)

| Hallazgo | Implicación para WFD |
|----------|----------------------|
| El mercado “firetech” en **California** se concentra en **detección temprana** (cámaras AI, sensores de gas, satélites térmicos) y **simuladores de spread operativos** (Technosylva en CAL FIRE), no en ROS de frente LWIR de dron. | Vuestro nicho (frente térmico observado + Decision Card + ABSTAIN) **casi no está ocupado** en las ferias CA. Oportunidad de posicionamiento; también soledad de comparables. |
| En **China** el ecosistema es **equipamiento + UAV + extinción + mando**, con ferias grandes en Beijing (forest/grassland fire equipment, China Fire, China Emergency Expo). Menos “paper product”, más hardware/drone/comms. | Útil para **proveedores térmicos / adaptadores de entrada**, no para anclas ROS oficiales occidentales. Contrato GeoTIFF multi-vendor gana peso. |
| **Open source** maduro en **simulación** (ELMFIRE, ForeFire) y **datasets satélite** (NDWS, WildfireSpreadTS, TS-SatFire, BCWildfire). Pobre en **ops LWIR multi-IF con ROS medido**. | Refuerza la tesis: el gap de WFD no es otra U-Net; es **anclas + terceros + diversificación de sensores**. |
| Eventos prioritarios 2026–2027: **Red Sky Summit (SF)**, **INTERSCHUTZ WildfireCamp (Hannover)**, **ICFFR Coimbra**, **IDGA Wildfire Tech Summit (San Diego 2027)**, **China Emergency Expo / China Fire / Beijing Forest Fire Expo**. | Calendario de demos y networking; no de reentrenamiento ML. |
| Tendencia 2024–2026: **digital twins** (NASA FireSense/WDT), **fusión multi-sensor**, **UAS en agencia**, **abstención / fiabilidad** todavía rara en marketing. | Decision Card + reliability gate es **diferenciador narrativo** en sala de mando. |

**Conclusión de mesa:** no perseguir “más papers de IoU”. Perseguir (1) presencia en 1–2 ferias/congresos con demo de 30 min, (2) adaptadores a datos de terceros (Pano/OroraTech-class open feeds cuando existan APIs, ELMFIRE/ForeFire como prior de física, CEMS/EFFIS), (3) no vender ML holdout como ROS táctico.

---

## 1. Congresos y ferias — California / West Coast USA

### 1.1 Prioridad alta (firetech / decisión / tech)

| Evento | Cuándo / dónde | Qué es | Relevancia WFD |
|--------|----------------|--------|----------------|
| **Red Sky Summit** | **4 nov 2026 · San Francisco, CA** | Firetech “thought leaders”: fire service, utilities, insurance, startups, philanthropy. Fundado 2023. Aplicación a asistencia. | **#1 networking CA.** Audiencia de adopción, no de paper. Pitch: Decision Card + shadow ops + honesty. URL: [redskysummit.com](https://redskysummit.com/) |
| **IDGA Wildfire Technology Summit** | Histórico anual; **próximo listado: 21–22 abr 2027 · San Diego, CA** (8ª ed.). | Summit de agencias + vendors: CAL FIRE, USFS, utilities, UAS, AI, prediction/suppression. Speakers habituales: CAL FIRE OWTRD, Esri, Technosylva, Pano AI, NASA, etc. | **#1 compradores institucionales USA.** Ideal para ver competencia y lenguaje de procurement. Market report 2026–2030 y whitepapers UAS. URL: [idga.org/events-wildfiremanagement](https://www.idga.org/events-wildfiremanagement) |
| **CAL FIRE — Office of Wildfire Technology R&D (OWTRD)** | Permanente (CA state) | Hub estatal de tecnologías emergentes; informes anuales 2024 y 2025 públicos. | **Canal de entrada regulatorio/tech review**, no feria. Leer reports antes de cualquier pitch CA. [fire.ca.gov/what-we-do/wildfire-technology](https://www.fire.ca.gov/what-we-do/wildfire-technology) |
| **California WUI Symposium (NASFM)** | **17–19 ago 2026 · Garden Grove / Orange County, CA** | Wildland-Urban Interface + día extra BESS safety. | Adopción/códigos/comunidad; menos ROS técnico, más política de interfaz. |

### 1.2 Prioridad media (operativo, preparación, GIS)

| Evento | Cuándo / dónde | Notas |
|--------|----------------|-------|
| **Wildfire and Earthquake Expo** | **26 abr 2026 · Sonoma County Fairgrounds** | Expo pública de preparación (6ª ed.). Buena para outreach local, no para B2G tech deep. [fireandearthquakeexpo.org](https://www.fireandearthquakeexpo.org/) |
| **Sierra Nevada Regional Meeting (CA Wildfire & Forest Resilience Task Force)** | **19 mar 2026 · Tuolumne County** | Política/resiliencia regional. |
| **TechCon SoCal 2026** | **21–23 may 2026 · San Diego State University** | Tech general; speakers firetech (p. ej. Wildfire Systems). No es vertical puro. |
| **California Fire Science Seminar Series** | Feb–mar (virtual, CAFSC) | Ciencia aplicada; bajo coste de seguimiento. |
| **Esri User Conference / GIS wildfire track** | Anual (TBD por año; San Diego histórico) | Capa cartográfica y “Wildland Fire Solutions” (Anthony Schultz / Esri aparece en IDGA). WFD no es GIS-first, pero el comprador sí habla ArcGIS. |
| **WFCA IGNITE Symposium** | 2026 (Las Vegas track; wildfire + technology) | Western Fire Chiefs; tracks wildfire/tech. |
| **IAFC Technology Summit International** | **7–9 dic 2026 · Denver, CO** | Tech de emergencia general (AR, AI disaster); adyacente. |

### 1.3 Adyacentes USA (no CA, pero el circuito firetech va)

| Evento | Cuándo | Nota |
|--------|--------|------|
| **Colorado Wildland Fire Conference** | **15–16 abr 2026 · Fort Collins, CO** | Ops + partners; sponsors/exhibitors. |
| **Wildland Fire Canada + Canadian Smoke Forum** | **19–23 oct 2026 · Saskatoon** | Agencias + smoke; IAWF. |
| **Heat & Fire Expo USA** | **4–5 mar 2026 · Miami Beach, FL** | Prep/management/recovery wildfire (más “consumer/industry” que sala de mando). |
| **FDIC International** | Anual (Indianapolis circuito) | Bomberos municipales; poco wildland puro. |
| **NFPA Conference & Expo** | 2026 Las Vegas (ciclo NFPA) | Códigos/seguridad; adyacente. |

### 1.4 Ecosistema California: quién “ocupa el tablero” (no son ferias, son competidores/aliados)

| Actor | Rol 2024–2026 | Relación con WFD |
|-------|----------------|------------------|
| **Technosylva** (Wildfire Analyst / Tactical Analyst) | Plataforma de inteligencia en CAL FIRE; en 2025 ~13k simulaciones automáticas de spread; publicación a ~6k crew en móvil. Estudio peer-reviewed con CAL FIRE sobre accuracy de modelos. | **Referencia de producto de decisión táctica.** WFD no compite en simulación Rothermel-scale statewide; compite en **frente observado LWIR + honestidad/ABSTAIN**. Estudiar su UX de “intelligence to field”. [technosylva.com](https://technosylva.com/) |
| **Pano AI** | Cámaras montaña + AI detección + situational awareness; presencia en IDGA. | Detección pre-ignición/early; **upstream** de ops ROS. Posible fuente futura de “alert in” no de máscara térmica. |
| **OroraTech** | Satélites térmicos + plataforma monitoring; Series B ~$13.5M (may 2025). | Capa open/space; complementar packs CEMS, no sustituir LWIR dron. |
| **Dryad Networks (Silvanet)** | Sensores de gas en dosel + LoRa; ultra-early detection; grants EU 2024; drone suppression “Florian”. | Muy early-warning; no ROS de frente. |
| **EMBERPOINT, Bridger Aerospace, Perimeter Solutions, Vibrant Planet, Armada, Trident Sensing…** | Expositores habituales IDGA (aviación, retardantes, sensing, planning). | Mapear 1-pager “quién hace qué capa” para no reinventar. |
| **NASA FireSense + Wildfire Digital Twin** | Fusión in-situ/air/space + AI forecast; campañas prescribed 2025; ESTO FireSense Technology. | Alineado con **decision twin mínimo** de WFD (estado + meteo + predicción corta + incertidumbre). Narrativa científica útil. |

---

## 2. Congresos y ferias — China

### 2.1 Ferias / expos (prioridad industrial)

| Evento | Cuándo / dónde | Contenido | Relevancia WFD |
|--------|----------------|-----------|----------------|
| **中国(北京)国际森林草原消防与救援装备展览会** (China Beijing International Forest & Grassland Fire & Rescue Equipment Exhibition) | **2025: 26–28 jun · Beijing Shougang International Convention Center**; ediciones **2026 (26–28 jun)** y **2027 (24–26 jun)** anunciadas en portales del organizador | Equipamiento forest/grassland fire, rescate, UAV, mando. | **#1 feria CN vertical forest fire.** Ideal para ver **drones térmicos, cámaras IR, station caps, software de mando**. No esperéis open datasets. |
| **CHINA FIRE** (中国国际消防设备技术交流展览会) | **13–16 oct 2025 · New China International Exhibition Center, Beijing** (21ª ed.) | Una de las ferias de fuego más grandes del mundo (protección + equipo). | Vertical más “structural fire + equipment”; buscad pabellones **forest / aviation / UAV**. |
| **中国国际应急管理展览会 (China International Emergency Management Exhibition / China Emergency Expo)** | **2026: 8–10 sep · China National Convention Center, Beijing** (anunciado; Interschutz network) | Emergencias nacionales, forest grassland extinguishing series, aviación AG-600M, smart emergency. | Canal **MEM / gobierno + export “Belt & Road” emergency**. Narrativa de producto dual + audit puede encajar en “智慧应急”. |
| **广州国际应急安全博览会** (Guangzhou emergency/safety + fire) | Ciclo anual (14ª ed. mencionada en 2025 invites) | Sur de China; export/import. | Secundario; útil si hay partner UAV en Guangdong. |
| **Chongqing Aerospace / UAV tech expos** (p. ej. oct 2026 listados en agregadores) | Variable | UAV industrial. | Solo si buscáis **OEM térmico**, no ciencia de ROS. |

### 2.2 Hechos de industria CN 2024–2026 (novedades operativas, no papers)

| Ítem | Evidencia pública | Nota para WFD |
|------|-------------------|---------------|
| **UAV en forest aviation firefighting** | MEM press 2025: drones con bombas de decenas de kg + **comms mesh** en zonas sin señal. | China empuja **UAV como plataforma de extinción y red**, no solo ISR. Vuestro stack es ISR/ROS → complementary. |
| **AG-600M** anfibio ~12 t agua; **Xinzhou-60** ~6 t | Ensayos/uso operativo reportado 2025 | Escala de extinción aérea; fuera de scope WFD. |
| **Ejercicios “应急使命·2025”** (Daxing’anling forest + Shenzhen high-rise) | Xinhua jun 2025 | Demostración de capacidad multi-escenario; interés en **C2**. |
| **DJI forest fire use-cases** | Material comercial/enterprise DJI | Ecosistema masivo de drones; contrato de entrada GeoTIFF genérico **debe** contemplar export DJI/IR de terceros. |
| **South-South / UNDP Belarus forest fire project** (CN support, 2025) | UNDP | Export de capacidad CN en forest fire tech. |

### 2.3 Ciencia / papers CN (muestreo; no exhaustivo arXiv CN)

La frontera científica CN 2024–2026 en fire se reparte entre:

- Detección satélite / Himawari / FY + deep learning  
- UAV RGB-IR fusion  
- Modelos de spread híbridos  
- Digital twin reviews (MDPI Fire 2024 cita NASA WDT como referente)

**Para WFD:** priorizar **papers con validación de frente o ROS**, no mIoU de smoke detection en lab. Mantener pipeline de `wfd-literature-ingest` / fire_intel scrape.

---

## 3. Congresos internacionales de referencia (no CA/CN pero obligatorios)

| Evento | Cuándo | Por qué importa |
|--------|--------|-----------------|
| **INTERSCHUTZ 2026** + **WildfireCamp@INTERSCHUTZ** | **1–6 jun 2026 · Hannover** | Feria mundial fire/rescue; **premiere WildfireCamp** (early detection, prevention, combat). Vallfirest y vendors wildland. **Mejor feria europea 2026 para product fit.** |
| **10th ICFFR + 19th IAWF Safety Summit** | **31 oct – 6 nov 2026 · Coimbra** | Congreso científico forest fire cada ~4 años. Deadline papers ~**15 mar 2026**. **Mejor sitio para peer audience** de ROS/perímetros. [events.adai.pt](https://events.adai.pt/en/10th-icffr) |
| **UK Wildfire Conference 2026** | **11–12 nov 2026 · Leeds** | “New Perspectives – Shared Solutions”. Europa ops. |
| **Wildland Fire Canada 2026** | **19–23 oct · Saskatoon** | Agencias + smoke. |
| **IGARSS 2026** | **10–13 ago 2026 · Washington, DC** | Remote sensing (NASA FireSense booth). Para capa open/sat, no ops LWIR. |

---

## 4. Estudios, datasets y open source (2024–2026)

### 4.1 Datasets abiertos / semi-abiertos

| Recurso | Año / tipo | Qué aporta | Uso WFD |
|---------|------------|------------|---------|
| **Next Day Wildfire Spread (NDWS)** | Google / Kaggle (baseline histórico) | 64×64 multi-canal next-day | Ya en repo (`ndws_v21`); G1 KILL — no reabrir sin nuevo framing. |
| **WildfireSpreadTS** | NeurIPS-era multi-temporal | 5 días, multi-modal, leave-one-year | Pretrain / temporal real si se retoma ML sat. |
| **TS-SatFire** | Scientific Data **nov 2025** | Multi-task: active fire, daily monitoring, next-day; Kaggle + GitHub baselines | Candidato a **bench open** comparado con CEMS packs. Code: github.com/zhaoyutim/TS-SatFire |
| **BCWildfire** | arXiv **nov 2025** | Multi-factor largo plazo, 38 covariates (fire, weather, fuel, terrain, human) | Features de riesgo; no máscara LWIR. |
| **WildFireSpread (Orion-AI-Lab)** | Dataset ~9500 fires + DL final burned area | HuggingFace zip 64×64 10 days | Comparables de burned area, no ROS táctico. |
| **WildfireDB** | open occurrence + satellite features | Spread + suppression agents framing | Research only. |
| **FIRMS / VIIRS / MODIS** | continuo NASA | Hotspots | Ya en demos firms; no perímetro oficial. |
| **EFFIS / Copernicus EMS / CEMS** | continuo UE | Perímetros, RDA, activaciones | Ya en open packs WFD; O2 “oficial-lite”. |
| **WFIGS / NIFC perimeters** | USA public | Perímetros reportados | Benchmark geométrico si hay IF con solape temporal USA (no ES). |
| **State of Wildfires 2024–2025** | ESSD **oct 2025** (Kelley et al.) | Inventario global BA, emisiones, attribution climate; **13 datasets** en Zenodo community | Contexto macro; no front-scale. DOI: 10.5194/essd-17-5377-2025 |

### 4.2 Simuladores / motores open source

| Proyecto | License / stack | Capacidad | Encaje WFD |
|----------|-----------------|-----------|------------|
| **ELMFIRE** | EPL-2.0 · Fortran · [elmfire.io](https://elmfire.io/) · github.com/lautenberger/elmfire | Level-set spread; forecast real-time, reconstruct historical, burn probability; usado en CONUS ops-scale | **Prior de física / envelope** para comparar ROS observado vs simulado sin reescribir Rothermel. Papers WUI 2026. |
| **ForeFire** | open C++ · github.com/forefireAPI/forefire · JOSS | Motor de propagación research + forecasting | Alternativa europea a ELMFIRE; evaluar API. |
| **FARSITE / FlamMap / BehavePlus** | USFS (histórico; no “nuevo 2024” pero baseline industria) | Comportamiento fuego | Referencia de lenguaje ops USA. |
| **Cellular automata / RF pipelines** (repos varios 2025) | hobby→thesis | Spread multi-hora | Bajo valor industrial salvo ideas de features. |

### 4.3 Papers / líneas SOTA accionables (resumen cruzado con mega-research)

| Línea | 2024–2026 | Acción WFD |
|-------|-----------|------------|
| **Multi-day satellite spread** (SwinUnet pretrain, MA-Net, APAU-Net) | Mejoras AP multi-día | Solo si se reabre ML sat; no field_ops. |
| **PINN / physics-informed** (Vogiatzoglou et al.; PhysFire) | Parámetros interpretables | Regularizar crecimiento normal al frente / wind-aligned; no sustituir ROS ops. |
| **UAV RGB–thermal fusion** (FireCast-Fusion class) | Corto horizonte | Alinear RGB+LWIR en pipeline si Heligrafics lo da; contrato multi-banda. |
| **SAR + UAV** | All-weather + detalle | Open/proxy; no ancla ROS. |
| **Digital twins** (NASA WDT, FIRETWIN, reviews MDPI Fire) | Fusión multi-escala | Mapear a Decision Card + envelope + outbox (ya embrión). |
| **LFMC / fuel moisture products** | SERDP / USFS 2025–26 | Mejorar fuel stack Tobarra/Hellín (ya en PR fuel/AEMET). |

### 4.4 Estudios de industria / mercado

| Documento | Fuente | Uso |
|-----------|--------|-----|
| **Wildfire Management in the United States: Market Report 2026–2030** | IDGA (download del summit) | Funding, tech trends, state breakdown. |
| **The Rising Role of UAS in Wildfire Detection, Mitigation, and Suppression** | IDGA article | Argumentario drones. |
| **CAL FIRE OWTRD Annual Reports 2024 & 2025** | fire.ca.gov | Qué tecnologías mira el Estado de CA. |
| **NetZero Insights — Five Wildfire Management Startups 2025** | Dryad, OroraTech, etc. | Mapa competitivo early detection. |
| **Technosylva–CAL FIRE validation study** | 1,853 CA fires peer-reviewed framing | Cómo se vende “accuracy” en ops reales. |

---

## 5. Startups y productos comerciales (mapa de capas)

```text
EARLY DETECT          SITUATIONAL AWARENESS       SPREAD / RISK SIM           OPS FRONT (vuestro)
─────────────         ─────────────────────       ────────────────           ──────────────────
Dryad (gas)           Pano AI (cameras)           Technosylva (CAL FIRE)     WFD thermal ROS
OroraTech (sat IR)    ALERTCalifornia / watch     ELMFIRE / commercial       Decision Card
IQ FireWatch-class    towers                      utilities risk platforms   ABSTAIN / audit
sensors               Esri dashboards             Vibrant Planet planning    Open CEMS packs
```

**Novedad mínima pero real 2024–2026:**

1. **CAL FIRE empuja simulaciones de spread al móvil de 6.000 crews (2025)** → el estándar de entrega es **inteligencia al campo**, no un PDF de lab.  
2. **INTERSCHUTZ crea WildfireCamp** → wildfire deja de ser “rincón” en ferias de bomberos.  
3. **Red Sky Summit (SF)** consolida firetech como vertical de inversión/adopción.  
4. **TS-SatFire + BCWildfire (2025)** elevan la vara de datasets multi-task/multi-factor.  
5. **ForeFire en JOSS / ELMFIRE docs 2025** → simulación open más usable para research ops.  
6. **China: UAV mesh + bombas + grandes ferias forest equipment** → hardware ISR/extinción escala; software de decisión honest aún no es el discurso dominante en CN expos.  
7. **State of Wildfires report 2024–2025** → attribution climática y datasets globales como “background science”.  
8. **Digital twin narrative (NASA)** se normaliza en funding USA; WFD puede decir “decision twin mínimo” sin overclaim.

---

## 6. Calendario accionable (próximos 12–18 meses)

| Prioridad | Evento | Acción concreta WFD |
|-----------|--------|---------------------|
| **P0** | Red Sky Summit · SF · **4 nov 2026** | Aplicar asistencia; preparar demo 20 min Decision Card + Tobarra honesty. |
| **P0** | INTERSCHUTZ WildfireCamp · **1–6 jun 2026** | Si presupuesto: stand partner o visit + 10 one-pagers; ver Vallfirest/Dryad/OroraTech en persona. |
| **P0** | ICFFR Coimbra · **oct–nov 2026** | Abstract (deadline ~mar 2026): multi-ancla Tobarra/Hellín + ABSTAIN design. |
| **P1** | IDGA Wildfire Tech Summit · **abr 2027 San Diego** | Cuando haya demo tercero + Reliability Gate pack. |
| **P1** | China Emergency Expo · **sep 2026 Beijing** o Forest Fire Equipment Expo **jun 2026/27** | Solo si hay plan de **OEM térmico / partner CN**; no como “paper tour”. |
| **P2** | California WUI Symposium · **ago 2026** | Networking OSFM/CAL FIRE adjacency. |
| **P2** | UK Wildfire / Canada WFCC · **oct–nov 2026** | Europa/Commonwealth ops narrative. |
| **Continuo** | OWTRD reports + Technosylva public case studies | Lectura obligatoria antes de cualquier email a CA. |

---

## 7. Mejoras relevantes **para el código/producto WFD** (priorizadas)

### 7.1 Producto / adopción (máximo impacto)

| Mejora | Origen industria | Esfuerzo | Nota |
|--------|------------------|----------|------|
| Pack **demo-with-third-parties** (card firmada + replay 1 comando) | CAL FIRE mobile intel + Red Sky audience | M | Ya casi tenéis piezas |
| **Reliability Gate Report** legible (1–3 pp) | OWTRD / Technosylva validation culture | S | JSON → narrativa |
| Shadow mode con CCAA (solo observar + card) | Adopción CA utilities/agencies pattern | H (humano) | No es eng |
| One-pager **IoU ≠ ROS** | Confusión mercado AI fire | S | Anti-overclaim |

### 7.2 Ops / diversificación térmica

| Mejora | Origen | Esfuerzo |
|--------|--------|----------|
| Contrato entrada multi-vendor (DJI IR, genérico GeoTIFF, Heligrafics) | CN UAV ecosystem + US UAS trend | M |
| Reason codes de abstención visibles en commander | Diferenciador vs Technosylva-style always-on sim | S |
| Comparar ROS observado vs **ELMFIRE/ForeFire** en Tobarra | Open simulators 2025 | M–L |

### 7.3 Open perimeter

| Mejora | Origen | Esfuerzo |
|--------|--------|----------|
| Freshness score + checksum versionado packs | Industria data products | S–M |
| Bench opcional **TS-SatFire** vs packs CEMS | Scientific Data 2025 | M |
| No confundir CEMS con perímetro nacional O2 | Honesty interna | — |

### 7.4 ML (solo lab)

| Mejora | Origen | Esfuerzo |
|--------|--------|----------|
| No reentrenar v34 por moda | Plateau NDWS ya conocido | — |
| Si hay ciclo: multi-day WFTS/TS-SatFire + pretrain | Papers 2025 | L |
| Quantiles incertidumbre solo `research_open` | Industry still overclaims certainty | M |

---

## 8. Qué **no** es novedad (evitar ruido)

- Otra U-Net de smoke detection en GitHub con 3 stars.  
- “AI predicts wildfires” press releases sin perímetro/ROS medido.  
- Mapas CEMS reempaquetados como producto de pago (ya lo tenéis como capa open honesta).  
- Claim 99.9999% accuracy del fuego (mercado lo usa; WFD no debe).  
- Satélite high-temporality como si fuera **ops ROS 5–15 min** (es otra capa).

---

## 9. Mapa de amenazas / oportunidad (síntesis)

```text
                    DETECCIÓN TEMPRANA          SPREAD SIM OPS           FRENTE TÉRMICO MEDIDO
                    (saturado capital)          (Technosylva/ELMFIRE)    (hueco WFD)
CA market ───────► Pano, Dryad, OroraTech  ──► CAL FIRE stack      ──► casi vacío comercial
CN market ───────► torres + UAV + AI        ──► C2 / extinción      ──► hardware IR abundante
EU market ───────► EFFIS + sensors          ──► ForeFire / vendors  ──► Vallfirest etc. en ferias
WFD fit   ───────► no competir head-on     ──► usar como prior      ──► OWNEAR + Decision Card
```

**Tesis de producto actualizada con este research:**

> WFD no gana siendo “otro Technosylva” ni “otro Pano”. Gana siendo el sistema que **mide el frente cuando hay LWIR**, **se calla cuando no**, **fusiona open sin mentir**, y deja **audit trail** que un tercero puede reejecutar — demostrado en congresos (Coimbra), ferias (INTERSCHUTZ/Red Sky) y un shadow con organismo.

---

## 10. Fuentes (URLs clave)

### California / USA
- https://redskysummit.com/
- https://www.idga.org/events-wildfiremanagement
- https://www.fire.ca.gov/what-we-do/wildfire-technology
- https://technosylva.com/ · https://technosylva.com/customers/cal-fire/
- https://www.pano.ai/
- https://ororatech.com/
- https://www.dryad.net/silvanet
- https://cce.nasa.gov/firesense/
- https://science.nasa.gov/…/nasa-wildfire-digital-twin… (mayo 2024)
- https://www.fireandearthquakeexpo.org/
- https://wfca.com/ignite-fire-conference/
- https://www.iafc.org/events/…/technology-summit-international-2026

### China
- http://www.beijingyongle.com/ (Forest & Grassland Fire Equipment Expo Beijing)
- https://www.fireexpo.cn/ / CHINA FIRE 2025 (13–16 oct 2025, Beijing)
- http://www.emtfexpo.com/ · China Emergency Expo (2026-09-08–10 CNCC Beijing)
- https://www.interschutz.de/en/about-us/interschutz-events-worldwide/china-international-emergency-management-exhibition/
- MEM China press / Xinhua “应急使命·2025”

### Internacional
- https://www.interschutz.de/en/ · WildfireCamp
- https://events.adai.pt/en/10th-icffr · ICFFR 2026 Coimbra
- https://www.iawfonline.org/events/
- https://fireadaptedco.org/cwfc-home/

### Open source / datos / papers
- https://elmfire.io/ · https://github.com/lautenberger/elmfire
- https://github.com/forefireAPI/forefire
- https://www.nature.com/articles/s41597-025-06271-3 (TS-SatFire)
- https://github.com/zhaoyutim/TS-SatFire
- https://arxiv.org/html/2511.17597 (BCWildfire)
- https://essd.copernicus.org/articles/17/5377/2025/ (State of Wildfires 2024–2025)
- https://github.com/Orion-AI-Lab/WildFireSpread
- https://wildfire-modeling.github.io/ (WildfireDB)
- Mega-research interno: `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`

---

## 11. Próximos pasos sugeridos (checklist)

- [ ] Descargar **OWTRD 2024 + 2025** y resumir 1 página “qué compra CA”.  
- [ ] Aplicar **Red Sky Summit** (nov 2026) si hay demo pack listo.  
- [ ] Decidir presupuesto **INTERSCHUTZ jun 2026** (visita vs stand partner).  
- [ ] Preparar abstract **ICFFR** (deadline ~mar 2026).  
- [ ] Spike eng: **ELMFIRE o ForeFire** vs Tobarra ROS (comparabilidad, no replace).  
- [ ] Spike eng: contrato **multi-vendor LWIR** (DJI-class metadata).  
- [ ] Actualizar `docs/OPEN_RESOURCES_CATALOG.md` con TS-SatFire + BCWildfire.  
- [ ] **No** gastar ciclo en reentrenar ensemble por papers de mIoU satélite.

---

## 12. Control de calidad de este research

| Aspecto | Estado |
|---------|--------|
| Cobertura CA ferias/congresos 2025–2027 | Alta (eventos con URL verificada en web 2026-08) |
| Cobertura China ferias | Media-alta (portales organizador + Interschutz network; fechas 2025/26/27 sujetas a reconfirmación local) |
| OSS/datasets 2024–2026 | Alta |
| Papers exhaustivos CN interno | Baja–media (requiere CNKI/Wanfang o scrape dedicado) |
| Startups mapa | Media (top-of-mind firetech; no N=100 funding DB) |
| Deep-research harness multi-agent | Lanzado en paralelo; este doc es síntesis principal curada |

**Disclaimer:** fechas de ferias cambian; revalidar 2–4 semanas antes de viajar. Claims de funding de startups tomados de prensa 2024–2025; verificar en fuentes primarias antes de deck inversor.

---

*Documento generado para WildfireFrontDynamics — uso interno de priorización industria 2024–2026.*
