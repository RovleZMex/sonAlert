# MLOps setup — DagsHub + MLflow + DVC

Esta guia describe el *stack* de MLOps que usamos en `sonAlert` y los pasos exactos que cada integrante del equipo debe correr **una sola vez** para poder versionar datos, registrar experimentos y reproducir resultados.

## Stack

| Componente | Para que sirve | Donde vive |
|------------|----------------|------------|
| **DagsHub** | *Hosting* unificado del repo Git + *remote* DVC + servidor MLflow | `https://dagshub.com/<owner>/sonAlert` |
| **DVC** | Versionado de los `.parquet` de `data/` (los archivos NO se commitean a Git; solo punteros `.dvc`) | Local + DagsHub Storage |
| **MLflow** | Registro de experimentos: parametros, metricas, *artifacts*, modelos | Servidor MLflow embebido en DagsHub |

## Pre-requisitos

1. Tener cuenta en [DagsHub](https://dagshub.com) (gratis).
2. Pedirle a **Santiago** que te invite como colaborador al repo `sonAlert` en DagsHub.
3. Tener Python 3.10+ instalado.

> Si todavia no existe la carpeta `.venv/` en el proyecto, crearla antes de instalar dependencias:
>
> ```bash
> python -m venv .venv
> source .venv/bin/activate   # o .venv/Scripts/activate en Windows
> ```

## Bootstrap inicial — SOLO una vez para el proyecto

> :warning: Estos pasos los corre **Santiago** una sola vez. Los demas integrantes saltan a *Paso 1*.

```bash
# 1. Crear venv + instalar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 2. Generar los parquets locales (si no existen ya)
make pipeline

# 3. Inicializar DVC en el repo
dvc init
git add .dvc/.gitignore .dvc/config .dvcignore
git commit -m "mlops: inicializa DVC"

# 4. Crear repo espejo en DagsHub: https://dagshub.com/repo/create
#    Conectar el remote de Git:
git remote add dagshub https://dagshub.com/<owner>/sonAlert.git
git push dagshub main

# 5. Configurar DVC remote contra DagsHub Storage (ver Paso 4 mas abajo)
dvc remote add -d origin https://dagshub.com/<owner>/sonAlert.dvc
dvc remote modify origin --local auth basic
dvc remote modify origin --local user <usuario-dagshub>
dvc remote modify origin --local password <token-dagshub>

# 6. Versionar los parquets generados
dvc add data/raw data/interim data/processed
git add data/raw.dvc data/interim.dvc data/processed.dvc .gitignore
git commit -m "mlops: versiona datasets con DVC"
git push dagshub main
dvc push

# 7. Compartir token con el equipo (por privado) e invitarlos al repo en DagsHub
```

Listo. Despues de esto cualquier integrante puede `git pull && dvc pull` y tener el proyecto reproducible.

## Paso 1 — Instalar dependencias

```bash
.venv/bin/pip install -r requirements.txt
```

Esto instala `dagshub`, `mlflow`, `dvc[s3]`, `optuna`, `xgboost`, `lightgbm`, `shap`, ademas de todo lo previo.

## Paso 2 — Generar token de DagsHub

1. Ir a [DagsHub → Settings → Tokens](https://dagshub.com/user/settings/tokens).
2. Crear un token con permisos `read`/`write`.
3. Copiarlo (solo se muestra una vez).

## Paso 3 — Variables de entorno

Crear o editar el archivo `.env` en la raiz del repo (esta en `.gitignore`, no se sube):

```bash
# .env
DAGSHUB_USER_TOKEN=<tu-token>
MLFLOW_TRACKING_URI=https://dagshub.com/<owner>/sonAlert.mlflow
MLFLOW_TRACKING_USERNAME=<tu-usuario-dagshub>
MLFLOW_TRACKING_PASSWORD=<tu-token>
```

> El `MLFLOW_TRACKING_PASSWORD` es el mismo token de DagsHub. MLflow usa *basic auth*.

`sonalert/config.py` ya hace `load_dotenv()`, asi que cualquier *script* o *notebook* que importe del paquete tendra estas variables disponibles.

## Paso 4 — Clonar el remote DVC

Una sola vez tras clonar el repo:

```bash
# Configurar el remote (apunta al storage DVC de DagsHub)
.venv/bin/dvc remote add origin https://dagshub.com/<owner>/sonAlert.dvc
.venv/bin/dvc remote default origin
.venv/bin/dvc remote modify origin --local auth basic
.venv/bin/dvc remote modify origin --local user <tu-usuario-dagshub>
.venv/bin/dvc remote modify origin --local password <tu-token>

# Bajar los datos versionados (raw + processed)
.venv/bin/dvc pull
```

Despues de `dvc pull` deberias tener llenas las carpetas `data/raw/`, `data/interim/` y `data/processed/`. Si alguna esta vacia, avisa en el grupo — significa que el `dvc push` original no incluyo ese subdirectorio.

## Paso 5 — Validar el setup

Correr este *snippet* en una celda de Jupyter o en un REPL:

```python
import os
import mlflow
from dotenv import load_dotenv

load_dotenv()
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment("sanity_check")

with mlflow.start_run(run_name="hola_mundo"):
    mlflow.log_param("test", "ok")
    mlflow.log_metric("dummy", 1.0)

print("MLflow OK. Ve a https://dagshub.com/<owner>/sonAlert/experiments/")
```

Si ves el *run* en la pestaña *Experiments* de DagsHub, esta todo listo.

## Flujo de trabajo dia a dia

### Al empezar a trabajar

```bash
git pull
.venv/bin/dvc pull          # baja datos nuevos si alguien actualizo
```

### Al terminar de trabajar

```bash
# Si modificaste o regeneraste algun parquet en data/
.venv/bin/dvc add data/processed/panel_features.parquet
git add data/processed/panel_features.parquet.dvc
git commit -m "data: <descripcion del cambio>"

git push
.venv/bin/dvc push          # sube los datos al storage de DagsHub
```

### Al registrar un experimento desde un notebook

```python
import os, mlflow
from dotenv import load_dotenv

load_dotenv()
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment("baseline_logistic")   # o el que corresponda

with mlflow.start_run(run_name="lr_C1_l2_balanced"):
    mlflow.log_params({"C": 1.0, "penalty": "l2", "class_weight": "balanced"})
    # ... entrenar ...
    mlflow.log_metrics({"recall_critico": 0.78, "f1_macro": 0.61})
    mlflow.sklearn.log_model(model, "model")
```

## Convenciones

- **Un experimento por familia de modelos:** `baseline_logistic`, `svm_rf`, `gradient_boosting`. Asi la pestaña *Experiments* queda ordenada.
- **`run_name` descriptivo:** incluye los hiperparametros clave (ej. `xgb_lr0.05_depth6_estim500`).
- **Tags:** usa `mlflow.set_tag("model_family", "xgboost")` para poder filtrar despues.
- **Metricas obligatorias del proyecto:** `recall_critico`, `precision_critico`, `f1_macro`, `accuracy`. Cualquier *run* sin estas no cuenta como valido.

## Troubleshooting

| Sintoma | Causa probable | Fix |
|---------|----------------|-----|
| `mlflow` da `401 Unauthorized` | Token vencido o variables no cargadas | Regenerar token en DagsHub, actualizar `.env`, reiniciar el *kernel* |
| `dvc pull` baja 0 archivos | El *remote* no esta configurado o no tienes permisos | Re-correr Paso 4 verificando `<owner>` y permisos en DagsHub |
| `dvc push` falla con `403` | Token sin permisos de escritura | Generar token con `write` habilitado |
| MLflow no muestra los *runs* | Apuntando a *URI* local en vez de DagsHub | Confirmar `MLFLOW_TRACKING_URI` en `.env` |
