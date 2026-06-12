# Modelos Preentrenados Open Source para Predicción de Propagación de Incendios

La disponibilidad de pesos preentrenados (pretrained weights) y modelos de código abierto específicos para dinámicas de incendios es reducida debido a la alta dependencia de la geografía y los sensores locales. Sin embargo, existen proyectos de referencia clave y repositorios con modelos preentrenados listos para inferencia y transferencia de aprendizaje (transfer learning):

---

## 1. CanadaFireSat-Model (EPFL ECEO)
*   **Repositorio:** [eceo-epfl/CanadaFireSat-Model](https://github.com/eceo-epfl/CanadaFireSat-Model)
*   **Dataset Asociado:** [eceo-epfl/CanadaFireSat-Data](https://github.com/eceo-epfl/CanadaFireSat-Data)
*   **Descripción:** Suite de modelos de Deep Learning desarrollada por el Laboratorio de Observación de la Tierra (ECEO) de la Escuela Politécnica Federal de Lausana (EPFL). Predice la propagación de incendios a alta resolución espacial (100 metros).
*   **Arquitecturas Disponibles:**
    *   Codificadores basados en **CNN (ResNet)**.
    *   Codificadores basados en **Transformers (Vision Transformer - ViT)** para procesar series temporales de satélite.
*   **Insumos del Modelo:**
    *   Imágenes satelitales Sentinel-2 (series temporales).
    *   Variables meteorológicas ERA5-Land y MODIS.
    *   Métricas del sistema de peligro de incendios canadiense (FWI).
*   **Ground Truth:** Polígonos de incendios del National Burned Area Composite (NBAC).

---

## 2. Wildfire Prediction A3C-LSTM (Chung-Ang University / chaseungjoon)
*   **Repositorio de Código:** [chaseungjoon/WildFirePrediction](https://github.com/chaseungjoon/WildFirePrediction)
*   **Pesos Preentrenados (Hugging Face):** [chaseungjoon/wildfire-prediction-A3C-LSTM](https://huggingface.co/chaseungjoon/wildfire-prediction-A3C-LSTM)
*   **Descripción:** Modelo basado en **Aprendizaje por Refuerzo (Deep Reinforcement Learning - A3C)** combinado con células **LSTM** para modelar la toma de decisiones espaciales del fuego.
*   **Resolución:** Predice la propagación en una malla espacial de 300 metros.
*   **Ficheros de Pesos:** Archivo de pesos de PyTorch `v3.pt` disponible en Hugging Face, listo para cargar e inicializar.

---

## 3. ASUFM (Attention Swin U-net with Focal Modulation)
*   **Repositorio:** [bronteee/fire-asufm](https://github.com/bronteee/fire-asufm)
*   **Descripción:** Implementación de última generación de una arquitectura híbrida **Swin U-net** con mecanismos de modulación focal y atención espacial, diseñada específicamente para pronosticar la propagación de incendios forestales a gran escala.
*   **Variables de entrada:** Combina imágenes de reflectancia espectral con capas de humedad, vientos y topografía.

---

## 4. Modelos de Detección Térmica y Segmentación Temprana (YOLOv8 & Vision)
Si el objetivo es la segmentación previa del frente (píxeles calientes / frente activo) en fotos aéreas o de satélite:
*   **[touati-kamel/yolov8s-forest-fire-detection](https://huggingface.co/touati-kamel/yolov8s-forest-fire-detection):** Modelo YOLOv8 preentrenado para segmentar fuego y humo en imágenes RGB aéreas.
*   **[prithivMLmods/Forest-Fire-Detection](https://huggingface.co/prithivMLmods/Forest-Fire-Detection):** Modelo de codificación visión-lenguaje fine-tuneado para clasificación de tipos de incendios forestales.

---

## 5. Estrategia de Reutilización en Nuestro Pipeline
Para integrar estos modelos en nuestro producto empresarial, la ruta recomendada es:
1.  **Transfer Learning con CanadaFireSat:** Utilizar la estructura de su encoder ResNet/ViT preentrenado y realizar un *fine-tuning* con las secuencias locales de Heligrafics. Esto permite que el modelo aproveche los patrones generales de propagación aprendidos en Canadá y los adapte al clima y vegetación local.
2.  **Inferencia con A3C-LSTM:** Evaluar el rendimiento del modelo por refuerzo usando los pesos `v3.pt` sobre mallas sintéticas locales para contrastar predicciones puras de ML contra el estimador geométrico de normals.
