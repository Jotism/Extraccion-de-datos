"""
NDVI mensual de una zona, a partir del producto MODIS/061/MOD13A3.

MOD13A3 es el producto mensual "oficial" de MODIS Terra (1 km): se
genera promediando con pesos los compuestos de 16 días (MOD13A2) que
caen dentro de cada mes.
"""

import os

import ee
import pandas as pd

from .base import BaseEEExtractor


class NDVIExtractor(BaseEEExtractor):
    """Calcula el NDVI mensual promedio de una zona para un rango de años."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL_SIMPLIFIED_500m/2015/level1"
    MODIS_ASSET = "MODIS/061/MOD13A3"
    SCALE = 1000

    def __init__(self, admin0_name, admin1_name, start_year, end_year,
                 admin_dataset=None):
        """
        Parameters
        ----------
        start_year, end_year : int
            Rango de años (inclusive) a extraer.
        """
        super().__init__(admin0_name, admin1_name, admin_dataset)
        self.start_year = start_year
        self.end_year = end_year

    def _monthly_ndvi_feature(self, img):
        # SummaryQA: 0 = buena calidad, 1 = marginal, 2 = nieve/hielo, 3 = nublado
        qa_mask = img.select("SummaryQA").lte(1)
        ndvi_img = img.select("NDVI").updateMask(qa_mask).multiply(0.0001).rename("NDVI_d")

        stats = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=self.geometry,
            scale=self.SCALE,
            maxPixels=1e9,
        )

        date = img.date()
        return ee.Feature(None, {
            "year": date.get("year"),
            "month": date.get("month"),
            "date": date.format("YYYY-MM"),
            "NDVI_d": stats.get("NDVI_d"),
        })

    def extract(self):
        """Devuelve un DataFrame con una fila por mes del rango de años."""
        start_date = f"{self.start_year}-01-01"
        end_date = f"{self.end_year + 1}-01-01"

        modis_monthly = (
            ee.ImageCollection(self.MODIS_ASSET)
            .filterDate(start_date, end_date)
            .filterBounds(self.geometry)
            .select(["NDVI", "SummaryQA"])
        )

        ndvi_monthly_fc = ee.FeatureCollection(modis_monthly.map(self._monthly_ndvi_feature))

        info = ndvi_monthly_fc.getInfo()
        df = pd.DataFrame([f["properties"] for f in info["features"]])
        df = df[["date", "year", "month", "NDVI_d"]].sort_values("date").reset_index(drop=True)
        return df

    def save(self, output_dir="salidas_corrientes", filename=None):
        os.makedirs(output_dir, exist_ok=True)
        filename = filename or (
            f"{self.zone_slug}_ndvi_mensual_{self.start_year}_{self.end_year}.csv"
        )
        path = os.path.join(output_dir, filename)

        df = self.extract()
        df.to_csv(path, index=False)
        print(f"[NDVI] Guardado: {path} ({len(df)} filas)")
        return path
