"""Recurrentes y calendario de cargos anuales (Fase 37, docs/specs/fase_37_spec.md).

Una regla recurrente **propone** una transacción cada vez que vence una ocurrencia; el dueño la
confirma o la salta (D1). Nada se registra solo y no hay job: las pendientes se calculan bajo
demanda desde `next_date` (D2). Una ocurrencia confirmada crea una transacción normal por el
camino contable de siempre (`ledger.registrar_impacto`); este módulo no toca `ledger.py` ni
ninguna cifra existente.

Dos mitades: funciones **puras** arriba (solo `date`; nunca leen el reloj ni construyen `datetime`
naive — `core/periods.py` es el único dueño de esa aritmética) y la lógica con DB abajo, que
**no comitea** (el router es dueño de la transacción SQL).
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AccountNotFoundError,
    CategoryNotFoundError,
    ConflictError,
    ValidationError,
)
from app.core.periods import (
    dia_local,
    instante_de_dia,
    primer_dia_del_mes,
    rango_dias,
    sumar_meses,
    ultimo_dia_mes,
)
from app.core.timezones import get_zoneinfo
from app.models import models
from app.services import ledger
from app.services.ownership import obtener_propio

CENTAVO = Decimal("0.01")
MAX_REGLAS_POR_USUARIO = 100  # D17
MAX_PENDIENTES_POR_REGLA = 12  # D10
TOPE_PROYECCION = 400  # D13: iteraciones máximas por regla en el calendario
MESES_CALENDARIO = 12  # D13
MESES_HISTORIAL_SUGERENCIAS = 26  # D15
MESES_MAX_ULTIMA_OCURRENCIA = 13  # D15
ANIOS_MAX_FUTURO = 10  # guarda de desborde de `date` (no está en la spec; ver "Desvíos")
_MSG_NO_EXISTE = "La regla recurrente no existe o no tienes permisos."


# --------------------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------------------
def _ocurrencia_n(inicio: date, frecuencia: str, n: int) -> date:
    """Ocurrencia número `n` (0 = el ancla), siempre calculada desde `inicio` (D4)."""
    if frecuencia == "weekly":
        return inicio + timedelta(days=7 * n)
    if frecuencia == "monthly":
        return sumar_meses(inicio, n)
    if frecuencia == "yearly":
        return sumar_meses(inicio, 12 * n)
    raise ValueError(f"Frecuencia desconocida: {frecuencia!r}")


def primera_desde(inicio: date, frecuencia: str, desde: date) -> date:
    """Primera ocurrencia `>= desde` (reanudar, D11). Con `desde` anterior al ancla devuelve el ancla."""
    if desde <= inicio:
        return inicio
    if frecuencia == "weekly":
        n = ((desde - inicio).days + 6) // 7
    elif frecuencia == "monthly":
        n = max(0, (desde.year - inicio.year) * 12 + desde.month - inicio.month)
    elif frecuencia == "yearly":
        n = max(0, desde.year - inicio.year)
    else:
        raise ValueError(f"Frecuencia desconocida: {frecuencia!r}")
    while _ocurrencia_n(inicio, frecuencia, n) < desde:
        n += 1
    return _ocurrencia_n(inicio, frecuencia, n)


def siguiente_ocurrencia(inicio: date, frecuencia: str, actual: date) -> date:
    """Primera ocurrencia **estrictamente posterior** a `actual` (D3, D4)."""
    return primera_desde(inicio, frecuencia, actual + timedelta(days=1))


def ocurrencias_en(inicio: date, frecuencia: str, desde_next: date, hasta: date, tope: int) -> list[date]:
    """Ocurrencias de `desde_next` (que ya es una ocurrencia) a `hasta` inclusive, máximo `tope`."""
    salida: list[date] = []
    actual = desde_next
    while actual <= hasta and len(salida) < tope:
        salida.append(actual)
        actual = siguiente_ocurrencia(inicio, frecuencia, actual)
    return salida


def equivalente_mensual(monto: Decimal, frecuencia: str) -> Decimal:
    """Costo mensualizado (D14): semanal `x52/12`, mensual igual, anual `/12`; `ROUND_HALF_UP`."""
    if frecuencia == "weekly":
        mensual = monto * 52 / 12
    elif frecuencia == "yearly":
        mensual = monto / 12
    else:
        mensual = monto
    return mensual.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def normalizar_nombre(texto: str) -> str:
    """`strip` + minúsculas + espacios colapsados (D15)."""
    return " ".join(texto.lower().split())


def indice_ultima_pareja_anual(fechas: list[date], montos: list[Decimal]) -> int | None:
    """Índice (en la lista original) de la transacción que cierra la **última pareja anual** del
    grupo, o `None` si no hay (D15). Una pareja de transacciones consecutivas (por fecha) es anual
    si están separadas 350-380 días **y** el monto de la segunda difiere <= 20 % del de la primera.
    El monto se mide dentro de esa pareja, no contra las dos últimas del grupo, para que un cargo
    duplicado cercano no tape ni invente un patrón anual."""
    if len(fechas) < 2 or len(fechas) != len(montos):
        return None
    orden = sorted(range(len(fechas)), key=lambda i: fechas[i])
    for i, j in reversed(list(pairwise(orden))):
        if not 350 <= (fechas[j] - fechas[i]).days <= 380:
            continue
        previo = montos[i]
        if previo > 0 and abs(montos[j] - previo) <= previo * Decimal("0.20"):
            return j
    return None


# --------------------------------------------------------------------------------------
# Consultas auxiliares
# --------------------------------------------------------------------------------------
def _obtener(db: Session, user_id: int, rule_id: int, *, bloquear: bool = False) -> models.RecurringRule:
    # `bloquear` es la PRIMERA consulta de confirmar/saltar/editar/borrar (D20): serializa dos
    # confirmaciones de la misma ocurrencia y confirmar vs borrar. `releer` fuerza a leer el
    # `next_date` ya avanzado por quien tenía el lock.
    return obtener_propio(db, models.RecurringRule, user_id, rule_id, _MSG_NO_EXISTE, bloquear=bloquear, releer=True)


def _cuenta_del_usuario(db: Session, user_id: int, account_id: int, *, bloquear: bool = False) -> models.Account:
    consulta = db.query(models.Account).filter(models.Account.id == account_id, models.Account.user_id == user_id)
    if bloquear:
        # Mismo `FOR UPDATE` que `DELETE /accounts/{id}`: no queda una regla nueva sobre una cuenta
        # que se está borrando (la guarda de borrado mira las reglas con ese lock tomado).
        consulta = consulta.with_for_update()
    cuenta = consulta.first()
    if cuenta is None:
        raise AccountNotFoundError()
    return cuenta


def _categoria_del_usuario(db: Session, user_id: int, category_id: int) -> models.Category:
    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == user_id),
        )
        .first()
    )
    if categoria is None:
        raise CategoryNotFoundError()
    return categoria


def _referencias(
    db: Session, user_id: int, reglas: list[models.RecurringRule]
) -> tuple[dict[int, models.Account], set[int]]:
    """Cuentas vivas del usuario (por id) y ids de categorías vivas, para las reglas dadas. Una
    cuenta o categoría ausente del resultado está borrada (D7)."""
    if not reglas:
        return {}, set()
    cuentas = (
        db.query(models.Account)
        .filter(models.Account.user_id == user_id, models.Account.id.in_({r.account_id for r in reglas}))
        .all()
    )
    categorias = (
        db.query(models.Category.id)
        .filter(
            models.Category.id.in_({r.category_id for r in reglas}),
            or_(models.Category.user_id.is_(None), models.Category.user_id == user_id),
        )
        .all()
    )
    return {c.id: c for c in cuentas}, {c.id for c in categorias}


def _respuesta(regla: models.RecurringRule, cuenta: models.Account | None, categoria_ok: bool, hoy: date) -> dict:
    return {
        "id": regla.id,
        "name": regla.name,
        "type": regla.type,
        "amount": regla.amount,
        "currency": cuenta.currency if cuenta is not None else None,
        "account_id": regla.account_id,
        "category_id": regla.category_id,
        "frequency": regla.frequency,
        "start_date": regla.start_date,
        "next_date": regla.next_date,
        "status": regla.status,
        "monthly_equivalent": equivalente_mensual(regla.amount, regla.frequency),
        "is_annual": regla.frequency == "yearly",
        "is_due": regla.status == "active" and cuenta is not None and categoria_ok and regla.next_date <= hoy,
        "account_missing": cuenta is None,
        "category_missing": not categoria_ok,
        "created_at": regla.created_at,
    }


def _construir(db: Session, user: models.User, reglas: list[models.RecurringRule], hoy: date) -> list[dict]:
    cuentas, categorias = _referencias(db, user.id, reglas)
    return [_respuesta(r, cuentas.get(r.account_id), r.category_id in categorias, hoy) for r in reglas]


def _reglas_vigentes(db: Session, user: models.User) -> list[tuple[models.RecurringRule, models.Account]]:
    """Reglas activas con cuenta y categoría vivas (las únicas que proponen o proyectan, D7)."""
    reglas = (
        db.query(models.RecurringRule)
        .filter(models.RecurringRule.user_id == user.id, models.RecurringRule.status == "active")
        .order_by(models.RecurringRule.next_date, models.RecurringRule.id)
        .all()
    )
    cuentas, categorias = _referencias(db, user.id, reglas)
    return [(r, cuentas[r.account_id]) for r in reglas if r.account_id in cuentas and r.category_id in categorias]


# --------------------------------------------------------------------------------------
# Casos de uso (no comitean)
# --------------------------------------------------------------------------------------
def listar(db: Session, user: models.User, ahora: datetime) -> list[dict]:
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    reglas = (
        db.query(models.RecurringRule)
        .filter(models.RecurringRule.user_id == user.id)
        .order_by(models.RecurringRule.next_date, models.RecurringRule.id)
        .all()
    )
    return _construir(db, user, reglas, hoy)


def crear(db: Session, user: models.User, datos, ahora: datetime) -> dict:
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    cuenta = _cuenta_del_usuario(db, user.id, datos.account_id, bloquear=True)
    _categoria_del_usuario(db, user.id, datos.category_id)
    if datos.start_date < sumar_meses(hoy, -12):
        raise ValidationError("`start_date` no puede ser anterior a un año atrás.")
    if datos.start_date > sumar_meses(hoy, 12 * ANIOS_MAX_FUTURO):
        raise ValidationError(f"`start_date` no puede estar a más de {ANIOS_MAX_FUTURO} años en el futuro.")
    existentes = db.query(models.RecurringRule).filter(models.RecurringRule.user_id == user.id).count()
    if existentes >= MAX_REGLAS_POR_USUARIO:
        raise ValidationError(f"Alcanzaste el máximo de {MAX_REGLAS_POR_USUARIO} reglas recurrentes.")
    regla = models.RecurringRule(
        user_id=user.id,
        account_id=cuenta.id,
        category_id=datos.category_id,
        name=datos.name,
        type=datos.type.value,
        amount=datos.amount,
        frequency=datos.frequency.value,
        start_date=datos.start_date,
        next_date=datos.start_date,
        status="active",
    )
    db.add(regla)
    db.flush()
    db.refresh(regla)
    return _construir(db, user, [regla], hoy)[0]


def actualizar(db: Session, user: models.User, rule_id: int, datos, ahora: datetime) -> dict:
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    regla = _obtener(db, user.id, rule_id, bloquear=True)
    enviados = datos.model_fields_set

    if "name" in enviados and datos.name is not None:
        regla.name = datos.name
    if "amount" in enviados and datos.amount is not None:
        regla.amount = datos.amount
    if "account_id" in enviados and datos.account_id is not None and datos.account_id != regla.account_id:
        nueva = _cuenta_del_usuario(db, user.id, datos.account_id, bloquear=True)
        actual = db.query(models.Account).filter(models.Account.id == regla.account_id).first()
        if actual is not None and actual.currency != nueva.currency:
            raise ValidationError("La cuenta debe tener la misma moneda que la cuenta actual de la regla.")
        regla.account_id = nueva.id
    if "category_id" in enviados and datos.category_id is not None and datos.category_id != regla.category_id:
        regla.category_id = _categoria_del_usuario(db, user.id, datos.category_id).id
    if "status" in enviados and datos.status is not None:
        nuevo = datos.status.value
        if regla.status == "paused" and nuevo == "active":
            # D11: al reanudar no se acumulan las ocurrencias de la pausa.
            regla.next_date = primera_desde(regla.start_date, regla.frequency, max(regla.next_date, hoy))
        regla.status = nuevo

    db.flush()
    db.refresh(regla)
    return _construir(db, user, [regla], hoy)[0]


def eliminar(db: Session, user: models.User, rule_id: int) -> None:
    regla = _obtener(db, user.id, rule_id, bloquear=True)
    db.delete(regla)


def pendientes(db: Session, user: models.User, ahora: datetime) -> list[dict]:
    """Ocurrencias vencidas (`<= hoy`) de las reglas activas, hasta 12 por regla (D10), de más
    antigua a más nueva. Solo la primera de cada regla (`is_next`) se puede resolver (D9)."""
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    salida = []
    for regla, cuenta in _reglas_vigentes(db, user):
        fechas = ocurrencias_en(regla.start_date, regla.frequency, regla.next_date, hoy, MAX_PENDIENTES_POR_REGLA)
        for fecha in fechas:
            salida.append(
                {
                    "rule_id": regla.id,
                    "name": regla.name,
                    "type": regla.type,
                    "amount": regla.amount,
                    "currency": cuenta.currency,
                    "account_id": regla.account_id,
                    "category_id": regla.category_id,
                    "frequency": regla.frequency,
                    "occurrence_date": fecha,
                    "is_next": fecha == regla.next_date,
                }
            )
    salida.sort(key=lambda o: (o["occurrence_date"], o["rule_id"]))
    return salida


def _validar_ocurrencia(regla: models.RecurringRule, ocurrencia: date, hoy: date) -> None:
    """D9: solo se resuelve la ocurrencia más antigua, y solo si ya venció."""
    if regla.status != "active":
        raise ConflictError("La regla está pausada; reanúdala para resolver ocurrencias.")
    if ocurrencia != regla.next_date:
        raise ConflictError(f"La ocurrencia a resolver es la del {regla.next_date.isoformat()}.")
    if ocurrencia > hoy:
        raise ConflictError("Esta ocurrencia todavía no vence.")


def _avanzar(regla: models.RecurringRule) -> None:
    regla.next_date = siguiente_ocurrencia(regla.start_date, regla.frequency, regla.next_date)


def confirmar(
    db: Session, user: models.User, rule_id: int, ocurrencia: date, monto: Decimal | None, ahora: datetime
) -> models.Transaction:
    """Crea la transacción de la ocurrencia, mueve el saldo y avanza `next_date` (D8). Orden de
    locks: regla → cuenta (D20). El caller comitea y luego evalúa las alertas de presupuesto."""
    tz = get_zoneinfo(user.timezone)
    hoy = dia_local(ahora, tz)
    regla = _obtener(db, user.id, rule_id, bloquear=True)
    _validar_ocurrencia(regla, ocurrencia, hoy)
    cuenta = _cuenta_del_usuario(db, user.id, regla.account_id)
    _categoria_del_usuario(db, user.id, regla.category_id)

    importe = monto if monto is not None else regla.amount
    transaccion = models.Transaction(
        amount=importe,
        type=regla.type,
        date=instante_de_dia(ocurrencia, ahora, tz),
        description=regla.name,
        user_id=user.id,
        account_id=cuenta.id,
        category_id=regla.category_id,
        currency=cuenta.currency,  # hereda la moneda de la cuenta
    )
    db.add(transaccion)
    db.flush()
    ledger.registrar_impacto(db, cuenta.id, regla.type, importe)
    _avanzar(regla)
    return transaccion


def saltar(db: Session, user: models.User, rule_id: int, ocurrencia: date, ahora: datetime) -> dict:
    """Avanza `next_date` sin registrar nada (D9)."""
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    regla = _obtener(db, user.id, rule_id, bloquear=True)
    _validar_ocurrencia(regla, ocurrencia, hoy)
    _avanzar(regla)
    db.flush()
    db.refresh(regla)
    return _construir(db, user, [regla], hoy)[0]


def calendario(db: Session, user: models.User, ahora: datetime) -> dict:
    """12 meses calendario (el actual + 11) de cargos e ingresos proyectados, con totales por
    moneda y por mes, y el compromiso mensualizado de las reglas de gasto (D13, D14)."""
    hoy = dia_local(ahora, get_zoneinfo(user.timezone))
    primer_mes = primer_dia_del_mes(hoy)
    ultimo_mes = sumar_meses(primer_mes, MESES_CALENDARIO - 1)
    hasta = ultimo_mes.replace(day=ultimo_dia_mes(ultimo_mes.year, ultimo_mes.month))
    meses = [sumar_meses(primer_mes, i) for i in range(MESES_CALENDARIO)]
    items: dict[tuple[int, int], list[dict]] = {(m.year, m.month): [] for m in meses}
    compromiso: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for regla, cuenta in _reglas_vigentes(db, user):
        if regla.type == "expense":
            compromiso[cuenta.currency] += equivalente_mensual(regla.amount, regla.frequency)
        # Las vencidas de meses anteriores están en "pendientes": el calendario arranca en el mes actual.
        desde = regla.next_date
        if desde < primer_mes:
            desde = primera_desde(regla.start_date, regla.frequency, primer_mes)
        for fecha in ocurrencias_en(regla.start_date, regla.frequency, desde, hasta, TOPE_PROYECCION):
            items[(fecha.year, fecha.month)].append(
                {
                    "rule_id": regla.id,
                    "name": regla.name,
                    "type": regla.type,
                    "amount": regla.amount,
                    "currency": cuenta.currency,
                    "date": fecha,
                    "is_annual": regla.frequency == "yearly",
                    "is_overdue": fecha < hoy,
                }
            )

    salida_meses = []
    for m in meses:
        lista = sorted(items[(m.year, m.month)], key=lambda i: (i["date"], i["rule_id"]))
        por_moneda: dict[str, dict[str, Decimal]] = {}
        for it in lista:
            t = por_moneda.setdefault(it["currency"], {"income": Decimal("0.00"), "expense": Decimal("0.00")})
            t[it["type"]] += it["amount"]
        salida_meses.append(
            {
                "month": f"{m.year:04d}-{m.month:02d}",
                "items": lista,
                "totals": [
                    {"currency": c, "income": t["income"], "expense": t["expense"], "net": t["income"] - t["expense"]}
                    for c, t in sorted(por_moneda.items())
                ],
            }
        )
    return {
        "months": salida_meses,
        "monthly_commitment": [{"currency": c, "amount": a} for c, a in sorted(compromiso.items())],
    }


def sugerencias(db: Session, user: models.User, ahora: datetime) -> list[dict]:
    """Gastos de los últimos 26 meses que parecen un cargo anual y todavía no son una regla (D15)."""
    tz = get_zoneinfo(user.timezone)
    hoy = dia_local(ahora, tz)
    inicio, fin = rango_dias(sumar_meses(hoy, -MESES_HISTORIAL_SUGERENCIAS), hoy, tz)
    transacciones = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.user_id == user.id,
            models.Transaction.type == "expense",
            models.Transaction.description.isnot(None),
            models.Transaction.date >= inicio,
            models.Transaction.date < fin,
        )
        .order_by(models.Transaction.date, models.Transaction.id)
        .all()
    )
    grupos: dict[tuple[int, str, str], list[models.Transaction]] = defaultdict(list)
    for t in transacciones:
        nombre = normalizar_nombre(t.description)
        if nombre:
            grupos[(t.account_id, nombre, t.currency)].append(t)

    ya_recurrentes = {
        (r.account_id, normalizar_nombre(r.name))
        for r in db.query(models.RecurringRule).filter(models.RecurringRule.user_id == user.id).all()
    }
    limite_ultima = sumar_meses(hoy, -MESES_MAX_ULTIMA_OCURRENCIA)
    limite_proxima = sumar_meses(hoy, MESES_CALENDARIO)

    candidatas = []
    for (cuenta_id, nombre, moneda), grupo in grupos.items():
        if (cuenta_id, nombre) in ya_recurrentes:
            continue
        fechas = [dia_local(t.date, tz) for t in grupo]
        cierre = indice_ultima_pareja_anual(fechas, [t.amount for t in grupo])
        if cierre is None:
            continue
        # La sugerencia sale de la pareja anual (no de un cargo duplicado posterior).
        ultima = grupo[cierre]
        ultima_fecha = fechas[cierre]
        proxima = sumar_meses(ultima_fecha, 12)
        if ultima_fecha < limite_ultima or proxima > limite_proxima:
            continue
        candidatas.append((ultima, ultima_fecha, proxima, moneda, len(grupo)))

    if not candidatas:
        return []
    # Solo se sugiere lo que se puede crear: cuenta y categoría de la última siguen vivas.
    fantasmas = [models.RecurringRule(account_id=u.account_id, category_id=u.category_id) for u, *_ in candidatas]
    cuentas, categorias = _referencias(db, user.id, fantasmas)
    salida = []
    for ultima, ultima_fecha, proxima, moneda, cantidad in candidatas:
        if ultima.account_id not in cuentas or ultima.category_id not in categorias:
            continue
        salida.append(
            {
                "name": ultima.description.strip()[:100],
                "account_id": ultima.account_id,
                "category_id": ultima.category_id,
                "currency": moneda,
                "amount": ultima.amount,
                "last_date": ultima_fecha,
                "suggested_start_date": proxima,
                "occurrences": cantidad,
            }
        )
    salida.sort(key=lambda s: (s["suggested_start_date"], s["name"]))
    return salida
