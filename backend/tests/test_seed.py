"""Regresión del Hallazgo 1 de `docs/specs/fase_21_spec.md`: `run_seed()` corrido dos veces
contra un usuario de prueba que acumuló una API key y una categoría oculta no debe reventar
con `IntegrityError`.

Lo que este test necesita es una **capacidad** —FKs aplicadas—, no un motor: Postgres la da
gratis, SQLite hay que pedirla con `PRAGMA foreign_keys=ON` (que queda en el `connect`, en el
mismo lugar de siempre). Por eso este archivo arma su propio engine en vez de usar el `engine`
de la suite: ese lo volvería **vacío** en el opt-in SQLite, que es una única conexión en
memoria con `StaticPool` y sin el PRAGMA — una regresión ahí pasaría sin disparar el
`IntegrityError` (justo el falso verde que el docstring original advertía).

Fase 32 (B8): el engine propio se parametriza por dialecto y, en Postgres, vive en un
**esquema propio** (`oikos_test_seed`) de la misma base, no en el `public` de la suite. Motivo
(hallazgo 14, reproducido): este test commitea de verdad, y `test_seed.py` se recolecta justo
antes de `test_soft_delete.py`, cuyo assert de conteo global de la suite
(`SELECT COUNT(*) FROM transactions == 0`) es el único detector de que algo se filtró. Es el
mismo patrón que ya usa el test para el `PRAGMA` —un evento `connect` de SQLAlchemy sobre una
sola conexión— y con el esquema el aislamiento deja de depender del orden de recolección.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, engine_kwargs_for_url
from app.core.seed import run_seed
from app.models import models

# Categorías de sistema que el seed referencia por nombre (user_id IS NULL); en un engine
# vacío no existen y el seed las omitiría en silencio (WARNING) sin ejercitar la cascada.
_CATEGORIAS_SISTEMA = [
    {"name": "Salario", "type": "income"},
    {"name": "Alimentación", "type": "expense"},
    {"name": "Transporte", "type": "expense"},
    {"name": "Servicios Públicos", "type": "expense"},
    {"name": "Entretenimiento", "type": "expense"},
    {"name": "Suscripción", "type": "expense"},
    {"name": "Cuidado personal", "type": "expense"},
    {"name": "Otro", "type": "expense"},
]

# B8: namespace del engine propio en Postgres. Conserva "test" a propósito — si algún día esta
# base llega a un disco de datos compartido, el nombre sigue diciendo que no es de nadie.
ESQUEMA_SEED = "oikos_test_seed"


def _sembrar_categorias_sistema(session_factory: sessionmaker) -> None:
    """Equivale a `seed_default_categories()` (startup de la app) sobre el engine de test."""
    db = session_factory()
    try:
        for datos in _CATEGORIAS_SISTEMA:
            db.add(models.Category(name=datos["name"], type=datos["type"], user_id=None))
        db.commit()
    finally:
        db.close()


def _botar_esquema(test_db_url: str) -> None:
    """`DROP SCHEMA … CASCADE` desde una conexión con el `search_path` por defecto.

    Motor propio y desechable a propósito: cualquier conexión del engine del test tiene el
    `search_path` apuntando justo al esquema que se está borrando, y su pool podría devolver
    conexiones ya invalidadas al resto de la suite."""
    engine_admin = create_engine(test_db_url, **engine_kwargs_for_url(test_db_url))
    try:
        with engine_admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{ESQUEMA_SEED}" CASCADE'))
    finally:
        engine_admin.dispose()


@pytest.fixture
def engine_seed(test_db_url: str) -> Generator[Engine, None, None]:
    """Engine propio del test: FKs aplicadas, en un namespace que no comparte filas con el resto
    de la suite (Fase 32, B8).

    **SQLite** (opt-in `TEST_DATABASE_URL=sqlite://`): exactamente el código de la Fase 21 —
    `sqlite://` en memoria + `StaticPool` + `PRAGMA foreign_keys=ON` en el evento `connect` +
    `create_all`, sin esquema. La base en memoria muere con el `dispose()`.

    **Postgres** (default): mismo patrón del `PRAGMA`, pero `CREATE SCHEMA` + `SET search_path`
    en ese mismo evento, así que el `create_all` de abajo deja las 13 tablas en el esquema
    propio. Va después del `connect` porque las tablas tienen que caer en el esquema: no hay
    forma de decir "creá estas tablas acá" sin que el `search_path` de la sesión ya lo apunte."""
    if test_db_url.startswith("sqlite"):
        engine_sqlite = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine_sqlite, "connect")
        def _fk_pragma(dbapi_con, _rec):
            dbapi_con.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=engine_sqlite)
        try:
            yield engine_sqlite
        finally:
            engine_sqlite.dispose()
        return

    engine_pg = create_engine(test_db_url, **engine_kwargs_for_url(test_db_url))

    @event.listens_for(engine_pg, "connect")
    def _esquema_propio(dbapi_con, _rec):
        # `cursor()` en vez de `.execute()` del DBAPI: la receta oficial de SQLAlchemy para
        # conexiones con dialecto propio, y la que funciona igual con psycopg2 y psycopg3
        # (el `TEST_DATABASE_URL` del operador puede usar cualquiera de los dos).
        cursor = dbapi_con.cursor()
        try:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{ESQUEMA_SEED}"')
            cursor.execute(f'SET search_path TO "{ESQUEMA_SEED}"')
        finally:
            cursor.close()

    Base.metadata.create_all(bind=engine_pg)
    try:
        yield engine_pg
    finally:
        _botar_esquema(test_db_url)
        engine_pg.dispose()


def test_run_seed_twice_with_api_key_and_hidden_category_does_not_raise(engine_seed, monkeypatch):
    session_factory = sessionmaker(bind=engine_seed, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.core.seed.SessionLocal", session_factory)
    _sembrar_categorias_sistema(session_factory)

    run_seed()

    # El usuario de prueba acumuló una API key y una categoría oculta tras la primera
    # corrida — el caso exacto del Hallazgo 1: el borrado inline viejo de seed.py (anterior
    # a las Fases 16/18) no limpia estas dos tablas y revienta en el db.delete(existing).
    db = session_factory()
    try:
        user = db.query(models.User).filter(models.User.email == "test@test.com").first()
        assert user is not None
        db.add(
            models.ApiKey(
                user_id=user.id,
                name="regresion",
                key_hash="x" * 64,
                key_prefix="oikos_pat_",
            )
        )
        categoria_oculta = (
            db.query(models.Category)
            .filter(models.Category.user_id.is_(None), models.Category.name == "Alimentación")
            .first()
        )
        assert categoria_oculta is not None
        db.add(models.HiddenCategory(user_id=user.id, category_id=categoria_oculta.id))
        db.commit()
    finally:
        db.close()

    # Con delete_user_cascade (que borra ApiKey e HiddenCategory ANTES de Category/User) la
    # segunda corrida pasa; con el borrado inline viejo lanza IntegrityError.
    run_seed()
