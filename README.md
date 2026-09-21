# Extracción de Datos Satelitales y Ambientales (Google Earth Engine)
**Proyecto: ESA-UNICEF Dengue Forecast Project**

Este repositorio contiene un pipeline modular en Python para extraer, procesar y unificar variables agroclimáticas, topográficas y biofísicas utilizando la API de **Google Earth Engine (GEE)**. Su propósito es generar datasets temporales a nivel subnacional (provincias/estados) listos para el entrenamiento y evaluación de modelos de **Inteligencia Artificial / Machine Learning** orientados al pronóstico epidemiológico del Dengue.

---

## 📋 Tabla de Contenidos
1. [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
2. [Fuentes de Datos y Variables](#-fuentes-de-datos-y-variables)
3. [Requisitos Previos e Instalación](#-requisitos-previos-e-instalación)
4. [Autenticación con Google Earth Engine](#-autenticación-con-google-earth-engine)
5. [Guía Paso a Paso: Cómo Usar `main.py`](#-guía-paso-a-paso-cómo-usar-mainpy)
6. [Estructura del Dataset Resultante](#-estructura-del-dataset-resultante)
7. [Consideraciones para el Entrenamiento de IA](#-consideraciones-para-el-entrenamiento-de-ia)

---

## 🏛 Arquitectura del Proyecto

El código está estructurado de manera modular y orientada a objetos dentro del paquete `ee_extractors/`:

```text
Extraccion-de-datos/
│
├── ee_extractors/
│   ├── __init__.py            # Exporta extractores y UnifiedDatasetBuilder
│   ├── base.py                # Clase base BaseEEExtractor (autenticación y geometría FAO/GAUL)
│   ├── area.py                # AreaExtractor: Área geográfica en km²
│   ├── meteorologicas.py      # MeteorologicalExtractor: Variables ERA5 por día (temperatura, precipitación, etc.)
│   ├── ndvi.py                # NDVIExtractor: Índice de vegetación MODIS (mensual)
│   ├── topograficas.py        # TopographicExtractor: Estadísticas de elevación SRTM (estática)
│   ├── cobertura.py           # ForestCoverExtractor: Cobertura y pérdida forestal Hansen (WIP)
│   └── dataset_builder.py     # UnifiedDatasetBuilder: Unifica todas las fuentes en frecuencia diaria
│
├── Resultados_tablas/         # Directorio de salida para los archivos CSV generados
├── credentials.json           # Configuración de credenciales de Google OAuth (si aplica)
├── main.py                    # Script ejecutor principal y punto de configuración
└── README.md                  # Documentación del proyecto
```

---

## 🛰 Fuentes de Datos y Variables

El sistema consulta colecciones globales curadas en Google Earth Engine y aplica reducciones espaciales (`reduceRegion`) sobre el polígono administrativo de la región:

| Módulo | Dataset Earth Engine | Resolución | Frecuencia original | Variables extraídas |
| :--- | :--- | :--- | :--- | :--- |
| **Límites / Geometría** | `FAO/GAUL/2015/level1` / `...SIMPLIFIED_500m` | Vectorial | Estático | Polígono de delimitación administrativa |
| **Área** | Geodesia sobre polígono GAUL | 1 m (tolerancia) | Estático | `area_km2` |
| **Meteorología** | `ECMWF/ERA5/HOURLY` | ~27.8 km (0.25°) | Horaria → Diaria | `temperature_2m_d` (media, máx, mín en K), `dewpoint_temperature_2m_d` (K), `humidity_d` (%), `surface_pressure_d` (Pa), `total_precipitation_d` (mm/día), viento a 10m (`u_component...`, `v_component...` en m/s) |
| **Vegetación** | `MODIS/061/MOD13A3` | 1 km | Mensual | `NDVI_d` (filtrado por calidad `SummaryQA <= 1`, escalado 0.0001) |
| **Topografía** | `CGIAR/SRTM90_V4` | 90 m | Estático | Elevación: mín, máx, media, desviación estándar y varianza en metros (`*_elevation_d`) |
| **Cobertura Forestal (WIP)** | `UMD/hansen/global_forest_change_2025_v1_13` | ~30 m | Anual | `Forest_Cover_Percent` (remanente respecto al año 2000) |

---

## ⚙ Requisitos Previos e Instalación

### 1. Entorno Python
Se recomienda Python 3.9 o superior. Crear y activar un entorno virtual:

```bash
# En Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Dependencias requeridas
Instalar las librerías necesarias mediante `pip`:

```bash
pip install earthengine-api pandas pycountry
```

---

## 🔑 Autenticación con Google Earth Engine

Para realizar consultas a GEE es indispensable contar con una cuenta de Google registrada en [Google Earth Engine](https://earthengine.google.com/) y asociada a un proyecto de Google Cloud (con la Earth Engine API habilitada).

1. Abre tu terminal con el entorno activado.
2. Ejecuta:
   ```bash
   earthengine authenticate
   ```
3. Se abrirá una ventana en el navegador para iniciar sesión con tu cuenta de Google y seleccionar tu proyecto de Google Cloud.
4. Al autorizar, las credenciales quedarán guardadas localmente en tu sistema (`~/.config/earthengine/credentials`).
5. *Nota:* El código (`BaseEEExtractor`) cuenta con manejo automático que intenta hacer `ee.Initialize()` y, si falla, invoca `ee.Authenticate()`.

---

## 🚀 Guía Paso a Paso: Cómo Usar `main.py`

El archivo `main.py` centraliza la configuración y ejecución de las extracciones.

### Paso 1: Configurar la Región y Período Temporal

Abre `main.py` y localiza el bloque de configuración (líneas 33 a 37):

```python
# ---------------------------------------------------------------------
# Configuración general: zona, rango de años y directorio de salida.
# ---------------------------------------------------------------------
ADMIN0_NAME = "Argentina"     # Nombre del país (según FAO/GAUL)
ADMIN1_NAME = "Corrientes"    # Nombre de la provincia / estado / departamento
START_YEAR = 2001             # Año inicial (inclusive)
END_YEAR = 2005               # Año final (inclusive)
OUTPUT_DIR = "Resultados_tablas"  # Carpeta donde se guardarán los CSVs
```

> **Consejo sobre nombres administrativos:**  
> Los nombres deben coincidir con la nomenclatura de la colección `FAO/GAUL/2015/level1`. Ejemplos: `ADMIN0_NAME = "Brazil"`, `ADMIN1_NAME = "Sao Paulo"`.  
> El script detecta automáticamente los códigos ISO (`AR`, `AR-W`, etc.) mediante `pycountry` y búsqueda difusa (*fuzzy matching*).

### Paso 2: Elegir el Modo de Extracción

En la función `main()` de `main.py`:

```python
def main():
    # Opción A: Descomentar para guardar archivos individuales por cada extractor
    # run_individual_extractions()

    # Opción B: Construir el dataset unificado diario listo para IA
    run_unified_dataset()
```

* **`run_unified_dataset()` (Recomendado para IA):**  
  Ejecuta todos los extractores, armoniza las diferentes resoluciones temporales (diaria, mensual, estática) y consolida una única tabla diaria en `Resultados_tablas/dataset_<pais>_<provincia>_<desde>-<hasta>.csv`.
* **`run_individual_extractions()`:**  
  Genera CSVs separados para cada variable (un archivo para el área, uno por año de meteorología, uno de NDVI mensual y uno de elevación).

### Paso 3: Ejecución

Ejecuta el script desde la raíz del proyecto:

```bash
python main.py
```

### Paso 4: Monitoreo del Progreso en Consola

Durante la ejecución verás mensajes informativos como:
```text
=== Dataset unificado ===
[Dataset] Extrayendo variables meteorológicas (base diaria) ...
  [2001-01] 31 días descargados
  [2001-02] 28 días descargados
  ...
[Dataset] Extrayendo NDVI (mensual) ...
[Dataset] Extrayendo area (estatica) ...
Area de Corrientes, Argentina: 89507.068 km2
[Dataset] Extrayendo variables topograficas (estaticas) ...
[Dataset] Guardado: Resultados_tablas/dataset_argentina_corrientes_2001-2001.csv (365 filas, 21 columnas)

Listo. Todos los CSV quedaron en la carpeta "Resultados_tablas/".
```

---

## 📊 Estructura del Dataset Resultante

El dataset diario unificado incluye las siguientes columnas en orden estandarizado:

| Columna | Tipo | Descripción | Unidad / Rango |
| :--- | :--- | :--- | :--- |
| `Date` | Fecha | Fecha de observación (`YYYY-MM-DD`) | Diaria |
| `Year` | Entero | Año | `2001 - ...` |
| `Month` | Entero | Mes del año | `1 - 12` |
| `country_code` | Texto | Código ISO 3166-1 alpha-2 del país | ej. `AR` |
| `region_code` | Texto | Código ISO 3166-2 de la subdivisión | ej. `AR-W` |
| `area_km2` | Decimal | Superficie total de la región | $km^2$ |
| `NDVI_d` | Decimal | Normalized Difference Vegetation Index mensual | $[-1.0, 1.0]$ |
| `dewpoint_temperature_2m_d` | Decimal | Temperatura del punto de rocío a 2m | Kelvin ($K$) |
| `humidity_d` | Decimal | Humedad relativa media calculada | Porcentaje ($0 - 100\%$) |
| `max_temperature_2m_d` | Decimal | Temperatura máxima diaria a 2m | Kelvin ($K$) |
| `min_temperature_2m_d` | Decimal | Temperatura mínima diaria a 2m | Kelvin ($K$) |
| `surface_pressure_d` | Decimal | Presión atmosférica en superficie | Pascales ($Pa$) |
| `temperature_2m_d` | Decimal | Temperatura media diaria a 2m | Kelvin ($K$) |
| `total_precipitation_d` | Decimal | Precipitación acumulada del día | Milímetros ($mm$) |
| `u_component_of_wind_10m_d`| Decimal | Vector de viento horizontal Este-Oeste | $m/s$ |
| `v_component_of_wind_10m_d`| Decimal | Vector de viento horizontal Norte-Sur | $m/s$ |
| `max_elevation_d` | Decimal | Elevación máxima del terreno | Metros ($m$) |
| `mean_elevation_d` | Decimal | Elevación promedio del terreno | Metros ($m$) |
| `min_elevation_d` | Decimal | Elevación mínima del terreno | Metros ($m$) |
| `stdDev_elevation_d` | Decimal | Desviación estándar de elevación | Metros ($m$) |
| `variance_elevation_d` | Decimal | Varianza de la elevación | $m^2$ |

---