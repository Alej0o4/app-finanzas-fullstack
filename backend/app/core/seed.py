import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.default_categories import ensure_default_categories
from app.core.periods import dia_local, instante_de_dia, mediodia_local, sumar_meses
from app.core.security import get_password_hash
from app.core.timezones import DEFAULT_TIMEZONE, get_zoneinfo
from app.core.user_deletion import delete_user_cascade
from app.models import models
from app.services import cdt as cdt_service
from app.services import funds as funds_service
from app.services import recurring as recurring_service
from app.services.ledger import registrar_impacto

# Cuántos meses hacia atrás cubre el seed, además del mes en curso (Fase 11, seguimiento:
# antes las fechas estaban fijas en mayo-julio 2026 y quedaban "viejas" apenas cambiaba el
# mes real). Con MONTHS_BACK=5 el seed siempre cubre "hoy" + 5 meses atrás, sin importar
# cuándo se corra.
MONTHS_BACK = 5


def _shift_months(base_year: int, base_month: int, delta: int) -> tuple[int, int]:
    """(year, month) que resulta de retroceder `delta` meses desde (base_year, base_month)."""
    total = base_year * 12 + (base_month - 1) - delta
    return total // 12, total % 12 + 1


def _seed_date(today: datetime, months_ago: int, day: int) -> datetime:
    """Instante de una transacción de seed, coherente con B9 (Fase 34): las 12:00 locales del
    día en la zona del usuario seed (Bogotá); si el día es hoy, la hora real."""
    tz = get_zoneinfo(DEFAULT_TIMEZONE)
    hoy = dia_local(today, tz)
    year, month = _shift_months(hoy.year, hoy.month, months_ago)
    last_day_of_month = calendar.monthrange(year, month)[1]
    return instante_de_dia(date(year, month, min(day, last_day_of_month)), today, tz)


def _make_tx(db, user, account, category_name, category_type, amount, description, date):
    category = (
        db.query(models.Category)
        .filter(
            or_(models.Category.user_id.is_(None), models.Category.user_id == user.id),
            models.Category.name == category_name,
            models.Category.type == category_type,
        )
        .first()
    )
    if category is None:
        # No debe pasar en silencio: la última vez que pasó (categoría "Ocio" renombrada a
        # "Entretenimiento" en Fase 8) el seed perdió 6 transacciones y 1 presupuesto sin
        # ningún error visible.
        print(f"WARNING: categoría de seed no encontrada: '{category_name}' ({category_type}) — se omite la fila")
        return None
    return models.Transaction(
        amount=Decimal(str(amount)),
        currency=account.currency,
        type=category_type,
        description=description,
        date=date,
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
    )


def _build_transactions_data(cuenta, ahorros, tarjeta, today: datetime) -> list[tuple]:
    """Genera las filas de transacciones para el mes en curso y los `MONTHS_BACK` anteriores,
    con fechas relativas a `today` (Fase 11, seguimiento). El mes en curso solo incluye días
    hasta hoy — nada de fechas futuras aunque la plantilla las pida."""
    tx_data: list[tuple] = []

    for months_ago in range(MONTHS_BACK, -1, -1):  # de más viejo a más reciente
        # El ingreso mensual sube ~100.000 por mes para simular una progresión real, igual
        # que el seed original (3.000.000 en el mes más viejo → 3.500.000 en el actual).
        salario = 3_000_000 + (MONTHS_BACK - months_ago) * 100_000

        def d(day: int, _months_ago: int = months_ago) -> datetime:
            return _seed_date(today, _months_ago, day)

        tx_data += [
            (cuenta, "Salario", "income", salario, "Salario mensual", d(1)),
            (cuenta, "Alimentación", "expense", 90_000 + months_ago * 3_000, "Mercado quincenal", d(5)),
            (cuenta, "Transporte", "expense", 30_000 + months_ago * 2_000, "Gasolina", d(7)),
            (cuenta, "Servicios Públicos", "expense", 250_000, "Agua + Luz + Internet", d(9)),
            (cuenta, "Entretenimiento", "expense", 90_000, "Cine y salidas", d(12)),
            (cuenta, "Alimentación", "expense", 70_000, "Mercado", d(15)),
            (cuenta, "Suscripción", "expense", 25_000, "Netflix", d(15)),
            (cuenta, "Transporte", "expense", 18_000, "Uber", d(18)),
            (cuenta, "Cuidado personal", "expense", 90_000, "Barbería", d(20)),
            (cuenta, "Suscripción", "expense", 25_000, "Spotify", d(22)),
        ]

        if months_ago % 2 == 0:
            tx_data.append((cuenta, "Freelance", "income", 500_000 + months_ago * 50_000, "Proyecto freelance", d(23)))
        if months_ago % 3 == 0:
            tx_data.append((cuenta, "Otro", "expense", 50_000, "Gastos varios", d(27)))

        tx_data.append((ahorros, "Salario", "income", 1_200 + (MONTHS_BACK - months_ago) * 50, "Bono USD", d(20)))
        if months_ago % 2 == 1:
            tx_data.append((ahorros, "Entretenimiento", "expense", 200, "Compra en USD", d(15)))

        if months_ago % 3 == 1:
            tx_data.append((tarjeta, "Alimentación", "expense", 200_000, "Cena restaurante", d(28)))

    # El mes en curso no debe tener fechas futuras: descarta cualquier fila cuyo día caiga
    # después de hoy (equivale a "solo lo que ya pasó este mes").
    tz = get_zoneinfo(DEFAULT_TIMEZONE)
    return [row for row in tx_data if dia_local(row[-1], tz) <= dia_local(today, tz)]


def _categoria(db, user, nombre: str, tipo: str) -> models.Category:
    return (
        db.query(models.Category)
        .filter(
            or_(models.Category.user_id.is_(None), models.Category.user_id == user.id),
            models.Category.name == nombre,
            models.Category.type == tipo,
        )
        .one()
    )


def _crear_sobre(
    db,
    user,
    cuenta,
    nombre,
    tipo,
    *,
    aportes=(),
    target_amount=None,
    target_months=None,
    target_date=None,
    status="active",
):
    """Sobre de seed. `aportes`: (meses_atrás, día, monto, tipo_de_entrada) — el libro es la fuente
    del saldo, igual que en la app (`SUM(fund_entries.amount)`)."""
    tz = get_zoneinfo(DEFAULT_TIMEZONE)
    sobre = models.Fund(
        user_id=user.id,
        account_id=cuenta.id,
        name=nombre,
        kind=tipo,
        currency=cuenta.currency,
        target_amount=Decimal(str(target_amount)) if target_amount is not None else None,
        target_months=target_months,
        target_date=mediodia_local(target_date, tz) if target_date else None,
        status=status,
    )
    db.add(sobre)
    db.flush()
    ahora = datetime.now(UTC)
    for meses_atras, dia, monto, tipo_entrada in aportes:
        ocurrido = _seed_date(ahora, meses_atras, dia)
        local = dia_local(ocurrido, tz)
        db.add(
            models.FundEntry(
                fund_id=sobre.id,
                user_id=user.id,
                amount=Decimal(str(monto)) if tipo_entrada == "contribution" else -Decimal(str(monto)),
                type=tipo_entrada,
                occurred_at=ocurrido,
                period=f"{local.year:04d}-{local.month:02d}",
            )
        )
    db.flush()
    return sobre


def _gasto_con_sobre(db, user, cuenta, sobre, categoria, monto, descripcion, dias_atras):
    """Gasto normal pagado con un sobre (Fase 36): mismo camino que la API — transacción, impacto en
    la cuenta y retiro enlazado por `min(gasto, saldo)`."""
    ahora = datetime.now(UTC)
    tz = get_zoneinfo(DEFAULT_TIMEZONE)
    dia = dia_local(ahora, tz) - timedelta(days=dias_atras)
    tx = _make_tx(db, user, cuenta, categoria, "expense", monto, descripcion, instante_de_dia(dia, ahora, tz))
    db.add(tx)
    db.flush()
    registrar_impacto(db, cuenta.id, "expense", tx.amount)
    aplicado = funds_service.aplicar_gasto(db, user, sobre, tx.id, tx.amount, ahora)
    return tx, aplicado


def _seed_sobres(db, user, cuenta, ahorros, tarjeta, hoy: date):
    """Sobres para probar la Fase 35/36: uno por tipo y por situación (en ritmo, cumplido, sin
    respaldo, archivado, con gastos enlazados, en otra moneda)."""
    _crear_sobre(  # gasto anual en ritmo, vence en 4 meses
        db,
        user,
        cuenta,
        "SOAT",
        "annual_expense",
        target_amount=1200000,
        target_date=sumar_meses(hoy, 4),
        aportes=[(2, 5, 300000, "contribution"), (1, 5, 300000, "contribution")],
    )
    _crear_sobre(  # emergencia por meses de gasto (la meta sale del promedio de los 3 meses previos)
        db,
        user,
        cuenta,
        "Fondo de emergencia",
        "emergency",
        target_months=3,
        aportes=[(3, 2, 1000000, "contribution"), (1, 2, 500000, "contribution")],
    )
    _crear_sobre(  # meta en USD, otra moneda: poco aportado y vence en 3 meses
        db,
        user,
        ahorros,
        "Viaje a Lisboa",
        "goal",
        target_amount=2000,
        target_date=sumar_meses(hoy, 3),
        aportes=[(1, 10, 150, "contribution")],
    )
    _crear_sobre(  # cumplido
        db,
        user,
        cuenta,
        "Regalos de diciembre",
        "goal",
        target_amount=500000,
        aportes=[(2, 20, 300000, "contribution"), (0, 1, 200000, "contribution")],
    )
    _crear_sobre(  # sin respaldo: la tarjeta está en negativo y se apartó plata en ella
        db,
        user,
        tarjeta,
        "Pago de la tarjeta",
        "goal",
        target_amount=400000,
        aportes=[(0, 1, 100000, "contribution")],
    )
    _crear_sobre(  # archivado: aporte y retiro completo (saldo 0)
        db,
        user,
        cuenta,
        "Matrícula 2025",
        "goal",
        target_amount=800000,
        status="archived",
        aportes=[(4, 3, 800000, "contribution"), (3, 3, 800000, "withdrawal")],
    )
    ropa = _crear_sobre(
        db, user, cuenta, "Ropa", "goal", target_amount=600000, aportes=[(1, 8, 250000, "contribution")]
    )
    # Gastos pagados con el sobre: el primero cabe entero, el segundo excede el saldo (queda
    # 130.000 en el sobre → se aplican 130.000 y el resto cae como gasto normal).
    _gasto_con_sobre(db, user, cuenta, ropa, "Cuidado personal", 120000, "Chaqueta", 6)
    _gasto_con_sobre(db, user, cuenta, ropa, "Cuidado personal", 200000, "Zapatos", 2)


def _seed_recurrentes(db, user, cuenta, ahorros, hoy: date, today: datetime):
    """Reglas para probar la Fase 37: pendientes vencidas (varias por regla), al día, pausada, anual,
    en otra moneda, y un cargo anual detectable que todavía NO es regla (sugerencias)."""
    tz = get_zoneinfo(DEFAULT_TIMEZONE)

    def regla(nombre, tipo, monto, cuenta_, categoria, frecuencia, inicio, *, estado="active", al_dia=False):
        siguiente = recurring_service.primera_desde(inicio, frecuencia, hoy + timedelta(days=1)) if al_dia else inicio
        db.add(
            models.RecurringRule(
                user_id=user.id,
                account_id=cuenta_.id,
                category_id=_categoria(db, user, categoria, tipo).id,
                name=nombre,
                type=tipo,
                amount=Decimal(str(monto)),
                frequency=frecuencia,
                start_date=inicio,
                next_date=siguiente,
                status=estado,
            )
        )

    primero_mes = hoy.replace(day=1)
    regla("Arriendo", "expense", 1200000, cuenta, "Vivienda", "monthly", sumar_meses(primero_mes, -2))  # 3 pendientes
    regla("Clase de guitarra", "expense", 40000, cuenta, "Entretenimiento", "weekly", hoy - timedelta(days=8))
    regla("Netflix", "expense", 25000, cuenta, "Suscripción", "monthly", hoy.replace(day=15), al_dia=True)
    regla("Salario mensual", "income", 3500000, cuenta, "Salario", "monthly", primero_mes, al_dia=True)
    regla("Seguro del carro", "expense", 900000, cuenta, "Transporte", "yearly", hoy + timedelta(days=45))
    regla("Gimnasio", "expense", 90000, cuenta, "Cuidado personal", "monthly", sumar_meses(hoy, -1), estado="paused")
    regla("iCloud", "expense", 3, ahorros, "Suscripción", "monthly", hoy + timedelta(days=3))  # USD

    # Cargo anual detectable (sugerencias): dos cobros separados 365 días con montos parecidos, el
    # último hace ~10 meses, para que la próxima caiga dentro de los 12 meses del calendario.
    for dias_atras, monto in ((665, 280000), (300, 300000)):
        dia = hoy - timedelta(days=dias_atras)
        tx = _make_tx(
            db, user, cuenta, "Transporte", "expense", monto, "Seguro de moto", instante_de_dia(dia, today, tz)
        )
        db.add(tx)
        db.flush()
        registrar_impacto(db, cuenta.id, "expense", tx.amount)


def _seed_cdts(db, user, hoy: date):
    """CDT para probar la Fase 38: vigente, por vencer (<= 15 días), vencido sin redimir, redimido
    con rendimiento y en USD. Fechas relativas a hoy; no tocan cuentas ni transacciones (D1)."""

    def cdt(nombre, moneda, capital, tasa, abierto_hace, vence_en, *, redimido_hace=None):
        abierto = hoy - timedelta(days=abierto_hace)
        vence = hoy + timedelta(days=vence_en)
        capital = Decimal(str(capital))
        tasa = Decimal(str(tasa))
        fila = models.Cdt(
            user_id=user.id,
            name=nombre,
            currency=moneda,
            principal=capital,
            rate_ea=tasa,
            opened_on=abierto,
            maturity_on=vence,
            status="active",
        )
        if redimido_hace is not None:
            dia = hoy - timedelta(days=redimido_hace)
            fila.status = "redeemed"
            fila.redeemed_on = dia
            fila.final_amount = capital + cdt_service.interes_causado(
                capital, tasa, cdt_service.dias_transcurridos(abierto, vence, dia)
            )
        db.add(fila)

    cdt("CDT Bancolombia", "COP", 10000000, 11.5, 120, 60)  # vigente
    cdt("CDT Davivienda", "COP", 5000000, 10.8, 170, 10)  # por vencer
    cdt("CDT Banco de Bogotá", "COP", 3000000, 12.0, 200, -5)  # vencido sin redimir
    cdt("CDT Nu", "COP", 4000000, 11.0, 400, -35, redimido_hace=35)  # redimido con rendimiento
    cdt("CDT en dólares", "USD", 2000, 5.2, 60, 300)  # otra moneda


def run_seed():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.email == "test@test.com").first()
        if existing:
            # Orden de borrado dictado por FKs (ninguna tiene ondelete=CASCADE): lo
            # implementa delete_user_cascade en user_deletion.py (Decisión A3, Fase 21).
            delete_user_cascade(db, existing)
            db.flush()

        user = models.User(
            email="test@test.com",
            full_name="Test User",
            password_hash=get_password_hash("testpass123"),
            preferred_currency="COP",
            preferred_locale="es-CO",
            monthly_income=Decimal("3500000"),
            timezone=DEFAULT_TIMEZONE,
            # Login exige email_verified desde el gate agregado en auth.py — sin esto, el
            # usuario de seed quedaría bloqueado para iniciar sesión.
            email_verified=True,
        )
        db.add(user)
        db.flush()
        # QA-016: las categorías del sistema las siembra el startup de la app; si el seed corre
        # antes del primer arranque de uvicorn, las crea acá (misma función, idempotente).
        ensure_default_categories(db)
        print(f"User created: id={user.id}")

        freelance = models.Category(name="Freelance", type="income", user_id=user.id)
        servicios = models.Category(name="Servicios Públicos", type="expense", user_id=user.id)
        db.add_all([freelance, servicios])
        db.flush()

        cuenta = models.Account(
            name="Cuenta Principal",
            type="cash",
            balance=Decimal("14478000"),
            opening_balance=Decimal("14478000"),
            currency="COP",
            user_id=user.id,
            highlighted=True,
        )
        ahorros = models.Account(
            name="Ahorros USD",
            type="debit",
            balance=Decimal("4615"),
            opening_balance=Decimal("4615"),
            currency="USD",
            user_id=user.id,
            highlighted=True,
        )
        tarjeta = models.Account(
            name="Tarjeta Crédito",
            type="credit",
            balance=Decimal("-250000"),
            opening_balance=Decimal("-250000"),
            currency="COP",
            user_id=user.id,
        )
        db.add_all([cuenta, ahorros, tarjeta])
        db.flush()
        print(f"Accounts created: {cuenta.id} (COP), {ahorros.id} (USD), {tarjeta.id} (Tarjeta)")

        today = datetime.now(UTC)
        tx_data = _build_transactions_data(cuenta, ahorros, tarjeta, today)

        transactions = []
        for account, cat_name, cat_type, amount, desc, date in tx_data:
            tx = _make_tx(db, user, account, cat_name, cat_type, amount, desc, date)
            if tx is not None:
                transactions.append(tx)

        db.add_all(transactions)
        db.flush()
        # QA-016: `balance` arranca en `opening_balance` y cada transacción lo mueve por el
        # mismo servicio que usa la API, así balance == opening_balance + neto.
        for tx in transactions:
            registrar_impacto(db, tx.account_id, tx.type, tx.amount)
        db.flush()
        print(f"Transactions created: {len(transactions)} (cubren hoy y los {MONTHS_BACK} meses anteriores)")

        # Presupuestos del mes en curso, marcados is_recurring=True: ensure_recurring_budgets_
        # for_period (Fase 8 §3) los clona automáticamente para cada mes siguiente la próxima
        # vez que se visite el dashboard, así que el seed sigue siendo válido sin volver a
        # correrlo, sin importar cuánto tiempo pase.
        budgets_data = [
            ("Alimentación", Decimal("1500000")),
            ("Transporte", Decimal("400000")),
            ("Entretenimiento", Decimal("500000")),
            ("Suscripción", Decimal("100000")),
            ("Cuidado personal", Decimal("200000")),
            ("Servicios Públicos", Decimal("300000")),
        ]

        budgets = []
        for cat_name, amount_limit in budgets_data:
            category = (
                db.query(models.Category)
                .filter(
                    or_(models.Category.user_id.is_(None), models.Category.user_id == user.id),
                    models.Category.name == cat_name,
                    models.Category.type == "expense",
                )
                .first()
            )
            if category is None:
                print(f"WARNING: categoría de presupuesto de seed no encontrada: '{cat_name}' — se omite")
                continue
            budget = models.Budget(
                amount_limit=amount_limit,
                currency="COP",
                month=dia_local(today, get_zoneinfo(DEFAULT_TIMEZONE)).month,
                year=dia_local(today, get_zoneinfo(DEFAULT_TIMEZONE)).year,
                is_recurring=True,
                user_id=user.id,
                category_id=category.id,
            )
            budgets.append(budget)

        db.add_all(budgets)
        db.flush()
        print(f"Budgets created: {len(budgets)}")

        hoy = dia_local(today, get_zoneinfo(DEFAULT_TIMEZONE))
        _seed_sobres(db, user, cuenta, ahorros, tarjeta, hoy)
        _seed_recurrentes(db, user, cuenta, ahorros, hoy, today)
        _seed_cdts(db, user, hoy)
        db.commit()
        print("Funds: 7 (1 archivado) con 2 gastos pagados con sobre · Recurring: 7 reglas + 1 cargo anual sugerido")
        print("CDT: 5 (vigente, por vencer, vencido sin redimir, redimido, en USD)")
        print("\n--- SEED COMPLETE ---")
        print("Login: test@test.com / testpass123")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
