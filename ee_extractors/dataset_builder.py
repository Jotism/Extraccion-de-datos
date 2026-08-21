"""
Unifica las tablas generadas por los distintos extractores de Earth
Engine en un único dataset diario.

La granularidad final es diaria (la de MeteorologicalExtractor, que es
la más fina de las 5). El resto de las variables se "pegan" a cada
fila diaria repitiendo su valor:
  - NDVI_d           -> mismo valor para todos los días de un mes
  - Forest_Cover_Percent -> mismo valor para todos los días de un año
  - area_km2 y elevación -> mismo valor para todas las filas (estáticas)
Esto es intencional: cada fila diaria queda con la mejor información
disponible a esa fecha para cada variable, aunque no todas se midan
todos los días.
"""

import os

import pandas as pd

from .area import AreaExtractor
from .cobertura import ForestCoverExtractor
from .meteorologicas import MeteorologicalExtractor
from .ndvi import NDVIExtractor
from .topograficas import TopographicExtractor


class UnifiedDatasetBuilder:
    """
    Corre los 5 extractores (área, cobertura forestal, meteorológicas,
    NDVI, topográficas) para una misma zona y rango de años, y arma un
    único dataset diario con la estructura:

        Date, Year, Month, country_code, region_code, area_km2,
        NDVI_d, dewpoint_temperature_2m_d, humidity_d,
        max_temperature_2m_d, min_temperature_2m_d,
        surface_pressure_d, temperature_2m_d, total_precipitation_d,
        u_component_of_wind_10m_d, v_component_of_wind_10m_d,
        max_elevation_d, mean_elevation_d, min_elevation_d,
        stdDev_elevation_d, variance_elevation_d, Forest_Cover_Percent
    """

    COLUMN_ORDER = [
        "Date", "Year", "Month", "country_code", "region_code",
        "area_km2", "NDVI_d",
        "dewpoint_temperature_2m_d", "humidity_d",
        "max_temperature_2m_d", "min_temperature_2m_d",
        "surface_pressure_d", "temperature_2m_d",
        "total_precipitation_d",
        "u_component_of_wind_10m_d", "v_component_of_wind_10m_d",
        "max_elevation_d", "mean_elevation_d", "min_elevation_d",
        "stdDev_elevation_d", "variance_elevation_d",
        "Forest_Cover_Percent",
    ]

    def __init__(self, admin0_name, admin1_name, start_year, end_year,
                 country_code, region_code,
                 tree_cover_threshold=30, offset_hours=0):
        """
        Parameters
        ----------
        admin0_name, admin1_name : str
            País y provincia/estado (ADM0_NAME / ADM1_NAME de FAO/GAUL).
        start_year, end_year : int
            Rango de años (inclusive) del dataset.
        country_code : str
            Código ISO 3166-1 (alpha-2) del país, ej: "AR".
        region_code : str
            Código ISO 3166-2 de la región, ej: "AR-W" (Corrientes).
        tree_cover_threshold : int
            Parámetro de ForestCoverExtractor (ver cobertura.py).
        offset_hours : int
            Parámetro de MeteorologicalExtractor (ver meteorologicas.py).
        """
        self.admin0_name = admin0_name
        self.admin1_name = admin1_name
        self.start_year = start_year
        self.end_year = end_year
        self.country_code = country_code
        self.region_code = region_code

        self.area_extractor = AreaExtractor(admin0_name, admin1_name)
        self.forest_extractor = ForestCoverExtractor(
            admin0_name, admin1_name, start_year, end_year,
            tree_cover_threshold=tree_cover_threshold,
        )
        self.meteo_extractor = MeteorologicalExtractor(
            admin0_name, admin1_name, start_year, end_year,
            offset_hours=offset_hours,
        )
        self.ndvi_extractor = NDVIExtractor(
            admin0_name, admin1_name, start_year, end_year,
        )
        self.topo_extractor = TopographicExtractor(admin0_name, admin1_name)

    @property
    def zone_slug(self):
        return self.admin1_name.strip().lower().replace(" ", "_")

    @property
    def country_slug(self):
        return self.admin0_name.strip().lower().replace(" ", "_")

    def build(self):
        """Corre las 5 extracciones y devuelve el DataFrame diario unificado."""
        # --- 1) Base diaria: meteorológicas ---
        print("[Dataset] Extrayendo variables meteorológicas (base diaria) ...")
        meteo_by_year = self.meteo_extractor.extract()
        df = pd.concat(meteo_by_year.values(), ignore_index=True)
        df["Date"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"])
        df["Year"] = df["Date"].dt.year
        df["Month"] = df["Date"].dt.month

        # --- 2) NDVI mensual -> join por (Year, Month), se repite en
        #        cada dia del mes ---
        print("[Dataset] Extrayendo NDVI (mensual) ...")
        ndvi_df = self.ndvi_extractor.extract()
        ndvi_df = ndvi_df.rename(columns={"year": "Year", "month": "Month"})
        ndvi_df["Year"] = ndvi_df["Year"].astype(int)
        ndvi_df["Month"] = ndvi_df["Month"].astype(int)
        ndvi_df = ndvi_df[["Year", "Month", "NDVI_d"]]
        df = df.merge(ndvi_df, on=["Year", "Month"], how="left")

        # --- 3) Cobertura forestal anual -> join por Year, se repite
        #        en cada dia del anio ---
        print("[Dataset] Extrayendo cobertura forestal (anual) ...")
        forest_df = self.forest_extractor.extract()
        df = df.merge(forest_df, on="Year", how="left")

        # --- 4) Area (estatica) -> se repite en todas las filas ---
        print("[Dataset] Extrayendo area (estatica) ...")
        area_df = self.area_extractor.extract()
        df["area_km2"] = area_df.loc[0, "Area_km2"]

        # --- 5) Topograficas (estaticas) -> se repiten en todas las filas ---
        print("[Dataset] Extrayendo variables topograficas (estaticas) ...")
        topo_df = self.topo_extractor.extract()
        for col in ["min_elevation_d", "max_elevation_d", "mean_elevation_d",
                    "stdDev_elevation_d", "variance_elevation_d"]:
            df[col] = topo_df.loc[0, col]

        # --- 6) Codigos ISO ---
        df["country_code"] = self.country_code
        df["region_code"] = self.region_code

        # --- 7) Orden final de columnas + formato de fecha limpio ---
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df = df[self.COLUMN_ORDER].sort_values("Date").reset_index(drop=True)
        return df

    def save(self, output_dir="salidas_corrientes", filename=None):
        os.makedirs(output_dir, exist_ok=True)
        filename = filename or (
            f"dataset_{self.country_slug}_{self.zone_slug}_"
            f"{self.start_year}-{self.end_year}.csv"
        )
        path = os.path.join(output_dir, filename)

        df = self.build()
        df.to_csv(path, index=False)
        print(f"[Dataset] Guardado: {path} ({len(df)} filas, {len(df.columns)} columnas)")
        return path