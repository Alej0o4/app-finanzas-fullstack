import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Definimos la URL de conexión (Credenciales)
# DATABASE_URL puede ser SQLite (local) o PostgreSQL (Docker/producción).
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finanzas.db")

# 2. Creamos el "Motor" (Engine)
# connect_args solo es necesario para SQLite.
_engine_kwargs = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)

# 3. Creamos la Fábrica de Sesiones
# Una "sesión" es una transacción temporal. Aquí abrimos la conexión, hacemos los cambios y luego cerramos.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Creamos la Clase Base
# Todas nuestras tablas (Usuarios, Transacciones) heredarán de esta clase para que SQLAlchemy sepa que deben convertirse en tablas SQL.
Base = declarative_base()

# 5. Función de Inyección de Dependencias
# Esta función le dará una conexión de BD abierta a cada endpoint que la solicite, y la cerrará automáticamente al terminar.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()