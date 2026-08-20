"""
Variables de elevación (min, max, media, desvío, varianza) de una
zona, a partir del producto CGIAR/SRTM90_V4.

SRTM90_V4 es el conjunto de datos de elevación digital de la Misión
Topográfica con Radar del Transbordador (SRTM), producido para
proporcionar datos de elevación coherentes y de alta calidad con un
alcance casi global.
"""

import os

import ee
import pandas as pd

from .base import BaseEEExtractor


class TopographicExtractor(BaseEEExtractor):
    """Calcula estadísticas de elevación (SRTM) para una zona. No
    necesita rango de años: la elevación es estática."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL_SIMPLIFIED_500m/2015/level1"
    SRTM_ASSET = "CGIAR/SRTM90_V4"
    SCALE = 90

    def extract(self):
        """Devuelve un DataFrame de una fila con las estadísticas de
        elevación de la zona."""
        srtm = ee.Image(self.SRTM_ASSET).select("elevation")

        combined_reducer = (
            ee.Reducer.min()
            .combine(reducer2=ee.Reducer.max(), sharedInputs=True)
            .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
            .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True)
            .combine(reducer2=ee.Reducer.variance(), sharedInputs=True)
        )

        stats = srtm.reduceRegion(
            reducer=combined_reducer,
            geometry=self.geometry,
            scale=self.SCALE,
            maxPixels=1e9,
        )

        stats_feature = ee.Feature(None, {
            "region": self.zone_label,
            "min_elevation_d": stats.get("elevation_min"),
            "max_elevation_d": stats.get("elevation_max"),
            "mean_elevation_d": stats.get("elevation_mean"),
            "stdDev_elevation_d": stats.get("elevation_stdDev"),
            "variance_elevation_d": stats.get("elevation_variance"),
        })

        stats_collection = ee.FeatureCollection([stats_feature])
        info = stats_collection.getInfo()
        df = pd.DataFrame([f["properties"] for f in info["features"]])
        df = df[["region", "min_elevation_d", "max_elevation_d", "mean_elevation_d",
                 "stdDev_elevation_d", "variance_elevation_d"]]
        return df

    def save(self, output_dir="salidas_corrientes", filename=None):
        os.makedirs(output_dir, exist_ok=True)
        filename = filename or f"{self.zone_slug}_variables_elevacion.csv"
        path = os.path.join(output_dir, filename)

        df = self.extract()
        df.to_csv(path, index=False)
        print(f"[Topografia] Guardado: {path}")
        print(df.to_string(index=False))
        return path
