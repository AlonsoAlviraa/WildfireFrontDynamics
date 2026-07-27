# WildfireFrontDynamics — one-pager (España)

**Estado:** proyecto de software / I+D en fase pre-empresa  
**Contacto:** Alonso Alvira Ballano · alonso.alvbal@gmail.com · https://github.com/ (pendiente)  
**Fecha:** 2026-07  

---

## Problema

En megaincendios (ej. La Mierla, Sierra Norte GU) el PMA recibe **datos fragmentados**: satélite, prensa, radio, aéreos. Sobran mapas; faltan sistemas que digan **cuándo no recomendar** y dejen **rastro auditable**.

## Solución

Software de **apoyo a la decisión** en incendios:

| Capa | Qué hace |
|------|----------|
| **Open** | FIRMS multi-sensor, Sentinel-2, vigilancia CEMS, packs diarios |
| **Ops** | ROS / incident cuando hay LWIR o material de campo |
| **Decision Card** | **GO / HOLD / ABSTAIN** + política (field_ops / research) + hashes |

**Regla dura:** con solo open/prensa **no hay GO de campo**. Las ha de prensa **no** se convierten en ancla oficial.

## Qué ya existe (demostrable)

- Pack open **La Mierla jul-2026** (timeline satélite, mapas, cards HOLD)  
- Cadence regenerable (`run_la_mierla_open_day.py`)  
- Track ML CLM con métricas de holdout (investigación, no despacho mágico)  
- Diseño anti “silent GO”  

## Qué pedimos a un servicio / CCAA

1. Reunión de 30 min y feedback de utilidad  
2. Si encaja: **carta de interés** para proyectos UE (UCPM / Interreg)  
3. A medio plazo: acceso controlado a **LWIR/KMZ o Vp/ha** de 1–2 IF para validar ops (con confidencialidad)

## Qué ofrecemos

- Piloto de **monitorización open** durante campaña  
- Decision Card y brief sin inventar ROS  
- Transparencia total de limitaciones  
- Posible partner tech en propuestas europeas (sin coste de entrada para explorar)

## Encaje de financiación (transparencia)

Sin empresa aún: priorizamos **consorcio con end-user + universidad**.  
Con entidad jurídica más adelante: **NEOTEC/CDTI**, UCPM, SUDOE, Horizon como SME.

## No prometemos

- Sustituir perímetro oficial ni EGIF  
- Órdenes tácticas de despacho  
- “IA que apaga el fuego”  

---

**Siguiente paso:** una videollamada y el mapa/demo de La Mierla en pantalla compartida.
