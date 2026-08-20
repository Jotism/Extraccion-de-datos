"""
Variables meteorológicas diarias (ECMWF/ERA5/HOURLY) para una zona y
rango de años. Genera un DataFrame/CSV por año con:

    temperature_2m_d, max_temperature_2m_d, min_temperature_2m_d,
    dewpoint_temperature_2m_d, humidity_d, surface_pressure_d,
    total_precipitation_d, u_component_of_wind_10m_d, v_component_of_wind_10m_d

Los datos se traen mes a mes (getInfo) en vez de todo el año junto:
así cada pedido a Earth Engine es chico y no se golpea con el límite
de tiempo de cómputo de las llamadas interactivas.
"""

import os
import time

import ee
import pandas as pd

from .base import BaseEEExtractor


class MeteorologicalExtractor(BaseEEExtractor):
    """Extrae variables meteorológicas diarias de ERA5 para una zona."""

    DEFAULT_ADMIN_DATASET = "FAO/GAUL_SIMPLIFIED_500m/2015/level1"
    ERA5_ASSET = "ECMWF/ERA5/HOURLY"
    BANDS = [
        "temperature_2m",              # K
        "dewpoint_temperature_2m",     # K
        "surface_pressure",            # Pa
        "mean_total_precipitation_rate",  # kg/m^2/s == mm/s
        "u_component_of_wind_10m",     # m/s
        "v_component_of_wind_10m",     # m/s
    ]
    SCALE = 27830  # resolución nativa de ERA5 (~27.8 km)

    COLUMNS = [
        "date", "temperature_2m_d", "max_temperature_2m_d", "min_temperature_2m_d",
        "dewpoint_temperature_2m_d", "humidity_d", "surface_pressure_d",
        "total_precipitation_d", "u_component_of_wind_10m_d", "v_component_of_wind_10m_d",
    ]

    def __init__(self, admin0_name, admin1_name, start_year, end_year,
                 offset_hours=0, admin_dataset=None,
                 max_retries=3, retry_wait=5):
        """
        Parameters
        ----------
        start_year, end_year : int
            Rango de años (inclusive) a extraer.
        offset_hours : int
            Desfasaje horario para alinear los "días" a un huso
            horario distinto de UTC (ej. 3 para Argentina, ART=UTC-3).
        max_retries, retry_wait : int
            Reintentos y espera (segundos) ante fallos transitorios
            al pedir datos a Earth Engine.
        """
        super().__init__(admin0_name, admin1_name, admin_dataset)
        self.start_year = start_year
        self.end_year = end_year
        self.offset_hours = offset_hours
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self._era5_hourly = ee.ImageCollection(self.ERA5_ASSET).select(self.BANDS)

    @staticmethod
    def _hourly_relative_humidity(img):
        """RH (%) por hora, a partir de temperatura y punto de rocío
        (aproximación de Magnus-Tetens, coeficientes de Alduchov &
        Eskridge)."""
        t_c = img.select("temperature_2m").subtract(273.15)
        td_c = img.select("dewpoint_temperature_2m").subtract(273.15)
        rh = img.expression(
            "100 * exp((17.625*Td)/(243.04+Td) - (17.625*T)/(243.04+T))",
            {"T": t_c, "Td": td_c},
        ).rename("rh")
        return rh

    def _build_daily_collection(self, start_str, end_str):
        """FeatureCollection con variables diarias entre start_str
        (incluido) y end_str (excluido)."""
        start = ee.Date(start_str)
        end = ee.Date(end_str)
        n_days = end.difference(start, "day")

        def daily_feature(day_offset):
            day_offset = ee.Number(day_offset)
            d0 = start.advance(day_offset, "day").advance(self.offset_hours, "hour")
            d1 = d0.advance(1, "day")

            hourly = self._era5_hourly.filterDate(d0, d1)

            t2m = hourly.select("temperature_2m")
            temp_mean = t2m.mean().rename("temperature_2m_d")
            temp_max = t2m.max().rename("max_temperature_2m_d")
            temp_min = t2m.min().rename("min_temperature_2m_d")

            dewpoint_mean = (
                hourly.select("dewpoint_temperature_2m").mean()
                .rename("dewpoint_temperature_2m_d")
            )

            humidity_mean = hourly.map(self._hourly_relative_humidity).mean().rename("humidity_d")

            pressure_mean = (
                hourly.select("surface_pressure").mean()
                .rename("surface_pressure_d")
            )

            # rate (mm/s) -> acumulado diario (mm): sumar 24 valores
            # horarios y llevar cada uno a "mm en esa hora" (x 3600 s).
            precip_total = (
                hourly.select("mean_total_precipitation_rate").sum().multiply(3600)
                .rename("total_precipitation_d")
            )

            u_mean = hourly.select("u_component_of_wind_10m").mean().rename("u_component_of_wind_10m_d")
            v_mean = hourly.select("v_component_of_wind_10m").mean().rename("v_component_of_wind_10m_d")

            daily_img = (
                temp_mean.addBands(temp_max).addBands(temp_min)
                .addBands(dewpoint_mean).addBands(humidity_mean)
                .addBands(pressure_mean).addBands(precip_total)
                .addBands(u_mean).addBands(v_mean)
            )

            stats = daily_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=self.geometry,
                scale=self.SCALE,
                maxPixels=1e9,
            )

            return ee.Feature(None, {
                "date": start.advance(day_offset, "day").format("YYYY-MM-dd"),
                "temperature_2m_d": stats.get("temperature_2m_d"),
                "max_temperature_2m_d": stats.get("max_temperature_2m_d"),
                "min_temperature_2m_d": stats.get("min_temperature_2m_d"),
                "dewpoint_temperature_2m_d": stats.get("dewpoint_temperature_2m_d"),
                "humidity_d": stats.get("humidity_d"),
                "surface_pressure_d": stats.get("surface_pressure_d"),
                "total_precipitation_d": stats.get("total_precipitation_d"),
                "u_component_of_wind_10m_d": stats.get("u_component_of_wind_10m_d"),
                "v_component_of_wind_10m_d": stats.get("v_component_of_wind_10m_d"),
            })

        days = ee.List.sequence(0, n_days.subtract(1))
        return ee.FeatureCollection(days.map(daily_feature))

    def _fc_to_dataframe(self, fc):
        """Trae una ee.FeatureCollection como pandas.DataFrame vía
        getInfo(), con reintentos ante fallos transitorios."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                info = fc.getInfo()
                rows = [f["properties"] for f in info["features"]]
                return pd.DataFrame(rows)
            except Exception as err:  # noqa: BLE001
                last_err = err
                print(f"    reintento {attempt}/{self.max_retries} tras error: {err}")
                time.sleep(self.retry_wait)
        raise last_err

    def extract_year(self, year):
        """Devuelve el DataFrame diario de un único año, trayendo los
        datos mes a mes."""
        year_frames = []
        for month in range(1, 13):
            start_str = f"{year}-{month:02d}-01"
            end_str = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"

            fc = self._build_daily_collection(start_str, end_str)
            df_month = self._fc_to_dataframe(fc)
            year_frames.append(df_month)
            print(f"  [{year}-{month:02d}] {len(df_month)} días descargados")
            time.sleep(0.2)  # ser prolijo con la API

        df_year = pd.concat(year_frames, ignore_index=True)
        df_year = df_year[self.COLUMNS].sort_values("date").reset_index(drop=True)
        return df_year

    def extract(self):
        """Devuelve un dict {year: DataFrame} para todo el rango de años."""
        return {
            year: self.extract_year(year)
            for year in range(self.start_year, self.end_year + 1)
        }

    def save(self, output_dir="salidas_corrientes"):
        """Guarda un CSV por año en output_dir. Devuelve la lista de
        rutas generadas."""
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        for year in range(self.start_year, self.end_year + 1):
            df_year = self.extract_year(year)
            filename = f"{self.zone_slug}_variables_meteorologicas_{year}.csv"
            path = os.path.join(output_dir, filename)
            df_year.to_csv(path, index=False)
            print(f"[ERA5] Guardado: {path} ({len(df_year)} filas)\n")
            paths.append(path)
        return paths
