# Arquitecturas de Machine Learning para Modelado del Frente de Incendios

La predicción del frente activo a corto plazo se formula como un problema **espacio-temporal**. A continuación se detallan las dos arquitecturas dominantes y su combinación híbrida:

---

## 1. ConvLSTM (Convolutional Long Short-Term Memory)
*   **Propósito:** Modelar la inercia temporal del avance y la propagación del frente de fuego a lo largo del tiempo.
*   **Funcionamiento:**
    *   Sustituye la multiplicación de matrices de una LSTM tradicional por operaciones de **convolución espacial**.
    *   Permite que las celdas de memoria de la red almacenen información tanto del estado temporal (cuánto lleva ardiendo una zona) como de la estructura espacial del frente (forma del perímetro y dirección de avance).
*   **Ecuación Conceptual de Entrada/Salida:**
    $$X_{(t-N, \dots, t)} \xrightarrow{\text{ConvLSTM}} Y_{(t + \Delta t)}$$
    Donde la entrada es la secuencia histórica de los últimos frentes y la salida es el mapa de calor predictivo.

---

## 2. U-Net (Codificador-Decodificador Espacial)
*   **Propósito:** Delimitar con alta precisión la frontera espacial del frente de llama y procesar características de alta resolución del terreno (DEM, vegetación).
*   **Funcionamiento:**
    *   Su estructura en forma de "U" extrae características contextuales en el cuello de botella (encoder) y luego las proyecta de vuelta a la resolución original del mapa (decoder).
    *   Las **conexiones de salto (skip connections)** transfieren directamente detalles geométricos finos desde los niveles iniciales de convolución al decoder, evitando la pérdida de definición del borde del fuego.
*   **Variables de Canal de Entrada:**
    *   Canal 0: Estado del frente actual (máscara binaria o SDF - campo de distancia con signo).
    *   Canal 1: Pendiente del terreno.
    *   Canal 2: Orientación de laderas.
    *   Canal 3: Tipo de vegetación (mapa codificado).
    *   Canal 4: Dirección del viento proyectada sobre la topografía.

---

## 3. Arquitectura Híbrida: U-Net + ConvLSTM
El estándar de la industria para predicciones de alta calidad integra ambas redes en un único pipeline:

```
                      [Secuencia Temporal de Mapas (t-N ... t)]
                                         │
                                         ▼
                            ┌─────────────────────────┐
                            │    Encoder de U-Net     │ (Extracción de features espaciales)
                            └────────────┬────────────┘
                                         ▼
                            ┌─────────────────────────┐
                            │    Células ConvLSTM     │ (Aprendizaje de la dinámica temporal)
                            └────────────┬────────────┘
                                         ▼
                            ┌─────────────────────────┐
                            │    Decoder de U-Net     │ (Reconstrucción del mapa predictivo)
                            └────────────┬────────────┘
                                         ▼
                             [Predicción a t + 30 min]
```

### Ventajas del Enfoque Híbrido:
1.  **Física Implícita:** La red aprende de forma empírica cómo la pendiente local y la dirección del viento aceleran o frenan el frente (aproximación a las leyes físicas sin resolver ecuaciones diferenciales en tiempo real).
2.  **Resolución Fina:** La U-Net mantiene la precisión geométrica del borde, evitando que la predicción temporal difumine el frente de llama.
