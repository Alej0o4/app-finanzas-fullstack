"""Tests del resumen semanal automático (Fase 14 §14.3-§14.5; Fase 33 §B1-§B3, QA-037/QA-038).

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

La Fase 33 (QA-037, QA-038) agrega tres cosas sobre esa base:
- **B1:** el job del lunes resume la semana que CERRÓ, no la que arranca — se prueba de punta a
  punta por `run_weekly_summary_job` (el seam más alto: usuarios elegibles → semana → total →
  aviso persistido), con `freeze_time` en el instante real del cron.
- **B2:** la ventana de la semana se arma con zona horaria, así que los dos bordes del domingo
  ya no están corridos 5 h; y una referencia naive se rechaza con `ValueError`.
- **B3:** el texto dice "La semana pasada" y el delta "vs. la anterior".

Todas las fechas de este módulo son **aware en `America/Bogota`**: es la única forma de que
las semillas signifiquen lo mismo en los dos motores de la suite. Con fechas naive, psycopg2 las
guarda como UTC (ventana corrida, QA-038) y SQLite las guarda tal cual (ventana correcta pero
distinta) — el mismo test pasa por motivos distintos en cada motor. Awake-Bogotá describe el
instante real en los dos, que es lo que importa acá.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from sqlalchemy.exc import IntegrityError

from app.core.weekly_summary import (
    build_weekly_summary,
    run_weekly_summary_for_user,
    run_weekly_summary_job,
    spent_por_categoria_y_moneda_en_rango,
)
from app.models import models

# Zona de la ventana de la semana (Decisión 14.3.1 + B2). Explícita, no importada de
# `app.core.weekly_summary`: las semillas son datos del test, y escribirlas en la zona que el
# producto usa documenta el caso (el borde del domingo) en vez de esconderlo en un import.
BOGOTA = ZoneInfo("America/Bogota")

# Lunes de la semana ISO 37 de 2026, 07:00 America/Bogota = 12:00Z — la hora típica del job.
# Antes era naive y el comentario prometía 07:00 Bogotá mientras congelaba 07:00 UTC (= 02:00
# Bogotá): el comentario mentía (Fase 33, T4). Ahora el instante es el que dice.
REFERENCE = datetime(2026, 9, 7, 7, 0, tzinfo=BOGOTA)

# El instante real del cron (lunes 07:00 America/Bogota) en la semana 41: el job tiene que
# resumir la semana 40, que es la que cerró el domingo anterior (QA-037).
INSTANTE_DEL_CRON = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _sin_vapid(monkeypatch):
    """Saca las VAPID del entorno para que `enviar_push` tome su primer corte.

    Sin esto el resultado de estos tests depende del entorno: `backend/.env` (que `app.core.
    security` carga al importarse) trae un par VAPID de dev, y el contenedor del backend en
    producción los inyecta por `environment:`. Sin suscripciones push no hay red igual, pero
    la dependencia existe. Precedente: `tests/test_push.py`."""
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)


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


def _user_id(user) -> int:
    """Id de un usuario sembrado por este módulo.

    El job cierra su sesión en el `finally`, así que las instancias sembradas quedan
    detached: el id se lee por acá, antes de correrlo, en vez de después."""
    return user.id


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

    def test_naive_reference_date_is_rejected(self, db_session):
        """B2: la referencia DEBE venir con `tzinfo`.

        Sin ella la ventana se interpretaría en la zona del servidor (o, contra `timestamptz`,
        como UTC) y el resumen saldría corrido en silencio — el modo de fallo que produjo
        QA-038. `build_weekly_summary` llama `_limites_semana` con la referencia y con la
        referencia menos 7 días (para el delta), así que este assert cubre las dos."""
        user = _crear_usuario(db_session, "naive@test.com")

        with pytest.raises(ValueError, match="tzinfo"):
            build_weekly_summary(db_session, user, datetime(2026, 9, 7, 7, 0))


class TestVentanaSemanalConZona:
    """QA-038: los dos bordes del domingo (57 vs 60 en el reporte original).

    Ventana de la semana 37 correcta (B2): lunes 09/07 00:00 Bogotá = 09/07 05:00Z, domingo
    09/13 23:59:59 Bogotá = 09/14 04:59:59Z. Con los límites naive de antes, psycopg2 los
    leía como UTC: la ventana arrancaba 5 h antes (se colaban las 22:00-23:59 del domingo
    ANTERIOR) y terminaba 5 h antes (se perdían las 19:00-23:59 del domingo PROPIO).

    Cada caso lleva un usuario propio con un único gasto: si el borde se rompe, el fallo
    señala cuál de los dos se rompió en vez de diluirse en un total agregado. Ambos son
    verdes también en el opt-in SQLite (`TEST_DATABASE_URL=sqlite://`), que NO puede
    reproducir QA-038 — su `DATETIME` no guarda offset, así que una semilla en hora Bogotá
    se lee igual en los dos motores. El rojo de QA-038 se verifica en Postgres, que es el
    motor default de la suite."""

    @freeze_time(REFERENCE)
    def test_sunday_20_00_belongs_to_its_own_week(self, db_session):
        """Domingo 09/13 20:00 Bogotá (= 09/14 01:00Z) es de la semana 37, no de la 38."""
        user = _crear_usuario(db_session, "domingo-dentro@test.com")
        cat = _crear_categoria(db_session, user, "Cena")
        cuenta = _crear_cuenta(db_session, user, "COP")

        _crear_gasto(db_session, user, cuenta, cat, 100, datetime(2026, 9, 13, 20, 0, tzinfo=BOGOTA))

        resumen = build_weekly_summary(db_session, user, datetime.now(UTC))
        assert resumen["period_key"] == "2026-W37"
        assert resumen["total"] == 100
        assert resumen["categoria_principal_id"] == cat.id

    @freeze_time(REFERENCE)
    def test_previous_sunday_22_00_is_excluded(self, db_session):
        """Domingo 09/06 22:00 Bogotá (= lunes 09/07 03:00Z) es de la semana 36.

        Faltan 2 h para que arranque la 37, así que no puede sumar a su total: con la
        ventana corrida de antes se colaba."""
        user = _crear_usuario(db_session, "domingo-fuera@test.com")
        cat = _crear_categoria(db_session, user, "Cena")
        cuenta = _crear_cuenta(db_session, user, "COP")

        _crear_gasto(db_session, user, cuenta, cat, 999, datetime(2026, 9, 6, 22, 0, tzinfo=BOGOTA))

        resumen = build_weekly_summary(db_session, user, datetime.now(UTC))
        assert resumen["period_key"] == "2026-W37"
        assert resumen["total"] == 0
        assert resumen["categoria_principal_id"] is None


class TestRunWeeklySummaryForUser:
    @freeze_time(REFERENCE)
    def test_zero_spend_still_sends_sin_gastos_message(self, db_session):
        """Decisión 14.3.4: se envía siempre, incluso con $0 en la moneda preferida.

        B3: el mensaje dice "La semana pasada" — el resumen se manda el lunes y describe la
        semana que ya cerró."""
        user = _crear_usuario(db_session, "zero@test.com")
        _crear_cuenta(db_session, user, "COP")

        run_weekly_summary_for_user(db_session, user, datetime.now(UTC))

        notif = _notificaciones_de(user.id, db_session)
        assert len(notif) == 1
        assert notif[0].type == "weekly_summary"
        assert notif[0].body == "La semana pasada no registraste gastos — ¿todo tranquilo?"

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
        # B3: el cuerpo abre con "La semana pasada" (no "Gastaste")
        assert n.body.startswith("La semana pasada gastaste ")
        # El nombre de la categoría aparece en el cuerpo
        assert "Mercado" in n.body
        assert "1,200.00 COP" in n.body

    @freeze_time(REFERENCE)
    def test_delta_compares_against_the_week_before_the_closed_one(self, db_session):
        """B3: con base de comparación el cuerpo cierra con `({delta:+.0f}% vs. la anterior)`.

        El lunes el resumen habla de la semana cerrada, así que "semana pasada" sería
        ambiguo: la comparación es contra la anterior a la que se resume."""
        user = _crear_usuario(db_session, "delta@test.com")
        cat = _crear_categoria(db_session, user, "Comida")
        cuenta = _crear_cuenta(db_session, user, "COP")

        # Semana 36 [08/31-09/06]: 400. Semana 37: 600 → +50%
        _crear_gasto(db_session, user, cuenta, cat, 400, datetime(2026, 9, 2, 10, 0))
        _crear_gasto(db_session, user, cuenta, cat, 600, datetime(2026, 9, 8, 10, 0))

        run_weekly_summary_for_user(db_session, user, datetime.now(UTC))

        n = _notificaciones_de(user.id, db_session)[0]
        assert n.body == "La semana pasada gastaste 600.00 COP — el mayor gasto fue en Comida (+50% vs. la anterior)."

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

    @freeze_time(INSTANTE_DEL_CRON)
    def test_job_summarizes_the_week_that_closed(self, db_session, monkeypatch):
        """QA-037: el lunes el job manda el resumen de la semana que CERRÓ, no de la que arranca.

                 El instante congelado es el real del cron (lunes 2026-10-05 07:00 Bogotá). Con el
        código anterior el `period_key` era el de la semana 41 — la que acababa de empezar,
        de la que por definición casi no hay gasto — y por eso el mensaje "no registraste
        gastos" llegaba con gasto real en la bandeja.

        El job abre su propia sesión, así que se le pasa la del test
        (`app.core.weekly_summary.SessionLocal`): los saves del fixture se revierten en el
        teardown, el job solo ve los usuarios sembrados acá, y el `close()` del `finally`
        no rompe nada. NO se usa `real_session_factory`: esa sesión commitea de verdad, el
        job iteraría usuarios de otros tests y las filas quedarían en la base sin que nada
        las limpiara.
        """
        monkeypatch.setattr("app.core.weekly_summary.SessionLocal", lambda: db_session)

        user = _crear_usuario(db_session, "job-cerrada@test.com")
        user_id = _user_id(user)
        cat = _crear_categoria(db_session, user, "Mercado")
        cuenta = _crear_cuenta(db_session, user, "COP")
        # Un único gasto, en mitad de la semana 40 (lunes 09/28 - domingo 10/04). NADA en la
        # 41, la semana que resumía el código viejo: así el mensaje de "sin gastos" no puede
        # colarse por un total de cero y tapar el bug.
        _crear_gasto(db_session, user, cuenta, cat, 1200, datetime(2026, 9, 30, 12, 0, tzinfo=BOGOTA))

        run_weekly_summary_job()

        notif = _notificaciones_de(user_id, db_session)
        assert len(notif) == 1
        n = notif[0]
        assert n.type == "weekly_summary"
        # B1: la semana 40, la que cerró el domingo 10/04. Con el código anterior: "2026-W41".
        assert n.period_key == "2026-W40"
        assert n.title == "Tu resumen semanal"
        # El cuerpo prueba la selección de semana desde adentro: el total sale de la 40.
        assert "1,200.00 COP" in n.body
        assert "no registraste gastos" not in n.body

    @freeze_time(INSTANTE_DEL_CRON)
    def test_two_runs_same_week_leave_one_notification_each(self, db_session, monkeypatch):
        """Decisión 14.1.2 aplicada al job: correrlo dos veces no duplica el aviso.

        El `except IntegrityError` del job se traga el choque y hace `rollback`, así que el
        segundo `run_weekly_summary_job()` no propaga nada — por eso no hay `pytest.raises`
        acá. Un segundo usuario habilitado con la misma semana recibe SU aviso: el índice
        único es por `(user_id, type, period_key)`, no por semana."""
        monkeypatch.setattr("app.core.weekly_summary.SessionLocal", lambda: db_session)

        user_a = _crear_usuario(db_session, "job-a@test.com")
        user_a_id = _user_id(user_a)
        user_b = _crear_usuario(db_session, "job-b@test.com")
        user_b_id = _user_id(user_b)
        cat_a = _crear_categoria(db_session, user_a, "Mercado")
        cuenta_a = _crear_cuenta(db_session, user_a, "COP")
        _crear_gasto(db_session, user_a, cuenta_a, cat_a, 1200, datetime(2026, 9, 30, 12, 0, tzinfo=BOGOTA))
        cat_b = _crear_categoria(db_session, user_b, "Mercado")
        cuenta_b = _crear_cuenta(db_session, user_b, "COP")
        _crear_gasto(db_session, user_b, cuenta_b, cat_b, 500, datetime(2026, 9, 30, 12, 0, tzinfo=BOGOTA))

        run_weekly_summary_job()
        run_weekly_summary_job()

        assert len(_notificaciones_de(user_a_id, db_session)) == 1
        assert len(_notificaciones_de(user_b_id, db_session)) == 1
