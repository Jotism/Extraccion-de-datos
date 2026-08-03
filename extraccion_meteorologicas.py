"""
Exporta variables diarias (2015-01-01 a 2025-12-31) para la provincia de
Corrientes (Argentina), usando Google Earth Engine.

Genera un grupo de tablas (una por cada año) con la siguiente estructura:

    Variables meteorológicas de ECMWF/ERA5/HOURLY (una fila por día):
       temperature_2m_d, max_temperature_2m_d, min_temperature_2m_d, 
       dewpoint_temperature_2m_d, humidity_d, surface_pressure_d,
       total_precipitation_d, u_component_of_wind_10m_d, v_component_of_wind_10m_d
     Se exportan en 11 tareas (una por año) hacia Google Drive.

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
# 3) Colección ERA5 Hourly con las bandas que vamos a necesitar
# --------------------------------------------------------------------
BANDS = [
    'temperature_2m',              # K
    'dewpoint_temperature_2m',     # K
    'surface_pressure',            # Pa
    'mean_total_precipitation_rate',  # kg/m^2/s == mm/s
    'u_component_of_wind_10m',     # m/s
    'v_component_of_wind_10m',     # m/s
]
era5_hourly = ee.ImageCollection('ECMWF/ERA5/HOURLY').select(BANDS)

SCALE = 27830  # resolución nativa de ERA5 (~27.8 km)

# Desfasaje horario opcional para alinear los "días" al huso de Argentina
# (ART = UTC-3). Con 0 los días se calculan en UTC. Con 3, el día
# calendario arranca a las 00:00 hora argentina.
OFFSET_HOURS = 0


def hourly_relative_humidity(img):
    """RH (%) por hora, a partir de temperatura y punto de rocío
    (aproximación de Magnus-Tetens, coeficientes de Alduchov & Eskridge)."""
    t_c = img.select('temperature_2m').subtract(273.15)
    td_c = img.select('dewpoint_temperature_2m').subtract(273.15)
    rh = img.expression(
        '100 * exp((17.625*Td)/(243.04+Td) - (17.625*T)/(243.04+T))',
        {'T': t_c, 'Td': td_c},
    ).rename('rh')
    return rh


def build_daily_collection(start_str, end_str):
    """
    FeatureCollection con variables meteorológicas diarias sobre
    'geometry', entre start_str (incluido) y end_str (excluido).
    """
    start = ee.Date(start_str)
    end = ee.Date(end_str)
    n_days = end.difference(start, 'day')

    def daily_feature(day_offset):
        day_offset = ee.Number(day_offset)
        d0 = start.advance(day_offset, 'day').advance(OFFSET_HOURS, 'hour')
        d1 = d0.advance(1, 'day')

        hourly = era5_hourly.filterDate(d0, d1)

        t2m = hourly.select('temperature_2m')
        temp_mean = t2m.mean().subtract(273.15).rename('temperature_2m_d')
        temp_max = t2m.max().subtract(273.15).rename('max_temperature_2m_d')
        temp_min = t2m.min().subtract(273.15).rename('min_temperature_2m_d')

        dewpoint_mean = (
            hourly.select('dewpoint_temperature_2m').mean().subtract(273.15)
            .rename('dewpoint_temperature_2m_d')
        )

        humidity_mean = hourly.map(hourly_relative_humidity).mean().rename('humidity_d')

        pressure_mean = (
            hourly.select('surface_pressure').mean().divide(100)
            .rename('surface_pressure_d')
        )

        # rate (mm/s) -> acumulado diario (mm): sumar 24 valores horarios y
        # llevar cada uno a "mm en esa hora" multiplicando por 3600 s.
        precip_total = (
            hourly.select('mean_total_precipitation_rate').sum().multiply(3600)
            .rename('total_precipitation_d')
        )

        u_mean = hourly.select('u_component_of_wind_10m').mean().rename('u_component_of_wind_10m_d')
        v_mean = hourly.select('v_component_of_wind_10m').mean().rename('v_component_of_wind_10m_d')

        daily_img = (
            temp_mean.addBands(temp_max).addBands(temp_min)
            .addBands(dewpoint_mean).addBands(humidity_mean)
            .addBands(pressure_mean).addBands(precip_total)
            .addBands(u_mean).addBands(v_mean)
        )

        stats = daily_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=SCALE,
            maxPixels=1e9,
        )

        return ee.Feature(None, {
            'date': start.advance(day_offset, 'day').format('YYYY-MM-dd'),
            'temperature_2m_d': stats.get('temperature_2m_d'),
            'max_temperature_2m_d': stats.get('max_temperature_2m_d'),
            'min_temperature_2m_d': stats.get('min_temperature_2m_d'),
            'dewpoint_temperature_2m_d': stats.get('dewpoint_temperature_2m_d'),
            'humidity_d': stats.get('humidity_d'),
            'surface_pressure_d': stats.get('surface_pressure_d'),
            'total_precipitation_d': stats.get('total_precipitation_d'),
            'u_component_of_wind_10m_d': stats.get('u_component_of_wind_10m_d'),
            'v_component_of_wind_10m_d': stats.get('v_component_of_wind_10m_d'),
        })

    days = ee.List.sequence(0, n_days.subtract(1))
    return ee.FeatureCollection(days.map(daily_feature))


COLUMNS = [
    'date', 'temperature_2m_d', 'max_temperature_2m_d', 'min_temperature_2m_d', 
    'dewpoint_temperature_2m_d', 'humidity_d', 'surface_pressure_d', 
    'total_precipitation_d', 'u_component_of_wind_10m_d', 'v_component_of_wind_10m_d',
]

# --------------------------------------------------------------------
# 4) Exportar variables meteorológicas, una tarea por año
# --------------------------------------------------------------------
tasks = []
for year in range(2015, 2026):
    start_str = f'{year}-01-01'
    end_str = f'{year + 1}-01-01'

    fc = build_daily_collection(start_str, end_str)

    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=f'Corrientes_variables_diarias_{year}',
        folder='ERA5_Corrientes',
        fileNamePrefix=f'corrientes_variables_diarias_{year}',
        fileFormat='CSV',
        selectors=COLUMNS,
    )
    task.start()
    tasks.append(task)
    print(f'[ERA5] Tarea enviada para {year}: {task.id}')

print('\nProgreso de las tareas:')
print('https://code.earthengine.google.com/tasks')
print('Las tablas se guardan en la carpeta "ERA5_Corrientes" en Google Drive')