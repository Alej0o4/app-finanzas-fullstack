"""Guardia de drift entre `app/models/models.py` y la cadena de migraciones (Fase 32, B9, Q3).

Nada en la suite comprueba que las migraciones coincidan con los modelos: hoy se edita
`models.py` sin escribir la migración, los 350 tests pasan en verde y el problema revienta en el
`CMD` de Docker, que corre `alembic upgrade head` antes de levantar uvicorn. Acá ese atraso se
convierte en un test de sesión (~1,5 s en Postgres, ~1,2 s en SQLite).

Corre en los **dos** motores y **sin** markers extra: el opt-in SQLite no puede ser un modo
donde el drift no se ve (User Story 21).

Dos decisiones que no son obvias:

- **Base propia, obligatoria.** La base de la suite queda con `create_all` y **sin**
  `alembic_version`; contra esa base `alembic check` responde `FAILED: Target database is not up
  to date`, que no es drift sino un falso positivo (hallazgo 15). Acá se provisiona una base
  migrada a `head` y se dropea al terminar: en Postgres, `DROP DATABASE IF EXISTS` +
  `CREATE DATABASE` con un sufijo que conserva "test" (la guarda de QA-001); en SQLite, un
  archivo temporal fuera del repo, que es lo que hace que el test sirva en los dos motores
  (hallazgo 16).
- **Subprocess, no la API de Alembic.** `alembic/env.py:23` pisa `sqlalchemy.url` con
  `app.core.database.SQLALCHEMY_DATABASE_URL`, que se construye **al import** desde
  `DATABASE_URL`. Como el conftest ya importó ese módulo, una llamada programática apuntaría a la
  base equivocada y no habría forma de sobrescribirla sin tocar `env.py` (que está fuera de
  scope). Un subprocess con `DATABASE_URL` en el `env` reproduce exactamente el camino del
  `CMD` de Docker: `alembic upgrade head` y nada más.

El resultado se asserta en el **cuerpo** del test, no acá: un fixture que falla se reporta como
error de setup y deja el test en verde — un drift tiene que leerse como test fallido (User
Story 22).
"""

import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.core.database import engine_kwargs_for_url

# `backend/` **de esta checkout**, no `os.getcwd()`: el subprocess necesita el `alembic.ini`,
# el `script_location` y el `prepend_sys_path = .` que hacen que `app` sea importable, y si el
# `cwd` fuera el del shell podría correr contra otra copia del repo (o no correr).
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Sufijo de la base de la guardia: derivado del nombre de la de la suite, conservando "test"
# (guarda de QA-001 — el nombre de la base tiene que decirlo) y sin pisarla.
SUFIJO_BASE_DRIFT = "_drift"

# Red contra un cuelgue, no un presupuesto de tiempo: la corrida dura ~1,5 s en Postgres y
# ~1,2 s en SQLite, sin contar el arranque del contenedor.
TIMEOUT_ALEMBIC_S = 300


def _correr_alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    """`alembic <args>` contra `url`, por subprocess.

    Réplica del `CMD` de Docker (`alembic upgrade head` con `DATABASE_URL` en el entorno), que
    es el camino que hay que vigilar. `sys.executable` y no `"alembic"` para que corra el
    intérprete del venv de la suite."""
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=TIMEOUT_ALEMBIC_S,
        check=False,
    )


@contextmanager
def _motor_de_administracion(url: str) -> Generator[Engine, None, None]:
    """Engine para los statements a nivel de BASE (`CREATE`/`DROP DATABASE`) — los mismos dos
    `kwargs` del fixture `admin_engine` de B5, y por el mismo motivo: `AUTOCOMMIT` porque
    `CREATE DATABASE` no puede correr dentro de una transacción (a diferencia del
    `ALTER DATABASE` del seam, que sí puede), y `NullPool` para no dejar conexiones vivas que
    le bloqueen el `DROP` de teardown.

    Es LOCAL y no el `admin_engine` del conftest porque ese fixture es de función y esta
    corrida es de sesión (pytest no deja pedir un fixture de función desde uno de sesión), y
    porque `admin_engine` hoy existe para el `ALTER DATABASE … SET timezone` del seam: si algún
    día esta guardia necesita otro motor de administración, la señal es que los dos se unifican.
    """
    engine_admin = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool, **engine_kwargs_for_url(url))
    try:
        yield engine_admin
    finally:
        engine_admin.dispose()


@pytest.fixture(scope="session")
def resultado_alembic_check(test_db_url: str, tmp_path_factory) -> tuple[str, subprocess.CompletedProcess]:
    """Corre `alembic upgrade head` + `alembic check` contra una base PROPIA y devuelve
    `(paso, proceso)` para que el test lo asserte.

    El `engine` de la suite no puede hacer el `CREATE DATABASE`: su `drop_all`/`create_all` es
    sobre la base de la suite, que es justo la que hay que NO tocar (y `create_all` la deja sin
    `alembic_version`, donde el `check` da un falso positivo).

    Si el rol no puede crear bases (Postgres con privilegios reducidos — un caso que ni el
    contenedor de testcontainers ni la receta de `AGENTS.md` tienen) el test se **salta** con un
    motivo que nombra lo que falta, en vez de romper la corrida entera. La alternativa —esquemas
    vía `?options=-c search_path=…` en la URL— queda anotada como trabajo futuro para el día que
    aparezca ese rol (B9)."""
    if test_db_url.startswith("sqlite"):
        # Una `sqlite://` en memoria no tiene dónde vivir: la guardia necesita una base
        # PERSISTENTE y vacía, y por eso un archivo temporal (hallazgo 16).
        archivo = tmp_path_factory.mktemp("alembic_drift") / "oikos_test_drift.db"
        url_drift = f"sqlite:///{archivo}"
    else:
        url_suite = make_url(test_db_url)
        # Sufijo aleatorio: dos sesiones de pytest contra el mismo Postgres del operador no
        # deben pisarse la base de drift (el `DROP … IF EXISTS` de abajo borraría la ajena).
        url_drift_obj = url_suite.set(database=f"{url_suite.database}{SUFIJO_BASE_DRIFT}_{uuid.uuid4().hex[:8]}")
        url_drift = url_drift_obj.render_as_string(hide_password=False)

        try:
            with _motor_de_administracion(test_db_url) as motor, motor.connect() as conn:
                # `IF EXISTS` por defensa: con el sufijo aleatorio no debería existir.
                conn.execute(text(f'DROP DATABASE IF EXISTS "{url_drift_obj.database}"'))
                conn.execute(text(f'CREATE DATABASE "{url_drift_obj.database}"'))
        except DBAPIError as exc:
            # 42501 = insufficient_privilege, 42P04 = duplicate_database.
            codigo = getattr(exc.orig, "pgcode", None)
            if codigo in {"42501", "42P04"} or "permission denied" in str(exc):
                pytest.skip(
                    f"el rol de la suite no puede crear la base {url_drift_obj.database!r} "
                    f"(Postgres {codigo}): la guardia de drift necesita una base migrada propia, "
                    "porque contra la base de la suite (creada con create_all, sin alembic_version) "
                    "`alembic check` da un falso positivo"
                )
            raise

    try:
        upgrade = _correr_alembic(url_drift, "upgrade", "head")
        if upgrade.returncode != 0:
            # Si la cadena no aplica, el `check` no tiene nada que comparar: se devuelve el
            # paso que falló para que el mensaje de aserción nombre la causa real.
            return "upgrade head", upgrade
        return "check", _correr_alembic(url_drift, "check")
    finally:
        # Se limpia aunque el test falle: la base es desechable y dejarla tirada solo hace
        # ruido en la corrida siguiente.
        if test_db_url.startswith("sqlite"):
            archivo.unlink(missing_ok=True)
        else:
            with _motor_de_administracion(test_db_url) as motor, motor.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{url_drift_obj.database}"'))


def test_alembic_check_no_encuentra_drift_entre_models_y_migraciones(resultado_alembic_check):
    """La cadena de migraciones, aplicada a una base vacía, deja EXACTAMENTE el esquema que
    `models.py` describe. Si esto falla, o falta una migración o sobró una."""
    paso, proceso = resultado_alembic_check
    salida = (proceso.stdout + proceso.stderr).strip()
    assert proceso.returncode == 0, (
        f"`alembic {paso}` falló contra una base migrada a head: hay drift entre "
        f"`app/models/models.py` y la cadena de migraciones.\n\n"
        f"Salida de alembic:\n{salida}\n\n"
        "Si editaste los modelos sin migración, corré la skill /alembic-migration "
        "(`alembic revision --autogenerate` y revisá el archivo a mano antes de commitear)."
    )
