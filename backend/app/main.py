from fastapi import FastAPI
# 1. Importamos las herramientas de nuestra base de datos y los modelos
from app.core.database import engine, Base
from app.models import models

# 2. ¡La instrucción de fabricación!
# Esto le dice a SQLAlchemy: "Revisa todos los modelos y crea las tablas físicas en el archivo .db si no existen"
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Finanzas Personales",
    description="Backend para gestión de ingresos, gastos y presupuestos."
)

@app.get("/")
def ruta_raiz():
    return {
        "estado": "OK",
        "mensaje": "¡Motor de Finanzas en línea y base de datos conectada!"
    }