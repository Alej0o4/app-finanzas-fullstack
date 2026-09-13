"""Regresión del Hallazgo 1 de `docs/specs/fase_21_spec.md`: `run_seed()` corrido dos veces
contra un usuario de prueba que acumuló una API key y una categoría oculta no debe reventar
con `IntegrityError`.

El conftest corre sobre SQLite en memoria SIN `PRAGMA foreign_keys=ON` — SQLite no aplica
FKs por defecto, así que una regresión ahí sería vacua (el código viejo del borrado inline
también pasaría). Este test construye su propio engine con FK enforcement activado para que
el `IntegrityError` del borrado incompleto realmente se dispare si `delete_user_cascade`
vuelve a olvidar una tabla hija.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
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


def _sembrar_categorias_sistema(session_factory: sessionmaker) -> None:
    """Equivale a `seed_default_categories()` (startup de la app) sobre el engine de test."""
    db = session_factory()
    try:
        for datos in _CATEGORIAS_SISTEMA:
            db.add(models.Category(name=datos["name"], type=datos["type"], user_id=None))
        db.commit()
    finally:
        db.close()


def test_run_seed_twice_with_api_key_and_hidden_category_does_not_raise(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _fk_pragma(dbapi_con, _rec):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
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
