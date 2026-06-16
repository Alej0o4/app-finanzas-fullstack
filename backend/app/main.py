from fastapi import FastAPI
from app.core.database import engine, Base
from app.models import models
from app.api import transactions,users,accounts,categories,budgets

# Creamos las tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Finanzas Personales",
    description="Backend para gestión de ingresos, gastos y presupuestos."
)

# IMPORTANTE: Conectamos el enrutador secundario a la API
# Le ponemos el prefijo "/api/transactions" para mantener todo ordenado
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transacciones"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Cuentas"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categorías"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["Presupuestos"])

@app.get("/")
def ruta_raiz():
    return {
        "estado": "OK",
        "mensaje": "¡Motor de Finanzas en línea y base de datos conectada!"
    }