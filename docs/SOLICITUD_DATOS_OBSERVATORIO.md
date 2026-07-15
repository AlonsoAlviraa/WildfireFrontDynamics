# Solicitud de datos al Observatorio (loop 2 semanas)

> Para desbloquear saltos **O1** (multi-ancla), **O2** (error geométrico) y **O5** (2º grado A).  
> Sin estos datos el techo del loop es **GO parcial** (motor validado solo en Tobarra).

---

## 1. Anclas operativas por incendio (prioridad alta)

Para cada IF que podáis (ideal: Cardoso 2025, Hellín 2024, La Estrella, Tobarra ya lo tenemos):

| Campo | Ejemplo Tobarra | Notas |
|-------|-----------------|-------|
| ID / nombre IF | TOBARRA-AB-20240802 | |
| Fecha detección | 2024-08-02 16:42 | |
| Vp media (m/min) | 7 | o rango si no hay media |
| Superficie (ha) | 39 | en el momento del parte |
| Intensidad / comportamiento | Media-Alta, contraviento | opcional |
| Fuente | INFOCAM / FIDIAS / parte | |

Formato aceptable: tabla en correo, Excel, o CSV.

---

## 2. Perímetros / croquis independientes (prioridad alta para O2)

Ideal (cualquiera de estos):

- Shapefile / GeoPackage / GeoJSON de perímetro en **CRS métrico** (UTM ETRS89 preferible)
- O croquis georreferenciado por franjas horarias (mínimo 2 instantes)
- O enlace a capa ya publicada (Copernicus EMS, etc.) si aplica

**Mínimo útil:** 1 perímetro de Tobarra o de otro IF con secuencia LWIR en el repo.

---

## 3. Confirmación de uso del informe

En 5 minutos, ¿el formato `operational_report.html` + capa de frente os sirve?

- ¿Qué sobra?
- ¿Qué falta (tabla medios, mapa base, hora oficial, etc.)?

---

## 4. Qué os devolvemos a cambio

Con anclas + 1 perímetro:

1. ROS multi-estimador en **≥2 IF** con ratio vs ancla  
2. Error geométrico (Hausdorff / P50) donde haya perímetro  
3. Pack GIS (`main_front.gpkg` + timeline) listo para QGIS  

Sin datos nuevos: seguimos mejorando estabilidad Tobarra y el producto GIS, y documentamos el techo.

---

## 5. Texto corto para correo

```text
Buenos días,

Para la siguiente quincena de validación del motor de dinámica de frente
necesitamos, si es posible:

1) Vp media y/o superficie (ha) de Cardoso 2025 y Hellín 2024 (u otros IF
   con secuencia térmica), en el formato que tengáis de parte operativo.
2) Un perímetro vectorial o croquis georreferenciado (aunque sea de un solo
   instante) para Tobarra u otro IF, para medir error geométrico real.
3) Feedback breve de si el informe operativo HTML os resulta usable.

Con eso podemos pasar de “Tobarra en el mismo orden de magnitud que INFOCAM”
a validación multi-incendio defendible.

Gracias.
```
