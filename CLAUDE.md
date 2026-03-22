# sonAlert — Guía para Claude

## Estructura del proyecto

Este proyecto sigue estrictamente la estructura de **Cookiecutter Data Science (CCDS v2)**.
Siempre que agregues, muevas o modifiques archivos, respeta la siguiente organización:

```
sonAlert/
├── data/
│   ├── raw/          ← Datos originales, nunca se modifican
│   ├── interim/      ← Transformaciones intermedias
│   ├── processed/    ← Datos listos para modelado
│   └── external/     ← Datos de fuentes externas
│
├── models/           ← Modelos entrenados serializados (.pkl, .joblib, etc.)
├── notebooks/        ← Jupyter notebooks de exploración (nombrar: ##_descripcion.ipynb)
├── references/       ← Diccionarios de datos, manuales, documentación externa
├── reports/
│   └── figures/      ← Gráficas y visualizaciones generadas
│
├── docs/             ← Documentación del proyecto (MkDocs)
│
└── sonalert/         ← Paquete Python del proyecto
    ├── config.py     ← Paths centralizados y configuración
    ├── dataset.py    ← Carga y generación de datasets
    ├── features.py   ← Ingeniería de características
    ├── plots.py      ← Funciones de visualización
    └── modeling/
        ├── train.py  ← Entrenamiento de modelos
        └── predict.py← Predicciones / inferencia
```

### Reglas de estructura

- **Código reutilizable** va en `sonalert/` (el paquete Python), no en notebooks.
- **Notebooks** son solo para exploración y comunicación de resultados; la lógica final se extrae al paquete.
- **Datos raw nunca se modifican**; cualquier transformación produce archivos en `interim/` o `processed/`.
- **Modelos entrenados** se guardan en `models/`, nunca en `notebooks/` ni en el paquete.
- **Figuras generadas** van en `reports/figures/`, no sueltas en la raíz.
- Nunca crear carpetas o módulos fuera de esta estructura sin justificación explícita del usuario.
