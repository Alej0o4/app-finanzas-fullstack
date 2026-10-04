"""Migración de DATOS de la Fase 34 (X1/X2): fechas históricas `00:00Z` -> `17:00Z` del mismo día.

Corre contra una base PROPIA migrada a la revisión anterior (como `test_migrations.py`: no se
puede usar la base de la suite, que no tiene `alembic_version`): se siembran filas, se aplica
`upgrade head`, se comprueba, se aplica el `downgrade` y se comprueba el retorno. En los dos
motores (Postgres y el opt-in SQLite), porque la migración tiene una rama por dialecto.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import engine_kwargs_for_url
from app.models import models
from tests.test_migrations import _correr_alembic, _motor_de_administracion

REV_ANTERIOR = "a34c0de1b7f2"  # fase_34_user_timezone: el esquema final, sin la migración de datos


@pytest.fixture
def url_migrable(test_db_url: str, tmp_path) -> Generator[str, None, None]:
    """URL de una base vacía y desechable (archivo temporal en SQLite, base nueva en Postgres)."""
    if test_db_url.startswith("sqlite"):
        yield f"sqlite:///{tmp_path / 'oikos_test_x1.db'}"
        return
    destino = make_url(test_db_url).set(database=f"{make_url(test_db_url).database}_x1_{uuid.uuid4().hex[:8]}")
    with _motor_de_administracion(test_db_url) as motor, motor.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{destino.database}"'))
    try:
        yield destino.render_as_string(hide_password=False)
    finally:
        with _motor_de_administracion(test_db_url) as motor, motor.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{destino.database}"'))


def _alembic(url: str, *args: str) -> None:
    proceso = _correr_alembic(url, *args)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr


def _fecha(valor) -> datetime:
    """Lee `transactions.date` crudo: aware en Postgres, texto UTC naive en SQLite."""
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


def _fechas(engine) -> dict[str, datetime]:
    with engine.connect() as conn:
        return {d: _fecha(f) for d, f in conn.execute(text("SELECT description, date FROM transactions"))}


def _utc(*args, **kw) -> datetime:
    return datetime(*args, tzinfo=UTC, **kw)


SEMBRADAS = {
    "medianoche": _utc(2026, 3, 10),
    "primero-de-mes": _utc(2026, 3, 1),
    "borrada": _utc(2026, 5, 20),
    "con-microsegundo": _utc(2026, 3, 10, 0, 0, 0, 1),
    "medianoche-bogota": _utc(2026, 3, 10, 5),
    "tarde": _utc(2026, 3, 10, 22, 30),
}

ESPERADO_TRAS_UPGRADE = {
    "medianoche": _utc(2026, 3, 10, 17),
    "primero-de-mes": _utc(2026, 3, 1, 17),
    "borrada": _utc(2026, 5, 20, 17),  # las borradas lógicamente también se migran
    "con-microsegundo": SEMBRADAS["con-microsegundo"],
    "medianoche-bogota": SEMBRADAS["medianoche-bogota"],
    "tarde": SEMBRADAS["tarde"],
}


def test_upgrade_mueve_la_medianoche_utc_a_las_17z_y_downgrade_la_devuelve(url_migrable):
    _alembic(url_migrable, "upgrade", REV_ANTERIOR)
    engine = create_engine(url_migrable, poolclass=NullPool, **engine_kwargs_for_url(url_migrable))
    try:
        with Session(engine) as db:
            user = models.User(email="x1@example.com", full_name="X1", password_hash="x")
            db.add(user)
            db.flush()
            cuenta = models.Account(name="C", type="cash", currency="COP", user_id=user.id, balance=Decimal("123.45"))
            cat = models.Category(name="Comida", type="expense", user_id=user.id)
            db.add_all([cuenta, cat])
            db.flush()
            for descripcion, fecha in SEMBRADAS.items():
                db.add(
                    models.Transaction(
                        amount=Decimal("10.00"),
                        currency="COP",
                        type="expense",
                        description=descripcion,
                        date=fecha,
                        user_id=user.id,
                        account_id=cuenta.id,
                        category_id=cat.id,
                        deleted_at=_utc(2026, 6, 1) if descripcion == "borrada" else None,
                    )
                )
            db.commit()

        assert _fechas(engine) == SEMBRADAS  # el sembrado quedó como se esperaba en este motor

        _alembic(url_migrable, "upgrade", "head")
        assert _fechas(engine) == ESPERADO_TRAS_UPGRADE
        with engine.connect() as conn:
            assert Decimal(str(conn.execute(text("SELECT balance FROM accounts")).scalar())) == Decimal(
                "123.45"
            )  # saldos intactos

        # Idempotente: ya no queda ninguna fila a 00:00Z exacta, y subir de nuevo no cambia nada.
        _alembic(url_migrable, "upgrade", "head")
        assert _fechas(engine) == ESPERADO_TRAS_UPGRADE

        _alembic(url_migrable, "downgrade", REV_ANTERIOR)
        assert _fechas(engine) == SEMBRADAS

        _alembic(url_migrable, "upgrade", "head")  # ciclo completo: sube otra vez al mismo estado
        assert _fechas(engine) == ESPERADO_TRAS_UPGRADE
    finally:
        engine.dispose()
