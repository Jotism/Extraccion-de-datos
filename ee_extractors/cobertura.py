"""
WORK IN PROGRESS
Forest_Cover_Percent según la metodología del proyecto ESA-UNICEF Dengue.

El % del año Y refleja el 100% inicial en el año 2000 menos el porcentaje 
acumulado de pérdida de bosque relativo a la cobertura inicial.
"""

import os

import ee
import pandas as pd

from .base import BaseEEExtractor


class ForestCoverExtractor(BaseEEExtractor):
    """Extrae el porcentaje de cobertura forestal remanente acumulada."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL/2015/level1"
    HANSEN_ASSET = "UMD/hansen/global_forest_change_2025_v1_13"
    SCALE = 100          # resolución nativa de Hansen (m)
    TILE_SCALE = 4       # ayuda a evitar timeouts en reduceRegion

    def __init__(self, admin0_name, admin1_name, start_year, end_year,
                 tree_cover_threshold=30, admin_dataset=None):
        super().__init__(admin0_name, admin1_name, admin_dataset)
        self.start_year = start_year
        self.end_year = end_year
        self.tree_cover_threshold = tree_cover_threshold

        hansen = ee.Image(self.HANSEN_ASSET)
        self._tree_cover_2000 = hansen.select("treecover2000")
        self._loss_year = hansen.select("lossyear")   # 0 = sin pérdida
        self._gain = hansen.select("gain")             # ganancia
        self._datamask = hansen.select("datamask").eq(1)

        # Bosque de referencia inicial (Año 2000)
        self._forest_2000_mask = self._tree_cover_2000.gte(
            self.tree_cover_threshold
        ).Or(self._gain).updateMask(self._datamask)

        self._pixel_area = ee.Image.pixelArea()

        # Superficie total de bosque en el año 2000 (m²)
        self._initial_forest_area = (
            self._pixel_area
            .updateMask(self._forest_2000_mask)
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=self.geometry,
                scale=self.SCALE,
                maxPixels=1e13,
                bestEffort=True,
                tileScale=self.TILE_SCALE,
            )
            .get("area")
        )

    def _forest_percent(self, year):
        yr_code = year - 2000
        
        # Pérdida de bosque acumulada desde 2001 hasta el año actual
        loss_mask = (
            self._forest_2000_mask
            .And(self._loss_year.gt(0))
            .And(self._loss_year.lte(yr_code))
        )

        # Área perdida acumulada hasta el año `year` (m²)
        accumulated_loss_area = (
            self._pixel_area
            .updateMask(loss_mask)
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=self.geometry,
                scale=self.SCALE,
                maxPixels=1e13,
                bestEffort=True,
                tileScale=self.TILE_SCALE,
            )
            .get("area")
        )

        # Cálculo: 100% - (% de pérdida acumulada sobre el área inicial del 2000)
        loss_percent = ee.Number(accumulated_loss_area).divide(self._initial_forest_area).multiply(100)
        return ee.Number(100).subtract(loss_percent)

    def extract(self):
        """Devuelve un DataFrame con una fila por año del rango."""
        rows = []
        for year in range(self.start_year, self.end_year + 1):
            print(f"[ForestCover] Calculando {year} ...")
            f_pct = self._forest_percent(year).getInfo()
            rows.append({
                "Year": year,
                "Forest_Cover_Percent": round(f_pct, 12) if f_pct is not None else None,
            })
            print(rows[-1])
        return pd.DataFrame(rows)

    def save(self, output_dir=".", filename=None):
        os.makedirs(output_dir, exist_ok=True)
        filename = filename or (
            f"{self.zone_slug}_forest_cover_{self.start_year}_{self.end_year}.csv"
        )
        path = os.path.join(output_dir, filename)

        df = self.extract()
        df.to_csv(path, index=False)
        print(f"[ForestCover] Guardado: {path}")
        return path