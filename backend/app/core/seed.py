import calendar
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import models

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
    year, month = _shift_months(today.year, today.month, months_ago)
    last_day_of_month = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day_of_month))


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
    return [row for row in tx_data if row[-1].date() <= today.date()]


def run_seed():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.email == "test@test.com").first()
        if existing:
            db.query(models.Budget).filter(models.Budget.user_id == existing.id).delete()
            db.query(models.Transaction).filter(models.Transaction.user_id == existing.id).delete()
            db.query(models.Account).filter(models.Account.user_id == existing.id).delete()
            db.query(models.Category).filter(models.Category.user_id == existing.id).delete()
            db.query(models.RefreshToken).filter(models.RefreshToken.user_id == existing.id).delete()
            # user_id es NOT NULL en las tres (Fases 7 y 10): sin borrarlas explícitamente,
            # db.delete(existing) intenta poner user_id=NULL vía el FK y revienta con
            # IntegrityError apenas el usuario de prueba tiene algún token o idempotency key
            # real generado por uso normal de la app (p. ej. probar "olvidé mi contraseña" o
            # reintentar un POST /transactions con Idempotency-Key).
            db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == existing.id).delete()
            db.query(models.EmailVerificationToken).filter(
                models.EmailVerificationToken.user_id == existing.id
            ).delete()
            db.query(models.IdempotencyKey).filter(models.IdempotencyKey.user_id == existing.id).delete()
            db.delete(existing)
            db.flush()

        user = models.User(
            email="test@test.com",
            full_name="Test User",
            password_hash=get_password_hash("testpass123"),
            preferred_currency="COP",
            preferred_locale="es-CO",
            monthly_income=Decimal("3500000"),
        )
        db.add(user)
        db.flush()
        print(f"User created: id={user.id}")

        freelance = models.Category(name="Freelance", type="income", user_id=user.id)
        servicios = models.Category(name="Servicios Públicos", type="expense", user_id=user.id)
        db.add_all([freelance, servicios])
        db.flush()

        cuenta = models.Account(
            name="Cuenta Principal",
            type="cash",
            balance=Decimal("14478000"),
            currency="COP",
            user_id=user.id,
            highlighted=True,
        )
        ahorros = models.Account(
            name="Ahorros USD",
            type="debit",
            balance=Decimal("4615"),
            currency="USD",
            user_id=user.id,
            highlighted=True,
        )
        tarjeta = models.Account(
            name="Tarjeta Crédito",
            type="credit",
            balance=Decimal("-250000"),
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
                month=today.month,
                year=today.year,
                is_recurring=True,
                user_id=user.id,
                category_id=category.id,
            )
            budgets.append(budget)

        db.add_all(budgets)
        db.commit()
        print(f"Budgets created: {len(budgets)}")
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
