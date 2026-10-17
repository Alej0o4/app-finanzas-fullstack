"""Sobres virtuales y disponible real (Fase 35, docs/specs/fase_35_spec.md).

Un sobre es una capa de asignación sobre una cuenta: dinero comprometido pero no gastado. No
mueve dinero ni toca `Account.balance`/`ledger.py`; su saldo es `SUM(fund_entries.amount)`.
Todo cálculo financiero vive acá (el frontend solo presenta).

Dos mitades: funciones **puras** arriba (fechas ya resueltas a `date` en la zona del usuario,
sin leer el reloj ni construir `datetime` naive — `core/periods.py` es el único dueño de esa
aritmética) y la lógica con DB abajo.
"""

from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AccountNotFoundError, ConflictError, NotFoundError, ValidationError
from app.core.periods import dia_local, mediodia_local, rango_mes
from app.core.timezones import get_zoneinfo
from app.models import models

CENTAVO = Decimal("0.01")
MESES_PROMEDIO = 3  # D3: meses completos que promedian el gasto del fondo de emergencia
KINDS_META_FIJA = {"annual_expense", "goal"}
_MSG_NO_EXISTE = "El sobre no existe o no tienes permisos."


# --------------------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------------------
def meses_restantes(objetivo: date | None, hoy: date) -> int | None:
    """Meses calendario entre el mes de `hoy` y el de `objetivo` (D2). `None` sin fecha; `0` si
    la fecha ya pasó; mínimo 1 si no (el mes en curso cuenta como un mes para aportar)."""
    if objetivo is None:
        return None
    if objetivo < hoy:
        return 0
    return max(1, (objetivo.year - hoy.year) * 12 + (objetivo.month - hoy.month))


def aporte_requerido(restante: Decimal | None, meses: int | None) -> Decimal | None:
    """`restante / meses` redondeado hacia arriba al centavo (D2). `None` sin fecha o sin nada
    por aportar. Con la fecha vencida (`meses == 0`) se pide todo lo que falta."""
    if restante is None or meses is None or restante <= 0:
        return None
    return (restante / max(meses, 1)).quantize(CENTAVO, rounding=ROUND_CEILING)


def ritmo(saldo: Decimal, meta: Decimal | None, creado: date, objetivo: date | None, hoy: date) -> str | None:
    """`completed` / `on_track` / `behind` / `None` (D2). Ritmo lineal por días desde el día de
    creación hasta el objetivo; sin meta o sin fecha no hay ritmo que medir."""
    if meta is None:
        return None
    if saldo >= meta:
        return "completed"
    if objetivo is None:
        return None
    if hoy >= objetivo or objetivo <= creado:
        return "behind"
    fraccion = Decimal((hoy - creado).days) / Decimal((objetivo - creado).days)
    fraccion = min(max(fraccion, Decimal(0)), Decimal(1))
    esperado = (meta * fraccion).quantize(CENTAVO, rounding=ROUND_DOWN)
    return "behind" if saldo < esperado else "on_track"


def progreso(saldo: Decimal, meta: Decimal | None) -> float | None:
    """Porcentaje 0-100 (capado) de la meta cubierto por el saldo."""
    if meta is None or meta <= 0:
        return None
    return float(min(max(saldo / meta * 100, Decimal(0)), Decimal(100)).quantize(Decimal("0.1")))


def meta_efectiva(target_amount: Decimal | None, target_months: int | None, promedio: Decimal | None) -> Decimal | None:
    """Meta fija, o `target_months x promedio` (D3); `None` si no hay promedio."""
    if target_amount is not None:
        return target_amount
    if target_months is None or promedio is None:
        return None
    return (promedio * target_months).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def runway(saldo: Decimal, promedio: Decimal | None) -> Decimal | None:
    """Meses que cubre el saldo con el gasto promedio, a un decimal."""
    if promedio is None or promedio <= 0:
        return None
    return (saldo / promedio).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------------------
# Consultas
# --------------------------------------------------------------------------------------
def _saldos(db: Session, fund_ids: list[int]) -> dict[int, Decimal]:
    if not fund_ids:
        return {}
    filas = (
        db.query(models.FundEntry.fund_id, func.sum(models.FundEntry.amount))
        .filter(models.FundEntry.fund_id.in_(fund_ids))
        .group_by(models.FundEntry.fund_id)
        .all()
    )
    return {fund_id: total for fund_id, total in filas}


def promedio_gasto_mensual(db: Session, user_id: int, moneda: str, ahora: datetime, tz: ZoneInfo) -> Decimal | None:
    """Gasto promedio mensual en `moneda` de los hasta 3 meses completos anteriores al actual
    (zona del usuario), sobre todas las cuentas. Solo cuentan los meses desde el de la primera
    transacción del usuario (D3); sin ninguno, o sin gasto, devuelve `None`."""
    primera = db.query(func.min(models.Transaction.date)).filter(models.Transaction.user_id == user_id).scalar()
    if primera is None:
        return None
    primera = dia_local(primera, tz)
    hoy = dia_local(ahora, tz)
    meses: list[tuple[int, int]] = []
    y, m = hoy.year, hoy.month
    for _ in range(MESES_PROMEDIO):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        if (y, m) >= (primera.year, primera.month):
            meses.append((y, m))
    if not meses:
        return None
    meses.sort()
    inicio = rango_mes(*meses[0], ahora, tz)[0]
    fin = rango_mes(*meses[-1], ahora, tz)[1]
    total = (
        db.query(func.sum(models.Transaction.amount))
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == "expense",
            models.Transaction.currency == moneda,
            models.Transaction.date >= inicio,
            models.Transaction.date < fin,
        )
        .scalar()
    ) or Decimal("0.00")
    if total <= 0:
        return None
    return (total / len(meses)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _respuesta(
    fund: models.Fund,
    saldo: Decimal,
    faltante: Decimal,
    promedio: Decimal | None,
    hoy: date,
    tz: ZoneInfo,
) -> dict:
    meta = meta_efectiva(fund.target_amount, fund.target_months, promedio)
    objetivo = dia_local(fund.target_date, tz) if fund.target_date else None
    restante = max(meta - saldo, Decimal("0.00")) if meta is not None else None
    meses = meses_restantes(objetivo, hoy)
    es_emergencia = fund.kind == "emergency"
    return {
        "id": fund.id,
        "name": fund.name,
        "kind": fund.kind,
        "status": fund.status,
        "account_id": fund.account_id,
        "currency": fund.currency,
        "balance": saldo,
        "target_amount": meta,
        "target_months": fund.target_months,
        "target_date": objetivo,
        "progress_pct": progreso(saldo, meta),
        "remaining": restante,
        "months_remaining": meses,
        "required_contribution": aporte_requerido(restante, meses),
        "pace": ritmo(saldo, meta, dia_local(fund.created_at, tz), objetivo, hoy) if fund.created_at else None,
        "monthly_expense_avg": promedio if es_emergencia else None,
        "runway_months": runway(saldo, promedio) if es_emergencia else None,
        "backing_shortfall": faltante,
        "created_at": fund.created_at,
    }


def _construir(db: Session, user: models.User, fondos: list[models.Fund], ahora: datetime) -> list[dict]:
    """Respuestas de `fondos` con sus métricas. `backing_shortfall` (D4) se calcula contra TODOS
    los sobres activos de cada cuenta, no solo los listados."""
    tz = get_zoneinfo(user.timezone)
    hoy = dia_local(ahora, tz)
    cuentas_ids = {f.account_id for f in fondos}
    activos = (
        db.query(models.Fund)
        .filter(models.Fund.user_id == user.id, models.Fund.status == "active", models.Fund.account_id.in_(cuentas_ids))
        .all()
        if cuentas_ids
        else []
    )
    ids = {f.id for f in fondos} | {f.id for f in activos}
    saldos = _saldos(db, list(ids))
    apartado: dict[int, Decimal] = {}
    for f in activos:
        apartado[f.account_id] = apartado.get(f.account_id, Decimal("0.00")) + saldos.get(f.id, Decimal("0.00"))
    cuentas = (
        {
            a.id: a.balance
            for a in db.query(models.Account)
            .filter(models.Account.user_id == user.id, models.Account.id.in_(cuentas_ids))
            .all()
        }
        if cuentas_ids
        else {}
    )
    promedios: dict[str, Decimal | None] = {}
    respuestas = []
    for f in fondos:
        if f.kind == "emergency" and f.currency not in promedios:
            promedios[f.currency] = promedio_gasto_mensual(db, user.id, f.currency, ahora, tz)
        # El faltante nunca excede lo apartado: una cuenta con saldo negativo (p. ej. una
        # tarjeta) sin nada apartado en ella no tiene sobres "sin respaldo".
        reservado = apartado.get(f.account_id, Decimal("0.00"))
        faltante = min(reservado, max(reservado - cuentas.get(f.account_id, Decimal("0.00")), 0))
        if f.status != "active":
            faltante = Decimal("0.00")  # un archivado no aparta nada: no está "sin respaldo"
        respuestas.append(
            _respuesta(
                f,
                saldos.get(f.id, Decimal("0.00")),
                Decimal(faltante).quantize(CENTAVO),
                promedios.get(f.currency),
                hoy,
                tz,
            )
        )
    return respuestas


def _obtener(db: Session, user_id: int, fund_id: int, *, bloquear: bool = False) -> models.Fund:
    consulta = db.query(models.Fund).filter(models.Fund.id == fund_id, models.Fund.user_id == user_id)
    if bloquear:
        # Fase 31 (patrón): `FOR UPDATE` es la PRIMERA consulta de la operación; serializa
        # aportes/retiros concurrentes del mismo sobre. En SQLite no genera nada.
        consulta = consulta.with_for_update()
    fund = consulta.first()
    if fund is None:
        raise NotFoundError(_MSG_NO_EXISTE)
    return fund


def _cuenta_del_usuario(db: Session, user_id: int, account_id: int) -> models.Account:
    # FOR UPDATE: serializa con `DELETE /accounts/{id}`, que toma el mismo lock (su guard de
    # sobres activos), para que no quede un sobre activo sobre una cuenta borrada.
    cuenta = (
        db.query(models.Account)
        .filter(models.Account.id == account_id, models.Account.user_id == user_id)
        .with_for_update()
        .first()
    )
    if cuenta is None:
        raise AccountNotFoundError()
    return cuenta


# --------------------------------------------------------------------------------------
# Casos de uso
# --------------------------------------------------------------------------------------
def listar(db: Session, user: models.User, ahora: datetime, include_archived: bool = False) -> list[dict]:
    consulta = db.query(models.Fund).filter(models.Fund.user_id == user.id)
    if not include_archived:
        consulta = consulta.filter(models.Fund.status == "active")
    return _construir(db, user, consulta.order_by(models.Fund.id).all(), ahora)


def detalle(db: Session, user: models.User, fund_id: int, ahora: datetime) -> dict:
    fund = _obtener(db, user.id, fund_id)
    respuesta = _construir(db, user, [fund], ahora)[0]
    respuesta["entries"] = (
        db.query(models.FundEntry)
        .filter(models.FundEntry.fund_id == fund.id)
        .order_by(models.FundEntry.occurred_at.desc(), models.FundEntry.id.desc())
        .limit(50)
        .all()
    )
    return respuesta


def _validar_fecha_objetivo(objetivo: date, hoy: date) -> None:
    if objetivo < hoy:
        raise ValidationError("La fecha objetivo no puede ser anterior a hoy.")


def crear(db: Session, user: models.User, datos, ahora: datetime) -> dict:
    tz = get_zoneinfo(user.timezone)
    cuenta = _cuenta_del_usuario(db, user.id, datos.account_id)
    if datos.target_date is not None:
        _validar_fecha_objetivo(datos.target_date, dia_local(ahora, tz))
    fund = models.Fund(
        user_id=user.id,
        account_id=cuenta.id,
        name=datos.name,
        kind=datos.kind.value,
        currency=cuenta.currency,
        target_amount=datos.target_amount,
        target_months=datos.target_months,
        target_date=mediodia_local(datos.target_date, tz) if datos.target_date else None,
        status="active",
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return _construir(db, user, [fund], ahora)[0]


def actualizar(db: Session, user: models.User, fund_id: int, datos, ahora: datetime) -> dict:
    tz = get_zoneinfo(user.timezone)
    fund = _obtener(db, user.id, fund_id, bloquear=True)
    if fund.status != "active":
        raise ConflictError("Desarchiva el sobre para editarlo.")
    enviados = datos.model_fields_set

    if "name" in enviados and datos.name is not None:
        fund.name = datos.name

    if "account_id" in enviados and datos.account_id is not None and datos.account_id != fund.account_id:
        cuenta = _cuenta_del_usuario(db, user.id, datos.account_id)
        if cuenta.currency != fund.currency:
            raise ValidationError("La cuenta debe tener la misma moneda del sobre.")
        fund.account_id = cuenta.id

    # La meta se evalúa como un todo: lo enviado reemplaza a la alternativa (monto XOR meses).
    if "target_amount" in enviados or "target_months" in enviados:
        if "target_amount" in enviados and "target_months" in enviados:
            nuevo_monto, nuevos_meses = datos.target_amount, datos.target_months
        elif "target_amount" in enviados:
            nuevo_monto, nuevos_meses = datos.target_amount, None
        else:
            nuevo_monto, nuevos_meses = None, datos.target_months
        if (nuevo_monto is None) == (nuevos_meses is None):
            raise ValidationError("Indica `target_amount` o `target_months`, uno solo.")
        if nuevos_meses is not None and fund.kind != "emergency":
            raise ValidationError("`target_months` solo aplica al fondo de emergencia.")
        fund.target_amount, fund.target_months = nuevo_monto, nuevos_meses

    if "target_date" in enviados:
        if datos.target_date is None:
            fund.target_date = None
        else:
            _validar_fecha_objetivo(datos.target_date, dia_local(ahora, tz))
            fund.target_date = mediodia_local(datos.target_date, tz)

    db.commit()
    db.refresh(fund)
    return _construir(db, user, [fund], ahora)[0]


def _saldo_bloqueado(db: Session, fund_id: int) -> Decimal:
    return (
        db.query(func.sum(models.FundEntry.amount)).filter(models.FundEntry.fund_id == fund_id).scalar()
    ) or Decimal("0.00")


def registrar_movimiento(
    db: Session, user: models.User, fund_id: int, tipo: str, monto: Decimal, nota: str | None, ahora: datetime
) -> models.FundEntry:
    """Aporte (`contribution`) o retiro (`withdrawal`). Toma el row-lock del sobre antes de
    leer el saldo, así dos retiros concurrentes no pueden dejarlo en negativo (B6)."""
    tz = get_zoneinfo(user.timezone)
    fund = _obtener(db, user.id, fund_id, bloquear=True)
    if fund.status != "active":
        raise ConflictError("El sobre está archivado.")
    if tipo == "withdrawal":
        saldo = _saldo_bloqueado(db, fund.id)
        if monto > saldo:
            raise ValidationError(f"El sobre solo tiene {saldo} apartado.")
    hoy = dia_local(ahora, tz)
    entrada = models.FundEntry(
        fund_id=fund.id,
        user_id=user.id,
        amount=monto if tipo == "contribution" else -monto,
        type=tipo,
        occurred_at=ahora,
        period=f"{hoy.year:04d}-{hoy.month:02d}",
        note=nota,
    )
    db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada


def archivar(db: Session, user: models.User, fund_id: int, ahora: datetime) -> dict:
    fund = _obtener(db, user.id, fund_id, bloquear=True)
    if fund.status != "archived":
        if _saldo_bloqueado(db, fund.id) != 0:
            raise ConflictError("Retira el saldo del sobre antes de archivarlo.")
        fund.status = "archived"
        db.commit()
        db.refresh(fund)
    return _construir(db, user, [fund], ahora)[0]


def desarchivar(db: Session, user: models.User, fund_id: int, ahora: datetime) -> dict:
    fund = _obtener(db, user.id, fund_id, bloquear=True)
    if fund.status != "active":
        cuenta = db.query(models.Account).filter(models.Account.id == fund.account_id).first()
        if cuenta is None:
            raise ConflictError("La cuenta del sobre ya no existe.")
        if cuenta.currency != fund.currency:
            raise ConflictError("La moneda de la cuenta cambió; el sobre ya no coincide con ella.")
        fund.status = "active"
        db.commit()
        db.refresh(fund)
    return _construir(db, user, [fund], ahora)[0]


def disponibilidad(db: Session, user_id: int, moneda_preferida: str) -> dict[str, list[dict]]:
    """Disponible real por moneda (B11, D1): `accounts_total` (todas las cuentas),
    `committed` (sobres activos) y `free_to_spend` = diferencia. Monedas ordenadas con la
    preferida primero; una moneda que solo está en un lado cuenta como 0 en el otro."""
    cuentas = dict(
        db.query(models.Account.currency, func.sum(models.Account.balance))
        .filter(models.Account.user_id == user_id)
        .group_by(models.Account.currency)
        .all()
    )
    sobres = dict(
        db.query(models.Fund.currency, func.sum(models.FundEntry.amount))
        .join(models.FundEntry, models.FundEntry.fund_id == models.Fund.id)
        .filter(models.Fund.user_id == user_id, models.Fund.status == "active")
        .group_by(models.Fund.currency)
        .all()
    )
    monedas = sorted(set(cuentas) | set(sobres), key=lambda c: (0 if c == moneda_preferida else 1, c))
    cero = Decimal("0.00")
    return {
        "accounts_total": [{"currency": c, "total": cuentas.get(c) or cero} for c in monedas],
        "committed": [{"currency": c, "total": sobres.get(c) or cero} for c in monedas],
        "free_to_spend": [
            {"currency": c, "total": (cuentas.get(c) or cero) - (sobres.get(c) or cero)} for c in monedas
        ],
    }
