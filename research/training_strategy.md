# Estudio de Estrategia de Entrenamiento e Hiperparámetros (WFD-ML)

Para realizar un ajuste fino (fine-tuning) exitoso del modelo fundacional A3C-LSTM en la predicción del frente de incendios táctico, es crucial definir una estrategia de optimización y regularización que garantice la convergencia y evite el sobreajuste (overfitting) o el desvanecimiento de gradientes en la capa LSTM.

A continuación, se detalla la propuesta técnica de hiperparámetros y optimización:

---

## 1. Selección del Optimizador (Optimizer)

### Opción Recomendada: AdamW
*   **Por qué:** Para el ajuste fino, es preferible utilizar **AdamW** (Adam con desacoplamiento de decaimiento de peso / Weight Decay Decoupling) en lugar de Adam estándar o RMSprop.
*   **Justificación:** Adam estándar aplica la penalización de regularización L2 multiplicándola por el gradiente acumulado, lo que reduce la efectividad del decaimiento en parámetros con gradientes grandes. AdamW desacopla la regularización L2 de los gradientes, aplicando el decaimiento de peso directamente sobre los parámetros. En modelos recurrentes (LSTM) y convolucionales profundos, esto evita que los pesos crezcan desmesuradamente, estabilizando el entrenamiento y mejorando la generalización.
*   **Parámetros base:**
    *   $\beta_1 = 0.9$ (inercia de primer orden)
    *   $\beta_2 = 0.999$ (inercia de segundo orden)
    *   $\epsilon = 1\text{e-}8$ (evita divisiones por cero)
    *   $\text{Weight Decay} = 1\text{e-}4$

---

## 2. Tasa de Aprendizaje (Learning Rate) y Planificación (Scheduling)

### A. Tasa de Aprendizaje Base (LR)
*   **Valor:** $1\text{e-}4$ (para fine-tuning).
*   **Justificación:** Al realizar un ajuste fino de pesos preentrenados, una tasa alta ($1\text{e-}3$) destruiría las características espaciales ya aprendidas por el encoder convolucional. Una tasa muy baja ($1\text{e-}5$) haría que el entrenamiento fuera extremadamente lento y propenso a quedarse estancado en mínimos locales del nuevo dataset táctico.

### B. Planificador: Cosine Annealing LR Scheduler
*   **Funcionamiento:** Reduce la tasa de aprendizaje siguiendo una curva de coseno, desde el valor inicial hasta un valor mínimo (ej. $1\text{e-}6$).
*   **Ventaja:** En las fases iniciales, permite al modelo explorar rápidamente el espacio de pérdidas, mientras que en las fases finales reduce drásticamente el paso para permitir un ajuste fino de precisión quirúrgica de los pesos de la cabeza de políticas de 8 vecinos.

---

## 3. Formulación de Funciones de Pérdida (Loss Functions)

Dado que la red tiene dos cabezas de predicción (Policy Head y Value Head), optimizamos una pérdida conjunta:

### A. Pérdida de la Política (Policy Loss)
Dado que cada celda de fuego activa decide propagarse de manera independiente a sus 8 vecinas, formulamos la propagación como **8 tareas de clasificación binaria concurrentes**.
*   **Pérdida Principal:** **Binary Cross-Entropy con Logits (BCEWithLogitsLoss)**.
*   **Pérdida Avanzada (Focal Loss):** En mallas grandes, la gran mayoría de vecinos se mantienen en $0$ (no propagación), lo que crea un gran desbalance de clases. Si se observa que el modelo es perezoso (no predice avances por miedo a equivocarse), se implementará **Focal Loss** para reducir la ponderación de las muestras negativas fáciles y enfocar el gradiente en los frentes de avance reales.

### B. Pérdida del Valor (Value Loss)
*   **Métrica:** **Mean Squared Error (MSE)** entre el valor predicho por la cabeza de valor ($V^\pi(s)$) y el retorno real descontado del episodio de propagación.

---

## 4. Regularización y Estabilización

*   **Gradient Clipping (Recorte de Gradientes):** Forzar `max_norm = 0.5` en los gradientes antes de cada paso del optimizador. Esto es **obligatorio** para evitar el problema de "gradientes explosivos" típico de los LSTMs cuando procesan secuencias espaciales consecutivas muy largas.
*   **Dropout:** Mantener los niveles de dropout actuales ($0.1$ en convoluciones, $0.2$ en capas lineales) para forzar la redundancia de características y evitar que el modelo dependa de píxeles individuales ruidosos.

---

## 5. Estrategia de Validación: Leave-One-Event-Out (LOEO)

Para certificar el rendimiento empresarial, **nunca** se debe validar dividiendo las imágenes de un mismo incendio al azar (fuga de datos temporal).
*   **Estrategia:** Si disponemos de 5 incendios históricos de Heligrafics, entrenamos con 4 y validamos con el restante. Repetimos el proceso rotando el incendio excluido. Esto garantiza que la métrica de IoU predictivo represente la capacidad del modelo de generalizar ante un **incendio completamente nuevo**.
