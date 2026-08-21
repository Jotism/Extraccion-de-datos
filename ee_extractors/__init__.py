"""
Paquete de extractores de datos geoespaciales (Google Earth Engine)
para una zona administrativa (país + provincia/estado) determinada.

Todas las clases heredan de BaseEEExtractor, que maneja la
autenticación/inicialización de Earth Engine y la resolución de la
geometría de la zona.
"""

from .base import BaseEEExtractor
from .area import AreaExtractor
from .cobertura import ForestCoverExtractor
from .meteorologicas import MeteorologicalExtractor
from .ndvi import NDVIExtractor
from .topograficas import TopographicExtractor
from .dataset_builder import UnifiedDatasetBuilder

__all__ = [
    "BaseEEExtractor",
    "AreaExtractor",
    "ForestCoverExtractor",
    "MeteorologicalExtractor",
    "NDVIExtractor",
    "TopographicExtractor",
    "UnifiedDatasetBuilder",
]