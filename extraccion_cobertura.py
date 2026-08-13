"""
Corrientes (Argentina) - Forest_Cover_Percent anual 2015-2025,
exportado como CSV a Google Drive/ERA5_Corrientes/

FOREST_COVER  -> UMD/hansen/global_forest_change_2025_v1_13 (Hansen GFC v1.13)
    Un pixel cuenta como bosque en el anio Y si:
      - su cobertura de copa en el anio 2000 es >= TREE_COVER_THRESHOLD
        (o fue clasificado como "gain" entre 2000-2012), Y
      - todavia no perdio bosque para el anio Y (lossyear == 0, o
        lossyear > Y-2000).
    % = promedio de esa mascara 0/1 sobre la region (los pixeles
    enmascarados -agua / sin datos- se excluyen automaticamente).

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

YEARS = list(range(2015, 2026))
FOREST_SCALE = 30          # resolucion nativa de Hansen (m)
TREE_COVER_THRESHOLD = 30  # % de copa usado para definir "bosque" en 2000
TILE_SCALE = 4             # ayuda a evitar timeouts en reduceRegion

# ---------------------------------------------------------------------
# 3. Cobertura forestal (Hansen Global Forest Change)
# ---------------------------------------------------------------------
hansen = ee.Image("UMD/hansen/global_forest_change_2025_v1_13")
tree_cover_2000 = hansen.select("treecover2000")
loss_year = hansen.select("lossyear")        # 0 = sin perdida, 1-25 = 2001-2025
gain = hansen.select("gain")                 # ganancia registrada solo 2000-2012
datamask = hansen.select("datamask").eq(1)   # 1 = tierra valida (excluye agua)

forest_2000_mask = tree_cover_2000.gte(TREE_COVER_THRESHOLD).Or(gain)


def forest_percent(year):
    yr_code = year - 2000
    still_forest = (
        forest_2000_mask
        .And(loss_year.eq(0).Or(loss_year.gt(yr_code)))
        .rename("forest")
        .updateMask(datamask)
    )
    result = still_forest.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=FOREST_SCALE,
        maxPixels=1e13,
        bestEffort=True,
        tileScale=TILE_SCALE,
    )
    return ee.Number(result.get("forest")).multiply(100)


# ---------------------------------------------------------------------
# 4. Calcular todos los anios
# ---------------------------------------------------------------------
rows = []
for year in YEARS:
    print(f"Calculando {year} ...")
    f_pct = forest_percent(year).getInfo()
    rows.append(
        {
            "Year": year,
            "Forest_Cover_Percent": round(f_pct, 3) if f_pct is not None else None,
        }
    )
    print(rows[-1])

df = pd.DataFrame(rows)
print(df)

# ---------------------------------------------------------------------
# 5. Copia local + exportacion a Drive/ERA5_Corrientes
# ---------------------------------------------------------------------
local_csv = "Corrientes_Forest_Cover_2015_2025.csv"
df.to_csv(local_csv, index=False)
print(f"Copia local guardada en: {local_csv}")

