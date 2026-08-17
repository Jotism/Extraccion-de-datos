"""
Exporta variables de elevacion de la provincia de Corrientes
(Argentina), usando el producto CGIAR/SRTM90_V4, y las guarda como CSV
LOCAL (con pandas) en vez de subirlas a Google Drive.

SRTM90_V4 es el conjunto de datos de elevación digital de la Misión
Topográfica con Radar del Transbordador (SRTM), se produjo originalmente
para proporcionar datos de elevación coherentes y de alta calidad con un
alcance casi global.

Requisitos previos:
  pip install earthengine-api pandas
  Un proyecto de Google Cloud con la Earth Engine API habilitada.
"""
import os

import ee
import pandas as pd

# --------------------------------------------------------------------
# 1) Autenticación e inicialización
# --------------------------------------------------------------------
ee.Authenticate()
ee.Initialize()

# --------------------------------------------------------------------
# 2) Región de interés: provincia de Corrientes, Argentina
# --------------------------------------------------------------------
corrientes_fc = (
    ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level1')
    .filter(ee.Filter.eq('ADM0_NAME', 'Argentina'))
    .filter(ee.Filter.eq('ADM1_NAME', 'Corrientes'))
)
geometry = corrientes_fc.geometry()

# --------------------------------------------------------------------
# 3) Construimos la coleccion a exportar
# --------------------------------------------------------------------
srtm = ee.Image("CGIAR/SRTM90_V4").select('elevation')

combined_reducer = ee.Reducer.min() \
    .combine(reducer2=ee.Reducer.max(), sharedInputs=True) \
    .combine(reducer2=ee.Reducer.mean(), sharedInputs=True) \
    .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True) \
    .combine(reducer2=ee.Reducer.variance(), sharedInputs=True)

stats = srtm.reduceRegion(
    reducer=combined_reducer,
    geometry=geometry,
    scale=90,
    maxPixels=1e9
)

stats_feature = ee.Feature(None, {
    'region': 'Corrientes, Argentina',
    'min_elevation_d': stats.get('elevation_min'),
    'max_elevation_d': stats.get('elevation_max'),
    'mean_elevation_d': stats.get('elevation_mean'),
    'stdDev_elevation_d': stats.get('elevation_stdDev'),
    'variance_elevation_d': stats.get('elevation_variance')
})

stats_collection = ee.FeatureCollection([stats_feature])

# --------------------------------------------------------------------
# 4) Traer el resultado (getInfo) y guardar CSV local
# --------------------------------------------------------------------
OUTPUT_DIR = 'salidas_corrientes'
os.makedirs(OUTPUT_DIR, exist_ok=True)

info = stats_collection.getInfo()
df = pd.DataFrame([f['properties'] for f in info['features']])
df = df[['region', 'min_elevation_d', 'max_elevation_d', 'mean_elevation_d',
         'stdDev_elevation_d', 'variance_elevation_d']]

output_path = os.path.join(OUTPUT_DIR, 'corrientes_variables_elevacion.csv')
df.to_csv(output_path, index=False)

print(f'Guardado: {output_path}')
print(df.to_string(index=False))