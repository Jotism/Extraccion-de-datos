"""
Forest_Cover_Percent anual de una zona, a partir de Hansen Global
Forest Change.

Un pixel cuenta como bosque en el anio Y si:
  - su cobertura de copa en el anio 2000 es >= tree_cover_threshold
    (o fue clasificado como "gain" entre 2000-2012), Y
  - todavia no perdio bosque para el anio Y (lossyear == 0, o
    lossyear > Y-2000).
% = promedio de esa mascara 0/1 sobre la region (los pixeles
enmascarados -agua / sin datos- se excluyen automaticamente).
"""

import os

import ee
import pandas as pd

from .base import BaseEEExtractor


class ForestCoverExtractor(BaseEEExtractor):
    """Calcula el % de cobertura forestal año a año para una zona."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL/2015/level1"
    HANSEN_ASSET = "UMD/hansen/global_forest_change_2025_v1_13"
    SCALE = 30          # resolucion nativa de Hansen (m)
    TILE_SCALE = 4       # ayuda a evitar timeouts en reduceRegion

    def __init__(self, admin0_name, admin1_name, start_year, end_year,
                 tree_cover_threshold=30, admin_dataset=None):
        """
        Parameters
        ----------
        start_year, end_year : int
            Rango de años (inclusive) a calcular.
        tree_cover_threshold : int
            % de copa (año 2000) usado para definir "bosque".
        """
        super().__init__(admin0_name, admin1_name, admin_dataset)
        self.start_year = start_year
        self.end_year = end_year
        self.tree_cover_threshold = tree_cover_threshold

        hansen = ee.Image(self.HANSEN_ASSET)
        self._tree_cover_2000 = hansen.select("treecover2000")
        self._loss_year = hansen.select("lossyear")   # 0 = sin perdida
        self._gain = hansen.select("gain")             # ganancia 2000-2012
        self._datamask = hansen.select("datamask").eq(1)  # 1 = tierra valida
        self._forest_2000_mask = self._tree_cover_2000.gte(
            self.tree_cover_threshold
        ).Or(self._gain)

    def _forest_percent(self, year):
        yr_code = year - 2000
        still_forest = (
            self._forest_2000_mask
            .And(self._loss_year.eq(0).Or(self._loss_year.gt(yr_code)))
            .rename("forest")
            .updateMask(self._datamask)
        )
        result = still_forest.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=self.geometry,
            scale=self.SCALE,
            maxPixels=1e13,
            bestEffort=True,
            tileScale=self.TILE_SCALE,
        )
        return ee.Number(result.get("forest")).multiply(100)

    def extract(self):
        """Devuelve un DataFrame con una fila por año del rango."""
        rows = []
        for year in range(self.start_year, self.end_year + 1):
            print(f"[ForestCover] Calculando {year} ...")
            f_pct = self._forest_percent(year).getInfo()
            rows.append({
                "Year": year,
                "Forest_Cover_Percent": round(f_pct, 3) if f_pct is not None else None,
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
