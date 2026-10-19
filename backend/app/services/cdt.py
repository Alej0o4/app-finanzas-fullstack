"""CDT: inversión a plazo fijo como módulo independiente (Fase 38, docs/specs/fase_38_spec.md).

Un CDT no toca el libro contable (D1): ni `Account.balance`, ni `Transaction`, ni `ledger.py`.
Este módulo calcula el interés causado, los días que faltan y el aviso de vencimiento, y suma el
CDT vigente al patrimonio total (`net_worth`), nunca al disponible real ni al fondo de emergencia.

Dos mitades: funciones **puras** arriba (solo `date`/`Decimal`; nunca leen el reloj ni construyen
`datetime` naive — `core/periods.py` es el único dueño de esa aritmética) y la lógica con DB abajo,
que **no comitea** (el router es dueño de la transacción SQL).
"""

from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.periods import dia_local, sumar_meses
from app.core.timezones import get_zoneinfo
from app.models import models

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
DIAS_AVISO = 15  # D3: `due_soon` cuando faltan 15 días o menos
MAX_CDT_POR_USUARIO = 50  # D11
ANIOS_MAX_PLAZO = 10  # D8
ANIOS_MAX_ATRAS = 10  # D8: `opened_on` desde hoy - 10 años
_MSG_NO_EXISTE = "El CDT no existe o no tienes permisos."


# --------------------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------------------
def dias_transcurridos(opened_on: date, maturity_on: date, hoy: date) -> int:
    """Días de interés causados a `hoy`, acotados a `[0, plazo]` (D2): antes de abrir vale 0 y
    después del vencimiento deja de causarse."""
    plazo = (maturity_on - opened_on).days
    return max(0, min((hoy - opened_on).days, plazo))


def interes_causado(capital: Decimal, tasa_ea: Decimal, dias: int) -> Decimal:
    """Interés bruto E.A. compuesto, base 365 (D2): `capital * ((1 + r)^(dias/365) - 1)` con
    `r = tasa_ea / 100`, calculado con `Decimal.ln()/exp()` y redondeado a centavo (HALF_UP)."""
    if dias <= 0:
        return CERO
    with localcontext() as ctx:
        ctx.prec = 28
        r = tasa_ea / Decimal(100)
        factor = ((Decimal(1) + r).ln() * Decimal(dias) / Decimal(365)).exp()
        interes = capital * (factor - Decimal(1))
    return interes.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def dias_para_vencer(maturity_on: date, hoy: date) -> int:
    """Días hasta el vencimiento; negativo si ya venció."""
    return (maturity_on - hoy).days


def alerta(maturity_on: date, hoy: date, estado: str) -> str:
    """`ok` | `due_soon` (faltan 1..15 días) | `matured` (vence hoy o ya venció y sigue vigente, D3)."""
    if estado != "active":
        return "ok"
    faltan = dias_para_vencer(maturity_on, hoy)
    if faltan <= 0:
        return "matured"
    if faltan <= DIAS_AVISO:
        return "due_soon"
    return "ok"


# --------------------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------------------
def _item(cdt: models.Cdt, hoy: date) -> dict:
    """Respuesta de un CDT con todas las cifras calculadas (D12, D14). Un CDT redimido congela
    las cifras al día de la redención: `current_value` es lo que realmente se recibió."""
    plazo = (cdt.maturity_on - cdt.opened_on).days
    activo = cdt.status == "active"
    referencia = hoy if activo else cdt.redeemed_on
    transcurridos = dias_transcurridos(cdt.opened_on, cdt.maturity_on, referencia)
    causado = interes_causado(cdt.principal, cdt.rate_ea, transcurridos)
    al_vencimiento = interes_causado(cdt.principal, cdt.rate_ea, plazo)
    return {
        "id": cdt.id,
        "name": cdt.name,
        "currency": cdt.currency,
        "principal": cdt.principal,
        "rate_ea": cdt.rate_ea,
        "opened_on": cdt.opened_on,
        "maturity_on": cdt.maturity_on,
        "status": cdt.status,
        "redeemed_on": cdt.redeemed_on,
        "final_amount": cdt.final_amount,
        "realized_interest": None if activo else cdt.final_amount - cdt.principal,
        "term_days": plazo,
        "elapsed_days": transcurridos,
        "accrued_interest": causado,
        "current_value": cdt.principal + causado if activo else cdt.final_amount,
        "maturity_interest": al_vencimiento,
        "maturity_value": cdt.principal + al_vencimiento,
        "days_to_maturity": dias_para_vencer(cdt.maturity_on, hoy) if activo else None,
        "alert": alerta(cdt.maturity_on, hoy, cdt.status),
        "created_at": cdt.created_at,
    }


def _orden_monedas(monedas, preferida: str) -> list[str]:
    return sorted(monedas, key=lambda c: (0 if c == preferida else 1, c))


def _totales(items: list[dict], preferida: str) -> list[dict]:
    """Totales por moneda, solo de los vigentes (D12)."""
    acumulado: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"principal": CERO, "accrued_interest": CERO, "current_value": CERO, "maturity_value": CERO}
    )
    for it in items:
        if it["status"] != "active":
            continue
        t = acumulado[it["currency"]]
        for campo in ("principal", "accrued_interest", "current_value", "maturity_value"):
            t[campo] += it[campo]
    return [{"currency": c, **acumulado[c]} for c in _orden_monedas(acumulado, preferida)]


# --------------------------------------------------------------------------------------
# Casos de uso (no comitean)
# --------------------------------------------------------------------------------------
def _hoy(user: models.User, ahora: datetime) -> date:
    return dia_local(ahora, get_zoneinfo(user.timezone))


def _obtener(db: Session, user_id: int, cdt_id: int, *, bloquear: bool = False) -> models.Cdt:
    consulta = db.query(models.Cdt).filter(models.Cdt.id == cdt_id, models.Cdt.user_id == user_id)
    if bloquear:
        consulta = consulta.with_for_update()
    cdt = consulta.first()
    if cdt is None:
        raise NotFoundError(_MSG_NO_EXISTE)
    return cdt


def _validar_fechas(opened_on: date, maturity_on: date, hoy: date) -> None:
    """D8: vencimiento posterior a la apertura, plazo <= 10 años y apertura en [hoy-10a, hoy+1a]."""
    if maturity_on <= opened_on:
        raise ValidationError("`maturity_on` debe ser posterior a `opened_on`.")
    if maturity_on > sumar_meses(opened_on, 12 * ANIOS_MAX_PLAZO):
        raise ValidationError(f"El plazo no puede superar {ANIOS_MAX_PLAZO} años.")
    if opened_on < sumar_meses(hoy, -12 * ANIOS_MAX_ATRAS):
        raise ValidationError(f"`opened_on` no puede ser anterior a {ANIOS_MAX_ATRAS} años atrás.")
    if opened_on > sumar_meses(hoy, 12):
        raise ValidationError("`opened_on` no puede estar a más de un año en el futuro.")


def listar(db: Session, user: models.User, ahora: datetime, estado: str | None = None) -> dict:
    hoy = _hoy(user, ahora)
    consulta = db.query(models.Cdt).filter(models.Cdt.user_id == user.id)
    if estado is not None:
        consulta = consulta.filter(models.Cdt.status == estado)
    cdts = consulta.all()
    vigentes = sorted((c for c in cdts if c.status == "active"), key=lambda c: (c.maturity_on, c.id))
    redimidos = sorted((c for c in cdts if c.status == "redeemed"), key=lambda c: (c.redeemed_on, c.id), reverse=True)
    items = [_item(c, hoy) for c in vigentes + redimidos]
    return {"items": items, "totals": _totales(items, user.preferred_currency)}


def crear(db: Session, user: models.User, datos, ahora: datetime) -> dict:
    hoy = _hoy(user, ahora)
    _validar_fechas(datos.opened_on, datos.maturity_on, hoy)
    if db.query(models.Cdt).filter(models.Cdt.user_id == user.id).count() >= MAX_CDT_POR_USUARIO:
        raise ValidationError(f"Alcanzaste el máximo de {MAX_CDT_POR_USUARIO} CDT.")
    cdt = models.Cdt(
        user_id=user.id,
        name=datos.name,
        currency=datos.currency,
        principal=datos.principal,
        rate_ea=datos.rate_ea,
        opened_on=datos.opened_on,
        maturity_on=datos.maturity_on,
        status="active",
    )
    db.add(cdt)
    db.flush()
    db.refresh(cdt)
    return _item(cdt, hoy)


def actualizar(db: Session, user: models.User, cdt_id: int, datos, ahora: datetime) -> dict:
    """Edita un CDT vigente (D9); uno redimido responde 409."""
    hoy = _hoy(user, ahora)
    cdt = _obtener(db, user.id, cdt_id, bloquear=True)
    if cdt.status != "active":
        raise ConflictError("Un CDT redimido no se puede editar.")
    enviados = datos.model_fields_set
    for campo in ("name", "currency", "principal", "rate_ea", "opened_on", "maturity_on"):
        if campo in enviados:
            setattr(cdt, campo, getattr(datos, campo))
    # Las cotas relativas a hoy solo se revisan si la edición toca fechas: renombrar un CDT viejo
    # no debe fallar por una cota que ya no cumple (hallazgo del code-review).
    if "opened_on" in enviados or "maturity_on" in enviados:
        _validar_fechas(cdt.opened_on, cdt.maturity_on, hoy)
    db.flush()
    db.refresh(cdt)
    return _item(cdt, hoy)


def redimir(db: Session, user: models.User, cdt_id: int, datos, ahora: datetime) -> dict:
    """Marca el CDT como redimido (D4). No crea transacción ni mueve saldos (D1). El segundo de dos
    `redeem` simultáneos espera el lock de la fila y ve `redeemed` -> 409."""
    hoy = _hoy(user, ahora)
    cdt = _obtener(db, user.id, cdt_id, bloquear=True)
    if cdt.status != "active":
        raise ConflictError("El CDT ya fue redimido.")
    fecha = datos.redeemed_on if datos.redeemed_on is not None else hoy
    if fecha < cdt.opened_on:
        raise ValidationError("`redeemed_on` no puede ser anterior a la apertura del CDT.")
    if fecha > hoy:
        raise ValidationError("`redeemed_on` no puede ser una fecha futura.")
    if datos.final_amount is not None:
        final = datos.final_amount
    else:
        dias = dias_transcurridos(cdt.opened_on, cdt.maturity_on, fecha)
        final = cdt.principal + interes_causado(cdt.principal, cdt.rate_ea, dias)
    cdt.status = "redeemed"
    cdt.redeemed_on = fecha
    cdt.final_amount = final
    db.flush()
    db.refresh(cdt)
    return _item(cdt, hoy)


def eliminar(db: Session, user: models.User, cdt_id: int) -> None:
    """Borrado real en cualquier estado (D10); no toca nada más (D1)."""
    cdt = _obtener(db, user.id, cdt_id, bloquear=True)
    db.delete(cdt)


def patrimonio(
    db: Session, user: models.User, ahora: datetime, moneda_preferida: str, accounts_total: list[dict]
) -> dict[str, list[dict]]:
    """`cdt_total` y `net_worth = accounts_total + cdt_total` por moneda (D5). Solo CDT vigentes,
    con `principal + interés causado a hoy`. `accounts_total` lo calcula `funds.disponibilidad`; acá
    solo se suma. No altera `free_to_spend`, `committed` ni `balances`."""
    hoy = _hoy(user, ahora)
    vigentes = db.query(models.Cdt).filter(models.Cdt.user_id == user.id, models.Cdt.status == "active").all()
    cdt: dict[str, Decimal] = defaultdict(lambda: CERO)
    for c in vigentes:
        causado = interes_causado(c.principal, c.rate_ea, dias_transcurridos(c.opened_on, c.maturity_on, hoy))
        cdt[c.currency] += c.principal + causado
    cuentas = {a["currency"]: a["total"] for a in accounts_total}
    monedas = _orden_monedas(set(cuentas) | set(cdt), moneda_preferida)
    return {
        "cdt_total": [{"currency": c, "total": cdt.get(c, CERO)} for c in monedas],
        "net_worth": [{"currency": c, "total": cuentas.get(c, CERO) + cdt.get(c, CERO)} for c in monedas],
    }
