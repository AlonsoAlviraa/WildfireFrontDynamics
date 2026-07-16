# Mega-análisis: China — linhuo (林火) / wildfire spread

Fecha: 2026-07-16  
Alcance: GitHub CN, Gitee/GitCode (vía menciones), literatura CN, “reddit chino” (知乎 / V2EX / foros), código vendored y **port a WFD**.

---

## 1. Resumen ejecutivo (qué sirve para nosotros)

| Hallazgo | Utilidad WFD | Acción |
|----------|--------------|--------|
| **Modelo 王正非 (Wang Zhengfei)** = estándar CN de ROS estadístico | Alta: prior físico + anisotropía viento/pendiente | **Implementado** `wildfire_front/cn_wang_zhengfei.py` |
| **毛贤敏 (Mao)** 8 direcciones viento×pendiente | Alta: forma de envelope no isótropa | En mismo módulo |
| **元胞自动机 CA + Wang** (papers CAF/BJFU) | Media: demo / research | **CA mínimo** `cn_cellular_ca.py` |
| Repos Java/Vue CN (fire-spread, CesiumFire, BackEnd) | Media: patrón envelope polar 360° + Cesium | Clonados en `_vendor_cn/`; ideas portadas, no Java en runtime |
| YongfengX WildfireSpreadTS (CN author) | Media-alta ML next-day | Clonado; ideas FNO/ensemble (research), no sustituye CLM v28 ops |
| Gitee “modelo del colega” (citado, a menudo borrado) | Baja: datos privados no subidos | No reutilizable |
| Zhihu / foros | Baja: UCI Portugal + SVM área, no ROS aéreo | Solo contexto |
| Rothermel recalibrado sur de China (点烧) | Media: no usar US params raw | Nota calibración |

**Conclusión operativa:** China no tiene un “FIRMS mágico” abierto mejor que el nuestro, pero **sí** tiene el stack mental correcto para sala:  
**ROS empírico simple (Wang) × CA/GIS polar × visualización Cesium**.  
Nosotros ya superamos en **ROS observada multi-estimador + grados A/B/C + envelope etiquetado**. El valor CN es **priors y forma anisotrópica**, no sustituir Tobarra.

**Híbrido recomendado (hecho en script):**  
`magnitud = ROS observada (Tobarra ~5.7 m/min)` × `forma = Wang/Mao polar`.

---

## 2. Ecosistema “GitHub chino” / Gitee / GitCode

### 2.1 Repos CN directos (útiles)

| Repo | Qué es | Stars | Valor real |
|------|--------|-------|------------|
| [xllyll/fire-spread](https://github.com/xllyll/fire-spread) | Java: 王正非 en README; simulación polar 360° + DEM + vegetación + barreras | ~3 | **Patrón envelope** por rayos; fórmula real simplificada/heurística en código |
| [winrelde/ForestFireSpreadBackEnd](https://github.com/winrelde/ForestFireSpreadBackEnd) | Spring/Java backend; dice copiar Gitee Linux→Windows; **datos no subidos** | ~3 | Arquitectura ops (API→DB→OpenLayers/Cesium) |
| [winrelde/CesiumFire](https://github.com/winrelde/CesiumFire) | Vue + Cesium visualización linhuo | ~4 | UX 3D; no motor ROS |
| [icydengyw/ForestFireSpreadSystem](https://github.com/icydengyw/ForestFireSpreadSystem) | “模拟林区火灾蔓延” — casi vacío (solo README) | ~5 | Señal de demanda, cero código |
| [lishulincug/fs_demo](https://github.com/lishulincug/fs_demo) | Vue + Baidu Map 森林防火 | ~5 | Dashboard, no spread physics |
| [fumu-keji/smart-forest-farm](https://github.com/fumu-keji/smart-forest-farm) | 智慧林场 big-screen | ~4 | UI command-center |
| GitCode docs “森林火灾数学模型” | Documentación modelos | — | Pedagógico |

**Vendored (shallow clone, no commit grande al remoto si no se pide):**  
`_vendor_cn/fire-spread`, `CesiumFire`, `FireCellularAutomata`, `YongfengX-WildfireSpreadTS`

### 2.2 Repos adyacentes (no CN exclusivos, usados en papers CN)

| Repo | Nota |
|------|------|
| Cell2Fire / FARSITE | Papers CN (Liangshan, etc.) comparan re-init con satélite |
| FireCellularAutomata (Samyak) | CA + viento/topo demo Python |
| YongfengX/wildfire-spread-prediction | Mejora WildfireSpreadTS AP 0.35→0.47 (FNO/ensemble) |

### 2.3 Gitee / “reddit chino”

- **Gitee:** muchos forks de “林火蔓延” son tesis con DEM locales **no publicados** (el propio winrelde lo admite). Scraping masivo = baja señal.
- **知乎:** posts tipo “UCI Forest Fires + SVM” (área quemada Portugal) — **no** dinámica de frente aéreo.
- **V2EX / Bilibili:** demos UE4 / Unreal linhuo 3D (CAF journals) — visualización, no validación ROS.
- **No existe** un subreddit-equivalente con miles de datasets LWIR abiertos de brigadas chinas (dato sensible / gobierno).

---

## 3. Literatura CN clave (fórmulas que importan)

### 3.1 Wang Zhengfei 王正非

```
R = R0 · Kw · Ks · Kφ
Kw = exp(0.1783 · V · cos θ)     # V m/s
Ks = exp( ± 3.533 · (tan φ)^1.2 ) # + upslope / − downslope
```

- R0: velocidad inicial (laboratorio / empírico meteo).  
- Límite frecuente: pendiente < 60°.  
- Mao Xianmin: 上坡/下坡/左平/右平 + viento.

### 3.2 CA + Wang (BJFU, CAF, Central South Forestry)

- Grid + factor matrices combustible/topografía + meteo.  
- Mejor que CA puro “Game of Life fire”.  
- Uso: simulación táctica **con** capas GIS — mismo hueco que nosotros: **falta ancla real multi-IF**.

### 3.3 Rothermel en sur de China

- Params US **malos** en 8 combustibles sur (MRE ~70%); re-fit baja error a ~16%.  
- Lección: **no copiar Rothermel US a CLM sin calibrar**; por eso preferimos ROS observada + prior forma.

### 3.4 FARSITE vs Cell2Fire (China remote sensing journals)

- Re-inicialización con perímetros satélite mejora errores de simulación larga.  
- Alineado con nuestro gate O2 (Hausdorff vs perímetro oficial).

---

## 4. Código implementado en WFD (este ciclo)

| Archivo | Función |
|---------|---------|
| `wildfire_front/cn_wang_zhengfei.py` | R0, Kw, Ks, 8-dir Mao, anillo polar, `physics_prior_report` |
| `wildfire_front/cn_cellular_ca.py` | CA 2D mínimo + curva quemado |
| `scripts/run_cn_physics_prior.py` | Prior vs ROS obs + **calibración escala** (híbrido) |
| `tests/test_cn_wang_zhengfei.py` | Tests unitarios |

```bash
python scripts/run_cn_physics_prior.py --obs-ros 5.71 --wind-force 3 --ca
python -m pytest tests/test_cn_wang_zhengfei.py -q
```

---

## 5. Qué NO copiar

- Binarios/Windows bat de backends sin datos.  
- DEM paths hardcodeados (`/Users/xllyll/Downloads/chongqi.tif`).  
- Visualización Cesium completa (peso frontend; nuestro Leaflet ya cubre demo).  
- Entrenar otro NDWS en China sin IF locales — no desbloquea O1/O2 CLM.  
- Inventar emails de 应急管理部 o 森林消防 — mismo criterio GDPR/ético.

---

## 6. Roadmap CN → producto emergencia

| Prioridad | Item | Estado |
|-----------|------|--------|
| P0 | Híbrido ROS_obs × forma Wang | **Script listo** |
| P1 | Meter polar calibrado en `emergency_envelope` GeoJSON opcional | Siguiente |
| P2 | R0 desde AEMET (T, RH, viento) por IF | Cuando haya meteo pack |
| P3 | Ideas FNO/ensemble de YongfengX solo si reabrimos G1 temporal | HOLD (G1 KILL) |
| P4 | Cesium only if cliente paga 3D | No ahora |

---

## 7. Contactos / papers CN (para citar, no spamear)

- Journals: 北京林业大学, 中国林业科学研究院, 中南林业科技大学, 遥感学报 (FARSITE/Cell2Fire).  
- Emails de autores: en PDFs de corresponding author (ORCID) — pedir **solo** si colaboración científica, no scraping.  
- Instituciones: CAF, BJFU, Northeast Forestry Univ. (帽儿山 wind tunnel).

---

## 8. Veredicto brutal

China publica **mucho paper + poco dato abierto operativo**. Su “código de GitHub” es a menudo UI + CA de juguete o Java sin DEM.  
El oro es la **fórmula Wang/Mao** y el **patrón polar 360°** — ya en nuestro repo.  
El resto del “mega” se gana con **GEACAM/EFFIS perímetros**, no con más estrellas en Gitee.
