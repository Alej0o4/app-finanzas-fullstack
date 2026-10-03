"""Normalización de texto para comparar nombres (Fase 16 §16.2, QA-028).

Vive en `core/` y no duplicado por router por la regla de que **ningún router importa otro
router**: `api/transactions.py` (resolución de categoría por nombre de Fase 16 §16.2) y
`api/categories.py` (unicidad de nombre por usuario y tipo, QA-028) comparan nombres con la
MISMA regla, pero uno no puede importar al otro. Es el mismo criterio que ya usan
`core/periods.py` y `core/default_categories.py`: un módulo chico de `core/` con funciones
puras, importado por los routers que lo necesitan.

Sin estado propio, sin dependencias y sin acceso a la base: una función pura `str -> str`.
"""

import unicodedata


def normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre para comparar sin acentos, mayúsculas ni espacios.

    "Alimentación" == "alimentacion" == "ALIMENTACIÓN" == "  Alimentación  " — la
    comparación case y acento-insensible de la Decisión 16.2.2, que es la que usa el
    resolver por nombre de `POST`/`PUT /transactions` y la que QA-028 extiende al chequeo
    de duplicados de `POST`/`PUT /categories`.

    `.lower()` y no `.casefold()` a propósito: es exactamente la transformación que la Fase
    16 ya tenía (y con la que se probó `test_default_categories_have_no_normalized_name_type_collisions`
    sobre el catálogo de sistema), así que el catálogo sembrado no cambia de significado al
    unificar la función. Para el español —y para los nombres de categoría del app— no hay
    diferencia observable entre las dos.
    """
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.strip().lower()
