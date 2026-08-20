"""
Clase base para las extracciones de datos de Earth Engine.

Se encarga de:
  - autenticar / inicializar Earth Engine una sola vez por instancia
  - resolver la geometría de la zona de interés (país + provincia/estado)
    a partir de un dataset administrativo FAO/GAUL
"""

import ee


class BaseEEExtractor:
    """
    Clase base de la que heredan todos los extractores.

    Cada extractor concreto recibe la zona de interés (país + división
    administrativa nivel 1) y, si corresponde, el rango de años a
    extraer. La geometría se resuelve de forma perezosa (lazy) la
    primera vez que se usa.
    """

    #: Dataset administrativo por defecto (limites nivel 1: provincias/estados)
    DEFAULT_ADMIN_DATASET = "FAO/GAUL/2015/level1"

    def __init__(self, admin0_name, admin1_name, admin_dataset=None):
        """
        Parameters
        ----------
        admin0_name : str
            Nombre del país (propiedad ADM0_NAME), ej: "Argentina".
        admin1_name : str
            Nombre de la provincia/estado (propiedad ADM1_NAME),
            ej: "Corrientes".
        admin_dataset : str, optional
            Asset de Earth Engine con los límites administrativos a
            usar. Si no se especifica, cada clase usa su propio valor
            por defecto (ver DEFAULT_ADMIN_DATASET en cada subclase).
        """
        self.admin0_name = admin0_name
        self.admin1_name = admin1_name
        self.admin_dataset = admin_dataset or self.DEFAULT_ADMIN_DATASET

        self._initialize_ee()
        self._geometry = None

    @staticmethod
    def _initialize_ee():
        """Inicializa Earth Engine, autenticando de forma interactiva
        la primera vez que haga falta (una sola vez por sesión)."""
        try:
            ee.Initialize()
        except Exception:
            ee.Authenticate()
            ee.Initialize()

    @property
    def geometry(self):
        """Geometría (ee.Geometry) de la zona de interés, calculada
        una sola vez y cacheada."""
        if self._geometry is None:
            fc = ee.FeatureCollection(self.admin_dataset).filter(
                ee.Filter.And(
                    ee.Filter.eq("ADM0_NAME", self.admin0_name),
                    ee.Filter.eq("ADM1_NAME", self.admin1_name),
                )
            )
            self._geometry = fc.geometry()
        return self._geometry

    @property
    def zone_label(self):
        """Etiqueta legible de la zona, ej: 'Corrientes, Argentina'."""
        return f"{self.admin1_name}, {self.admin0_name}"

    @property
    def zone_slug(self):
        """Nombre de la zona apto para nombres de archivo."""
        return self.admin1_name.strip().lower().replace(" ", "_")

    def extract(self):
        """Debe implementarse en cada subclase: corre el cálculo en
        Earth Engine y devuelve un pandas.DataFrame (o similar)."""
        raise NotImplementedError

    def save(self, output_dir=".", filename=None):
        """Debe implementarse en cada subclase: llama a extract() y
        guarda el/los resultado(s) como CSV local."""
        raise NotImplementedError
