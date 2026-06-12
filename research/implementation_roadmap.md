# Hoja de Ruta de Implementación: De Dinámica Histórica a Predicción con ML

Esta hoja de ruta describe los pasos técnicos necesarios para evolucionar la arquitectura actual del repositorio (`WildfireFrontDynamics`) desde un analizador histórico hacia un pipeline de entrenamiento y predicción espacio-temporal basado en Machine Learning (U-Net + ConvLSTM).

---

## Fase 1: Extracción del Dataset de Entrenamiento (ML Data Prep)
Antes de construir el modelo, debemos convertir nuestras observaciones en un formato tensorizado que pueda consumir PyTorch o TensorFlow:

1.  **Conversión de Geometría a Raster:** 
    *   Utilizar el módulo actual `reconstruction.py` (`reconstruct_arrival_from_components`) para rasterizar las geometrías de `FrontObservation` (frentes históricos de Heligrafics) y generar mapas bidimensionales de tiempo de llegada y presencia de fuego.
2.  **Alineación de Capas Auxiliares (Features):**
    *   Crear un script en `scripts/prep_spatial_features.py` que descargue y alinee espacialmente las capas de elevación (DEM), pendiente (slope) y combustible (vegetación) usando la misma resolución y extensión espacial que el raster de Heligrafics (vía `rasterio`).
3.  **Generación de Ventanas Temporales (Sequences):**
    *   Generar secuencias del tipo `(t-2, t-1, t)` como variables de entrada y el estado del frente en `t + 30 min` como la variable objetivo (Target) a predecir.

---

## Fase 2: Implementación de la Red Neuronal (Model Definition)
1.  **Estructura del Repositorio:**
    *   Crear un nuevo paquete interno `wildfire_front/ml/` que contenga:
        *   `wildfire_front/ml/dataset.py`: Cargador de datos (PyTorch `Dataset` y `DataLoader`).
        *   `wildfire_front/ml/models.py`: Definición de la arquitectura U-Net y ConvLSTM.
        *   `wildfire_front/ml/train.py`: Bucle de entrenamiento con soporte para validación cruzada dejando eventos completos fuera.
2.  **Función de Pérdida (Loss Function) Personalizada:**
    *   Implementar una pérdida que combine **Binary Cross-Entropy (BCE)** para la presencia del fuego con un término de **penalización por distancia (Hausdorff loss)** para castigar severamente las predicciones que se desvíen muchos metros del frente real.

---

## Fase 3: Integración y Dashboard de Predicción
1.  **Inferencia en Tiempo Real:**
    *   Modificar la CLI (`cli.py`) para añadir el comando `predict`:
        ```powershell
        python -m wildfire_front predict --images data/sample/images --model-weights models/unet_convlstm.pth --output outputs/prediction
        ```
2.  **Visualización en Dashboard:**
    *   Modificar `outputs.py` para incluir la capa de **probabilidad de propagación predicha** en el dashboard interactivo `report.html`. Las isocronas predichas se mostrarán como áreas sombreadas (de amarillo a rojo) superpuestas sobre el mapa de frentes históricos.
3.  **Auditoría de Inferencia:**
    *   El módulo de calidad (`quality.py`) registrará el IoU y el error medio de las predicciones conforme se vayan confirmando con las siguientes pasadas de la aeronave de Heligrafics, permitiendo auditar la precisión en tiempo de ejecución.
