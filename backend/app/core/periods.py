"""Aritmética de calendario con zona horaria del usuario (Fase 29 B1; Fase 34 B6).

Único lugar donde se resuelven "mes actual", "semana actual", rangos de días y el día
local de un instante (Fase 34, B6c: prohibido construir `datetime(...)` naive o resolver
"actual" desde UTC fuera de este módulo). Vive en `core/` porque lo importan módulos que no
son routers y no deben conocerse entre sí (`api/dashboard.py`, `core/budget_alerts.py`,
`core/weekly_summary.py`) — mismo criterio que `core/budget_recurrence.py`.

Funciones puras con `ahora` inyectado (nunca leen el reloj) y la zona (`ZoneInfo`) como
parámetro. **Todo límite devuelto es un datetime aware en UTC** (Fase 34, H5): comparar
contra `timestamptz` en Postgres y contra el UTC naive que guarda SQLite da lo mismo en los
dos motores. **El límite superior es siempre EXCLUSIVO** (Fase 31 B6): todo consumidor
compara con `< fin`, nunca `<=`.

`resolver_mes` valida lo que llega por query param (frontera de confianza); `rango_mes` NO
valida y jamás lanza por un mes futuro, solo acota el rango (ver su docstring).
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Se importa con alias porque `ValidationError` también es el nombre de la excepción de
# Pydantic, y en este módulo el dominio manda (H13: primer uso de la 422 de dominio).
from app.core.exceptions import ValidationError as DomainValidationError


def _a_utc(dt: datetime) -> datetime:
    """Normaliza a UTC aware; un datetime naive se lee como UTC (nunca como hora del servidor)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _medianoche_local(dia: date, tz: ZoneInfo) -> datetime:
    """00:00 locales de `dia` como instante aware en UTC."""
    return _a_utc(datetime.combine(dia, time.min, tzinfo=tz))


def dia_local(instante: datetime, tz: ZoneInfo) -> date:
    """Día de calendario de `instante` en la zona `tz`. Un `instante` naive se lee como UTC
    (así lo guarda SQLite y así se interpretan los datetimes naive de la API)."""
    return _a_utc(instante).astimezone(tz).date()


def instante_de_dia(dia: date, ahora: datetime, tz: ZoneInfo) -> datetime:
    """Instante UTC con el que se guarda una transacción cargada solo con un día (B9).

    Si `dia` es hoy en la zona del usuario → `ahora` (hora real del registro); si es otro
    día → las 12:00 locales de ese día (el mediodía hace al día robusto a un cambio de zona
    de ±12 h)."""
    if dia == dia_local(ahora, tz):
        return _a_utc(ahora)
    return _a_utc(datetime.combine(dia, time(12, 0), tzinfo=tz))


def limites_semana(instante: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """`[lunes 00:00 local, lunes siguiente 00:00 local)` de la semana lunes-domingo que
    contiene `instante`, en UTC aware. Fin exclusivo (Fase 34 H7)."""
    hoy = dia_local(instante, tz)
    lunes = hoy - timedelta(days=hoy.weekday())  # lunes = 0 ... domingo = 6
    return _medianoche_local(lunes, tz), _medianoche_local(lunes + timedelta(days=7), tz)


def rango_dias(inicio: date, fin: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """`[00:00 local de inicio, 00:00 local del día siguiente a fin)` en UTC aware — `fin`
    es un día INCLUIDO por el que llama; el límite devuelto es exclusivo."""
    return _medianoche_local(inicio, tz), _medianoche_local(fin + timedelta(days=1), tz)


def resolver_mes(year: int | None, month: int | None, ahora: datetime, tz: ZoneInfo) -> tuple[int, int, bool]:
    """Resuelve el período mensual pedido → `(year, month, es_mes_actual)`.

    Sin `year`/`month` devuelve el mes actual **en la zona `tz`** (Fase 34 B8); "mes futuro"
    se evalúa contra ese mes.

    `year`/`month` son entrada de usuario, así que acá sí se valida y cada falla es un
    422 de dominio con `detail` string — un `year=abc` lo rechaza FastAPI antes, con
    otra forma de respuesta (`{"detail": [...]}`).

    `year` se acota a un año de calendario real por el mismo motivo (H13): `datetime(0, 1, 1)`
    y `datetime(99999, 1, 1)` lanzan `ValueError`, que sin este chequeo terminaría como un 500.
    Los períodos se comparan como tuplas `(year, month)`, nunca con aritmética de días.
    """
    hoy = dia_local(ahora, tz)
    if year is None and month is None:
        return hoy.year, hoy.month, True
    if year is None or month is None:
        raise DomainValidationError("Se deben enviar `year` y `month`, o ninguno.")
    if not 1 <= month <= 12:
        raise DomainValidationError("`month` debe ser un número entre 1 y 12.")
    if not 1 <= year <= date.max.year:
        raise DomainValidationError(f"`year` debe ser un año entre 1 y {date.max.year}.")
    if (year, month) > (hoy.year, hoy.month):
        raise DomainValidationError("No se puede consultar un mes futuro.")
    return year, month, (year, month) == (hoy.year, hoy.month)


def rango_mes(year: int, month: int, ahora: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Acota un mes calendario de la zona `tz` a `[inicio, fin)` **semiabierto**, en
    datetimes aware UTC — `fin` es EXCLUSIVO (Fase 31 B6, QA-019; Fase 34 B6).

    El techo es `ahora` cuando el período es el mes en curso de la zona (igual que siempre) y
    las 00:00 locales del primer día del mes siguiente cuando no lo es (diciembre → 1 de
    enero del año siguiente). Una comparación `<=` contra ese valor perdería instantes con
    fracción de segundo y, peor, contaría la medianoche del mes siguiente.

    Todos los consumidores deben comparar con `< fin`, NUNCA `<= fin`. Por eso esta función
    se renombró desde `rango_mes_utc` (Fase 34, B6b: cambió la firma): un consumidor que
    alguien olvide actualizar es un `ImportError` inmediato, no una medianoche contada dos
    veces.

    **No valida nada y nunca lanza por un mes futuro.** Es deliberado: el motor de alertas
    llama a `spent_por_categoria_y_moneda` con el mes *futuro* de un presupuesto ya creado
    (presupuestos anticipados — `budget_alerts.evaluate_budget_thresholds_for_category` se
    dispara con la fecha de la transacción, que puede ser del mes siguiente), y ese mes se
    evalúa completo desde que existe. Si esta función validara "no hay mes futuro", el
    `ValidationError` caería en el `try/except` + `db.rollback()` de
    `evaluate_budget_thresholds_safely` (Decisión 13.3.4) y el motor de alertas moriría en
    silencio. Por eso la validación vive en `resolver_mes`, que solo atiende lo que llega
    por HTTP.

    Espera un mes de calendario válido (`year >= 1`, `1 <= month <= 12`); en otro caso
    `date(...)` lanza `ValueError`, que es un error de programación del caller.
    """
    inicio = _medianoche_local(date(year, month, 1), tz)
    siguiente = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    hoy = dia_local(ahora, tz)
    if (year, month) == (hoy.year, hoy.month):
        return inicio, _a_utc(ahora)
    return inicio, _medianoche_local(siguiente, tz)


RANGO_DESC = (
    "Día `YYYY-MM-DD` (interpretado en la zona horaria del usuario; `end_date` incluye todo ese día) "
    "o datetime ISO 8601 completo (instante; `end_date` inclusivo)."
)

_SOLO_DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parsear_limite(valor: str, nombre: str) -> date | datetime:
    try:
        if _SOLO_DIA.match(valor):
            return date.fromisoformat(valor)
        return datetime.fromisoformat(valor)
    except ValueError:
        raise DomainValidationError(f"`{nombre}` debe ser un día `YYYY-MM-DD` o un datetime ISO 8601 válido.") from None


def resolver_rango(
    start_date: str | None, end_date: str | None, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Resuelve los parámetros `start_date`/`end_date` de los endpoints de rango a
    `[inicio, fin)` en UTC aware, `fin` EXCLUSIVO (Fase 34, B7). Cada extremo acepta:

    - solo-día `YYYY-MM-DD` → se interpreta en la zona del usuario: inicio = 00:00 local del
      día, fin = 00:00 local del día SIGUIENTE (incluye todo el último día);
    - datetime completo → instante tal cual (un datetime naive se lee como UTC, igual que
      siempre); como `end_date` es inclusivo (`fin = end + 1 µs`, o sea `<= end`) para no
      cambiar el contrato de los clientes curl / API key.

    Un extremo ausente devuelve `None`. Todo consumidor compara `>= inicio` y `< fin`.
    Un valor ilegible es un 422 de dominio con `detail` string."""
    inicio = fin = None
    if start_date is not None:
        v = _parsear_limite(start_date, "start_date")
        inicio = _medianoche_local(v, tz) if type(v) is date else _a_utc(v)
    if end_date is not None:
        v = _parsear_limite(end_date, "end_date")
        fin = _medianoche_local(v + timedelta(days=1), tz) if type(v) is date else _a_utc(v) + timedelta(microseconds=1)
    return inicio, fin
