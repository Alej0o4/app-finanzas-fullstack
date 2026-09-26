"""Resolución y acotado de períodos mensuales en UTC (Fase 29, Decisión B1).

Vive en `core/` porque lo importan dos módulos que no son routers y no deben conocerse
entre sí: `api/dashboard.py` (navegación por mes del dashboard) y `core/budget_alerts.py`
("cuánto gasté" de un presupuesto) — mismo criterio que `core/budget_recurrence.py`.

Dos funciones puras con `ahora` inyectado, deliberadamente separadas:

- `resolver_mes` valida lo que llega por query param (frontera de confianza) y devuelve
  además si el período es el mes en curso.
- `limites_mes_utc` NO valida y jamás lanza por un mes futuro; solo acota el rango.

Que la validación viva en una y no en la otra no es una asimetría estética: ver el
docstring de `limites_mes_utc`.

La semántica de mes es UTC, no la hora local del dueño (supuesto 1 de la fase). El
desfase resultante en el borde de mes (desde las 19:00 hora Bogotá del último día el
"mes actual" UTC ya es el siguiente) se acepta y está registrado en `docs/TODO.md` (H11).
"""

from calendar import monthrange
from datetime import datetime

# Se importa con alias porque `ValidationError` también es el nombre de la excepción de
# Pydantic, y en este módulo el dominio manda (H13: primer uso de la 422 de dominio).
from app.core.exceptions import ValidationError as DomainValidationError


def resolver_mes(year: int | None, month: int | None, ahora: datetime) -> tuple[int, int, bool]:
    """Resuelve el período mensual pedido → `(year, month, es_mes_actual)`.

    Sin `year`/`month` devuelve el mes actual UTC, que es el comportamiento de siempre
    (historia 47: los endpoints sin parámetros responden exactamente como antes).

    `year`/`month` son entrada de usuario, así que acá sí se valida y cada falla es un
    422 de dominio con `detail` string — un `year=abc` lo rechaza FastAPI antes, con
    otra forma de respuesta (`{"detail": [...]}`).

    `year` se acota a un año de calendario real por el mismo motivo (H13): `datetime(0, 1, 1)`
    y `datetime(99999, 1, 1)` lanzan `ValueError`, que sin este chequeo terminaría como un 500.
    Los períodos se comparan como tuplas `(year, month)`, nunca con aritmética de días.
    """
    if year is None and month is None:
        return ahora.year, ahora.month, True
    if year is None or month is None:
        raise DomainValidationError("Se deben enviar `year` y `month`, o ninguno.")
    if not 1 <= month <= 12:
        raise DomainValidationError("`month` debe ser un número entre 1 y 12.")
    if not 1 <= year <= datetime.max.year:
        raise DomainValidationError(f"`year` debe ser un año entre 1 y {datetime.max.year}.")
    if (year, month) > (ahora.year, ahora.month):
        raise DomainValidationError("No se puede consultar un mes futuro.")
    return year, month, (year, month) == (ahora.year, ahora.month)


def limites_mes_utc(year: int, month: int, ahora: datetime) -> tuple[datetime, datetime]:
    """Acota un mes calendario a `(inicio, limite)` en datetimes **naive** UTC.

    El techo es `ahora` cuando el período es el mes en curso y el último día a las
    23:59:59 cuando no lo es. Es la semántica exacta que tenía el cálculo inline de
    `budget_alerts.spent_por_categoria_y_moneda` y que comparten ahora el summary y los
    presupuestos del dashboard (H9: la lógica estaba copiada en tres sitios).

    **No valida nada y nunca lanza por un mes futuro.** Es deliberado: el motor de
    alertas llama a `spent_por_categoria_y_moneda` con el mes *futuro* de un presupuesto
    ya creado (presupuestos anticipados — `budget_alerts.evaluate_budget_thresholds_for_
    category` se dispara con la fecha de la transacción, que puede ser del mes
    siguiente), y ese mes se evalúa completo desde que existe. Si esta función validara
    "no hay mes futuro", el `ValidationError` caería en el `try/except` + `db.rollback()`
    de `evaluate_budget_thresholds_safely` (Decisión 13.3.4) y el motor de alertas
    moriría en silencio: la transacción se guardaría pero nunca se avisaría ningún
    umbral. Por eso la validación vive en `resolver_mes`, que solo atiende lo que llega
    por HTTP.

    Espera un mes de calendario válido (`year >= 1`, `1 <= month <= 12`); en otro caso
    `datetime(...)` lanza `ValueError`, que es un error de programación del caller, no
    una condición de negocio.
    """
    inicio = datetime(year, month, 1)
    ultimo_dia = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
    if (year, month) == (ahora.year, ahora.month):
        # `replace(tzinfo=None)` quita la zona; en un `ahora` ya naive es un no-op.
        return inicio, ahora.replace(tzinfo=None)
    return inicio, ultimo_dia
