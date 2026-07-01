from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # 1. Importamos el Middleware
from app.core.database import engine, Base, SessionLocal
from app.models import models

from app.api import transactions, users, accounts, categories, budgets, auth, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Finanzas Personales",
    description="Backend para gestión de ingresos, gastos y presupuestos."
)

DEFAULT_CATEGORIES = [
    {"name": "Alimentación", "type": "expense"},
    {"name": "Transporte", "type": "expense"},
    {"name": "Ocio", "type": "expense"},
    {"name": "Cuidado personal", "type": "expense"},
    {"name": "Suscripción", "type": "expense"},
    {"name": "Otro (Gasto)", "type": "expense"},
    {"name": "Salario", "type": "income"},
    {"name": "Otro (Ingreso)", "type": "income"},
]

LEGACY_DEFAULT_CATEGORY_NAMES = {
    ("expense", "Otro"): "Otro (Gasto)",
    ("income", "Otro"): "Otro (Ingreso)",
}


def seed_default_categories() -> None:
    db = SessionLocal()
    try:
        for category_data in DEFAULT_CATEGORIES:
            existing_category = db.query(models.Category).filter(
                models.Category.user_id.is_(None),
                models.Category.name == category_data["name"],
                models.Category.type == category_data["type"],
            ).first()

            if existing_category is None:
                legacy_name = LEGACY_DEFAULT_CATEGORY_NAMES.get((category_data["type"], category_data["name"]))
                if legacy_name:
                    existing_category = db.query(models.Category).filter(
                        models.Category.user_id.is_(None),
                        models.Category.name == legacy_name,
                        models.Category.type == category_data["type"],
                    ).first()

                    if existing_category is not None:
                        existing_category.name = category_data["name"]
                        continue

            if existing_category is None:
                db.add(models.Category(**category_data, user_id=None))

        db.commit()
    finally:
        db.close()

# 2. CONFIGURACIÓN CORS (Bloqueo de Fronteras)
# Aquí ponemos la URL donde vivirá nuestro Frontend en desarrollo
origenes_permitidos = [
    "http://localhost:3000", # Puerto clásico de React
    "http://localhost:5173", # Puerto clásico de Vite (React moderno)
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"], # Permitimos GET, POST, PUT, DELETE...
    allow_headers=["*"], # Permitimos todos los encabezados (incluyendo los Tokens)
)

# 3. Conexión de Enrutadores
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transacciones"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Cuentas"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categorías"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["Presupuestos"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.on_event("startup")
def initialize_shared_data():
    seed_default_categories()

@app.get("/")
def ruta_raiz():
    return {"estado": "OK", "mensaje": "Motor de Finanzas seguro y en línea."}