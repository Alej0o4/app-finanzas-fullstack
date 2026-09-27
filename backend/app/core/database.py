import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker, with_loader_criteria
from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime

# 1. Definimos la URL de conexión (Credenciales)
# DATABASE_URL puede ser SQLite (local) o PostgreSQL (Docker/producción).
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finanzas.db")


def engine_kwargs_for_url(url: str) -> dict:
    """Arma los `kwargs` de `create_engine` según el dialecto (Fase 31, Decisión B8).

    SQLite: `check_same_thread=False`, como siempre. Postgres: fija la sesión en UTC
    vía `-c timezone=UTC` — la app ya trabaja en datetimes naive UTC en todos lados
    (`core/periods.py`), y sin esto los agregados de fecha (cashflow-series,
    dashboard, monthly-summary) quedarían a merced del timezone configurado en el
    servidor Postgres, no del de la app (QA-022). `tests/conftest.py` (T1) usa esta
    misma función para el engine de `TEST_DATABASE_URL`, así la suite contra Postgres
    corre con la misma sesión que producción.
    """
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if url.startswith("postgresql"):
        return {"connect_args": {"options": "-c timezone=UTC"}}
    return {}


# 2. Creamos el "Motor" (Engine)
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs_for_url(SQLALCHEMY_DATABASE_URL))

# 3. Creamos la Fábrica de Sesiones
# Una "sesión" es una transacción temporal. Aquí abrimos la conexión, hacemos los cambios y luego cerramos.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Creamos la Clase Base
# Todas nuestras tablas (Usuarios, Transacciones) heredan de esta clase para que SQLAlchemy sepa que deben convertirse en tablas SQL.
Base = declarative_base()


class SoftDeleteMixin:
    """Borrado lógico (Fase 8 §6): una fila con `deleted_at` poblado se considera eliminada.

    Vive junto a `Base` y no en `models.py` para no invertir la dependencia entre ambos
    módulos (`models` importa de `database`) — ver Decisión 6.1 del spec de Fase 8.
    Aplicado solo en las entidades de dominio (User, Account, Category, Transaction,
    Budget); los modelos de token quedan fuera (Decisión 6.3).
    """

    deleted_at = Column(DateTime(timezone=True), nullable=True)


# 5. Filtro global de borrado lógico (Fase 8 §6, Decisión 6.1).
# Registrado sobre la CLASE Session: alcanza a toda sesión creada en el proceso
# (app real, seed.py, tests) porque todos importan este módulo. Solo lecturas —
# las actualizaciones Core de saldo en transactions.py llevan su filtro
# `.where(deleted_at.is_(None))` explícito en el call-site (Opción A del plan).
@event.listens_for(Session, "do_orm_execute")
def _filtrar_borrados_logicos(execute_state):
    if execute_state.is_select and not execute_state.is_column_load and not execute_state.is_relationship_load:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
        )


# 6. Función de Inyección de Dependencias
# Esta función le dará una conexión de BD abierta a cada endpoint que la solicite, y lo cerrará automáticamente al terminar.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
