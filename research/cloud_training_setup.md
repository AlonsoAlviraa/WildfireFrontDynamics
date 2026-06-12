# Guía de Configuración: Entrenamiento en la Nube (Kaggle y Google Colab)

Esta guía detalla los pasos para ejecutar el entrenamiento y ajuste fino del modelo A3C-LSTM en la nube utilizando hardware gratuito (GPUs NVIDIA T4 / P100) en **Kaggle Notebooks** o **Google Colab**, con subida directa del checkpoint resultante a **Hugging Face Hub**.

---

## Opción A: Ejecución en Kaggle (Recomendado)

Kaggle aloja directamente el dataset de Google `Next Day Wildfire Spread` en su catálogo de datasets. Esto elimina la necesidad de descargar datos.

### Paso 1: Crear un Notebook en Kaggle
1. Ve a [Kaggle](https://www.kaggle.com/) e inicia sesión.
2. Haz clic en **Create** -> **New Notebook**.
3. En la barra lateral derecha (Settings), activa el **Accelerator** seleccionando **GPU T4 x2** o **GPU P100**.
4. Activa la opción de **Internet on** (requiere verificación de número telefónico en Kaggle) para poder descargar librerías e interactuar con Hugging Face.

### Paso 2: Importar Datasets
*   En la esquina superior derecha, haz clic en **+ Add Input**.
*   Busca `next-day-wildfire-spread` y agrégalo. El dataset se montará automáticamente en la ruta `/kaggle/input/next-day-wildfire-spread`.

### Paso 3: Código de Inicialización y Entrenamiento
Pega y ejecuta las siguientes celdas de código en tu notebook de Kaggle:

```python
# 1. Instalar dependencias requeridas
!pip install -q rasterio huggingface_hub torch

# 2. Clonar el repositorio del proyecto
!git clone https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git
%cd WildfireFrontDynamics

# 3. Configurar PYTHONPATH para que reconozca los módulos del proyecto
import sys
sys.path.append(".")

# 4. Lanzar el script de entrenamiento en la nube
# Reemplaza 'TU_TOKEN_HF' y 'TU_USER/TU_REPO' con tus credenciales reales
!python -m wildfire_front.ml.cloud_train \
    --images /kaggle/input/next-day-wildfire-spread/images \
    --masks /kaggle/input/next-day-wildfire-spread/masks \
    --weights models/v3.pt \
    --output-weights outputs/fine_tuned_weights.pt \
    --epochs 15 \
    --lr 1e-4 \
    --hf-token "TU_TOKEN_HF" \
    --hf-repo "TU_USER/TU_REPO"
```

---

## Opción B: Ejecución en Google Colab

Ideal para entrenamientos rápidos y experimentación.

### Paso 1: Configurar el Entorno en Colab
1. Ve a [Google Colab](https://colab.research.google.com/).
2. Crea un nuevo bloc de notas.
3. Ve a **Entorno de ejecución** -> **Cambiar tipo de entorno de ejecución** y selecciona **T4 GPU** (o un acelerador de pago si dispones de saldo).

### Paso 2: Clonar y Ejecutar
Pega y ejecuta el siguiente código:

```python
# 1. Instalar dependencias
!pip install -q rasterio huggingface_hub torch

# 2. Clonar repositorio
!git clone https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git
%cd WildfireFrontDynamics

# 3. Configurar el PYTHONPATH
import sys
sys.path.append(".")

# 4. Lanzar el entrenamiento
# Si tienes tu dataset en Google Drive, puedes montarlo usando drive.mount('/content/drive')
!python -m wildfire_front.ml.cloud_train \
    --images data/candidates/semireal_controlled_001/images \
    --masks data/candidates/semireal_controlled_001/masks \
    --weights models/v3.pt \
    --output-weights outputs/fine_tuned_weights.pt \
    --epochs 5 \
    --lr 1e-4 \
    --hf-token "TU_TOKEN_HF" \
    --hf-repo "TU_USER/TU_REPO"
```

---

## Obtener el Token de Escritura de Hugging Face
1. Inicia sesión en [Hugging Face](https://huggingface.co/).
2. Ve a **Settings** -> **Access Tokens**.
3. Haz clic en **New Token**, asígnale el nombre `wildfire-training` y dale rol de **Write**.
4. Copia el token y úsalo en el argumento `--hf-token`.
