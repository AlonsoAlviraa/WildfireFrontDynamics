# PROPUESTA DE ARQUITECTURA TECNOLÓGICA: SISTEMA INTELIGENTE DE PREDICCIÓN TÁCTICA Y AUDITORÍA DE FRENTES DE INCENDIOS FORESTALES (WFD-ML)

---

## 1. Resumen Ejecutivo
El presente documento describe la propuesta técnica para el desarrollo e implantación de un sistema de predicción a corto plazo ($t + \Delta t$) de la propagación de frentes de incendios forestales. A diferencia de las metodologías tradicionales basadas en simulaciones físicas deterministas (que sufren de alta sensibilidad a la incertidumbre de los datos de entrada en tiempo real) o modelos de Machine Learning (ML) puros (que operan como cajas negras sin restricciones de seguridad), esta arquitectura propone un enfoque híbrido de dos etapas:

1.  **Modelo Primario (Base):** Un codificador espacial acoplado temporalmente (tipo **U-Net + ConvLSTM**), preentrenado con grandes bases de datos de teledetección y sometido a un proceso de **Fine-Tuning** local con datos térmicos de alta resolución (provistos por sistemas aéreos como Heligrafics).
2.  **Modelo Secundario (Meta-Labeler):** Una capa de toma de decisiones basada en **Meta-Labeling** que actúa como un filtro de confianza y seguridad operativa. Este modelo evalúa la viabilidad de la predicción del modelo base y determina si el sistema debe emitir una alerta o abstenerse por falta de observabilidad o inconsistencia física, protegiendo la seguridad de las brigadas en terreno.

---

## 2. Arquitectura del Sistema: Flujo de Datos y Asimilación
El pipeline está diseñado bajo el principio de **degradación elegante (graceful degradation)**, asegurando la operatividad del sistema incluso en escenarios de baja disponibilidad de datos.

```
                  ┌─────────────────────────────────────────┐
                  │       FUENTES DE ENTRADA (MÍNIMAS)      │
                  │  - Secuencias térmicas IR (Heligrafics)  │
                  │  - Modelo Digital del Terreno (DEM)     │
                  │  - Previsión meteorológica local (Viento)│
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │          PIPELINE DE INGESTA            │
                  │  - Ortorrectificación & Proyección UTM  │
                  │  - Extracción de frentes (MAD-Z/U-Net)  │
                  │  - QA de consistencia temporal          │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │       MODELO BASE (U-Net + ConvLSTM)    │
                  │  - Fine-tuning con datos locales        │
                  │  - Inferencia de propagación (t+30 min) │
                  └──────────┬───────────────────┬──────────┘
                             │                   │
                   (Predicción de mapa)    (Métricas de confianza)
                             ▼                   ▼
                  ┌─────────────────────────────────────────┐
                  │      META-LABELER (Filtro de Seguridad) │
                  │  - Ingesta de variables de incertidumbre│
                  │  - Predicción de fiabilidad (Confiar/No) │
                  └────────────────────┬────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
             [SI: Aprobado]                        [NO: Abstenido]
      Visualización en Dashboard             Alerta de baja confianza
     (Isocronas e IoU predictivo)            y recomendación de vuelo
```

---

## 3. Fase I: Fine-Tuning de Modelos Fundacionales a Escala Táctica

El entrenamiento de modelos convolucionales espaciales desde cero requiere miles de eventos catalogados. Para viabilizar este sistema en el ámbito operativo español, se propone una estrategia de **Transfer Learning** partiendo de modelos de teledetección global a escala satelital y adaptándolos a la escala métrica de los medios aéreos locales:

### 3.1 Modelo de Partida (Base Fundacional)
Se seleccionará como base la arquitectura **CanadaFireSat** (desarrollada por el laboratorio ECEO de la EPFL) o **ASUFM (Attention Swin U-net)**. Estas redes ya han aprendido las interacciones físicas generales entre topografía (pendientes, orientaciones de laderas), índices de sequedad de vegetación (NDVI) y avance espacial del fuego a partir de series temporales de satélites como Sentinel-2 y MODIS.

### 3.2 Proceso de Adaptación y Fine-Tuning
1.  **Congelación de Capas Iniciales (Feature Extractor):** Se congelan los pesos de las primeras capas convolucionales del encoder, las cuales se encargan de la detección de bordes, texturas de relieve y gradientes térmicos generales.
2.  **Ajuste Fino de la Cabeza Temporal (ConvLSTM y Decoder):** Se reentrenan las capas de la serie temporal y el decoder de upsampling utilizando la secuencia de **imágenes de infrarrojo térmico (IR) de Heligrafics** georreferenciadas. Esto permite:
    *   Pasar de una resolución espacial tosca de $100\text{ m}$ (satélite) a una **resolución táctica de $5\text{ m} - 10\text{ m}$**.
    *   Adaptar la inercia temporal del modelo a intervalos de actualización tácticos (fotogramas aéreos capturados cada $5 - 15\text{ minutos}$ en lugar de diarios).
    *   Calibrar la respuesta frente a vegetación y modelos de combustible locales (por ejemplo, el catálogo español de combustibles forestales comparado con el canadiense).

---

## 4. Fase II: Capa de Seguridad mediante Meta-Labeling

El mayor riesgo de la IA en la toma de decisiones críticas es el falso negativo (el modelo no predice que una zona arderá, pero esta se quema, poniendo en riesgo vidas humanas). El **Meta-Labeling** soluciona esto introduciendo una segunda opinión matemática basada en la fiabilidad.

### 4.1 Definición y Objetivos del Meta-Labeler
El modelo primario emite una predicción binaria sobre cada celda de terreno $C_{i,j}$ para el instante $t + \Delta t$:
*   $Y^*_{i,j} = 1$ (Arderá)
*   $Y^*_{i,j} = 0$ (No arderá)

El **Meta-modelo** realiza una clasificación binaria paralela para predecir si la salida del modelo primario es **correcta o incorrecta**:
*   $M_{i,j} = 1$ (La predicción $Y^*_{i,j}$ es de **confianza**; se puede mostrar al analista).
*   $M_{i,j} = 0$ (La predicción $Y^*_{i,j}$ es **inestable o de alto riesgo**; el sistema debe abstenerse localmente).

### 4.2 Insumos de Entrada del Meta-Modelo (Features de Confianza)
Para garantizar la viabilidad del meta-modelo bajo escasez de datos en tiempo real, este no requiere variables de campo externas, sino que se alimenta de **variables implícitas y de calidad métrica**:

1.  **Entropía de la Predicción Primaria:** Medida de incertidumbre del modelo base. Si la probabilidad de salida de la sigmoide de la U-Net está en la zona gris (por ejemplo, entre $0.45$ y $0.55$), la entropía es alta, lo que indica falta de certeza física.
2.  **Error Espacial Acumulado Reciente:** Discrepancia métrica (distancia de Hausdorff y valor del IoU) medida entre las predicciones de los últimos tres pasos de tiempo y las correspondientes observaciones reales de Heligrafics.
3.  **Complejidad Topográfica Local:** Gradiente de pendiente del terreno (DEM) y rugosidad local en un buffer de $50\text{ m}$ alrededor de la celda predicha.
4.  **Métricas del Sensor de la Aeronave:** Desviación e incertidumbre declarada del posicionamiento láser y la ortorrectificación de Heligrafics.
5.  **Exclusión por Viento Extremo:** Diferencia angular entre el viento previsto por los modelos meteorológicos regionales y la dirección del avance geométrico predicho por el modelo base.

### 4.3 Reducción de la Responsabilidad Civil y Operativa
Si el Meta-Labeler determina que la predicción tiene una probabilidad de acierto inferior al $85\%$ (configurable según el protocolo de protección civil), la interfaz de usuario **oculta el vector de predicción** en ese flanco y muestra una etiqueta de **"Abstención por baja observabilidad"**. Esto asegura que las brigadas forestales solo tomen decisiones basadas en telemetría predictiva certificada.

---

## 5. Inventario de Datos y Datasets para Entrenamiento y Validación

Para asegurar el éxito del entrenamiento y la posterior auditoría del sistema, se estructurará un dataset multi-fuente dividido en tres niveles:

| Nivel de Datos | Origen | Variables Incluidas | Propósito en el Pipeline |
|---|---|---|---|
| **Datos de Preentrenamiento** | CanadaFireSat / Mesogeos | Sentinel-2, ERA5, NDVI, DEM Global, FWI | Configuración inicial de pesos de la red convolucional (U-Net). |
| **Datos de Fine-Tuning** | FLAME 3 / Históricos de Quemas | Infrarrojo térmico aéreo, secuencias temporales, metadatos de vuelo | Ajuste fino de la dinámica espacial y temporal a alta resolución ($5\text{ m} - 10\text{ m}$). |
| **Datos de Validación y Auditoría (SLA)** | Secuencia Heligrafics (CMA) | Imágenes térmicas locales georreferenciadas, KMZ de operadores | Ajuste local del Meta-modelo, cálculo del IoU y Hausdorff predictivo para la certificación pública. |

---

## 6. Integración en los Sistemas de Emergencias (Despliegue y Dashboard)

El sistema final entregará dos productos clave para su adopción por los técnicos de operaciones de extinción:

1.  **Dashboard Táctico Interactivo (`report.html`):**
    *   **Isocronas Predictivas:** Líneas de tiempo que muestran la probabilidad acumulada de que el fuego alcance zonas críticas en los próximos 15, 30 y 60 minutos.
    *   **Indicador de Confiabilidad Espacial:** Las áreas del frente predictivo aprobadas por el Meta-Labeler se muestran en color sólido; las zonas de abstención se sombrean en gris advirtiendo al operador de la necesidad de un nuevo vuelo de reconocimiento o de no confiar en la inferencia automática.
2.  **API de Exportación GIS Estándar:**
    *   Salidas exportadas en formato **GeoPackage (.gpkg)** para su inserción automática en los sistemas cartográficos de despacho de emergencias. A diferencia de las exportaciones no conformes de GeoJSON, GeoPackage preservará el sistema de proyección métrico local (como UTM ETRS89 en España).

---

## 7. Conclusión de la Propuesta
Esta arquitectura tecnológica combina el poder del Deep Learning espaciotemporal para automatizar y acelerar el análisis de incendios, con el rigor y la prudencia de un modelo secundario de seguridad (Meta-Labeling). Su implantación representa una alternativa viable, defendible operacionalmente y segura, mitigando el riesgo de decisiones basadas en predicciones automáticas inestables.
