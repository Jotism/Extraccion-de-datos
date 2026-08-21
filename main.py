"""
Script principal: ejecuta todas las extracciones de datos de Earth
Engine (área, cobertura forestal, meteorológicas, NDVI, topográficas)
para una zona y rango de años determinados, guarda cada una como CSV
local, y además arma un dataset diario unificado con todas las
variables juntas.

Requisitos:
    pip install earthengine-api pandas pycountry
    earthengine authenticate      # una vez, en forma interactiva
"""
import pycountry
import difflib

from ee_extractors import (
    AreaExtractor,
    ForestCoverExtractor,
    MeteorologicalExtractor,
    NDVIExtractor,
    TopographicExtractor,
    UnifiedDatasetBuilder,
)

# ---------------------------------------------------------------------
# Configuración general: zona, rango de años y códigos ISO a usar.
# Cambiando estas variables se puede correr todo el pipeline para
# otra provincia/país u otro período, sin tocar las clases.
#
#   country_code -> ISO 3166-1 alpha-2 del país (ej. "AR" = Argentina)
#   region_code  -> ISO 3166-2 de la provincia/estado
#                   (ej. "AR-W" = Corrientes)
# ---------------------------------------------------------------------
ADMIN0_NAME = "Argentina"
ADMIN1_NAME = "Corrientes"
COUNTRY_CODE = pycountry.countries.search_fuzzy(ADMIN0_NAME)[0].alpha_2
REGION_CODE = ""
START_YEAR = 2015
END_YEAR = 2015
OUTPUT_DIR = "Resultados_tablas"

def find_subdivision_code_fuzzy(country_alpha2, region_name):
    subs = list(pycountry.subdivisions.get(country_code=country_alpha2))
    names = [s.name for s in subs]
    match = difflib.get_close_matches(region_name, names, n=1, cutoff=0.6)
    if match:
        return next(s.code for s in subs if s.name == match[0])
    return None

REGION_CODE = find_subdivision_code_fuzzy(COUNTRY_CODE, ADMIN1_NAME)

def run_individual_extractions():
    """Corre cada extractor por separado y guarda su propio CSV
    (igual que antes: un archivo por variable)."""
    print("=== Área ===")
    AreaExtractor(ADMIN0_NAME, ADMIN1_NAME).save(output_dir=OUTPUT_DIR)

    print("\n=== Cobertura forestal ===")
    ForestCoverExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    ).save(output_dir=OUTPUT_DIR)

    print("\n=== Variables meteorológicas ===")
    MeteorologicalExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    ).save(output_dir=OUTPUT_DIR)

    print("\n=== NDVI ===")
    NDVIExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    ).save(output_dir=OUTPUT_DIR)

    print("\n=== Variables topográficas ===")
    TopographicExtractor(ADMIN0_NAME, ADMIN1_NAME).save(output_dir=OUTPUT_DIR)


def run_unified_dataset():
    """Corre las 5 extracciones y arma el dataset diario unificado
    'dataset_<pais>_<provincia>_<desde>-<hasta>.csv'."""
    print("\n=== Dataset unificado ===")
    builder = UnifiedDatasetBuilder(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR,
        country_code=COUNTRY_CODE, region_code=REGION_CODE,
    )
    builder.save(output_dir=OUTPUT_DIR)

def main():
    run_individual_extractions()
    run_unified_dataset()
    print(f'\nListo. Todos los CSV quedaron en la carpeta "{OUTPUT_DIR}/".')


if __name__ == "__main__":
    main()