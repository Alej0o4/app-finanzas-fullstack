"""Zona horaria por usuario (Fase 34, Decisiones B1/B2).

Único punto de validación de zonas IANA: lo usan `PreferencesUpdate` (422 si es inválida),
y el registro por email / Google (si es inválida se cae al default, sin fallar).
"""

from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

DEFAULT_TIMEZONE = "America/Bogota"


@lru_cache(maxsize=1)
def _zonas_validas() -> frozenset[str]:
    return frozenset(available_timezones())


def es_zona_valida(nombre: str | None) -> bool:
    return isinstance(nombre, str) and nombre in _zonas_validas()


def zona_o_default(nombre: str | None) -> str:
    """Nombre válido tal cual; ausente o inválido → `DEFAULT_TIMEZONE` (registro, B5)."""
    return nombre if es_zona_valida(nombre) else DEFAULT_TIMEZONE


def get_zoneinfo(nombre: str | None) -> ZoneInfo:
    """`ZoneInfo` de la zona guardada de un usuario, con fallback al default."""
    return ZoneInfo(zona_o_default(nombre))
