# Opiniones de Expertos y Consenso Científico en Modelado de Incendios con ML

El modelado y predicción de incendios forestales mediante aprendizaje automático ha sido objeto de intensos debates científicos en la última década. A continuación se resume el estado del arte y el consenso de los expertos del sector:

---

## 1. El Dilema: Modelos Físicos vs. Modelos de Machine Learning

### Modelos Físicos (Semi-empíricos): FARSITE, WRF-SFIRE, Prometheus
*   **Consenso de los expertos:** Son herramientas robustas y científicamente entendibles, pero presentan graves deficiencias en situaciones de emergencia.
*   **El Problema:** La "basura de entrada". Requieren mapas de humedad de combustible por hora, modelos de viento microscópicos e inventarios de vegetación en tiempo real. Al no disponer de estos datos exactos en mitad de una emergencia, las simulaciones físicas se desvían de la realidad a los pocos minutos de iniciarse.

### Modelos de Machine Learning (Puros): ConvLSTM, U-Net
*   **Consenso de los expertos:** Son capaces de aprender patrones no lineales muy complejos directamente de las observaciones satelitales o aéreas (ej. cómo influyen microclimas inducidos por el propio fuego).
*   **El Problema:** Falta de restricciones físicas (efecto "caja negra"). Una red neuronal pura puede predecir que el fuego "salta" zonas sin combustible o avanza en dirección opuesta a la pendiente sin justificación, violando leyes de la termodinámica.

---

## 2. La Tendencia Científica: Modelos Híbridos y PINN (Physics-Informed Neural Networks)
El consenso actual de los investigadores (incluyendo laboratorios como Google Research, Stanford y centros forestales europeos) apunta a que **la solución real pasa por la hibridación**:

1.  **Asimilación Continua de Datos (Data Assimilation):** En lugar de simular a ciegas, el modelo predictivo de ML debe reiniciarse y re-calibrarse constantemente cada vez que recibe un dato observado real (como el infrarrojo de Heligrafics). La predicción no es a largo plazo, sino un "tactical forecast" (pronóstico táctico) a 30-60 minutos de horizonte.
2.  **Redes Neuronales Informadas por la Física (PINN):** Se penaliza a la función de pérdida (loss function) de la red neuronal si esta viola leyes físicas básicas de la propagación del fuego (por ejemplo, avanzar más rápido hacia abajo en una pendiente pronunciada que hacia arriba, a menos que el viento sea extremo).
3.  **Abstención Científica:** Los expertos insisten en que un modelo en producción debe negarse a emitir un veredicto (abstención) si la incertidumbre de la observación es mayor que el avance físico real esperado.

---

## 3. Conclusión Operativa para el Producto Comercial
Para que un software de predicción de incendios con ML sea aceptado por agencias forestales y de protección civil, debe demostrar:
*   **Trazabilidad del error:** El sistema debe auditar su propio error comparando predicciones pasadas con observaciones reales vectorizadas (como los KMZ de Heligrafics).
*   **Explicabilidad:** El usuario debe saber por qué el modelo estima una dirección de avance concreta (ej. correlacionándola con mapas de pendiente del terreno o ráfagas de viento registradas).
*   **Garantía de Seguridad:** Priorizar la prevención de falsos negativos (zonas que el modelo dice que no van a arder y terminan ardiendo, atrapando a las brigadas en terreno).
