from pathlib import Path

import numpy as np
import pandas as pd
import typer
from loguru import logger

from sonalert.config import (
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJ_ROOT,
    RAW_DATA_DIR,
)
from sonalert.dataset import CATEGORIA_COLS

app = typer.Typer()

GM_ORDINAL = {
    "Muy bajo": 1,
    "Bajo": 2,
    "Medio": 3,
    "Alto": 4,
    "Muy alto": 5,
}


# ---------------------------------------------------------------------------
# Paso 3: Enriquecimiento con features estáticos
# ---------------------------------------------------------------------------

def _strip_accents(s: str) -> str:
    """Elimina acentos de un string para matching robusto."""
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def load_municipio_catalog() -> dict[str, int]:
    """Carga el catálogo nombre→código de municipios desde references/.

    Genera dos variantes de cada nombre (con y sin acentos) para matching
    robusto contra fuentes que no usan acentos (ej. Zonas Salva).
    """
    catalogo = pd.read_excel(
        PROJ_ROOT / "references" / "incidencia_delictiva" / "Catalogo.xlsx",
        sheet_name="cat_municipio",
    )
    mapping = {}
    for _, row in catalogo.iterrows():
        nombre = row["Municipio"].upper().strip()
        cve = row["Cve. Municipio"]
        mapping[nombre] = cve
        mapping[_strip_accents(nombre)] = cve
    return mapping


def enrich_marginacion(panel: pd.DataFrame) -> pd.DataFrame:
    """Une índice de marginación municipal 2020 al panel."""
    mg = pd.read_excel(
        RAW_DATA_DIR / "marginacion_municipal" / "Indice de marginación por municipio 2020.xlsx",
    )

    feature_cols = [
        "CVE_MUN", "POB_TOT", "ANALF", "SBASC", "OVSDE", "OVSEE",
        "OVSAE", "OVPT", "VHAC", "PL.5000", "PO2SM",
        "IM_2020", "GM_2020", "IMN_2020",
    ]
    mg = mg[feature_cols].copy()
    mg["GM_2020"] = mg["GM_2020"].map(GM_ORDINAL)
    mg = mg.rename(columns={"CVE_MUN": "Cve. Municipio"})

    panel = panel.merge(mg, on="Cve. Municipio", how="left")
    n_missing = panel["IM_2020"].isna().sum()
    if n_missing > 0:
        logger.warning(f"Marginación: {n_missing} filas sin match")
    return panel


def enrich_poblacion(panel: pd.DataFrame) -> pd.DataFrame:
    """Une proyecciones de población anuales al panel."""
    pop = pd.read_excel(
        RAW_DATA_DIR / "proyecciones_poblacion"
        / "Indicadores demográficos 1990 - 2040.xlsx",
    )

    pop_cols = ["CLAVE", "AÑO", "POB_MIT_MUN", "POB_15_64", "EDAD_MED", "RAZ_DEP"]
    pop = pop[pop_cols].rename(columns={"CLAVE": "Cve. Municipio", "AÑO": "año"})

    panel["año"] = panel["fecha"].dt.year
    panel = panel.merge(pop, on=["Cve. Municipio", "año"], how="left")

    n_missing = panel["POB_MIT_MUN"].isna().sum()
    if n_missing > 0:
        logger.warning(f"Población: {n_missing} filas sin match")

    # Tasas por 100,000 habitantes
    for cat in CATEGORIA_COLS:
        panel[f"{cat}_tasa"] = (panel[cat] / panel["POB_MIT_MUN"]) * 100_000

    # Estrato poblacional (ordinal: 0=rural, 1=pequeño, 2=medio, 3=urbano)
    panel["pop_bucket"] = pd.qcut(
        panel["POB_MIT_MUN"], q=4, labels=[0, 1, 2, 3],
    ).astype(int)

    return panel


def enrich_zonas_salva(panel: pd.DataFrame) -> pd.DataFrame:
    """Agrega features de densidad de Zonas Salva por municipio."""
    nombre_to_cve = load_municipio_catalog()

    dfs = []
    zonas_dir = RAW_DATA_DIR / "zonas_salva"
    for f in zonas_dir.glob("*.xlsx"):
        dfs.append(pd.read_excel(f))

    if not dfs:
        logger.warning("No se encontraron archivos de Zonas Salva")
        return panel

    zonas = pd.concat(dfs, ignore_index=True)
    zonas = zonas.drop_duplicates(subset=["LATITUD", "LONGITUD"])

    # Mapear nombre de municipio a código
    zonas["Cve. Municipio"] = (
        zonas["MUNICIPIO"].str.upper().str.strip().map(nombre_to_cve)
    )

    sin_match = zonas[zonas["Cve. Municipio"].isna()]["MUNICIPIO"].unique()
    if len(sin_match) > 0:
        logger.warning(f"Zonas Salva sin mapeo de municipio: {sin_match}")

    zonas = zonas.dropna(subset=["Cve. Municipio"])
    zonas["Cve. Municipio"] = zonas["Cve. Municipio"].astype(int)

    zonas_features = zonas.groupby("Cve. Municipio").agg(
        n_zonas_salva=("DESCRIPCION_LUGAR", "count"),
        n_tipos_lugar=("TIPO_LUGAR", "nunique"),
        n_colonias_cubiertas=("COLONIA", "nunique"),
        n_escuelas=("TIPO_LUGAR", lambda x: (x == "ESCUELA").sum()),
        n_gobierno=("TIPO_LUGAR", lambda x: (x == "GOBIERNO").sum()),
        n_salud=("TIPO_LUGAR", lambda x: (x == "SALUD").sum()),
    ).reset_index()

    panel = panel.merge(zonas_features, on="Cve. Municipio", how="left")

    # Municipios sin zonas salva → 0
    zonas_cols = [
        "n_zonas_salva", "n_tipos_lugar", "n_colonias_cubiertas",
        "n_escuelas", "n_gobierno", "n_salud",
    ]
    panel[zonas_cols] = panel[zonas_cols].fillna(0).astype(int)

    return panel


# ---------------------------------------------------------------------------
# Paso 4: Feature engineering temporal
# ---------------------------------------------------------------------------

def add_temporal_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Agrega lags, rolling stats, features cíclicos y dummies."""
    panel = panel.copy()

    # Asegurar orden correcto para lags
    panel = panel.sort_values(["Cve. Municipio", "fecha"]).reset_index(drop=True)

    # Temporales básicas
    panel["mes"] = panel["fecha"].dt.month
    panel["trimestre"] = panel["fecha"].dt.quarter
    panel["mes_sin"] = np.sin(2 * np.pi * panel["mes"] / 12)
    panel["mes_cos"] = np.cos(2 * np.pi * panel["mes"] / 12)

    # Lags y rolling por municipio
    for cat in CATEGORIA_COLS:
        g = panel.groupby("Cve. Municipio")[cat]

        # Lags
        panel[f"{cat}_lag1"] = g.shift(1)
        panel[f"{cat}_lag2"] = g.shift(2)
        panel[f"{cat}_lag3"] = g.shift(3)
        panel[f"{cat}_lag12"] = g.shift(12)

        # Rolling stats — transform() para respetar fronteras de grupo
        panel[f"{cat}_roll3_mean"] = g.transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).mean()
        )
        panel[f"{cat}_roll6_mean"] = g.transform(
            lambda x: x.shift(1).rolling(6, min_periods=1).mean()
        )
        panel[f"{cat}_roll12_mean"] = g.transform(
            lambda x: x.shift(1).rolling(12, min_periods=1).mean()
        )
        panel[f"{cat}_roll3_std"] = g.transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).std()
        )

        # Tendencia YoY
        panel[f"{cat}_yoy_change"] = (
            (panel[cat] - panel[f"{cat}_lag12"]) / (panel[f"{cat}_lag12"] + 1)
        )

    # COVID dummies
    panel["covid_lockdown"] = (
        (panel["año"] == 2020) & (panel["mes"].between(4, 6))
    ).astype(int)
    panel["covid_period"] = panel["año"].isin([2020, 2021]).astype(int)

    # Índice compuesto de crimen violento
    panel["crimen_violento_total"] = (
        panel["homicidio_doloso"]
        + panel["feminicidio"]
        + panel["robo_violento"]
        + panel["secuestro"]
    )

    # Drop primeros 12 meses por municipio (NaN en lag12 y yoy_change)
    # Garantiza dataset sin NaN, model-agnostic y listo para entrenar
    lag12_cols = [f"{cat}_lag12" for cat in CATEGORIA_COLS]
    n_before = len(panel)
    panel = panel.dropna(subset=lag12_cols)
    logger.info(f"Filas eliminadas por NaN en lag12: {n_before - len(panel)}")

    return panel


@app.command()
def main(
    input_path: Path = INTERIM_DATA_DIR / "panel_base.parquet",
    output_path: Path = PROCESSED_DATA_DIR / "panel_features.parquet",
) -> None:
    """Enriquece el panel base con features estáticos y temporales."""
    logger.info(f"Cargando panel base desde {input_path}...")
    panel = pd.read_parquet(input_path)
    logger.info(f"Panel base: {len(panel):,} filas")

    logger.info("Paso 3.1: Enriqueciendo con marginación municipal...")
    panel = enrich_marginacion(panel)

    logger.info("Paso 3.2: Enriqueciendo con proyecciones de población...")
    panel = enrich_poblacion(panel)

    logger.info("Paso 3.3: Enriqueciendo con Zonas Salva...")
    panel = enrich_zonas_salva(panel)

    logger.info("Paso 4: Generando features temporales...")
    panel = add_temporal_features(panel)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_path, index=False)
    logger.success(
        f"Panel con features guardado en {output_path} "
        f"({len(panel):,} filas × {len(panel.columns)} columnas)"
    )


if __name__ == "__main__":
    app()
