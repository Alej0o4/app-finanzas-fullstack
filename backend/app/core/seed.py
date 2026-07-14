from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import models


def _make_tx(db, user, account, category_name, category_type, amount, description, date):
    category = db.query(models.Category).filter(
        or_(models.Category.user_id.is_(None), models.Category.user_id == user.id),
        models.Category.name == category_name,
        models.Category.type == category_type,
    ).first()
    if category is None:
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
            db.delete(existing)
            db.flush()

        user = models.User(
            email="test@test.com",
            full_name="Test User",
            password_hash=get_password_hash("testpass123"),
            preferred_currency="COP",
            preferred_locale="es-CO",
        )
        db.add(user)
        db.flush()
        print(f"User created: id={user.id}")

        freelance = models.Category(name="Freelance", type="income", user_id=user.id)
        servicios = models.Category(name="Servicios Públicos", type="expense", user_id=user.id)
        db.add_all([freelance, servicios])
        db.flush()

        cuenta = models.Account(
            name="Cuenta Principal", type="cash", balance=Decimal("14478000"),
            currency="COP", user_id=user.id, highlighted=True,
        )
        ahorros = models.Account(
            name="Ahorros USD", type="debit", balance=Decimal("4615"),
            currency="USD", user_id=user.id, highlighted=True,
        )
        tarjeta = models.Account(
            name="Tarjeta Crédito", type="credit", balance=Decimal("-250000"),
            currency="COP", user_id=user.id,
        )
        db.add_all([cuenta, ahorros, tarjeta])
        db.flush()
        print(f"Accounts created: {cuenta.id} (COP), {ahorros.id} (USD), {tarjeta.id} (Tarjeta)")

        tx_data = [
            # --- MAYO 2026 ---
            (cuenta,   "Salario",            "income",  3000000, "Salario mensual",                     datetime(2026, 5, 1)),
            (cuenta,   "Alimentación",       "expense", 130000,  "Mercado semanal",                    datetime(2026, 5, 5)),
            (cuenta,   "Ocio",               "expense", 200000,  "Cena y cervezas",                    datetime(2026, 5, 8)),
            (cuenta,   "Transporte",         "expense", 35000,   "Gasolina",                           datetime(2026, 5, 12)),
            (cuenta,   "Suscripción",        "expense", 25000,   "Netflix",                            datetime(2026, 5, 15)),
            (cuenta,   "Alimentación",       "expense", 85000,   "Mercado",                            datetime(2026, 5, 18)),
            (cuenta,   "Freelance",          "income",  500000,  "Diseño web - Cliente A",            datetime(2026, 5, 22)),
            (cuenta,   "Cuidado personal",   "expense", 85000,   "Barbería",                           datetime(2026, 5, 25)),
            (ahorros,  "Salario",            "income",  1200,    "Bono USD - proyecto internacional",  datetime(2026, 5, 20)),

            # --- JUNIO 2026 ---
            (cuenta,   "Salario",            "income",  3200000, "Salario mensual",                     datetime(2026, 6, 1)),
            (cuenta,   "Alimentación",       "expense", 95000,   "Desayuno y almuerzo fuera",          datetime(2026, 6, 3)),
            (cuenta,   "Transporte",         "expense", 18000,   "Uber",                               datetime(2026, 6, 5)),
            (cuenta,   "Alimentación",       "expense", 150000,  "Mercado quincenal",                  datetime(2026, 6, 8)),
            (cuenta,   "Servicios Públicos", "expense", 250000,  "Agua + Luz + Gas",                    datetime(2026, 6, 10)),
            (cuenta,   "Ocio",               "expense", 85000,   "Cine y palomitas",                   datetime(2026, 6, 12)),
            (cuenta,   "Suscripción",        "expense", 25000,   "Spotify",                            datetime(2026, 6, 15)),
            (cuenta,   "Alimentación",       "expense", 62000,   "Almuerzo ejecutivo",                 datetime(2026, 6, 18)),
            (cuenta,   "Transporte",         "expense", 45000,   "Gasolina",                           datetime(2026, 6, 20)),
            (cuenta,   "Freelance",          "income",  800000,  "App mobile - Cliente B",            datetime(2026, 6, 22)),
            (cuenta,   "Cuidado personal",   "expense", 120000,  "Corte + productos",                  datetime(2026, 6, 25)),
            (cuenta,   "Otro",               "expense", 45000,   "Regalo cumpleaños",                  datetime(2026, 6, 28)),
            (ahorros,  "Ocio",               "expense", 300,     "Viaje fin de semana",                datetime(2026, 6, 25)),
            (tarjeta,  "Alimentación",       "expense", 250000,  "Cena restaurante",                   datetime(2026, 6, 28)),

            # --- JULIO 2026 ---
            (cuenta,   "Salario",            "income",  3500000, "Salario mensual",                     datetime(2026, 7, 1)),
            (cuenta,   "Alimentación",       "expense", 45000,   "Café y pan",                         datetime(2026, 7, 2)),
            (cuenta,   "Transporte",         "expense", 12000,   "Bus",                                datetime(2026, 7, 3)),
            (cuenta,   "Alimentación",       "expense", 120000,  "Mercado semanal",                    datetime(2026, 7, 5)),
            (cuenta,   "Servicios Públicos", "expense", 280000,  "Agua + Luz + Internet",               datetime(2026, 7, 7)),
            (cuenta,   "Ocio",               "expense", 180000,  "Concierto",                          datetime(2026, 7, 8)),
            (cuenta,   "Alimentación",       "expense", 55000,   "Almuerzo",                           datetime(2026, 7, 12)),
            (cuenta,   "Alimentación",       "expense", 90000,   "Mercado quincenal",                  datetime(2026, 7, 14)),
            (cuenta,   "Suscripción",        "expense", 25000,   "Netflix",                            datetime(2026, 7, 15)),
            (cuenta,   "Transporte",         "expense", 85000,   "Gasolina",                           datetime(2026, 7, 10)),
            (cuenta,   "Transporte",         "expense", 15000,   "Taxi",                               datetime(2026, 7, 16)),
            (cuenta,   "Ocio",               "expense", 55000,   "Videojuego",                         datetime(2026, 7, 18)),
            (cuenta,   "Freelance",          "income",  1200000, "Consultoría - Cliente C",            datetime(2026, 7, 20)),
            (cuenta,   "Suscripción",        "expense", 25000,   "Spotify",                            datetime(2026, 7, 22)),
            (cuenta,   "Cuidado personal",   "expense", 95000,   "Barbería + productos",               datetime(2026, 7, 24)),
            (cuenta,   "Otro",               "expense", 60000,   "Libro",                              datetime(2026, 7, 25)),
            (cuenta,   "Alimentación",       "expense", 78000,   "Despensa",                           datetime(2026, 7, 27)),
            (cuenta,   "Transporte",         "expense", 22000,   "Uber",                               datetime(2026, 7, 28)),
            (cuenta,   "Suscripción",        "expense", 25000,   "Crunchyroll",                        datetime(2026, 7, 30)),
            (ahorros,  "Salario",            "income",  1500,    "Bono USD - Julio",                   datetime(2026, 7, 3)),
            (ahorros,  "Ocio",               "expense", 200,     "Cena fuera",                         datetime(2026, 7, 15)),
            (ahorros,  "Alimentación",       "expense", 85,      "Mercado USD",                        datetime(2026, 7, 25)),
        ]

        transactions = []
        for account, cat_name, cat_type, amount, desc, date in tx_data:
            tx = _make_tx(db, user, account, cat_name, cat_type, amount, desc, date)
            if tx is not None:
                transactions.append(tx)

        db.add_all(transactions)
        db.flush()
        print(f"Transactions created: {len(transactions)}")

        budgets_data = [
            ("Alimentación",     Decimal("1500000"), 7, 2026),
            ("Transporte",       Decimal("400000"),  7, 2026),
            ("Ocio",             Decimal("500000"),  7, 2026),
            ("Suscripción",      Decimal("100000"),  7, 2026),
            ("Cuidado personal", Decimal("200000"),  7, 2026),
            ("Servicios Públicos", Decimal("300000"), 7, 2026),
        ]

        budgets = []
        for cat_name, amount_limit, month, year in budgets_data:
            category = db.query(models.Category).filter(
                or_(models.Category.user_id.is_(None), models.Category.user_id == user.id),
                models.Category.name == cat_name,
                models.Category.type == "expense",
            ).first()
            if category is None:
                continue
            budget = models.Budget(
                amount_limit=amount_limit,
                currency="COP",
                month=month,
                year=year,
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
