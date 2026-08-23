"""Fixtures compartidas del suite de pytest (Fase 7, §4.2 del spec).

Decisión de diseño 4.2.1 (spec): SQLite en memoria en vez de Postgres real — el alcance de
esta fase (transacciones, presupuestos, auth) no depende de comportamiento Postgres-específico
(a diferencia de `dashboard.py`, que sí bifurca por dialecto y queda fuera de este alcance).
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import models  # noqa: F401 - registra las tablas en Base.metadata antes del create_all

STRONG_PASSWORD = "Contrasena10"  # cumple la política de §2.3: no solo dígitos/letras, no común


@pytest.fixture(scope="session")
def engine():
    """Un único engine SQLite en memoria para toda la sesión de tests."""
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
def register_and_login(client: TestClient):
    """Factory: registra un usuario vía `POST /api/v1/users/` y loguea vía
    `POST /api/v1/auth/login`. Devuelve email/password/id/tokens/headers listos para usar."""
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
