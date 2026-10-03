"""Fixtures compartidas del suite de pytest (Fase 7, §4.2 del spec; motor de la suite
redefinido en la Fase 32, I1 + B1-B5).

La Fase 7 (§4.2.1) eligió SQLite en memoria para que el suite no dependiera de ningún servicio
externo. La Fase 32 lo da vuelta: **Postgres es el default**, porque es el motor que corre
producción —QA-003 (SQLite serializa las escrituras, no aplica `FOR UPDATE`) y QA-015 (no
aplica `Numeric(14,2)`) son exactamente lo que esa diferencia esconde— y el argumento es la
fricción, no la velocidad (Q1). SQLite sobrevive como **opt-in explícito**
(`TEST_DATABASE_URL=sqlite://`), nunca como fallback automático (Q2): un `pytest` "verde" en el
motor que no es el de producción es la clase de bug que esta fase viene a matar.

Dos modos, una sola variable —`TEST_DATABASE_URL`, que la Fase 31 ya había abierto (B2)::

    TEST_DATABASE_URL definida → se usa tal cual (Postgres del operador para depurar, o el
                                 `sqlite://` del opt-in offline)
    sin la variable            → `testcontainers` levanta un `postgres:16-alpine`
                                 desechable por sesión (I1)

Sin Docker no hay tercera opción: la suite **aborta** con código 2 y un mensaje con las tres
salidas (B1), nunca cae sola ni se saltea entera. Lo que el cambio de motor no toca es el resto
del alcance de §4.2.1: los endpoints de dominio no dependen de comportamiento Postgres-específico
(a diferencia de `dashboard.py`, que sí bifurca por dialecto y tenía sus dos ramas cubiertas).
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
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.database import Base, engine_kwargs_for_url, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import models

STRONG_PASSWORD = "Contrasena10"  # cumple la política de §2.3: no solo dígitos/letras, no común

# Fase 32 (I1, Q1 + Q7): el motor de la suite se resuelve en DOS ramos, con esta única variable
# como selector. Definida → se respeta tal cual (Postgres del operador, o el `sqlite://` del
# opt-in). Sin ella → `testcontainers` levanta un Postgres 16 desechable por sesión. Antes de la
# Fase 32 esta variable solo servía para lo segundo, y sin ella la suite caía a SQLite.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# La misma imagen que `docker-compose.yml` (Q1): que el suite mida el motor que corre
# producción, no una variante.
IMAGEN_TEST = "postgres:16-alpine"

# B1 (Q1 + Q2): sin contenedor no hay suite. El mensaje dice las TRES salidas porque "no levanté
# la DB" es un paso extra que hace que el gate se deje de correr, y la respuesta fácil a eso es
# caer a SQLite en silencio — que es exactamente lo que esta fase viene a matar.
_MENSAJE_SIN_DOCKER = """
No se pudo levantar el Postgres desechable de la suite (Fase 32, I1) — {detalle}

La suite NO cae a SQLite por su cuenta (Q2): un `pytest` "verde" en el motor que no es el de
producción es el bug que esta fase viene a matar, así que aborta con código 2.

Tres salidas:
  1. Levantá Docker y volvé a correr `pytest` — el contenedor se crea y se destruye solo.
  2. Apuntá a un Postgres propio (el nombre de la base tiene que contener "test", guarda de
     QA-001):
     TEST_DATABASE_URL=postgresql://usuario:clave@127.0.0.1:5432/oikos_test pytest
  3. Corré el opt-in offline en SQLite — mismo código, tests que no dependan de sesiones
     reales por request:
     TEST_DATABASE_URL=sqlite:// pytest
"""


def _exigir_nombre_de_test(url: str) -> None:
    """Guarda de seguridad (QA-001, Fase 31): el fixture `engine` hace `drop_all` sobre esta
    base — la lección de la fase es no confiar en que nadie apunte a producción por error. Se
    exige "test" en el NOMBRE de la base, no en la URL completa (un host o un usuario que
    contenga "test" no cuenta).

    Fase 32 (B2, Q7) la reduce a un helper que se aplica solo a los dos ramos **Postgres** de
    la URL resuelta (el del operador y el del contenedor). No aplica a las URLs SQLite: una
    `sqlite://` en memoria no tiene nombre de base que proteger, y `TEST_DATABASE_URL=sqlite://`
    ni siquiera llegaba a collection (hallazgo 7)."""
    nombre_base = urlparse(url).path.lstrip("/")
    if "test" not in nombre_base.lower():
        raise RuntimeError(
            f"La base de la suite ({nombre_base!r}) no tiene 'test' en el nombre — abortado por "
            "seguridad antes de conectarse (QA-001): el fixture `engine` hace `drop_all` sobre "
            "ella. Usá una base como 'oikos_test', nunca la de producción."
        )


def _motor_activo_es_sqlite() -> bool:
    """¿El motor con el que va a correr la suite es SQLite?

    Se deduce de `TEST_DATABASE_URL` a propósito: es lo único que existe antes de instanciar
    cualquier fixture, y `pytest_collection_modifyitems` corre antes de todos ellos. Sin la
    variable el default es Postgres (Q1), así que no se saltea nada — que también es la razón
    por la que el hook no puede levantarse un contenedor para averiguarlo (cobraría los ~9 s
    de arranque también en `pytest --collect-only`, B1)."""
    return (TEST_DATABASE_URL or "").startswith("sqlite")


# La guarda del ramo del OPERADOR es a nivel de módulo (B2): corre al importar el conftest,
# antes de abrir ninguna conexión, así que hasta `pytest --collect-only` aborta sin tocar la
# base. La del contenedor va dentro de su fixture (más abajo), porque el nombre de esa base
# solo existe una vez que arrancó.
if TEST_DATABASE_URL and not _motor_activo_es_sqlite():
    _exigir_nombre_de_test(TEST_DATABASE_URL)


def pytest_collection_modifyitems(config, items):
    """B4 (Q6): autoskip de los tests marcados `concurrencia` cuando el motor activo es SQLite.

    El marker dejó de ser de motor (`postgres`) y pasó a ser de AISLAMIENTO: lo que esos tests
    necesitan son sesiones reales por request, que una única conexión en memoria (`StaticPool`)
    no puede dar. El motivo nombra esa limitación y no la falta de una env var, para que nadie
    lea el skip como "un marker opcional que se puede apagar" (User Story 13)."""
    if not _motor_activo_es_sqlite():
        return
    skip_sqlite = pytest.mark.skip(
        reason="requiere sesiones reales por request; el opt-in SQLite (TEST_DATABASE_URL=sqlite://) no las soporta"
    )
    for item in items:
        if "concurrencia" in item.keywords:
            item.add_marker(skip_sqlite)


def pytest_report_header(config) -> list[str]:
    """User Story 11: "quiero saber con qué motor corrió la suite, para no confundir un verde de
    SQLite con uno de Postgres".

    Sin esto los dos modos son idénticos en la salida — mismo verde, mismos conteos de una línea
    — y la fricción que la fase ataca (Q1: correr la suite en el motor de producción no puede
    depender de acordarse) se pierde justo en el mensaje que el dueño lee al terminar. Es un
    agregado deliberado a la spec, que enunció la User Story pero no dejó decisión implementable.

    Solo dialecto y nombre de la base: nunca usuario, contraseña ni la URL completa — el header
    se imprime en logs y capturas de pantalla, y `TEST_DATABASE_URL` puede venir de un entorno
    compartido. Para el ramo del contenedor alcanza con la imagen (el puerto todavía no existe
    cuando corre este hook, y no hace falta para responder la pregunta).

    El modo se deduce del entorno con `_motor_activo_es_sqlite()` y NO se levanta el contenedor
    para averiguarlo: `pytest_report_header` corre antes que cualquier fixture, y hacerlo
    cobraría los ~9 s de arranque también en `pytest --collect-only` (User Story 10, B1)."""
    if _motor_activo_es_sqlite():
        return ["motor de la suite: SQLite (opt-in TEST_DATABASE_URL=sqlite://)"]
    if TEST_DATABASE_URL:
        return [f"motor de la suite: PostgreSQL del operador — base {urlparse(TEST_DATABASE_URL).path.lstrip('/')}"]
    return [f"motor de la suite: PostgreSQL {IMAGEN_TEST} (contenedor desechable de la sesión)"]


@pytest.fixture(scope="session")
def postgres_ephemeral():
    """Postgres 16 desechable de la sesión (I1, Q1). `None` cuando hay `TEST_DATABASE_URL`: en
    ese modo no se levanta ningún contenedor — el Postgres es del operador y este proceso solo
    abre y cierra conexiones contra él."""
    if TEST_DATABASE_URL:
        yield None
        return

    # Import perezoso: el opt-in `TEST_DATABASE_URL=sqlite://` no debe exigir Docker ni
    # `testcontainers` instalados — solo este ramo los usa.
    from docker.errors import DockerException
    from testcontainers.community.postgres import PostgresContainer
    from testcontainers.core.container import ContainerStartException

    # Credenciales EXPLÍCITAS, nunca las del entorno (hallazgo 11): `testcontainers` lee
    # `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` como defaults, y si el shell del dueño
    # las tiene exportadas (es lo normal: son las de compose) el contenedor de tests nacería con
    # otro usuario y otra base, y la guarda de nombre de QA-001 cortaría la corrida sin
    # explicación.
    try:
        contenedor = PostgresContainer(
            IMAGEN_TEST,
            username="oikos",
            password="oikos_test",
            dbname="oikos_test",
        ).start()
    except (DockerException, ContainerStartException) as exc:
        # `ContainerStartException` es un `RuntimeError`, NO un `DockerException` (hallazgo 12):
        # sin las dos, "no hay Docker" y "la imagen no arrancó" darían mensajes distintos.
        # El `try` cubre SOLO el arranque — un fallo de un test no entra acá, y el `pytest.exit`
        # no puede tragarse un error de teardown.
        detalle = (str(exc).splitlines() or ["(sin detalle)"])[0]
        pytest.exit(_MENSAJE_SIN_DOCKER.format(detalle=detalle), returncode=2)

    try:
        # Misma guarda de QA-001 que el ramo del operador, acá adentro porque el nombre de la
        # base del contenedor solo existe una vez que arrancó (B2).
        _exigir_nombre_de_test(contenedor.get_connection_url())
        yield contenedor
    finally:
        contenedor.stop()


@pytest.fixture(scope="session")
def test_db_url(postgres_ephemeral) -> str:
    """URL resuelta de la base de la suite (B2): `TEST_DATABASE_URL` tal cual si el operador la
    definió, o la del contenedor desechable. Fuente única — la consumen `engine`, `admin_engine`
    y los tests que necesitan hablar de la base por su cuenta."""
    return TEST_DATABASE_URL or postgres_ephemeral.get_connection_url()


@pytest.fixture(scope="session")
def engine(test_db_url: str) -> Generator[Engine, None, None]:
    """Motor de la suite (B3): un caso explícito por dialecto, porque `TEST_DATABASE_URL` ya no
    significa "Postgres o nada" — también puede ser el opt-in de SQLite.

    Postgres (default): mismos `kwargs` que arma la app real (`engine_kwargs_for_url`), con
    `drop_all`/`create_all` por sesión — la base es del contenedor (recién creada) o del operador,
    y tiene que arrancar vacía.

    SQLite (opt-in `TEST_DATABASE_URL=sqlite://`): conserva EXACTAMENTE lo de la Fase 7 —
    `sqlite://` + `StaticPool` + `check_same_thread=False`, `create_all` y **sin** `drop_all`.
    El `drop_all` sobra porque una base en memoria ya está vacía, y no hacerlo evita que un
    `sqlite:///ruta/a/algo.db` tocado a mano pierda sus tablas."""
    if test_db_url.startswith("sqlite"):
        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        yield test_engine
        test_engine.dispose()
        return

    test_engine = create_engine(test_db_url, **engine_kwargs_for_url(test_db_url))
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
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


# --- Seam de sesiones reales por request (Fase 32, B5 — antes `pg_*`, Fase 31 T2) ------
#
# Estos fixtures solo tienen sentido contra Postgres: `engine` en SQLite es una única
# conexión en memoria (StaticPool), que no simula ni sesiones separadas por request ni
# concurrencia real entre hilos. Los tests que los usan van todos marcados `concurrencia`
# (autoskip con el motor SQLite, ver pytest_collection_modifyitems arriba), así que estos
# fixtures nunca se invocan contra SQLite.
#
# El prefijo dejó de ser `pg_` por una razón semántica (Q6): con Postgres como default, un
# marker de "motor" ya no describe nada — describe el AISLAMIENTO que el test necesita.


@pytest.fixture(scope="session")
def real_session_factory(engine: Engine) -> sessionmaker:
    """`sessionmaker` bound al `engine` de la suite (B5): la sesión real por request que
    usan `real_client` y `real_register_and_login`.

    Vive como fixture propia porque `sessionmaker(bind=engine, …)` estaba copiado en ambos, y
    además la necesitan los tests que leen o escriben fuera de HTTP (`real_session`)."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def real_session(real_session_factory: sessionmaker, real_client: TestClient) -> Generator[Session, None, None]:
    """Una sesión de `real_session_factory`, para leer o escribir FUERA de HTTP.

    `db_session` no sirve para eso: es la transacción externa que la suite revierte al final
    del test, así que las sesiones de `real_client` —que commitean de verdad— nunca verían sus
    escrituras (y al revés: esto tampoco ve los commits ajenos hasta que se reabre la
    transacción).

    Depende de `real_client` aunque no lo use: su teardown trunca la base con locks exclusivos,
    y pytest destruye los fixtures en orden inverso al de instanciación, así que esta sesión
    tiene que cerrarse ANTES — si no, un test que pidiera `real_session` antes que
    `real_client` colgaría el `TRUNCATE` contra su transacción abierta. Además, así lo que esta
    sesión commitee también lo limpia ese teardown."""
    session = real_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_engine(test_db_url: str) -> Generator[Engine, None, None]:
    """Engine de ADMINISTRACIÓN: lo que la transacción de la suite no puede hacer. Hoy, solo el
    `ALTER DATABASE … SET timezone` de los dos tests de timezone (B5).

    Dos `kwargs` que la app no usa:

    - `isolation_level="AUTOCOMMIT"`: los statements de administración son a nivel de BASE
      (`ALTER DATABASE … SET`), y con esto cada uno surte efecto al ejecutarse, sin que cada
      call site del test tenga que acordarse del `conn.commit()` que repetía el código viejo.
    - `poolclass=NullPool`: cada `connect()` es una sesión NUEVA de verdad, que es lo que
      necesitan estos tests —`ALTER DATABASE … SET` solo afecta a las sesiones abiertas DESPUÉS,
      así que el `SHOW timezone` de control tiene que venir de una sesión nueva para estar
      midiendo el default actual de la base en vez de uno anterior (con una conexión reusada
      del pool de la suite, el assert pasaría sin comprobar nada). Como no hay pool, al
      terminar tampoco queda ninguna conexión viva que pueda filtrar `AUTOCOMMIT` a la suite.

    Los `kwargs` de producción (`engine_kwargs_for_url`) se le siguen pasando a propósito: el
    punto de esos tests es que la sesión de la app quede en UTC, así que hasta la conexión de
    control tiene que llevar el mismo `options: -c timezone=UTC` (B8)."""
    engine_admin = create_engine(
        test_db_url,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
        **engine_kwargs_for_url(test_db_url),
    )
    yield engine_admin
    engine_admin.dispose()


@pytest.fixture
def real_client(real_session_factory: sessionmaker, engine: Engine) -> Generator[TestClient, None, None]:
    """Cliente con sesión REAL por request — a diferencia de `client` (una única
    `db_session` compartida con savepoints, pensada para aislar cada test con un
    rollback), acá cada request abre y cierra su PROPIA sesión desde una
    `sessionmaker` bound al `engine` de la suite, con commits reales. Imprescindible
    para que los locks de fila (`FOR UPDATE`) y los commits de una petición sean
    visibles para otra que corre en paralelo desde otro hilo — la única forma de
    probar concurrencia real (B1/B2).

    Sin transacción externa que lo limpie con un rollback (cada commit fue real):
    al terminar, trunca sus propias filas. El `CASCADE` es lo que hace que esto sea "borrar la
    base entera" y no "borrar 6 tablas" — alcanza también `budgets`, `notifications`,
    `push_subscriptions`, `api_keys`, `hidden_categories` y los tokens, que no están en la
    lista explícita (hallazgo 13)."""
    session_factory = real_session_factory

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
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
def real_register_and_login(real_client: TestClient, real_session_factory: sessionmaker):
    """Factory análoga a `register_and_login`, pero contra `real_client`: marca
    `email_verified` con una conexión de una sola vez, con su propio commit real —
    `db_session` no sirve acá, es una transacción distinta (sin commits reales) que
    las conexiones de `real_client` nunca verían."""
    counter = {"n": 0}
    session_factory = real_session_factory

    def _factory(
        email: str | None = None,
        password: str = STRONG_PASSWORD,
        full_name: str = "Usuario Concurrencia",
    ) -> dict:
        counter["n"] += 1
        email = email or f"realuser{counter['n']}@example.com"

        register_response = real_client.post(
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

        login_response = real_client.post(
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
def real_make_account(real_client: TestClient):
    """Factory de cuentas vía el endpoint real, sobre `real_client`."""

    def _factory(
        headers: dict,
        name: str = "Cuenta concurrencia",
        type: str = "cash",
        currency: str = "COP",
        balance: str = "1000.00",
        highlighted: bool = False,
    ) -> dict:
        response = real_client.post(
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
def real_make_category(real_client: TestClient):
    """Factory de categorías vía el endpoint real, sobre `real_client`."""

    def _factory(headers: dict, name: str = "Categoría concurrencia", type: str = "expense") -> dict:
        response = real_client.post(
            "/api/v1/categories/",
            json={"name": name, "type": type},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _factory
