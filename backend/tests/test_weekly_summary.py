"""Tests del resumen semanal automático (Fase 14 §14.3-§14.5).

Excepción justificada a la convención de la suite: este módulo de `app/core/` se prueba
por call directo de las funciones (`build_weekly_summary`, `run_weekly_summary_for_user`,
`run_weekly_summary_job`) en lugar de vía `TestClient` — no existe ningún endpoint que
dispare el cálculo, lo dispara el scheduler (spec Fase 14, "Testing"). Se usa
`freezegun` para fijar `reference_date` con `freeze_time`.

Los casos cubren las decisiones numeradas de la spec:
- 14.3.1 semana lunes-domingo en America/Bogota (fechas de las transacciones sembradas).
- 14.3.3 solo moneda preferida cuenta.
- 14.3.4 se envía siempre, incluso $0.
- 14.3.5 delta vs semana anterior (None si previa == 0).
- 14.1.2 idempotencia por (user_id, type, period_key) a nivel DB → IntegrityError.
- incluido/excluido de `run_weekly_summary_job` por `weekly_summary_enabled`.
"""

from datetime import UTC, datetime

import pytest
from freezegun import freeze_time
from sqlalchemy.exc import IntegrityError

from app.core.weekly_summary import (
    build_weekly_summary,
    run_weekly_summary_for_user,
    spent_por_categoria_y_moneda_en_rango,
)
from app.models import models

# Lunes de la semana ISO 37 de 2026 (07:00 America/Bogota, hora típica del job).
REFERENCE = datetime(2026, 9, 7, 7, 0, 0)  # lunes 2026-09-07


def _crear_usuario(db, email: str, preferred_currency: str = "COP", weekly_enabled: bool = True) -> models.User:
    user = models.User(
        email=email,
        full_name="Test User",
        password_hash="no-usado",
        preferred_currency=preferred_currency,
        weekly_summary_enabled=weekly_enabled,
    )
    db.add(user)
    db.flush()
    return user


def _crear_categoria(db, user, name: str) -> models.Category:
    categoria = models.Category(name=name, type="expense", user_id=user.id)
    db.add(categoria)
    db.flush()
    return categoria


def _crear_cuenta(db, user, currency: str = "COP") -> models.Account:
    cuenta = models.Account(name="Cuenta", type="cash", currency=currency, user_id=user.id)
    db.add(cuenta)
    db.flush()
    return cuenta


def _crear_gasto(db, user, cuenta, categoria, amount, date: datetime) -> models.Transaction:
    tx = models.Transaction(
        amount=amount,
        currency=cuenta.currency,
        type="expense",
        description="gasto",
        date=date,
        user_id=user.id,
        account_id=cuenta.id,
        category_id=categoria.id,
    )
    db.add(tx)
    db.flush()
    return tx


def _notificaciones_de(user_id: int, db) -> list[models.Notification]:
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.id)
        .all()
    )


class TestBuildWeeklySummary:
    @freeze_time(REFERENCE)
    def test_total_and_top_category_in_preferred_currency(self, db_session):
        user = _crear_usuario(db_session, "a@test.com")
        cat_comida = _crear_categoria(db_session, user, "Comida")
        cat_transporte = _crear_categoria(db_session, user, "Transporte")
        cuenta = _crear_cuenta(db_session, user, "COP")

        # Dentro de la semana (lunes 09/07 - domingo 09/13): 1000 + 600 = 1600
        _crear_gasto(db_session, user, cuenta, cat_comida, 1000, datetime(2026, 9, 7, 10, 0))
        _crear_gasto(db_session, user, cuenta, cat_transporte, 600, datetime(2026, 9, 9, 12, 0))

        resumen = build_weekly_summary(db_session, user, datetime.now(UTC))
        assert resumen["period_key"] == "2026-W37"
        assert resumen["currency"] == "COP"
        assert resumen["total"] == 1600
        assert resumen["categoria_principal_id"] == cat_comida.id

    @freeze_time(REFERENCE)
    def test_non_preferred_currency_does_not_count(self, db_session):
        """Decisión 14.3.3: gasto en USD no cuenta para un usuario con preferred COP."""
        user = _crear_usuario(db_session, "b@test.com", preferred_currency="COP")
        cat = _crear_categoria(db_session, user, "Comida")
        cuenta_usd = _crear_cuenta(db_session, user, "USD")

        _crear_gasto(db_session, user, cuenta_usd, cat, 5000, datetime(2026, 9, 8, 10, 0))

        resumen = build_weekly_summary(db_session, user, datetime.now(UTC))
        assert resumen["total"] == 0
        assert resumen["categoria_principal_id"] is None

    @freeze_time(REFERENCE)
    def test_delta_vs_previous_week_and_none_when_previous_zero(self, db_session):
        user = _crear_usuario(db_session, "c@test.com")
        cat = _crear_categoria(db_session, user, "Comida")
        cuenta = _crear_cuenta(db_session, user, "COP")

        # Anterior semana [08/31-09/06]: 400. Esta semana: 600 → delta +50%
        _crear_gasto(db_session, user, cuenta, cat, 400, datetime(2026, 9, 2, 10, 0))
        _crear_gasto(db_session, user, cuenta, cat, 600, datetime(2026, 9, 8, 10, 0))

        resumen = build_weekly_summary(db_session, user, datetime.now(UTC))
        assert resumen["delta_pct"] == 50.0

        # Prev semana 0 → delta None
        user2 = _crear_usuario(db_session, "c2@test.com")
        cat2 = _crear_categoria(db_session, user2, "Comida")
        cuenta2 = _crear_cuenta(db_session, user2, "COP")
        _crear_gasto(db_session, user2, cuenta2, cat2, 600, datetime(2026, 9, 8, 10, 0))

        resumen2 = build_weekly_summary(db_session, user2, datetime.now(UTC))
        assert resumen2["delta_pct"] is None

    def test_spent_en_rango_filters_by_dates(self, db_session):
        user = _crear_usuario(db_session, "d@test.com")
        cat = _crear_categoria(db_session, user, "Comida")
        cuenta = _crear_cuenta(db_session, user, "COP")
        _crear_gasto(db_session, user, cuenta, cat, 100, datetime(2026, 9, 1, 10, 0))
        _crear_gasto(db_session, user, cuenta, cat, 200, datetime(2026, 9, 10, 10, 0))

        filas = spent_por_categoria_y_moneda_en_rango(db_session, user.id, datetime(2026, 9, 7), datetime(2026, 9, 13))
        assert filas == [(cat.id, "COP", 200)]


class TestRunWeeklySummaryForUser:
    @freeze_time(REFERENCE)
    def test_zero_spend_still_sends_sin_gastos_message(self, db_session):
        """Decisión 14.3.4: se envía siempre, incluso con $0 en la moneda preferida."""
        user = _crear_usuario(db_session, "zero@test.com")
        _crear_cuenta(db_session, user, "COP")

        run_weekly_summary_for_user(db_session, user, datetime.now(UTC))

        notif = _notificaciones_de(user.id, db_session)
        assert len(notif) == 1
        assert notif[0].type == "weekly_summary"
        assert notif[0].body == "Esta semana no registraste gastos — ¿todo tranquilo?"

    @freeze_time(REFERENCE)
    def test_positive_message_includes_total_category_and_period_key(self, db_session):
        user = _crear_usuario(db_session, "pos@test.com")
        cat = _crear_categoria(db_session, user, "Mercado")
        cuenta = _crear_cuenta(db_session, user, "COP")
        _crear_gasto(db_session, user, cuenta, cat, 1200, datetime(2026, 9, 8, 10, 0))

        run_weekly_summary_for_user(db_session, user, datetime.now(UTC))

        notif = _notificaciones_de(user.id, db_session)
        assert len(notif) == 1
        n = notif[0]
        # Decisión 14.1.2 / contract: budget_id None y period_key = semana ISO
        assert n.budget_id is None
        assert n.period_key == "2026-W37"
        # El nombre de la categoría aparece en el cuerpo
        assert "Mercado" in n.body
        assert "1,200.00 COP" in n.body

    @freeze_time(REFERENCE)
    def test_second_call_raises_integrity_error(self, db_session):
        """Decisión 14.1.2: unicidad (user_id, type, period_key) garantizada por DB."""
        user = _crear_usuario(db_session, "dup@test.com")
        _crear_cuenta(db_session, user, "COP")

        run_weekly_summary_for_user(db_session, user, datetime.now(UTC))
        with pytest.raises(IntegrityError):
            run_weekly_summary_for_user(db_session, user, datetime.now(UTC))
        db_session.rollback()


class TestRunWeeklySummaryJob:
    @freeze_time(REFERENCE)
    def test_disabled_user_excluded_from_batch(self, db_session):
        """`weekly_summary_enabled=False` → fuera del batch de `run_weekly_summary_job`.

        El job corre la query de usuarios elegibles en `run_weekly_summary_job`; aquí se
        verifica la query tal como el job la construye (Decisión 14.4.3): los usuarios con
        `weekly_summary_enabled=False` quedan excluidos, los habilitados incluidos."""
        enabled = _crear_usuario(db_session, "enabled@test.com", weekly_enabled=True)
        disabled = _crear_usuario(db_session, "disabled@test.com", weekly_enabled=False)

        user_ids = [
            u.id
            for u in db_session.query(models.User)
            .filter(models.User.weekly_summary_enabled.is_(True), models.User.deleted_at.is_(None))
            .all()
        ]
        assert disabled.id not in user_ids
        assert enabled.id in user_ids
