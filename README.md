# sonAlert

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Modelo predictivo de incidencia delictiva municipal para el estado de Sonora, Mexico.

Hermosillo y Ciudad Obregon (Cajeme) figuran en el ranking 2025 de las 50 ciudades mas violentas del mundo. Hermosillo registro un aumento del 60% en homicidios. Este proyecto construye un pipeline de datos y un modelo que predice la **incidencia de crimen violento por municipio y mes** usando datos historicos del portal de datos abiertos de Sonora, con el objetivo de optimizar la asignacion de recursos policiales a nivel estatal.

## Quick Start

```bash
# 1. Clonar y entrar al proyecto
git clone https://github.com/<tu-usuario>/sonAlert.git
cd sonAlert

# 2. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
pip install -e .

# 4. Descargar datos crudos desde datos.sonora.gob.mx
make download

# 5. Ejecutar pipeline completo (data → features)
make pipeline
```

Al terminar tendras `data/processed/panel_features.parquet` listo para entrenar.

## Pipeline

El pipeline tiene 2 etapas orquestadas con `make`. Los datos crudos en `data/raw/` son inmutables; los intermedios van a `data/interim/` y el output final a `data/processed/`.

```
data/raw/**  ──►  sonalert/dataset.py  ──►  data/interim/panel_base.parquet
                                                        │
                                                        ▼
                  sonalert/features.py  ──►  data/processed/panel_features.parquet
```

| Target | Comando | Output |
|--------|---------|--------|
| Panel base | `make data` | `data/interim/panel_base.parquet` |
| Feature engineering | `make features` | `data/processed/panel_features.parquet` |
| Pipeline completo | `make pipeline` | Ejecuta data + features |
| Descargar datos | `make download` | `data/raw/**` |

### Etapa 1: `dataset.py` — Ingestion y construccion del panel

1. Concatena 11 CSVs anuales de incidencia delictiva (2015-2025) con `encoding='utf-8-sig'`
2. Filtra filas con todos los meses en cero (sparsity ~85%)
3. Melt wide-to-long: columnas Enero-Diciembre → filas `(mes, conteo)`
4. Clasifica ~66 tipos de delito originales en 11 categorias agregadas
5. Pivot long-to-wide: una columna por categoria
6. Reindex completo: genera todas las combinaciones `(municipio, mes)` con `fill_value=0`
7. Excluye codigos agregados 26998 ("No especificado") y 26999 ("Total estatal")

**Output:** `panel_base.parquet` — 9,504 filas (72 municipios x 132 meses), 13 columnas.

### Etapa 2: `features.py` — Enriquecimiento y feature engineering

**Enriquecimiento estatico:**
- Marginacion municipal (CONAPO 2020) — 13 variables socioeconomicas
- Proyecciones de poblacion anual — permite calcular tasas per capita por 100k hab.
- Zonas Salva — conteo de puntos de infraestructura de seguridad por municipio
- `pop_bucket` — tamano de municipio codificado como ordinal (0=rural, 1=pequeno, 2=medio, 3=urbano)

**Feature engineering temporal (por municipio):**
- Lags: t-1, t-2, t-3, t-12 (x11 categorias = 44 features)
- Rolling means: ventanas 3, 6, 12 meses (x11 = 33 features)
- Rolling std: ventana 3 meses (x11 = 11 features)
- YoY change: `(x_t - x_{t-12}) / (x_{t-12} + 1)` (x11 = 11 features)
- Encoding ciclico: `mes_sin`, `mes_cos`
- COVID dummies: `covid_lockdown`, `covid_period`
- Target compuesto: `crimen_violento_total` = homicidio_doloso + feminicidio + robo_violento + secuestro

> **Data leakage prevention:** Todos los rolling features usan `shift(1)` antes del `.rolling()` para que la ventana nunca incluya el valor del mes actual.

**Output:** `panel_features.parquet` — 8,640 filas (72 municipios x 120 meses), 155 columnas, **0 NaN**.

## Dataset final

| Metrica | Valor |
|---------|-------|
| Filas | 8,640 (72 municipios x 120 meses) |
| Columnas | 155 (2 IDs + 153 features) |
| Periodo | Enero 2016 – Diciembre 2025 |
| NaN | 0 |
| Target | `crimen_violento_total` |
| Rango poblacion | 349 – 1,030,000 (Hermosillo) |

### Grupos de features

| Grupo | Cols | Ejemplos |
|-------|------|----------|
| Identificadores | 2 | `Cve. Municipio`, `fecha` |
| Conteos crudos | 11 | `homicidio_doloso`, `robo_violento`, `otros`, ... |
| Marginacion | 13 | `ANALF`, `IM_2020`, `GM_2020`, ... |
| Demografia | 5 | `POB_MIT_MUN`, `EDAD_MED`, `RAZ_DEP`, ... |
| Tasas per capita | 11 | `*_tasa` por cada categoria |
| Zonas Salva | 6 | `n_zonas_salva`, `n_escuelas`, `n_gobierno`, ... |
| Temporal basico | 4 | `mes`, `trimestre`, `mes_sin`, `mes_cos` |
| Lags | 44 | `*_lag1`, `*_lag2`, `*_lag3`, `*_lag12` |
| Rolling means | 33 | `*_roll3_mean`, `*_roll6_mean`, `*_roll12_mean` |
| Rolling std | 11 | `*_roll3_std` |
| YoY change | 11 | `*_yoy_change` |
| COVID + target | 3 | `covid_lockdown`, `covid_period`, `crimen_violento_total` |
| Pop bucket | 1 | `pop_bucket` (ordinal int 0-3) |

### Split temporal recomendado

Para series temporales el split debe ser **cronologico, nunca aleatorio**:

| Set | Periodo | Filas | % |
|-----|---------|-------|---|
| Train | 2016-2023 | 5,760 | 67% |
| Validation | 2024 | 864 | 10% |
| Test | 2025 | 864 | 10% |

El campo `fecha` se mantiene en el parquet para implementar el split downstream.

## Taxonomia de delitos

Los ~66 tipos de delito originales se agregan en 11 categorias:

| Categoria | Incluye | Violencia |
|-----------|---------|-----------|
| `homicidio_doloso` | Homicidio doloso (arma de fuego, arma blanca, otros) | Alta |
| `homicidio_culposo` | Homicidio culposo (todas las modalidades) | Alta |
| `feminicidio` | Feminicidio (todas las modalidades) | Alta |
| `lesiones` | Lesiones dolosas + culposas | Media |
| `robo_violento` | Robo con violencia (vehiculo, transeunte, negocio, casa, transportista) | Alta |
| `robo_sin_violencia` | Robo sin violencia, hurto | Baja |
| `violacion_sexual` | Violacion simple + equiparada | Alta |
| `secuestro` | Secuestro extorsivo, express, otros | Alta |
| `extorsion` | Extorsion (todas las modalidades) | Media |
| `violencia_familiar` | Violencia familiar | Media |
| `otros` | Resto (~55%): narcomenudeo, dano a propiedad, amenazas, fraude, etc. | Baja |

## Fuentes de datos

Todos los datos provienen de [datos.sonora.gob.mx](https://datos.sonora.gob.mx):

| Dataset | Estado | Granularidad | Periodo |
|---------|--------|-------------|---------|
| Incidencia delictiva (11 CSVs) | Integrado | Municipal x Mensual | 2015-2025 |
| Marginacion municipal (CONAPO) | Integrado | Municipal (snapshot) | 2020 |
| Proyecciones de poblacion (CONAPO) | Integrado | Municipal x Anual | 1990-2040 |
| Zonas Salva | Integrado (estatico) | Punto GPS → Municipal | Ene-Feb 2026 |
| Victimas fuero comun | Descartado | Ruptura estructural 2016+ | — |
| Comites ciudadanos | Descartado | n=18, 4 municipios | — |
| Marginacion por colonia | Fuera de scope | Intra-municipal | — |

## Limitaciones conocidas

- **Victimas sin desagregacion municipal (2016+):** ruptura estructural impide analisis demografico a nivel municipal
- **Variables faltantes de alto impacto:** clima, desempleo mensual, precio del dolar, calendario electoral, operativos policiales
- **Marginacion congelada en 2020:** snapshot unico replicado como constante temporal
- **Zonas Salva como proxy estatico:** solo 2 meses de datos, no captura evolucion temporal
- **Distribucion zero-inflated:** mediana 0 para la mayoria de categorias; puede requerir modelos especializados (zero-inflated Poisson, hurdle models)
- **Concentracion urbana extrema:** Hermosillo y Cajeme concentran la gran mayoria de incidentes

## Estructura del proyecto

```
├── Makefile                <- Pipeline: make data / make features / make pipeline
├── README.md
├── data
│   ├── interim             <- panel_base.parquet (checkpoint intermedio)
│   ├── processed           <- panel_features.parquet (dataset final, training-ready)
│   └── raw                 <- Datos inmutables de datos.sonora.gob.mx
│       ├── incidencia_delictiva/   <- 11 CSVs (2015-2025)
│       ├── marginacion_municipal/  <- CONAPO 2020
│       ├── proyecciones_poblacion/ <- CONAPO 1990-2040
│       ├── zonas_salva/            <- Ene-Feb 2026
│       └── ...
│
├── notebooks               <- EDA y analisis exploratorio
├── references              <- Diccionarios y catalogos de datos
├── reports                 <- Reportes generados (HTML, figuras)
├── requirements.txt        <- Dependencias del proyecto
│
└── sonalert                <- Codigo fuente
    ├── config.py           <- Variables de configuracion y rutas
    ├── dataset.py          <- Etapa 1: ingestion y panel base
    ├── features.py         <- Etapa 2: enriquecimiento y feature engineering
    └── modeling/
        ├── train.py        <- (placeholder) Entrenamiento de modelo
        └── predict.py      <- (placeholder) Inferencia
```

--------
