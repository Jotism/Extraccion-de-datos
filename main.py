"""
Script principal: ejecuta todas las extracciones de datos de Earth
Engine (área, cobertura forestal, meteorológicas, NDVI, topográficas)
para una zona y rango de años determinados, y guarda los resultados
como CSV locales.

Requisitos:
    pip install earthengine-api pandas
    earthengine authenticate      # una vez, en forma interactiva
"""

from ee_extractors import (
    AreaExtractor,
    ForestCoverExtractor,
    MeteorologicalExtractor,
    NDVIExtractor,
    TopographicExtractor,
)

# ---------------------------------------------------------------------
# Configuración general: zona, rango de años a extraer y carpeta destino.
# ADMIN0_NAME = nombre del pais
# ADMIN1_NAME = nombre de la provincia/estado
# ---------------------------------------------------------------------
ADMIN0_NAME = "Argentina"
ADMIN1_NAME = "Cordoba"
START_YEAR = 2015
END_YEAR = 2015
OUTPUT_DIR = "prueba_main"


def main():
    print("=== Área ===")
    area_extractor = AreaExtractor(ADMIN0_NAME, ADMIN1_NAME)
    area_extractor.save(output_dir=OUTPUT_DIR)

    print("\n=== Cobertura forestal ===")
    forest_extractor = ForestCoverExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    )
    forest_extractor.save(output_dir=OUTPUT_DIR)

    print("\n=== Variables meteorológicas ===")
    meteo_extractor = MeteorologicalExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    )
    meteo_extractor.save(output_dir=OUTPUT_DIR)

    print("\n=== NDVI ===")
    ndvi_extractor = NDVIExtractor(
        ADMIN0_NAME, ADMIN1_NAME, START_YEAR, END_YEAR
    )
    ndvi_extractor.save(output_dir=OUTPUT_DIR)

    print("\n=== Variables topográficas ===")
    topo_extractor = TopographicExtractor(ADMIN0_NAME, ADMIN1_NAME)
    topo_extractor.save(output_dir=OUTPUT_DIR)

    print(f'\nExtraccion terminada. Puede revisar los CSV en la carpeta: "{OUTPUT_DIR}/".')


if __name__ == "__main__":
    main()
