# Catálogo de Datasets para Predicción de Propagación de Incendios con ML

Para entrenar un modelo de aprendizaje automático de propagación a corto plazo ($t + \Delta t$), se requieren datasets con series temporales continuas que integren cartografía del terreno, meteorología y observaciones del estado del fuego. A continuación, se presenta un inventario de los datasets más relevantes a nivel internacional y operativo:

---

## 1. Next Day Wildfire Spread (Google Research)
*   **Descripción:** Dataset a gran escala y multivariante que abarca casi una década de incendios forestales históricos en EE. UU. Diseñado específicamente para machine learning espacial de propagación con antelación de 1 día.
*   **Formato de datos:** Tensor espacial en 2D (grids) alineado con variables topográficas, meteorológicas y de combustible.
*   **Variables clave:** 
    *   *Frente/Área Quemada:* Detección satelital diaria del frente activo.
    *   *Topografía:* Elevación, pendiente y orientación.
    *   *Combustible/Vegetación:* Índice de vegetación (NDVI) y sequedad.
    *   *Meteorología:* Temperatura, humedad relativa, dirección y velocidad del viento.
*   **Uso en el Proyecto:** Excelente base para probar arquitecturas convolucionales y validar el preprocesamiento de variables de entrada estáticas (pendientes, combustibles).

---

## 2. FLAME (Fire Live-Acoustic Detection and Multi-Sensor) / FLAME 3
*   **Descripción:** Dataset aéreo capturado con drones (UAV) en quemas controladas en EE. UU.
*   **Formato de datos:** Secuencias de video RGB y térmico radiométrico (IR) de alta resolución con emparejamiento temporal.
*   **Variables clave:**
    *   Espectro visible (RGB) e infrarrojo térmico (LWIR).
    *   Frecuencia temporal alta (fotogramas por segundo).
    *   Timestamps e información del vuelo.
*   **Uso en el Proyecto:** Es el candidato prioritario para entrenar y validar modelos de propagación a nivel microtáctico (resolución de metros y avance en minutos), muy similar al entorno operativo de Heligrafics.

---

## 3. NASA AMS (Autonomous Modular Sensor)
*   **Descripción:** Dataset de vuelos de sensor multiespectral de la NASA montado en aeronaves tripuladas y no tripuladas.
*   **Formato de datos:** Rasters georreferenciados multibanda (infrarrojo térmico, de onda corta y visible).
*   **Variables clave:**
    *   Bandas de alta reflectancia al fuego activo.
    *   Máscaras segmentadas de zonas calientes.
*   **Uso en el Proyecto:** Permite estudiar el procesamiento de imágenes multibanda y la conversión de píxeles calientes a coordenadas proyectadas en terreno.

---

## 4. Mesogeos
*   **Descripción:** Datacube diseñado específicamente para el ámbito del Mediterráneo europeo que abarca 17 años de datos (2006-2022).
*   **Formato de datos:** Grid espaciotemporal continuo armonizado de variables ambientales.
*   **Variables clave:**
    *   Perímetros reales de incendios del servicio EFFIS (European Forest Fire Information System).
    *   Predicciones meteorológicas ECMWF y topografía.
*   **Uso en el Proyecto:** Es el dataset geográficamente más representativo para validar la transferencia de modelos a incendios reales en climas mediterráneos, donde el combustible y la topografía difieren de los de EE. UU.

---

## 5. WildfireDB
*   **Descripción:** Dataset masivo de código abierto (más de 17 millones de puntos de datos) que asocia ocurrencias de incendios satelitales en EE. UU. (2012-2018) con factores ambientales locales.
*   **Uso en el Proyecto:** Útil para entrenamiento masivo de modelos tabulares y redes neuronales densas de probabilidad de propagación celda a celda.
