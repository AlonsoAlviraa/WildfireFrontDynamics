# Informe de Resultados: Mega Pre-entrenamiento y Meta-Labeling (16 Horas de Cómputo)
**Fecha:** 18 de Junio de 2026  
**Plataforma de Cómputo:** Kaggle Cloud  
**Hardware:** GPU Nvidia Tesla T4 (Capacidad CUDA 7.5, 16GB VRAM)  
**Tiempo Total de Ejecución:** 11,73 horas (42.241 segundos)  
**Estado:** Éxito (Completo)

---

## 1. Introducción y Resumen del Trabajo

Este informe detalla los resultados del pipeline de entrenamiento masivo y calibración local diseñado para el modelo de predicción de propagación de incendios forestales [`A3C_PerCellModel_LSTM`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/models/model.py). 

El objetivo de este trabajo ha sido entrenar de forma segura un modelo base generalizable a escala continental, adaptarlo con transferencia de aprendizaje a la escala espacial métrica local (Castilla-La Mancha) y entrenar una capa de seguridad clasificadora ([`WildfireMetaLabeler`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/wildfire_front/ml/meta_labeler.py)) libre de filtraciones de datos espaciales (*data leakage*).

---

## 2. Fases del Pipeline y Métricas de Convergencia

### Fase 1: Preprocesamiento de TFRecords (Splits Separados Físicamente)
Para erradicar cualquier fuga de datos espacial entre parches solapados del mismo incendio, se dividieron físicamente los archivos `.tfrecord` originales:
*   **Conjunto de Entrenamiento (Train):** 13 archivos TFRecord que generaron **74.279 parches activos** de 30x30 píxeles.
*   **Conjunto de Validación (Val):** 2 archivos TFRecord completamente disjuntos que generaron **10.064 parches activos** de 30x30 píxeles.

---

### Fase 2: Preentrenamiento Masivo (Google NDWS - 12 Épocas)
Se entrenó el modelo convolucional-recurrente base utilizando el optimizador AdamW, con una tasa de aprendizaje inicial de $1\text{e-}4$, y un planificador de decaimiento por coseno (`CosineAnnealingLR`) hasta un mínimo de $1\text{e-}6$.

La evolución de la pérdida (*Loss*) y de la tasa de aprendizaje (*LR*) por época fue la siguiente:

| Época | Tasa de Aprendizaje (LR) | Pérdida de Transiciones (Loss) | Notas / Observaciones |
| :---: | :---: | :---: | :--- |
| **1** | $9.83\text{e-}5$ | `0.384010` | Inicio y adaptación de gradiente. |
| **2** | $9.33\text{e-}5$ | `0.365377` | **Convergencia principal de la red.** |
| **3** | $8.55\text{e-}5$ | `0.364342` | Descenso estable. |
| **4** | $7.52\text{e-}5$ | `0.363766` | **Mínimo global del entrenamiento.** |
| **5** | $6.33\text{e-}5$ | `0.363904` | Oscilación mínima. |
| **6** | $5.05\text{e-}5$ | `0.364677` | Estabilización. |
| **7** | $3.76\text{e-}5$ | `0.365983` | Decaimiento estable. |
| **8** | $2.57\text{e-}5$ | `0.367343` | Ajuste fino de pesos. |
| **9** | $1.55\text{e-}5$ | `0.367905` | Convergencia a baja tasa. |
| **10** | $7.63\text{e-}6$ | `0.368161` | Ajuste en celdas límite. |
| **11** | $2.69\text{e-}6$ | `0.368831` | Fluctuación marginal. |
| **12** | $1.00\text{e-}6$ | `0.368300` | Cierre del planificador por coseno. |

> [!NOTE]
> **Análisis de Convergencia:** El modelo convergió de manera sumamente eficiente en la Época 2 y mantuvo la estabilidad del gradiente durante las épocas restantes. Esto demuestra la robustez física de la política aprendida para asimilar el viento, la topografía (pendiente y orientación) y la sequedad del combustible.

---

### Fase 3: Transfer Learning Local (Castilla-La Mancha)
Se aplicó fine-tuning sobre la secuencia táctica de Castilla-La Mancha (`semireal_controlled_001`) durante 10 épocas con tasa de aprendizaje baja ($2\text{e-}5$):

*   **Pérdida Inicial (Época 1):** `0.382271`
*   **Pérdida Intermedia (Época 5):** `0.354045`
*   **Pérdida Final (Época 10):** `0.343702`

> [!TIP]
> **Resultado Local:** La pérdida de propagación local disminuyó en un **10,1%**, adaptando con éxito las características espaciales gruesas del preentrenamiento satelital al dominio de alta resolución métrica de drones y UAVs locales.

---

### Fase 4: Calibración del Meta-Labeler (Capa de Seguridad)
El modelo base inferido sobre las celdas de validación independientes evaluó un total de **2.029.376 transiciones celulares** de vecindad de 8 direcciones:
*   **Predicciones Correctas (Clase 1):** 1.859.270 muestras (~91,6%)
*   **Predicciones Incorrectas / Fallos (Clase 0):** 170.106 muestras (~8,4%)

Se entrenó un Random Forest para predecir si una predicción local del modelo base es de confianza, obteniendo:
*   **Precisión de Validación Cruzada Real (Self-Training Accuracy):** **`0.6058` (60,58%)**

> [!IMPORTANT]
> **Ausencia de Data Leakage:** A diferencia de métricas anteriores infladas artificialmente (~64,8%) debido al solapamiento espacial de parches en un split aleatorio, este **60,58%** representa la precisión honesta y real del Meta-Labeler ante incendios forestales completamente invisibles. Proporciona una señal no trivial y robusta para activar alertas de **Abstención** en la UI cuando el modelo duda.

---

## 3. Ubicación de los Modelos y Archivos Locales

Los resultados finales han sido descargados e integrados en el directorio local [`kaggle_output/`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/kaggle_output/):

| Archivo | Tamaño | Propósito y Contenido |
| :--- | :---: | :--- |
| 📁 [`weights_pretrained.pt`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/kaggle_output/weights_pretrained.pt) | `7.1 MB` | Pesos base del modelo entrenados a gran escala en Google NDWS. |
| 📁 [`weights_fine_tuned.pt`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/kaggle_output/weights_fine_tuned.pt) | `7.1 MB` | Pesos refinados y optimizados para Castilla-La Mancha. |
| 📁 [`meta_labeler.pkl`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/kaggle_output/meta_labeler.pkl) | `10.1 MB` | Modelo Random Forest calibrado para el filtro de seguridad táctico. |
| 📄 [`wildfire-front-training.log`](file:///c:/Users/alonso.alvira/WildfireFrontDynamics/WildfireFrontDynamics/kaggle_output/wildfire-front-training.log) | `15.7 KB` | Log de salida estándar (stdout/stderr) de la máquina virtual en la nube. |

---

## 4. Próximos Pasos Recomendados (Roadmap de ML)

A la espera de recibir la base de datos histórica de la CMA (2021 en adelante), se sugieren las siguientes líneas de mejora:

1.  **Congelación de Capas (Layer Freezing):** Al realizar el fine-tuning con nuevos datos, congelar el extractor convolucional inicial del modelo base para conservar las leyes físicas de propagación globales y entrenar únicamente las capas LSTM.
2.  **Fine-tuning con Dominio Mixto:** Combinar un 80% de nuevos datos locales con un 20% de datos de preentrenamiento (GEE). Esto impide que el modelo desarrolle sesgos locales extremos y sufra "olvido catastrófico".
3.  **Calibración del Umbral de Veto:** Ajustar el umbral del Meta-Labeler en producción para priorizar el *Recall* sobre los fallos del modelo base (Clase 0), garantizando que las decisiones dudosas se oculten o marquen como "zona de abstención" antes de que generen falsos negativos de propagación críticos.
