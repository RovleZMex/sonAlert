from pathlib import Path

import requests
import typer
from loguru import logger
from tqdm import tqdm

from sonalert.config import PROCESSED_DATA_DIR, RAW_DATA_DIR

app = typer.Typer()

CKAN_BASE = "https://datos.sonora.gob.mx"
CKAN_API = f"{CKAN_BASE}/api/3/action/package_show"

# Datasets a descargar: (id_ckan, slug_local, descripcion)
DATASETS = [
    (
        "caf587a5-23ac-496b-85d4-6ceb1d615d78",
        "victimas_fuero_comun",
        "Víctimas del fuero común en el estado",
    ),
    (
        "93ca5e1c-702e-4e62-bc61-638907be184a",
        "incidencia_delictiva",
        "Incidencia delictiva municipal",
    ),
    (
        "cabaeaac-5611-4d26-95f3-cb51f172035a",
        "comites_ciudadanos",
        "Comités Ciudadanos",
    ),
    (
        "4452a2ec-86d4-4641-8194-03bedd8f061f",
        "zonas_salva",
        "Zonas Salva",
    ),
    (
        "e262a488-69e5-4064-bd2b-191c5c8fc9f9",
        "marginacion_municipal",
        "Índice de marginación por municipio",
    ),
    (
        "a3320cad-afd3-4840-8c3b-36236df26099",
        "marginacion_urbana_colonia",
        "Índice de marginación urbana por colonia",
    ),
    (
        "960ef0a9-73ed-4191-ae0b-b868d7e48292",
        "proyecciones_poblacion",
        "Proyecciones de población - Indicadores demográficos",
    ),
]

# Palabras clave que identifican archivos de referencia (van a /references/)
REFERENCE_KEYWORDS = ("diccionario", "catalogo", "catálogo", "catalog", "dictionary")


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

    with open(dest, "wb") as f, tqdm(
        total=total,
        unit="B",
        unit_scale=True,
        desc=dest.name,
        leave=False,
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


@app.command()
def download(
    raw_dir: Path = RAW_DATA_DIR,
    references_dir: Path = typer.Option(
        None, help="Directorio de referencias (por defecto: PROJECT_ROOT/references)"
    ),
) -> None:
    """Descarga los datasets crudos del portal datos.sonora.gob.mx."""
    from sonalert.config import PROJ_ROOT

    if references_dir is None:
        references_dir = PROJ_ROOT / "references"

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

            # Determinar extensión del archivo
            url_path = url.split("?")[0]
            suffix = Path(url_path).suffix or f".{fmt}" if fmt else ""
            filename = f"{name}{suffix}" if suffix else name

            # Clasificar como dato o referencia
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


@app.command()
def main(
    input_path: Path = RAW_DATA_DIR / "dataset.csv",
    output_path: Path = PROCESSED_DATA_DIR / "dataset.csv",
) -> None:
    """Procesa los datasets crudos y genera los datos procesados."""
    logger.info("Processing dataset...")
    logger.success("Processing dataset complete.")


if __name__ == "__main__":
    app()
