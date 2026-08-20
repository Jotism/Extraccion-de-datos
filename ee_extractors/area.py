"""
Área (km2) de una zona administrativa, calculada con Earth Engine.

Fuente por defecto: FAO/GAUL/2015/level1 (límites administrativos nivel 1)
"""

import os

import ee
import pandas as pd

from .base import BaseEEExtractor


class AreaExtractor(BaseEEExtractor):
    """Calcula el área (km2) de la zona de interés."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL/2015/level1"

    def extract(self):
        """Devuelve un DataFrame de una fila con el área en km2."""
        # geometry().area() da el area real en m2 (geodesia, no
        # proyeccion plana); maxError en metros es la tolerancia.
        area_m2 = self.geometry.area(maxError=1)
        area_km2_value = ee.Number(area_m2).divide(1e6).getInfo()

        print(f"Area de {self.zone_label}: {area_km2_value:.3f} km2")

        df = pd.DataFrame([{
            "Provincia": self.admin1_name,
            "Area_km2": round(area_km2_value, 3),
        }])
        return df

    def save(self, output_dir=".", filename=None):
        os.makedirs(output_dir, exist_ok=True)
        filename = filename or f"{self.zone_slug}_area_km2.csv"
        path = os.path.join(output_dir, filename)

        df = self.extract()
        df.to_csv(path, index=False)
        print(f"[Area] Guardado: {path}")
        return path
