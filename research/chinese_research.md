# Investigación y Avances en China en Predicción de Incendios con ML

China cuenta con algunas de las instituciones de ciencia del fuego más avanzadas del mundo, destacando el **State Key Laboratory of Fire Science (SKLFS)** en la Universidad de Ciencia y Tecnología de China (USTC) y departamentos especializados en la Universidad de Geociencias de China (CUG). Sus investigaciones combinan técnicas avanzadas de Deep Learning con simulación física y asimilación de datos satelitales (como FY-4A y Himawari-9).

---

## 1. Hibridación de Autómatas Celulares (CA) y Deep Learning
*   **Enfoque:** Tradicionalmente, los modelos de Autómatas Celulares se usan para simular el fuego celda a celda según reglas lógicas de transición. Los investigadores chinos han sustituido las reglas fijas de CA por **redes neuronales convolucionales (CNN)** que aprenden los coeficientes de transición espacial dinámicamente a partir de imágenes de satélite históricas.
*   **Proyecto de Referencia:** `Swayam2004/forest_fire_spread` y publicaciones asociadas a la Universidad de Tsinghua implementan redes híbridas **ResUNet-A + Autómatas Celulares** para mapear la propagación en tiempo real basándose en datos del satélite meteorológico de órbita geoestacionaria Fengyun.

---

## 2. Modelado a Escala Microtáctica (5 metros) - PolyU Hong Kong
*   **Enfoque:** La Universidad Politécnica de Hong Kong (PolyU) ha desarrollado marcos de Deep Learning a escala cruzada (cross-scale) para modelar la dinámica de incendios forestales a muy alta resolución (hasta 5 metros).
*   **Avance Clave:**
    *   Integración de datos de viento locales simulados con modelos CFD (Computational Fluid Dynamics) con redes ConvLSTM.
    *   Permite predecir no solo el avance general del frente diario, sino los comportamientos de "fuego de copa" (crown fire) y aceleraciones locales en laderas específicas de alta pendiente (como en la región de Liangshan, Sichuan).

---

## 3. Repositorios y Códigos Abiertos en China (Gitee & GitHub)
En las plataformas de código Gitee y GitHub de autores chinos destacan los siguientes desarrollos prácticos:

*   **[osnaren/forest-fire](https://github.com/osnaren/forest-fire)**: Implementación de detección y segmentación del contorno de incendios forestales mediante arquitecturas optimizadas de Deep Learning (como MobileNetV3 y YOLO adaptados) integradas con paneles de visualización web GIS en tiempo real.
*   **Algoritmos de Clasificación Radiométrica en FY-4A (Gitee/GitHub)**: Repositorios de procesamiento de satélites geoestacionarios chinos (Fengyun 4) que extraen anomalías de temperatura de brillo (brightness temperature) en bandas de onda media y larga para mapear el avance de frentes térmicos cada 15 minutos.
*   **Modelos de Reducción de Falsos Positivos**: Implementaciones que integran factores antrópicos (cercanía a carreteras, tendidos eléctricos) con modelos espaciotemporales LSTM de peligro de propagación.

---

## 4. Claves del Éxito de los Modelos Chinos Aplicables a Nuestro Pipeline
Para que nuestro software empresarial tenga un estándar competitivo global, debemos incorporar tres lecciones de las publicaciones chinas:
1.  **Fusión Multimodal Inmediata:** No entrenar el modelo solo con imágenes térmicas. Integrar el mapa de combustible (vegetación) y el DEM (pendiente/orientación) como **canales de entrada directos del tensor**, permitiendo que la red convolucional aprenda la interacción física de forma implícita.
2.  **Uso de Redes de Atención (Attention Mechanisms):** Emplear módulos de atención espacial (como CBAM o Swin Transformers) en la U-Net para que la red priorice las zonas secas y a favor del viento, donde la propagación es físicamente más probable.
3.  **Calibración Local por Evento (Instance-Level Calibration):** En lugar de un modelo de ML global para todo un país, usar un pre-entrenamiento global y realizar un **fine-tuning fino con las primeras 3 observaciones** del incendio actual para adaptar el modelo a las condiciones meteorológicas del día.
