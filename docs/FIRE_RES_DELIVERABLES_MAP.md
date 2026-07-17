# FIRE-RES deliverables → qué necesitamos en WildfireFrontDynamics

> Fuente: [https://fire-res.eu/deliverables-and-reports/](https://fire-res.eu/deliverables-and-reports/)  
> Contexto: mensaje Andrea (proyecto FIRE-RES finalizado; material público útil).  
> Fecha análisis: 2026-07-17  

## 0. Qué es FIRE-RES (y qué no es)

| | FIRE-RES | Nuestro repo (WFD) |
|--|----------|---------------------|
| Escala | EWE landscape / Europa, fire–atmósfera, resiliencia socio-ecológica | Frente LWIR local (ops) + next-day parches CLM (ML) |
| ROS | Modelado físico / simulación / lecciones operativas | **Medido** desde máscaras térmicas + anclas INFOCAM |
| Producto | Innovaciones, DSS pan-EU, ForeFire–MesoNH, EO | `incident_runtime_v1` + `clm_ensemble_v34` |
| Estado | **Finalizado** (H2020) | Activo, v34 cerrado |

**No copiar claims:** envelope 15/30/60 de WFD ≠ predicción EWE fire–atmósfera de FIRE-RES.

---

## 1. Prioridad ALTA — leer y usar ya

| ID | Título | Por qué nos sirve | Acción concreta WFD |
|----|--------|-------------------|---------------------|
| **[D1.1](https://fire-res.eu/wp-content/uploads/2024/01/D1.1_FIRE-RES_Transfer_of_LL_on_EWE.pdf)** | Transfer of lessons learned on EWE | Define retos: **monitorizar y predecir EWE**, incertidumbre, interoperabilidad, comunicación. Marco Castellnou et al. | Citar en memoria TFG / informe CMA. Alinear disclaimers de `incident` y brief. |
| **[D5.3](https://fire-res.eu/wp-content/uploads/2024/11/D5.3_FIRE-RES_IA5.2_Modelling-the-EWE-and-smoke-spread-based-on-coupled-fire-atmosphere-approaches.pdf)** | EWE + smoke con fire–atmósfera acoplado | **ForeFire + MesoNH**, forecast 24 h, update 12 h, pasos 10 min; validación Pedrógão, Portugal, Francia, Canarias. Códigos open-source UE. | Referencia “capa landscape”. No sustituye ROS dron. Opcional: link en OPEN_RESOURCES. |
| **[D5.4](https://fire-res.eu/wp-content/uploads/2024/12/D5.4_FIRE-RES_Modelling-of-fire-combustion-and-convective-processes_compressed.pdf)** | Combustión y convección | Por qué modelos clásicos fallan en EWE; **ROS** desde posición de frente vs tiempo; humedad, fuel, atmósfera. | Justificar límites de predicción y valor de **medir** frente (nuestro ops). |
| **[D5.12](https://fire-res.eu/wp-content/uploads/2024/03/D5.12_FIRE-RES_Tools-to-comunicate-scenarios-in-EWE-1.pdf)** | Tools to communicate EWE scenarios | Web/GIS en crisis: ruido vs información, interoperabilidad, mensajes BEFORE/DURING. | Mejorar **field kit / operator brief** (ya iniciado): capas, disclaimers, audiencia. |
| **[D5.6](https://fire-res.eu/wp-content/uploads/2024/12/D5.6_FIRE-RES_IA-5.5-brief-Earth-Observation-data-collection-to-support-decision-making.pdf)** | Earth Observation para decisión | GNSS-RO (atmósfera) + **dNBR/NDVI/biomasa/CO₂** post-fuego (ICGC Cataluña). | O2/perímetros: dNBR no es perímetro oficial, pero **BA / severidad** satelital como proxy documentado (nunca como “oficial” sin auditoría). |
| **[D5.1](https://fire-res.eu/wp-content/uploads/2023/10/D5.1_FIRE-RES_Technical-requirements-and-system-architecture-of-the-integrative-software-system-2.pdf)** | Requisitos y arquitectura software integrador | ISS / DSS multi-módulo. | Comparar con `incident` outbox + catalog productos (arquitectura dual). |

### Ideas accionables extraídas

1. **Medir ROS y ha/h en evento** (D1.1 / literatura citada en D1.10): FIRE-RES insiste en que energía y escenario EWE se relacionan con **ROS (m/min)** y **crecimiento (ha/h)**. Eso **valida nuestro eje ops** (frente + área + ancla Vp).  
2. **Incertidumbre y baja predictibilidad** (D1.1, D5.12): no vender envelope como táctica; sí como escenario con disclaimer — ya en kill list WFD.  
3. **ForeFire open-source** (D5.3): posible **benchmark landscape** futuro (no mes 1 si no hay GPU/equipo).  
4. **Comunicación GIS** (D5.12): checklist de capas (frente actual, envelope, grado, fuentes) → alinear `emergency_briefing.md` / `operator_brief_1p`.  
5. **EO post-fuego** (D5.6): para O2 BLOCKED, camino intermedio = BA Sentinel dNBR + nota “proxy, no oficial”.

---

## 2. Prioridad MEDIA — contexto científico / mes 2

| ID | Título | Uso |
|----|--------|-----|
| **[D1.3](https://fire-res.eu/wp-content/uploads/2023/10/D1.3_FIRE-RES_AdaptFirePotentialPoligons.pdf)** | Fire Potential Polygons adaptados a EWE | Polígonos de potencial / decisión espacial |
| **[D1.6](https://fire-res.eu/wp-content/uploads/2025/03/D1.6_FIRE-RES_Early-warning-indicators-1.pdf)** | Early-warning EWE (fire-weather + vegetación) | Early warning ≠ nuestro next-day CLM; contraste |
| **[D1.7](https://fire-res.eu/wp-content/uploads/2024/01/D1.7_FIRE-RES_Spatial-and-Temporal-conditions-EWE.pdf)** | Condiciones espaciales/temporales EWE Europa | Climatología de extremos |
| **[D5.5](https://fire-res.eu/wp-content/uploads/2025/06/D5.5_FIRE-RES_IA-5.2-brief-Extreme-Wildfire-Events-impact-and-risk-estimation-module.pdf)** | Impact / risk module | Riesgo e impacto |
| **[D5.15](https://fire-res.eu/wp-content/uploads/2025/08/D5.15_FIRE-RES_Integrative-Umbrella-System-for-EWE-decision-making.pdf)** | Umbrella system DSS | Integración multi-herramienta |
| **[Innovations Catalogue](https://fire-res.eu/wp-content/uploads/2025/11/FIRE-RES-Innovations-Catalogue.pdf)** | >80 innovaciones | Mapa de no reinventar (WUI, first attack, etc.) |

---

## 3. Prioridad BAJA / fuera de scope WFD

| WP | Ejemplos | Por qué fuera |
|----|----------|---------------|
| D2.x | WUI architecture, landscape design, post-fire restoration | Gestión territorial, no pipeline térmico |
| D3.x | Incentivos económicos, fire wine, seguros paramétricos | Socio-económico |
| D4.x | Cultura del riesgo, education platform, villages, policy | Comunicación social / legal |
| D4.11 | Humo / calidad del aire / evacuación | Salud pública (útil solo si se abre humo) |

---

## 4. Mapa a gaps actuales del plan mes WFD

| Gap WFD | ¿FIRE-RES lo resuelve? | Qué sacar |
|---------|------------------------|-----------|
| **O1** 2ª ancla Vp/ha | **No** (no da datos INFOCAM CLM) | Argumento científico de por qué medir ROS/ha en evento |
| **O2** perímetro oficial | **No** oficial; **D5.6** da vía EO/dNBR | Proxy documentado + sigue BLOCKED oficial |
| **P1** incident 2 IF | Parcial | Patrones de salida GIS/com (D5.12) |
| **M5** v35 datos | **No** | No reabre G1 NDWS; no es dataset CLM |
| Memoria TFG / CMA | **Sí** | Citar D1.1 + D5.3 + D5.4 como estado del arte EWE |

---

## 5. Lectura mínima recomendada (orden)

1. D1.1 (marco EWE + retos monitorización/predicción) — ~hojas de challenges.  
2. D5.3 abstract + §1 + case studies (ForeFire/MesoNH).  
3. D5.4 intro + secciones ROS / límites modelos.  
4. D5.12 challenges comunicación + checklist GIS.  
5. D5.6 Part 2 ICGC (severidad / NDVI) si se toca post-fuego.

Zenodo (DOI en portadas): D1.1 `10.5281/zenodo.10260790`, D5.3 `10.5281/zenodo.14187388`, D5.6 `10.5281/zenodo.14188148`, D5.12 `10.5281/zenodo.10715763`, D5.4 `10.5281/zenodo.14192901`.

---

## 6. Qué **no** necesitamos de FIRE-RES

- Reimplementar CFD / ForeFire en el mes (salvo interés TFG explícito).  
- Mezclar smoke/PM o seguros en el producto dual.  
- Tratar deliverables como **datos de validación** de Tobarra/Cardoso.  
- Contactar a Andrea pidiendo “datos internos” del proyecto cerrado: el valor es **público PDF**.

---

## 7. Siguiente paso en repo (si se implementa)

- [x] Este mapa.  
- [ ] Enlace corto en `OPEN_RESOURCES_CATALOG.md`.  
- [ ] 5–10 líneas en informe CMA / memoria: contraste EWE simulado vs frente observado LWIR.  
- [ ] Opcional: experimento **ForeFire** en un caso CLM (mes 2+, no bloquea GO_MES).

---

*FIRE-RES finalizado ≠ material inútil. Es biblioteca pública de EWE; nosotros seguimos midiendo frente y transfer CLM con gates honestos.*
