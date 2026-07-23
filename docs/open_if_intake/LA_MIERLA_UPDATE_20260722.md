# Update scrape — IF La Mierla · 2026-07-22

**Pack:** `outputs/open_if/la_mierla_20260717/`  
**Scrape JSON:** `outputs/open_if/la_mierla_20260717/scrape_latest.json`  
**Brief:** `operator_brief_open_if.md`

---

## 1. Situación consolidada (open sources)

| Campo | Valor | Confianza |
|-------|--------|-----------|
| Fase | **Estabilización** (INFOCAM 21 jul ~18:16 UTC) | alta (oficial X) |
| ha | **+30.000** INFOCAM; **30–32.000** prensa 21–22 jul | media (provisional) |
| Nivel | **2** | alta |
| Evacuados / confinados | **34** / **14** municipios | alta |
| PMA | **Tamajón** | alta |
| Control / extinguido | **No** (paso previo = estabilización) | alta (Fernández) |
| Segundo IF GU | **#IFSelas** ~1.700 ha, Nivel 2, 6 núcleos | alta (INFOCAM) |

**Lectura honesta:** estabilización = llama no avanza o no hay llama en frentes trabajados; **las ha pueden seguir subiendo** más despacio. No es EGIF final ni perímetro oficial.

---

## 2. Cronología breve 20–22 jul

| Momento | Hecho |
|---------|--------|
| 20 jul | “Fuera de capacidad de extinción”; récord CLM ~26k ha; estrategia defensiva (Fernández / prensa) |
| 21 jul AM | ~29k ha; 34+14; Nivel 2 |
| 21 jul ~18:16Z | INFOCAM: **fase estabilización**; +30k ha |
| 21 jul noche | 230 terrestres / 211 efectivos INFOCAM; sin aéreos al ocaso |
| 21 jul | Aagesen: **50% restauración** Estado; visita PMA |
| 21 jul | **Selas** Nivel 2 ~1.700 ha |
| 22 jul AM | Prensa 30–32k ha; **Sánchez + Page** visitan Tamajón ~11:00 |

---

## 3. Fuentes oficiales / técnicas (expertos)

### Juan José Fernández — director de la emergencia
- **20 jul:** fuera de capacidad de extinción; muy lejos de controlado; defensa de población.
- **21 jul (EFE/Infobae):** avances positivos flanco izquierdo cabeza→cola; ha entre **30–32k**; crecen **más lento**; cabeza eje Condemios–Cañamares–Bujados; **no llega a Soria**; paso de estrategia **defensiva a ofensiva**; aún se defiende Prádena de Atienza; **no piensan en control**, sí en **estabilización** (sin llama o llama sin avance).

### Plan INFOCAM (@Plan_INFOCAM)
- Parte formal **fase estabilización** + medios (ver posts 2079631495405203691, 2079668077201912044, 2079816687818269143).
- IF **Selas** paralelo (no mezclar estadísticas).

### Sara Aagesen (MITECO)
- Emergencia no acaba con extinción sino con **recuperación**.
- Gobierno asume **50% del coste de restauración** de la zona.

### Emiliano García-Page
- Mensajes de ofensiva / “luz más allá del humo” (21 jul prensa).
- Visita conjunta con Sánchez 22 jul (EP/EFE).

### Sector aéreo (prensa especializada)
- Extinción aérea depende mucho de **operadores privados** + trabajo en equipo con tierra (comentario sistémico, no parte oficial).

---

## 4. FIRMS (esta pasada WFD)

| | Anterior (21 jul) | Ahora (22 jul refresh) |
|--|------------------:|-----------------------:|
| Hotspots N20 24h | ~658 | **273** |
| Hull ~ha | ~40k | **~22k** |
| Fechas acq | 20–21 | **21–22** |

**Interpretación cauta:** menos píxeles calientes en la ventana NRT encaja con **menor actividad térmica / estabilización**, **no** con “ha oficiales bajaron”. El hull de 24h no es el área quemada acumulada.

---

## 5. Política / visitas

- **22 jul:** Pedro Sánchez + García-Page + delegado Gobierno en PMA Tamajón.
- Fuentes: [Europa Press](https://www.europapress.es/castilla-lamancha/noticia-pedro-sanchez-garcia-page-visitaran-miercoles-zonas-afectadas-incendio-mierla-20260722080502.html), EFE X.

---

## 6. Producto WFD

| Artefacto | Path |
|-----------|------|
| Mapa limpio | `outputs/open_if/la_mierla_20260717/map_satellite.html` |
| Mapa hotspots | `.../map.html` |
| Scrape | `.../scrape_latest.json` |
| Brief | `.../operator_brief_open_if.md` |
| Scorecard | `.../scorecard_pista_b.json` |

Decision: **HOLD** (sin LWIR/ops). Ancla sigue `pending_external`.

---

## 7. Links útiles

- INFOCAM: https://infocam.castillalamancha.es  
- X oficial: https://x.com/Plan_INFOCAM  
- Mapa pack: `C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\outputs\open_if\la_mierla_20260717\map_satellite.html`
