"""
Exporta el NDVI MENSUAL (2015-01 a 2025-12) de la provincia de Corrientes
(Argentina), usando el producto MODIS/061/MOD13A3.

MOD13A3 es el producto mensual "oficial" de MODIS Terra (1 km): se genera
promediando con pesos los compuestos de 16 días (MOD13A2) que caen dentro
de cada mes.

Requisitos previos:
  pip install earthengine-api
  Un proyecto de Google Cloud con la Earth Engine API habilitada.
"""

import ee

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
# 3) NDVI mensual MODIS (1 km)
# --------------------------------------------------------------------
SCALE = 1000

modis_monthly = (
    ee.ImageCollection('MODIS/061/MOD13A3')
    .filterDate('2015-01-01', '2026-01-01')
    .filterBounds(geometry)
    .select(['NDVI', 'SummaryQA'])
)


def monthly_ndvi_feature(img):
    # SummaryQA: 0 = buena calidad, 1 = marginal, 2 = nieve/hielo, 3 = nublado
    qa_mask = img.select('SummaryQA').lte(1)
    ndvi_img = img.select('NDVI').updateMask(qa_mask).multiply(0.0001).rename('NDVI_d')

    stats = ndvi_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=SCALE,
        maxPixels=1e9,
    )

    date = img.date()
    return ee.Feature(None, {
        'year': date.get('year'),
        'month': date.get('month'),
        'date': date.format('YYYY-MM'),
        'NDVI_d': stats.get('NDVI_d'),
    })


ndvi_monthly_fc = ee.FeatureCollection(modis_monthly.map(monthly_ndvi_feature))

# --------------------------------------------------------------------
# 4) Exportar a Drive
# --------------------------------------------------------------------
task = ee.batch.Export.table.toDrive(
    collection=ndvi_monthly_fc,
    description='Corrientes_NDVI_mensual_MOD13A3_2015_2025',
    folder='ERA5_Corrientes',
    fileNamePrefix='corrientes_ndvi_mensual_2015_2025',
    fileFormat='CSV',
    selectors=['date', 'year', 'month', 'NDVI_d'],
)
task.start()

print(f'Tarea de NDVI mensual enviada: {task.id}')
print('Progreso de la tarea: https://code.earthengine.google.com/tasks')
print('Se guarda como "corrientes_ndvi_mensual_2015_2025.csv" en la carpeta "ERA5_Corrientes" en Drive.')