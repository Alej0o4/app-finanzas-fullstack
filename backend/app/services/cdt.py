"""CDT: inversión a plazo fijo como módulo independiente (Fase 38, docs/specs/fase_38_spec.md).

Un CDT es un módulo aparte del libro contable: por sí solo no toca `Account.balance` ni
`Transaction`. Desde la Fase 39 puede vincularse a una cuenta de forma **opcional** mediante
transferencias (`source_account_id` al crear/editar, `account_id` al redimir): la transferencia de
constitución saca el capital de la cuenta, la de redención lo devuelve y el interés realizado entra
como un ingreso normal en la categoría base "Rendimientos" (D11/D12). Sin vínculo todo sigue
aislado como en la Fase 38. Este módulo calcula el interés causado, los días que faltan y el aviso de vencimiento, y suma el
CDT vigente al patrimonio total (`net_worth`), nunca al disponible real ni al fondo de emergencia.

Dos mitades: funciones **puras** arriba (solo `date`/`Decimal`; nunca leen el reloj ni construyen
`datetime` naive — `core/periods.py` es el único dueño de esa aritmética) y la lógica con DB abajo,
que **no comitea** (el router es dueño de la transacción SQL).
"""

from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy.orm import Session

from app.core.default_categories import ensure_default_categories
from app.core.exceptions import ConflictError, InternalServerError, NotFoundError, ValidationError
from app.core.periods import dia_local, instante_de_dia, sumar_meses
from app.core.timezones import get_zoneinfo
from app.models import models
from app.services import ledger
from app.services.transfers import bloquear_cuentas

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
DIAS_AVISO = 15  # D3: `due_soon` cuando faltan 15 días o menos
MAX_CDT_POR_USUARIO = 50  # D11
ANIOS_MAX_PLAZO = 10  # D8
ANIOS_MAX_ATRAS = 10  # D8: `opened_on` desde hoy - 10 años
_MSG_NO_EXISTE = "El CDT no existe o no tienes permisos."
_MSG_MONEDA_CUENTA = "La moneda de la cuenta debe coincidir con la del CDT."
CATEGORIA_RENDIMIENTOS = "Rendimientos"


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
def _item(
    cdt: models.Cdt, hoy: date, constitucion: models.Transfer | None = None, redencion: models.Transfer | None = None
) -> dict:
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
        "source_account_id": constitucion.from_account_id if constitucion else None,
        "source_transfer_id": constitucion.id if constitucion else None,
        "redeem_account_id": redencion.to_account_id if redencion else None,
        "redeem_transfer_id": redencion.id if redencion else None,
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


def _vinculos(db: Session, ids: list[int]) -> dict[int, dict[str, models.Transfer]]:
    """Transferencias vinculadas por CDT: `constitucion` (cuenta -> CDT) y `redencion` (CDT -> cuenta)."""
    mapa: dict[int, dict[str, models.Transfer]] = {}
    if not ids:
        return mapa
    for t in db.query(models.Transfer).filter(models.Transfer.cdt_id.in_(ids)).all():
        mapa.setdefault(t.cdt_id, {})["constitucion" if t.from_account_id is not None else "redencion"] = t
    return mapa


def _item_de(db: Session, cdt: models.Cdt, hoy: date) -> dict:
    v = _vinculos(db, [cdt.id]).get(cdt.id, {})
    return _item(cdt, hoy, v.get("constitucion"), v.get("redencion"))


def _constitucion(db: Session, cdt_id: int, *, bloquear: bool = False) -> models.Transfer | None:
    consulta = db.query(models.Transfer).filter(
        models.Transfer.cdt_id == cdt_id, models.Transfer.from_account_id.is_not(None)
    )
    if bloquear:
        consulta = consulta.with_for_update()
    return consulta.first()


def _constituir(
    db: Session, user: models.User, cdt: models.Cdt, cuenta: models.Account, ahora: datetime
) -> models.Transfer:
    """Transferencia de constitución (D12): el capital sale de la cuenta en la fecha de apertura."""
    t = models.Transfer(
        user_id=user.id,
        from_account_id=cuenta.id,
        to_account_id=None,
        cdt_id=cdt.id,
        amount_out=cdt.principal,
        currency_out=cdt.currency,
        amount_in=cdt.principal,
        currency_in=cdt.currency,
        date=instante_de_dia(cdt.opened_on, ahora, get_zoneinfo(user.timezone)),
        description=f"Constitución CDT {cdt.name}",
    )
    db.add(t)
    db.flush()
    ledger.aplicar_deltas(db, ledger.deltas_transferencia(cuenta.id, None, t.amount_out, t.amount_in))
    return t


def _categoria_rendimientos(db: Session) -> models.Category:
    def _buscar():
        return (
            db.query(models.Category)
            .filter(
                models.Category.user_id.is_(None),
                models.Category.name == CATEGORIA_RENDIMIENTOS,
                models.Category.type == "income",
            )
            .first()
        )

    categoria = _buscar()
    if categoria is None:  # base sin sembrar (p. ej. una base nueva antes del primer arranque)
        ensure_default_categories(db)
        categoria = _buscar()
    if categoria is None:
        raise InternalServerError("Falta la categoría base 'Rendimientos'.")
    return categoria


def listar(db: Session, user: models.User, ahora: datetime, estado: str | None = None) -> dict:
    hoy = _hoy(user, ahora)
    consulta = db.query(models.Cdt).filter(models.Cdt.user_id == user.id)
    if estado is not None:
        consulta = consulta.filter(models.Cdt.status == estado)
    cdts = consulta.all()
    vigentes = sorted((c for c in cdts if c.status == "active"), key=lambda c: (c.maturity_on, c.id))
    redimidos = sorted((c for c in cdts if c.status == "redeemed"), key=lambda c: (c.redeemed_on, c.id), reverse=True)
    vinculos = _vinculos(db, [c.id for c in cdts])
    items = [
        _item(c, hoy, vinculos.get(c.id, {}).get("constitucion"), vinculos.get(c.id, {}).get("redencion"))
        for c in vigentes + redimidos
    ]
    return {"items": items, "totals": _totales(items, user.preferred_currency)}


def crear(db: Session, user: models.User, datos, ahora: datetime) -> dict:
    hoy = _hoy(user, ahora)
    _validar_fechas(datos.opened_on, datos.maturity_on, hoy)
    if db.query(models.Cdt).filter(models.Cdt.user_id == user.id).count() >= MAX_CDT_POR_USUARIO:
        raise ValidationError(f"Alcanzaste el máximo de {MAX_CDT_POR_USUARIO} CDT.")
    cuenta = None
    if datos.source_account_id is not None:
        cuenta = bloquear_cuentas(db, user.id, {datos.source_account_id})[datos.source_account_id]
        if cuenta.currency != datos.currency:
            raise ValidationError(_MSG_MONEDA_CUENTA)
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
    if cuenta is not None:
        _constituir(db, user, cdt, cuenta, ahora)
    db.refresh(cdt)
    return _item_de(db, cdt, hoy)


def actualizar(db: Session, user: models.User, cdt_id: int, datos, ahora: datetime) -> dict:
    """Edita un CDT vigente (D9); uno redimido responde 409. Si tiene transferencia de constitución,
    cambiar capital, apertura o cuenta de origen la actualiza y reajusta los saldos (D12)."""
    hoy = _hoy(user, ahora)
    cdt = _obtener(db, user.id, cdt_id, bloquear=True)
    if cdt.status != "active":
        raise ConflictError("Un CDT redimido no se puede editar.")
    enviados = datos.model_fields_set
    nuevos = {
        c: getattr(datos, c) if c in enviados else getattr(cdt, c)
        for c in ("name", "currency", "principal", "rate_ea", "opened_on", "maturity_on")
    }
    # Las cotas relativas a hoy solo se revisan si la edición toca fechas: renombrar un CDT viejo
    # no debe fallar por una cota que ya no cumple (hallazgo del code-review).
    if "opened_on" in enviados or "maturity_on" in enviados:
        _validar_fechas(nuevos["opened_on"], nuevos["maturity_on"], hoy)

    # Orden de locks: CDT -> transferencia -> cuentas por id (D7).
    previa = _constitucion(db, cdt.id, bloquear=True)
    cuenta_nueva_id = datos.source_account_id if "source_account_id" in enviados else None
    if cuenta_nueva_id is None and previa is not None:
        cuenta_nueva_id = previa.from_account_id
    cuentas = {}
    if cuenta_nueva_id is not None:
        cuentas = bloquear_cuentas(db, user.id, {cuenta_nueva_id, previa.from_account_id if previa else None})
        if cuentas[cuenta_nueva_id].currency != nuevos["currency"]:
            raise ValidationError(_MSG_MONEDA_CUENTA)

    for campo, valor in nuevos.items():
        setattr(cdt, campo, valor)

    if cuenta_nueva_id is not None:
        if previa is None:
            _constituir(db, user, cdt, cuentas[cuenta_nueva_id], ahora)
        else:
            fecha = instante_de_dia(cdt.opened_on, ahora, get_zoneinfo(user.timezone))
            cambio_fecha = dia_local(previa.date, get_zoneinfo(user.timezone)) != cdt.opened_on
            if (
                previa.from_account_id != cuenta_nueva_id
                or previa.amount_out != cdt.principal
                or previa.currency_out != cdt.currency
            ):
                viejo = ledger.deltas_transferencia(previa.from_account_id, None, previa.amount_out, previa.amount_in)
                nuevo = ledger.deltas_transferencia(cuenta_nueva_id, None, cdt.principal, cdt.principal)
                ledger.aplicar_deltas(db, ledger.sumar_deltas(ledger.invertir_deltas(viejo), nuevo))
                previa.from_account_id = cuenta_nueva_id
                previa.amount_out = previa.amount_in = cdt.principal
                previa.currency_out = previa.currency_in = cdt.currency
            if cambio_fecha:
                previa.date = fecha
            previa.description = f"Constitución CDT {cdt.name}"
    db.flush()
    db.refresh(cdt)
    return _item_de(db, cdt, hoy)


def redimir(db: Session, user: models.User, cdt_id: int, datos, ahora: datetime) -> dict:
    """Marca el CDT como redimido (D4). Sin `account_id` solo cambia de estado, como en la Fase 38.
    Con `account_id` (D11) el capital vuelve a esa cuenta con una transferencia de redención y el
    interés realizado entra como ingreso "Rendimientos"; la cuenta debe ser de la moneda del CDT y
    `final_amount < principal` es 422 (la pérdida se registra a mano). El segundo de dos `redeem`
    simultáneos espera el lock de la fila y ve `redeemed` -> 409."""
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
    cuenta = None
    if datos.account_id is not None:
        if final < cdt.principal:
            raise ValidationError(
                "Con cuenta destino, `final_amount` no puede ser menor que el capital; "
                "redime sin cuenta y registra la pérdida a mano."
            )
        cuenta = bloquear_cuentas(db, user.id, {datos.account_id})[datos.account_id]
        if cuenta.currency != cdt.currency:
            raise ValidationError(_MSG_MONEDA_CUENTA)
    cdt.status = "redeemed"
    cdt.redeemed_on = fecha
    cdt.final_amount = final
    if cuenta is not None:
        instante = instante_de_dia(fecha, ahora, get_zoneinfo(user.timezone))
        db.add(
            models.Transfer(
                user_id=user.id,
                from_account_id=None,
                to_account_id=cuenta.id,
                cdt_id=cdt.id,
                amount_out=cdt.principal,
                currency_out=cdt.currency,
                amount_in=cdt.principal,
                currency_in=cdt.currency,
                date=instante,
                description=f"Redención CDT {cdt.name}",
            )
        )
        ledger.aplicar_deltas(db, ledger.deltas_transferencia(None, cuenta.id, cdt.principal, cdt.principal))
        interes = final - cdt.principal
        if interes > 0:
            # Ingreso real (cuenta en flujo). Los ingresos no disparan alertas de presupuesto (solo gasto).
            db.add(
                models.Transaction(
                    user_id=user.id,
                    account_id=cuenta.id,
                    category_id=_categoria_rendimientos(db).id,
                    type="income",
                    amount=interes,
                    currency=cuenta.currency,
                    date=instante,
                    description=f"Rendimientos CDT {cdt.name}",
                )
            )
            ledger.registrar_impacto(db, cuenta.id, "income", interes)
    db.flush()
    db.refresh(cdt)
    return _item_de(db, cdt, hoy)


def eliminar(db: Session, user: models.User, cdt_id: int) -> None:
    """Borrado real (D10). Un CDT vigente con transferencia de constitución devuelve el capital a la
    cuenta y borra la transferencia (D12); uno redimido con transferencias vinculadas es 409 (son
    historia real); uno sin vínculo se borra como en la Fase 38."""
    cdt = _obtener(db, user.id, cdt_id, bloquear=True)
    vinculadas = db.query(models.Transfer).filter(models.Transfer.cdt_id == cdt.id).with_for_update().all()
    if vinculadas:
        if cdt.status != "active":
            raise ConflictError(
                "No se puede borrar un CDT redimido con transferencias vinculadas: son parte del historial de tus cuentas."
            )
        bloquear_cuentas(db, user.id, {t.from_account_id for t in vinculadas})
        for t in vinculadas:
            viejo = ledger.deltas_transferencia(t.from_account_id, t.to_account_id, t.amount_out, t.amount_in)
            ledger.aplicar_deltas(db, ledger.invertir_deltas(viejo))
            db.delete(t)
        db.flush()
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
