"""Fixtures compartidas del suite de pytest (Fase 7, §4.2 del spec).

Decisión de diseño 4.2.1 (spec): SQLite en memoria en vez de Postgres real — el alcance de
esta fase (transacciones, presupuestos, auth) no depende de comportamiento Postgres-específico
(a diferencia de `dashboard.py`, que sí bifurca por dialecto y queda fuera de este alcance).
"""

import os
from collections.abc import Generator

# Red de seguridad: fijar estas env vars ANTES de importar app.main (más abajo), que dispara
# `load_dotenv()` en app.core.security al importarse. `load_dotenv()` nunca sobreescribe una env
# var que ya existe (default `override=False`), así que fijarlas acá primero es suficiente para
# que el test suite quede totalmente aislado de cualquier `.env` real del filesystem — no solo
# para que nunca pueda enviar un correo real (EMAIL_PROVIDER), sino para que tampoco firme JWTs
# de test con una SECRET_KEY de producción si por lo que sea `load_dotenv()` encuentra un `.env`
# real (ver comentario en security.py sobre por qué eso podía pasar).
os.environ.setdefault("EMAIL_PROVIDER", "console")
os.environ.setdefault("SECRET_KEY", "test-secret-key-solo-para-pytest-no-usar-en-real")

from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, engine_kwargs_for_url, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import models

STRONG_PASSWORD = "Contrasena10"  # cumple la política de §2.3: no solo dígitos/letras, no común

# 🆕 Fase 31 (T1, B8): con TEST_DATABASE_URL la suite corre contra un Postgres
# desechable en vez de SQLite en memoria — necesario para los tests `postgres`
# (concurrencia real, límites de Numeric, timezone de sesión). Sin la variable, todo
# sigue igual que siempre.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    # Guarda de seguridad (QA-001): el fixture de abajo hace `drop_all` sobre esta
    # base — la lección de la fase es no confiar en que nadie apunte a producción
    # por error. Se exige "test" en el nombre de la base, no en la URL completa (un
    # host o usuario que contenga "test" no cuenta).
    _nombre_base = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    if "test" not in _nombre_base.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL apunta a una base sin 'test' en el nombre ({_nombre_base!r}) "
            "— abortado por seguridad antes de conectarse (QA-001). Usá una base como "
            "'oikos_test', nunca la de producción."
        )


def pytest_collection_modifyitems(config, items):
    """Salta automáticamente los tests marcados `postgres` cuando no hay
    TEST_DATABASE_URL (T1) — corren solo contra el Postgres desechable de la receta
    de `CLAUDE.md`, nunca contra SQLite."""
    if TEST_DATABASE_URL:
        return
    skip_pg = pytest.mark.skip(reason="requiere TEST_DATABASE_URL (Postgres desechable)")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_pg)


@pytest.fixture(scope="session")
def engine():
    """Motor de la suite: SQLite en memoria por defecto, o el Postgres desechable de
    `TEST_DATABASE_URL` (T1) — mismos `kwargs` que arma la app real (B8)."""
    if TEST_DATABASE_URL:
        test_engine = create_engine(TEST_DATABASE_URL, **engine_kwargs_for_url(TEST_DATABASE_URL))
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        return

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """Sesión aislada por test vía savepoints anidados (patrón recomendado de SQLAlchemy para
    tests de integración: cada test corre dentro de una transacción externa que se revierte
    por completo al final, aunque el código bajo prueba haga sus propios `commit()`)."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = session_factory()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    """`slowapi` guarda los contadores en memoria de proceso, keyeados por `get_remote_address`
    — que bajo `TestClient` es siempre el mismo host. Sin este reset, los límites de
    login/registro (5/minute) se acumularían entre tests no relacionados. El propio test de
    rate limiting hace varias llamadas seguidas *dentro* de un mismo test, así que no lo pisa."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """`TestClient` con `get_db` apuntando a la sesión de test.

    Deliberadamente NO se usa `with TestClient(app) as client:` — eso dispararía el lifespan
    de `startup`, que corre `seed_default_categories()` contra la base de datos real (vía
    `SessionLocal`, no vía `get_db`, así que el override de abajo no lo protegería). Sin el
    context manager, el lifespan no se dispara (verificado: `@app.on_event` no corre si no se
    entra al `with`), y los tests que necesitan una categoría la crean vía el endpoint real.
    """

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def register_and_login(client: TestClient, db_session: Session):
    """Factory: registra un usuario vía `POST /api/v1/users/` y loguea vía
    `POST /api/v1/auth/login`. Devuelve email/password/id/tokens/headers listos para usar.

    El login exige `email_verified` (gate agregado en `auth.py`); esta factory marca el
    usuario como verificado directo en la sesión de test para no forzar a cada test que
    solo necesita "un usuario logueado" a pasar por el flujo real de verificación por
    token. `TestEmailVerification` sí ejercita ese flujo real sin pasar por este atajo."""
    counter = {"n": 0}

    def _factory(
        email: str | None = None,
        password: str = STRONG_PASSWORD,
        full_name: str = "Usuaria de Prueba",
    ) -> dict:
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.com"

        register_response = client.post(
            "/api/v1/users/",
            json={"email": email, "full_name": full_name, "password": password},
        )
        assert register_response.status_code == 200, register_response.text
        user_data = register_response.json()

        db_session.query(models.User).filter(models.User.email == email).update({"email_verified": True})
        db_session.commit()

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200, login_response.text
        tokens = login_response.json()

        return {
            "email": email,
            "password": password,
            "id": user_data["id"],
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        }

    return _factory


@pytest.fixture
def test_user(register_and_login) -> dict:
    return register_and_login(email="owner@example.com")


@pytest.fixture
def auth_headers(test_user) -> dict:
    return test_user["headers"]


@pytest.fixture
def other_user(register_and_login) -> dict:
    """Un segundo usuario, para los tests de ownership (404 en recursos ajenos)."""
    return register_and_login(email="otra-persona@example.com")


@pytest.fixture
def make_account(client: TestClient):
    """Factory de cuentas vía el endpoint real (no inserta directo en la sesión)."""

    def _factory(
        headers: dict,
        name: str = "Cuenta de prueba",
        type: str = "cash",  # coincide con el nombre del campo del schema (AccountBase.type)
        currency: str = "COP",
        balance: str = "1000.00",
        highlighted: bool = False,
    ) -> dict:
        response = client.post(
            "/api/v1/accounts/",
            json={
                "name": name,
                "type": type,
                "currency": currency,
                "balance": balance,
                "highlighted": highlighted,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _factory


@pytest.fixture
def make_category(client: TestClient):
    """Factory de categorías (propias del usuario) vía el endpoint real."""

    def _factory(headers: dict, name: str = "Categoría de prueba", type: str = "expense") -> dict:
        response = client.post(
            "/api/v1/categories/",
            json={"name": name, "type": type},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _factory


@pytest.fixture
def captured_emails(monkeypatch):
    """Intercepta `send_email` en los módulos que lo llaman, para poder leer el token de
    verificación/reset del cuerpo del correo sin depender de un proveedor real (§2.1/§2.2 usan
    `EMAIL_PROVIDER=console` por defecto, que solo loguea)."""
    emails: list[dict] = []

    def _fake_send_email(to: str, subject: str, html_body: str) -> None:
        emails.append({"to": to, "subject": subject, "html_body": html_body})

    monkeypatch.setattr("app.api.auth.send_email", _fake_send_email)
    monkeypatch.setattr("app.api.users.send_email", _fake_send_email)
    return emails


# --- Seam de concurrencia real contra Postgres (Fase 31, T2) ---------------------
#
# Estos fixtures solo tienen sentido con TEST_DATABASE_URL: `engine` en SQLite es una
# única conexión en memoria (StaticPool), que no simula concurrencia real entre
# hilos. Los tests que los usan van todos marcados `postgres` (autoskip sin la env
# var, ver pytest_collection_modifyitems arriba), así que estos fixtures nunca se
# invocan contra SQLite.


@pytest.fixture
def pg_client(engine) -> Generator[TestClient, None, None]:
    """Cliente con sesión REAL por request — a diferencia de `client` (una única
    `db_session` compartida con savepoints, pensada para aislar cada test con un
    rollback), acá cada request abre y cierra su PROPIA sesión desde una
    `sessionmaker` bound al `engine` de la suite, con commits reales. Imprescindible
    para que los locks de fila (`FOR UPDATE`) y los commits de una petición sean
    visibles para otra que corre en paralelo desde otro hilo — la única forma de
    probar concurrencia real (B1/B2).

    Sin transacción externa que lo limpie con un rollback (cada commit fue real):
    al terminar, trunca sus propias filas."""
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

    with engine.connect() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE transactions, idempotency_keys, refresh_tokens, "
                "accounts, categories, users RESTART IDENTITY CASCADE"
            )
        )
        conn.commit()


@pytest.fixture
def pg_register_and_login(pg_client: TestClient, engine):
    """Factory análoga a `register_and_login`, pero contra `pg_client`: marca
    `email_verified` con una conexión de una sola vez, con su propio commit real —
    `db_session` no sirve acá, es una transacción distinta (sin commits reales) que
    las conexiones de `pg_client` nunca verían."""
    counter = {"n": 0}
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _factory(
        email: str | None = None,
        password: str = STRONG_PASSWORD,
        full_name: str = "Usuario Concurrencia",
    ) -> dict:
        counter["n"] += 1
        email = email or f"pguser{counter['n']}@example.com"

        register_response = pg_client.post(
            "/api/v1/users/",
            json={"email": email, "full_name": full_name, "password": password},
        )
        assert register_response.status_code == 200, register_response.text
        user_id = register_response.json()["id"]

        db = session_factory()
        try:
            db.query(models.User).filter(models.User.id == user_id).update({"email_verified": True})
            db.commit()
        finally:
            db.close()

        login_response = pg_client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200, login_response.text
        tokens = login_response.json()

        return {
            "id": user_id,
            "email": email,
            "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        }

    return _factory


@pytest.fixture
def pg_make_account(pg_client: TestClient):
    """Factory de cuentas vía el endpoint real, sobre `pg_client`."""

    def _factory(
        headers: dict,
        name: str = "Cuenta concurrencia",
        type: str = "cash",
        currency: str = "COP",
        balance: str = "1000.00",
        highlighted: bool = False,
    ) -> dict:
        response = pg_client.post(
            "/api/v1/accounts/",
            json={
                "name": name,
                "type": type,
                "currency": currency,
                "balance": balance,
                "highlighted": highlighted,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _factory


@pytest.fixture
def pg_make_category(pg_client: TestClient):
    """Factory de categorías vía el endpoint real, sobre `pg_client`."""

    def _factory(headers: dict, name: str = "Categoría concurrencia", type: str = "expense") -> dict:
        response = pg_client.post(
            "/api/v1/categories/",
            json={"name": name, "type": type},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _factory
