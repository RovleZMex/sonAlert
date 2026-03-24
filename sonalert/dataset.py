from pathlib import Path

import pandas as pd
import typer
from loguru import logger

from sonalert.config import INTERIM_DATA_DIR, RAW_DATA_DIR

app = typer.Typer()

MONTH_COLS = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
MES_MAP = {m: i + 1 for i, m in enumerate(MONTH_COLS)}

# Mapeo de Tipo de delito → categoría agregada para el modelo
TIPO_TO_CATEGORIA = {
    "Homicidio": None,  # se resuelve por subtipo
    "Feminicidio": "feminicidio",
    "Lesiones": "lesiones",
    "Robo": None,  # se resuelve por modalidad
    "Secuestro": "secuestro",
    "Extorsión": "extorsion",
    "Violencia familiar": "violencia_familiar",
    "Violación simple": "violacion_sexual",
    "Violación equiparada": "violacion_sexual",
}

SUBTIPO_HOMICIDIO = {
    "Homicidio doloso": "homicidio_doloso",
    "Homicidio culposo": "homicidio_culposo",
}

CATEGORIA_COLS = [
    "homicidio_doloso",
    "homicidio_culposo",
    "feminicidio",
    "lesiones",
    "robo_violento",
    "robo_sin_violencia",
    "violacion_sexual",
    "secuestro",
    "extorsion",
    "violencia_familiar",
    "otros",
]


def _classify_crime(row: pd.Series) -> str:
    """Clasifica una fila de incidencia en una categoría agregada."""
    tipo = row["Tipo de delito"]
    subtipo = row["Subtipo de delito"]
    modalidad = row["Modalidad"]

    # Homicidio: resolver por subtipo
    if tipo == "Homicidio":
        return SUBTIPO_HOMICIDIO.get(subtipo, "otros")

    # Robo: resolver por presencia de "Con violencia" / "Sin violencia" en modalidad
    if tipo == "Robo":
        if isinstance(modalidad, str) and "Con violencia" in modalidad:
            return "robo_violento"
        return "robo_sin_violencia"

    # Tipos con mapeo directo
    cat = TIPO_TO_CATEGORIA.get(tipo)
    if cat is not None:
        return cat

    return "otros"


def load_incidencia(raw_dir: Path = RAW_DATA_DIR, years: range = range(2015, 2026)) -> pd.DataFrame:
    """Carga y concatena los CSVs de incidencia delictiva, filtra ceros y hace melt."""
    dfs = []
    for year in years:
        path = raw_dir / "incidencia_delictiva" / f"{year}.csv"
        df = pd.read_csv(path, encoding="utf-8-sig")
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Filas totales crudas: {len(combined):,}")

    # Filtrar filas donde todos los meses son cero
    combined = combined[combined[MONTH_COLS].sum(axis=1) > 0]
    logger.info(f"Filas con datos (>0): {len(combined):,}")

    # Excluir municipios ficticios (26998=No especificado, 26999=Otros municipios)
    fake_munis = {26998, 26999}
    n_fake = combined["Cve. Municipio"].isin(fake_munis).sum()
    if n_fake > 0:
        combined = combined[~combined["Cve. Municipio"].isin(fake_munis)]
        logger.info(f"Excluidos {n_fake} filas de municipios ficticios (26998/26999)")

    # Melt: columnas mensuales → filas
    long = combined.melt(
        id_vars=["Año", "Cve. Municipio", "Bien jurídico afectado",
                 "Tipo de delito", "Subtipo de delito", "Modalidad"],
        value_vars=MONTH_COLS,
        var_name="mes_nombre",
        value_name="conteo",
    )

    # Crear columna de fecha
    long["mes"] = long["mes_nombre"].map(MES_MAP)
    long["fecha"] = pd.to_datetime(
        long[["Año", "mes"]].rename(columns={"Año": "year", "mes": "month"}).assign(day=1)
    )

    # Clasificar en categoría agregada
    long["categoria"] = long.apply(_classify_crime, axis=1)

    logger.info(f"Filas después de melt: {len(long):,}")
    return long


def build_panel(long_df: pd.DataFrame) -> pd.DataFrame:
    """Construye el panel base: (municipio, mes) → conteo por categoría."""
    panel = (
        long_df
        .groupby(["Cve. Municipio", "fecha", "categoria"])["conteo"]
        .sum()
        .reset_index()
    )

    wide = panel.pivot_table(
        index=["Cve. Municipio", "fecha"],
        columns="categoria",
        values="conteo",
        fill_value=0,
    ).reset_index()

    # Aplanar el MultiIndex de columnas
    wide.columns.name = None

    # Asegurar que todas las categorías existen como columnas
    for cat in CATEGORIA_COLS:
        if cat not in wide.columns:
            wide[cat] = 0

    # Completar serie temporal sin gaps (todos los municipios × todos los meses)
    all_municipios = sorted(wide["Cve. Municipio"].unique())
    all_fechas = pd.date_range("2015-01-01", "2025-12-01", freq="MS")

    full_idx = pd.MultiIndex.from_product(
        [all_municipios, all_fechas],
        names=["Cve. Municipio", "fecha"],
    )

    wide = (
        wide
        .set_index(["Cve. Municipio", "fecha"])
        .reindex(full_idx, fill_value=0)
        .reset_index()
    )

    logger.info(
        f"Panel base: {len(wide):,} filas, "
        f"{wide['Cve. Municipio'].nunique()} municipios, "
        f"{wide['fecha'].nunique()} meses"
    )
    return wide


@app.command("download")
def download(
    raw_dir: Path = RAW_DATA_DIR,
    references_dir: Path = typer.Option(
        None, help="Directorio de referencias (por defecto: PROJECT_ROOT/references)"
    ),
) -> None:
    """Descarga los datasets crudos del portal datos.sonora.gob.mx."""
    import requests
    from tqdm import tqdm as tqdm_bar

    from sonalert.config import PROJ_ROOT

    CKAN_BASE = "https://datos.sonora.gob.mx"
    CKAN_API = f"{CKAN_BASE}/api/3/action/package_show"
    REFERENCE_KEYWORDS = ("diccionario", "catalogo", "catálogo", "catalog", "dictionary")
    DATASETS = [
        ("caf587a5-23ac-496b-85d4-6ceb1d615d78", "victimas_fuero_comun", "Víctimas del fuero común en el estado"),
        ("93ca5e1c-702e-4e62-bc61-638907be184a", "incidencia_delictiva", "Incidencia delictiva municipal"),
        ("cabaeaac-5611-4d26-95f3-cb51f172035a", "comites_ciudadanos", "Comités Ciudadanos"),
        ("4452a2ec-86d4-4641-8194-03bedd8f061f", "zonas_salva", "Zonas Salva"),
        ("e262a488-69e5-4064-bd2b-191c5c8fc9f9", "marginacion_municipal", "Índice de marginación por municipio"),
        ("a3320cad-afd3-4840-8c3b-36236df26099", "marginacion_urbana_colonia", "Índice de marginación urbana por colonia"),
        ("960ef0a9-73ed-4191-ae0b-b868d7e48292", "proyecciones_poblacion", "Proyecciones de población"),
    ]

    if references_dir is None:
        references_dir = PROJ_ROOT / "references"

    def _is_reference(resource: dict) -> bool:
        name = resource.get("name", "").lower()
        return any(kw in name for kw in REFERENCE_KEYWORDS)

    def _download_file(url: str, dest: Path) -> None:
        if dest.exists():
            logger.info(f"Ya existe, omitiendo: {dest.name}")
            return
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f, tqdm_bar(
            total=total, unit="B", unit_scale=True, desc=dest.name, leave=False,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))

    def _get_resources(dataset_id: str) -> list[dict]:
        response = requests.get(CKAN_API, params={"id": dataset_id}, timeout=30)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"CKAN API error para dataset {dataset_id}: {result}")
        return result["result"]["resources"]

    for dataset_id, slug, description in DATASETS:
        logger.info(f"Procesando: {description}")
        try:
            resources = _get_resources(dataset_id)
        except Exception as e:
            logger.error(f"No se pudieron obtener recursos para '{description}': {e}")
            continue

        for resource in resources:
            url = resource.get("url")
            name = resource.get("name", "archivo")
            fmt = resource.get("format", "").lower()
            if not url:
                logger.warning(f"  Sin URL para recurso '{name}', omitiendo.")
                continue
            url_path = url.split("?")[0]
            suffix = Path(url_path).suffix or f".{fmt}" if fmt else ""
            filename = f"{name}{suffix}" if suffix else name

            if _is_reference(resource):
                dest = references_dir / slug / filename
            else:
                dest = raw_dir / slug / filename

            logger.info(f"  Descargando: {filename} -> {dest.parent.relative_to(PROJ_ROOT)}/")
            try:
                _download_file(url, dest)
            except requests.HTTPError as e:
                logger.error(f"  Error HTTP al descargar '{filename}': {e}")
            except Exception as e:
                logger.error(f"  Error inesperado al descargar '{filename}': {e}")

    logger.success("Descarga completa.")


@app.command("main")
def main(
    raw_dir: Path = RAW_DATA_DIR,
    output_path: Path = INTERIM_DATA_DIR / "panel_base.parquet",
) -> None:
    """Ingesta de datos crudos → panel base en data/interim/."""
    logger.info("Paso 1: Cargando incidencia delictiva...")
    long = load_incidencia(raw_dir)

    logger.info("Paso 2: Construyendo panel base...")
    panel = build_panel(long)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_path, index=False)
    logger.success(f"Panel base guardado en {output_path} ({len(panel):,} filas)")


if __name__ == "__main__":
    app()
