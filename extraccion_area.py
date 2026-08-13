"""
Corrientes (Argentina) - Area de la provincia en km2, calculada con Earth
Engine y exportada como CSV a Google Drive/ERA5_Corrientes/

Fuente: FAO/GAUL/2015/level1 (limites administrativos nivel 1)

Requisitos:
    pip install earthengine-api pandas
    earthengine authenticate      # una vez, en forma interactiva
"""

import ee
import pandas as pd

# ---------------------------------------------------------------------
# 1. Autenticacion e inicializacion
# ---------------------------------------------------------------------
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()

# ---------------------------------------------------------------------
# 2. Region de interes: provincia de Corrientes, Argentina
# ---------------------------------------------------------------------
admin1 = ee.FeatureCollection("FAO/GAUL/2015/level1")
corrientes = admin1.filter(
    ee.Filter.And(
        ee.Filter.eq("ADM0_NAME", "Argentina"),
        ee.Filter.eq("ADM1_NAME", "Corrientes"),
    )
)
region = corrientes.geometry()

# ---------------------------------------------------------------------
# 3. Calcular area en km2
# ---------------------------------------------------------------------
# geometry().area() devuelve el area en m2 (usa la geodesia real, no una
# proyeccion plana), maxError en metros para la tolerancia de calculo.
area_m2 = region.area(maxError=1)
area_km2 = ee.Number(area_m2).divide(1e6)

area_km2_value = area_km2.getInfo()
print(f"Area de Corrientes: {area_km2_value:.3f} km2")

# ---------------------------------------------------------------------
# 4. Guardar CSV local + exportar a Drive/ERA5_Corrientes
# ---------------------------------------------------------------------
df = pd.DataFrame([{"Provincia": "Corrientes", "Area_km2": round(area_km2_value, 3)}])
print(df)

local_csv = "Corrientes_Area_km2.csv"
df.to_csv(local_csv, index=False)
print(f"Copia local guardada en: {local_csv}")