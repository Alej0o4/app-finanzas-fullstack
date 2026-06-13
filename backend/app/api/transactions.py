from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importamos nuestras piezas
from app.core.database import get_db
from app.models import models
from app.schemas import schemas

# Inicializamos nuestro "Tablero Secundario"
router = APIRouter()

# Definimos la ruta POST para CREAR una transacción
# Nota cómo le decimos a FastAPI que use el filtro de salida: response_model=schemas.TransactionResponse
@router.post("/", response_model=schemas.TransactionResponse)
def crear_transaccion(
    transaccion: schemas.TransactionCreate, # 1. El JSON entrante pasa por el filtro Pydantic
    db: Session = Depends(get_db)           # 2. Inyección de Dependencia: Nos abre una conexión a la BD
):
    # Paso A: Convertimos el JSON validado (Schema) en un objeto físico de la BD (Modelo)
    # El **transaccion.dict() desempaqueta los datos automáticamente
    nueva_transaccion = models.Transaction(**transaccion.dict())
    
    # Paso B: Preparamos la pieza en la memoria temporal (RAM)
    db.add(nueva_transaccion)
    
    # Paso C: ¡El gatillo! Guardamos los datos físicamente en el disco duro (.db)
    db.commit()
    
    # Paso D: Actualizamos nuestro objeto en Python para que la BD le inyecte el 'id' y la 'fecha' que acaba de generar
    db.refresh(nueva_transaccion)
    
    # Paso E: Devolvemos el objeto. FastAPI lo pasará por el filtro de salida (TransactionResponse) automáticamente
    return nueva_transaccion

# Añade esto debajo de tu función POST

# 1. Definimos la ruta GET. 
# Nota clave: La respuesta ya no es un solo Schema, sino una Lista de ellos.
@router.get("/", response_model=List[schemas.TransactionResponse])
def obtener_transacciones(
    # 2. Parámetros de consulta (Query Parameters) para la Paginación
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    # Paso A: Le pedimos a SQLAlchemy que busque en el modelo Transaction
    # Paso B: Aplicamos el salto (offset) y el límite, y traemos todos (.all())
    transacciones = db.query(models.Transaction).offset(skip).limit(limit).all()
    
    # Paso C: Devolvemos la lista. FastAPI y Pydantic filtrarán CADA elemento de la lista automáticamente.
    return transacciones

# Añade esto al final de app/api/transactions.py

@router.delete("/{transaction_id}")
def eliminar_transaccion(
    transaction_id: int,                  # Recibimos el ID desde la URL
    db: Session = Depends(get_db)
):
    # Paso A: Buscamos la transacción en la base de datos por su ID
    transaccion_existente = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    
    # Paso B: Control de calidad / Programación Defensiva
    # Si el usuario nos pide borrar un ID que no existe (ej. el 999), detenemos la máquina
    if not transaccion_existente:
        raise HTTPException(
            status_code=404, 
            detail=f"Error: La transacción con ID {transaction_id} no existe en la base de datos."
        )
    
    # Paso C: Si existe, le decimos al ORM que la remueva de la memoria
    db.delete(transaccion_existente)
    
    # Paso D: Confirmamos los cambios en el disco duro (.db)
    db.commit()
    
    # Paso E: Devolvemos un mensaje de éxito
    return {
        "estado": "OK",
        "mensaje": f"Transacción con ID {transaction_id} eliminada exitosamente de la base de datos."
    }