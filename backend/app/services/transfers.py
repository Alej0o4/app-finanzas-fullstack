"""Transferencias entre cuentas propias (Fase 39, docs/specs/fase_39_spec.md).

Una transferencia mueve saldos y **no es flujo**: vive en su propia tabla (`transfers`), no crea
filas en `Transaction` y ningún KPI, dona, Analítica, presupuesto, alerta ni resumen semanal la
lee (D1). Soporta cambio de moneda con `amount_out`/`amount_in` y deriva la tasa (D2/D9).

Dos mitades, como `cdt.py`: funciones **puras** arriba (solo `Decimal`; la aritmética de calendario
vive en `core/periods.py`) y casos de uso con DB abajo, que **no comitean** (el router es dueño de
la transacción SQL). Los saldos se mueven con `ledger.aplicar_deltas` (SQL atómico, orden fijo por
id de cuenta, D7) y las cuentas involucradas se bloquean con `FOR UPDATE` en ese mismo orden.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import AccountNotFoundError, BadRequestError, ConflictError, NotFoundError, ValidationError
from app.core.periods import instante_de_dia, resolver_rango
from app.core.timezones import get_zoneinfo
from app.models import models
from app.services import ledger

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
MONEDA_BASE = "COP"
_TOPE_MONTO = Decimal(10) ** 12  # Numeric(14,2): 12 dígitos enteros
_MSG_NO_EXISTE = "La transferencia no existe o no tienes permisos."


# --------------------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------------------
def calcular_monto_entrada(
    moneda_salida: str,
    moneda_entrada: str,
    monto_salida: Decimal,
    monto_entrada: Decimal | None,
    tasa: Decimal | None,
) -> Decimal:
    """Monto que entra al destino (D2/D9).

    Misma moneda: entra lo mismo que sale (`amount_in` ausente o igual; `exchange_rate` es 422).
    Monedas distintas: exactamente uno de `amount_in` / `exchange_rate`. La tasa se expresa SIEMPRE
    como COP por 1 unidad de la moneda extranjera, sea cual sea el sentido, y solo aplica a pares con
    COP (sin COP se exige `amount_in`). Redondeo `ROUND_HALF_UP` a centavo."""
    if moneda_salida == moneda_entrada:
        if tasa is not None:
            raise ValidationError("`exchange_rate` no aplica entre cuentas de la misma moneda.")
        if monto_entrada is not None and monto_entrada != monto_salida:
            raise ValidationError("Entre cuentas de la misma moneda, `amount_in` debe ser igual a `amount_out`.")
        return monto_salida
    if (monto_entrada is None) == (tasa is None):
        raise ValidationError("Entre monedas distintas envía exactamente uno de `amount_in` o `exchange_rate`.")
    if tasa is None:
        return monto_entrada
    if MONEDA_BASE not in (moneda_salida, moneda_entrada):
        raise ValidationError(f"`exchange_rate` solo aplica a pares con {MONEDA_BASE}; envía `amount_in`.")
    # tasa = COP por 1 unidad extranjera: COP -> extranjera divide, extranjera -> COP multiplica.
    bruto = monto_salida / tasa if moneda_salida == MONEDA_BASE else monto_salida * tasa
    resultado = bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if resultado <= 0:
        raise ValidationError("Con esa tasa el monto de entrada se redondea a cero.")
    if resultado >= _TOPE_MONTO:
        raise ValidationError("Con esa tasa el monto de entrada excede el máximo permitido.")
    return resultado


def tasa_implicita(
    moneda_salida: str, monto_salida: Decimal, moneda_entrada: str, monto_entrada: Decimal
) -> Decimal | None:
    """COP por 1 unidad extranjera implícita en la transferencia, o `None` si es de una sola moneda
    o no involucra COP (D9). Dato derivado: no se persiste."""
    if moneda_salida == moneda_entrada:
        return None
    if moneda_salida == MONEDA_BASE:
        return (monto_salida / monto_entrada).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if moneda_entrada == MONEDA_BASE:
        return (monto_entrada / monto_salida).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return None


def instante_de_fecha(valor: date | datetime | None, ahora: datetime, tz) -> datetime:
    """Instante con el que se guarda la transferencia (D13, mismas reglas que `Transaction`): solo-día
    → hora real si es hoy en la zona del usuario, 12:00 locales si es otro día; datetime → tal cual
    (un naive se lee como UTC); ausente → ahora."""
    if valor is None:
        return ahora
    if isinstance(valor, datetime):
        return valor
    return instante_de_dia(valor, ahora, tz)


# --------------------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------------------
def _nombres_cdt(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {c.id: c.name for c in db.query(models.Cdt).filter(models.Cdt.id.in_(ids)).all()}


def a_respuesta(t: models.Transfer, nombre_cdt: str | None = None, warnings: list[dict] | None = None) -> dict:
    return {
        "id": t.id,
        "from_account_id": t.from_account_id,
        "to_account_id": t.to_account_id,
        "cdt_id": t.cdt_id,
        "cdt_name": nombre_cdt,
        "amount_out": t.amount_out,
        "currency_out": t.currency_out,
        "amount_in": t.amount_in,
        "currency_in": t.currency_in,
        "exchange_rate": tasa_implicita(t.currency_out, t.amount_out, t.currency_in, t.amount_in),
        "date": t.date,
        "description": t.description,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "warnings": warnings or [],
    }


def respuestas(db: Session, transferencias: list[models.Transfer]) -> list[dict]:
    nombres = _nombres_cdt(db, {t.cdt_id for t in transferencias if t.cdt_id is not None})
    return [a_respuesta(t, nombres.get(t.cdt_id)) for t in transferencias]


# --------------------------------------------------------------------------------------
# Acceso y locks
# --------------------------------------------------------------------------------------
def bloquear_cuentas(db: Session, user_id: int, ids: set[int | None]) -> dict[int, models.Account]:
    """Cuentas del usuario con `FOR UPDATE` en orden ascendente de id (D7: evita deadlocks entre
    transferencias cruzadas). Una cuenta ajena o borrada es 404, sin distinguir."""
    ids_reales = sorted(i for i in ids if i is not None)
    cuentas = {
        c.id: c
        for c in db.query(models.Account)
        .filter(models.Account.id.in_(ids_reales), models.Account.user_id == user_id)
        .order_by(models.Account.id)
        .with_for_update()
        .all()
    }
    if len(cuentas) != len(ids_reales):
        raise AccountNotFoundError()
    return cuentas


def _obtener(db: Session, user_id: int, transfer_id: int, *, bloquear: bool = False) -> models.Transfer:
    consulta = db.query(models.Transfer).filter(models.Transfer.id == transfer_id, models.Transfer.user_id == user_id)
    if bloquear:
        consulta = consulta.with_for_update()
    t = consulta.first()
    if t is None:
        raise NotFoundError(_MSG_NO_EXISTE)
    return t


def _rechazar_si_cdt(t: models.Transfer) -> None:
    if t.cdt_id is not None:
        raise ConflictError("Esta transferencia pertenece a un CDT; se administra desde el CDT.")


def avisos(db: Session, cuenta: models.Account) -> list[dict]:
    """`BELOW_COMMITTED` (D6): si tras mover el saldo la cuenta de origen queda por debajo de lo
    comprometido en sus sobres activos. Solo informa: nunca bloquea. Va tras aplicar los deltas."""
    db.refresh(cuenta)
    comprometido = (
        db.query(func.sum(models.FundEntry.amount))
        .join(models.Fund, models.Fund.id == models.FundEntry.fund_id)
        .filter(models.Fund.account_id == cuenta.id, models.Fund.status == "active")
        .scalar()
    ) or CERO
    if comprometido > 0 and cuenta.balance < comprometido:
        return [
            {
                "code": "BELOW_COMMITTED",
                "account_id": cuenta.id,
                "currency": cuenta.currency,
                "committed": comprometido,
                "balance_after": cuenta.balance,
            }
        ]
    return []


# --------------------------------------------------------------------------------------
# Casos de uso (no comitean)
# --------------------------------------------------------------------------------------
def listar(
    db: Session,
    user: models.User,
    *,
    account_id: int | None,
    start_date: str | None,
    end_date: str | None,
    skip: int,
    limit: int,
) -> tuple[list[dict], int]:
    inicio, fin = resolver_rango(start_date, end_date, get_zoneinfo(user.timezone))
    if inicio is not None and fin is not None and inicio >= fin:
        raise BadRequestError("La fecha inicial no puede ser mayor que la fecha final.")
    consulta = db.query(models.Transfer).filter(models.Transfer.user_id == user.id)
    if account_id is not None:
        consulta = consulta.filter(
            or_(models.Transfer.from_account_id == account_id, models.Transfer.to_account_id == account_id)
        )
    if inicio is not None:
        consulta = consulta.filter(models.Transfer.date >= inicio)
    if fin is not None:
        consulta = consulta.filter(models.Transfer.date < fin)
    total = consulta.with_entities(func.count()).scalar()
    filas = consulta.order_by(models.Transfer.date.desc(), models.Transfer.id.desc()).offset(skip).limit(limit).all()
    return respuestas(db, filas), total


def detalle(db: Session, user: models.User, transfer_id: int) -> dict:
    return respuestas(db, [_obtener(db, user.id, transfer_id)])[0]


def crear(db: Session, user: models.User, datos, ahora: datetime) -> dict:
    cuentas = bloquear_cuentas(db, user.id, {datos.from_account_id, datos.to_account_id})
    origen, destino = cuentas[datos.from_account_id], cuentas[datos.to_account_id]
    monto_entrada = calcular_monto_entrada(
        origen.currency, destino.currency, datos.amount_out, datos.amount_in, datos.exchange_rate
    )
    t = models.Transfer(
        user_id=user.id,
        from_account_id=origen.id,
        to_account_id=destino.id,
        amount_out=datos.amount_out,
        currency_out=origen.currency,
        amount_in=monto_entrada,
        currency_in=destino.currency,
        date=instante_de_fecha(datos.date, ahora, get_zoneinfo(user.timezone)),
        description=datos.description,
    )
    db.add(t)
    db.flush()
    ledger.aplicar_deltas(db, ledger.deltas_transferencia(origen.id, destino.id, t.amount_out, t.amount_in))
    db.refresh(t)
    return a_respuesta(t, warnings=avisos(db, origen))


def actualizar(db: Session, user: models.User, transfer_id: int, datos, ahora: datetime) -> dict:
    """Revierte el efecto anterior y aplica el nuevo en un solo juego de UPDATE ordenado por id (D7)."""
    t = _obtener(db, user.id, transfer_id, bloquear=True)
    _rechazar_si_cdt(t)
    cuentas = bloquear_cuentas(
        db, user.id, {t.from_account_id, t.to_account_id, datos.from_account_id, datos.to_account_id}
    )
    origen, destino = cuentas[datos.from_account_id], cuentas[datos.to_account_id]
    monto_entrada = calcular_monto_entrada(
        origen.currency, destino.currency, datos.amount_out, datos.amount_in, datos.exchange_rate
    )
    viejo = ledger.deltas_transferencia(t.from_account_id, t.to_account_id, t.amount_out, t.amount_in)
    nuevo = ledger.deltas_transferencia(origen.id, destino.id, datos.amount_out, monto_entrada)
    ledger.aplicar_deltas(db, ledger.sumar_deltas(ledger.invertir_deltas(viejo), nuevo))

    t.from_account_id, t.to_account_id = origen.id, destino.id
    t.amount_out, t.currency_out = datos.amount_out, origen.currency
    t.amount_in, t.currency_in = monto_entrada, destino.currency
    enviados = datos.model_fields_set
    if datos.date is not None:
        t.date = instante_de_fecha(datos.date, ahora, get_zoneinfo(user.timezone))
    if "description" in enviados:
        t.description = datos.description
    db.flush()
    db.refresh(t)
    return a_respuesta(t, warnings=avisos(db, origen))


def eliminar(db: Session, user: models.User, transfer_id: int) -> None:
    t = _obtener(db, user.id, transfer_id, bloquear=True)
    _rechazar_si_cdt(t)
    bloquear_cuentas(db, user.id, {t.from_account_id, t.to_account_id})
    viejo = ledger.deltas_transferencia(t.from_account_id, t.to_account_id, t.amount_out, t.amount_in)
    ledger.aplicar_deltas(db, ledger.invertir_deltas(viejo))
    db.delete(t)
    db.flush()
