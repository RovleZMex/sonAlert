# Referencias y diccionarios de datos

Esta carpeta contiene los **diccionarios de datos** de los datasets crudos que alimentan el *pipeline* y los del dataset procesado final, junto con los enlaces a las fuentes originales y el contexto institucional del proyecto.

## Equipo

Proyecto desarrollado para la materia **Aprendizaje Automático Aplicado** de la **Universidad de Sonora**, impartida por **Dr. Julio Waissman**.

| Integrante |
|------------|
| Santiago Robles |
| José Cazares |
| Luis Ochoa |

**Subject-matter expert consultada:** Diana Ballesteros (Gobierno del Estado de Sonora).

## Fuentes de datos

Todos los *datasets* provienen del portal **[datos.sonora.gob.mx](https://datos.sonora.gob.mx)** y están publicados bajo licencia **Creative Commons Attribution [Open Data]**.

| Dataset | Estado en el proyecto | URL |
|---------|----------------------|-----|
| Incidencia delictiva municipal | Integrado | [Incidencia delictiva municipal](https://datos.sonora.gob.mx/dataset/Incidencia%20delictiva%20municipal) |
| Incidencia delictiva municipal — metodología anterior | Integrado (años previos) | [Incidencia delictiva municipal - metodología anterior](https://datos.sonora.gob.mx/dataset/Incidencia%20delictiva%20municipal%20-%20metodolog%C3%ADa%20anterior) |
| Índice de marginación por municipio (CONAPO) | Integrado | [Índice de marginación por municipio](https://datos.sonora.gob.mx/dataset/%C3%8Dndice%20de%20marginaci%C3%B3n%20por%20municipio) |
| Proyecciones de población — Indicadores demográficos | Integrado | [Proyecciones de población](https://datos.sonora.gob.mx/dataset/Proyecciones%20de%20poblaci%C3%B3n%20-%20Indicadores%20demogr%C3%A1ficos) |
| Zonas Salva | Integrado (estático) | [Zonas Salva](https://datos.sonora.gob.mx/dataset/Zonas%20Salva) |
| Índice de marginación urbana por colonia | Fuera de scope | [Índice de marginación urbana por colonia](https://datos.sonora.gob.mx/dataset/Indice%20de%20marginaci%C3%B3n%20urbana%20por%20colonia) |
| Víctimas del fuero común en el estado | Descartado | [Víctimas del fuero común](https://datos.sonora.gob.mx/dataset/V%C3%ADctimas%20del%20fuero%20com%C3%BAn%20en%20el%20estado) |
| Víctimas del fuero común — metodología anterior | Descartado | [Víctimas del fuero común - metodología anterior](https://datos.sonora.gob.mx/dataset/V%C3%ADctimas%20del%20fuero%20com%C3%BAn%20en%20el%20estado%20-%20metodolog%C3%ADa%20anterior) |
| Comités Ciudadanos | Descartado | [Comités Ciudadanos](https://datos.sonora.gob.mx/dataset/Comit%C3%A9s%20Ciudadanos) |

> **Nota:** El portal no expone fechas de última actualización por *dataset*. Los snapshots usados en este proyecto fueron descargados manualmente en febrero de 2026.

## Diccionarios de datos

### Datos crudos

Cada subcarpeta contiene un `Diccionario` (xlsx o csv) y, cuando aplica, un `Catalogo` con las claves y descripciones del dataset original tal como lo publica el portal.

| Carpeta | Archivos |
|---------|----------|
| [`incidencia_delictiva/`](./incidencia_delictiva/) | `Diccionario.xlsx`, `Catalogo.xlsx` |
| [`marginacion_municipal/`](./marginacion_municipal/) | `Diccionario.xlsx`, `Catalogo.xlsx` |
| [`marginacion_urbana_colonia/`](./marginacion_urbana_colonia/) | `Diccionario.xlsx`, `Catalogo.xlsx` |
| [`proyecciones_poblacion/`](./proyecciones_poblacion/) | `Diccionario.xlsx`, `Catalogo.xlsx` |
| [`victimas_fuero_comun/`](./victimas_fuero_comun/) | `Diccionario.xlsx`, `Catalogo.xlsx` |
| [`zonas_salva/`](./zonas_salva/) | `Diccionario.csv` |
| [`comites_ciudadanos/`](./comites_ciudadanos/) | `Diccionario.csv` |

### Datos procesados

[`datos_procesados/Diccionario.csv`](./datos_procesados/Diccionario.csv) — diccionario de las 155 columnas del dataset final `data/processed/panel_features.parquet`. Contiene los campos:

- `variable` — nombre de la columna
- `tipo_dato` — dtype de pandas
- `grupo` — agrupación lógica (identificador, conteo crudo, marginación, demografía, tasas per cápita, *lags*, *rolling*, *yoy*, etc.)
- `descripcion` — descripción legible
- `fuente` — origen del dato (CSV o cálculo derivado)

## Contexto del problema

### Ranking 2025 de ciudades más violentas

El proyecto se motiva en el ranking 2025 elaborado en conjunto por el **CCSPJP (Consejo Ciudadano para la Seguridad Pública y Justicia Penal A.C.)**, la **Comisión Mexicana de Derechos Humanos (CMDH)** y **Misión Rescate México**. En esa edición:

- **Ciudad Obregón (Cajeme)** ocupa el **lugar #9** mundial.
- **Hermosillo** ocupa el **lugar #46** mundial.

> Cobertura del ranking: [Infobae — México lidera ranking de ciudades más violentas en 2025 con 17 urbes en la lista (12-feb-2026)](https://www.infobae.com/mexico/2026/02/12/mexico-lidera-ranking-de-ciudades-mas-violentas-en-2025-con-17-urbes-en-la-lista/).

### Programa Zonas Salva

Programa estatal del Gobierno de Sonora que despliega puntos de infraestructura de seguridad (escuelas, dependencias de gobierno, espacios públicos) marcados como zonas con vigilancia reforzada. En este proyecto se usa como *proxy estático* de presencia institucional por municipio.

> El programa no cuenta con un sitio oficial documentado al momento de elaborar este *README*; el dataset publicado en `datos.sonora.gob.mx` es la única referencia estructurada disponible.
