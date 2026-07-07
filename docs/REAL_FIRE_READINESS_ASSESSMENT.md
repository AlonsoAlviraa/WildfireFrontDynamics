# Evaluación de Viabilidad — Prueba en Incendio Real

> **Fecha**: 2026-07-07  
> **Pregunta**: ¿Podemos llevar el sistema a probar en un incendio real?

---

## Resumen ejecutivo

**Respuesta corta: Sí, pero como sistema de post-proceso (no en tiempo real durante el incendio).**

El sistema está listo para procesar imágenes térmicas de un incendio real **después** de la captura, generar geometrías de frente observadas, estimar velocidades de avance y producir reportes trazables. **No** está diseñado para predecir la propagación en tiempo real durante la emergencia.

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Ingesta de GeoTIFFs reales | ✅ **Listo** | 7 incendios procesados (414 TIFs) |
| Reconstrucción de frente observado | ✅ **Listo** | Pipeline validado con datos LWIR |
| Estimación de velocidades | ✅ **Listo** | Con incertidumbre y abstención |
| Reportes trazables (SHA-256) | ✅ **Listo** | HTML + GeoJSON + NPZ |
| Predicción ML en tiempo real | ⚠️ **Parcial** | Modelo entrenado, falta inferencia optimizada |
| Despliegue en campo (edge) | ❌ **No** | Requiere desarrollo adicional |
| Integración con feeds de dron | ❌ **No** | Falta conector de streaming |

---

## Lo que SÍ se puede hacer hoy

### Escenario A: Post-proceso de imágenes capturadas

```
Dron captura LWIR durante incendio
    → Descarga GeoTIFFs a laptop
    → wildfire-front geotiff-ingest <directorio>
    → Sistema produce:
        - Geometría observada del frente (GeoJSON)
        - Velocidades de avance por segmento
        - Campos de tiempo de llegada
        - Reporte HTML autocontenido
        - Manifiesto con SHA-256 (trazabilidad)
```

**Esto funciona hoy.** Es el modo en que se procesaron los 7 incendios de Castilla-La Mancha.

### Escenario B: Validación contra GT conocido

Si se dispone de un perímetro oficial post-incendio (ej. Copernicus EMS, MACF):
- El sistema puede comparar su reconstrucción observada vs. el perímetro oficial
- Genera métricas de error y cobertura

### Escenario C: Demostración técnica

El pipeline `wildfire-front demo` genera escenarios sintéticos con GT conocido, útil para demostrar capacidades sin necesidad de datos reales.

---

## Lo que NO se puede hacer hoy (gaps reales)

### 1. Predicción en tiempo real

El modelo A3C-LSTM está entrenado pero **no hay pipeline de inferencia optimizada** para servir predicciones en vivo. Falta:

- [ ] Endpoint de inferencia (REST/gRPC) que acepte el frame actual y devuelva predicción
- [ ] Optimización de latencia (cuantización, ONNX, TensorRT)
- [ ] Buffer de streaming para mantener la secuencia temporal (3 frames)
- [ ] Manejo de CRS dinámico (el sistema asume reproyección previa)

### 2. Despliegue en campo

- [ ] Container Docker en edge device (Jetson, laptop táctica)
- [ ] Integración con software de estación de tierra del dron (DJI, etc.)
- [ ] Offline-first (sin dependencia de nube durante el vuelo)
- [ ] UI para operadores de emergencia

### 3. Validación operacional

- [ ] Comparar velocidades estimadas vs. velocidades medidas en campo
- [ ] Validar con equipos de extinción (observación directa del frente)
- [ ] Calibrar thresholds de binarización para diferentes sensores

---

## Requisitos técnicos para una prueba de campo

### Datos de entrada mínimos

Para que el sistema funcione, se necesita:

1. **Secuencia de imágenes térmicas LWIR** (mínimo 2 frames, idealmente 5+)
   - Formato: GeoTIFF con CRS métrico proyectado (no WGS84 lat/lon)
   - Resolución espacial: idealmente <30 m/pixel
   - Intervalo temporal: conocido y consistente
   - Ver contrato: `docs/GEOTIFF_INPUT_CONTRACT.md`

2. **CRS métrico**: Las imágenes deben estar reproyectadas a un CRS métrico (UTM, ETRS89, etc.). El sistema rechaza WGS84 automáticamente.

3. **Calidad suficiente**: Frames con poca señal o ruido excesivo se rechazan (como pasó con 50 frames de `la_estrella_acom2_2024`).

### Hardware mínimo

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| Laptop | 8 GB RAM, CPU i5 | 16 GB RAM, GPU opcional |
| Disco | 2 GB libres | 10 GB (para outputs) |
| Python | 3.11+ | 3.12 |
| Dependencias | numpy, rasterio, affine | + torch, scipy para ML |

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Sensor nuevo no calibrado | Alta | Medio | Threshold MAD adaptativo ya implementado |
| CRS no métrico (GPS bruto) | Media | Alto | Validación + reproyección automática disponible |
| Pocos frames (<3) | Alta | Medio | Abstención automática cuando no hay suficiente señal |
| Condiciones de baja contraste | Media | Medio | Control de calidad con rechazo automático |
| Expectativa de tiempo real | Alta | Alto | **Dejar claro que es post-proceso** |

---

## Recomendación

**Se puede llevar a una prueba real en modo post-proceso.**

### Plan de prueba sugerido (1 día)

1. **Mañana**: Vuelo de dron sobre incendio activo o reciente, captura LWIR
2. **Mediodía**: Descarga de datos, reproyección a UTM
3. **Tarde**: Procesamiento con `wildfire-front geotiff-ingest`
4. **Final del día**: Revisión de resultados con equipo de extinción, comparación con observación de campo

### Preparación necesaria antes de salir al campo

- [ ] Verificar que `wildfire-front` está instalado en el laptop de campo
- [ ] Llevar script de reproyección listo (`scripts/prepare_real_if_geotiffs.py`)
- [ ] Tener Docker image construida como backup (`docker build -t wildfire-front .`)
- [ ] Imprimir `docs/RUNBOOK_NEW_FIRES.md` como guía rápida
- [ ] Verificar contrato de entrada (`docs/GEOTIFF_INPUT_CONTRACT.md`) con el operador del dron

### Lo que NO prometer

- ❌ "Predicción de hacia dónde va el fuego en los próximos 10 minutos" (no implementado)
- ❌ "Alertas en tiempo real al centro de mando" (no implementado)
- ❌ "Funciona con cualquier sensor" (requiere LWIR térmico o similar)

---

## Roadmap hacia tiempo real (futuro)

Si el objetivo es llegar a tiempo real, el orden sugerido es:

1. **Endpoint de inferencia** (1-2 semanas): FastAPI + TorchScript, acepta frame → devuelve predicción
2. **Buffer de streaming** (1 semana): Mantiene últimos 3 frames para alimentar la LSTM
3. **UI para operadores** (1-2 semanas): Dashboard simple con mapa y velocidad del frente
4. **Optimización de latencia** (1 semana): Cuantización INT8, target <500ms por frame
5. **Prueba de campo en tiempo real** (cuando todo lo anterior esté listo)

**Estimación total hacia tiempo real**: 4-6 semanas de desarrollo adicional.