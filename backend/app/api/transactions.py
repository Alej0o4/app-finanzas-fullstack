from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

# 🔒 Importamos a nuestro Guardia de Seguridad
from app.core.security import get_current_user

router = APIRouter()

# --- RUTA PROTEGIDA ---
@router.post("/", response_model=schemas.TransactionResponse)
def crear_transaccion(
    transaccion: schemas.TransactionCreate, 
    db: Session = Depends(get_db),
    # 🔒 El Guardia entra en acción: Extrae al usuario dueño del token invisible
    current_user: models.User = Depends(get_current_user) 
):
    # Ya no tomamos el user_id del JSON (porque lo borramos del schema). 
    # Lo inyectamos directamente nosotros desde el servidor. Es infalsificable.
    nueva_transaccion = models.Transaction(
        **transaccion.dict(),
        user_id=current_user.id  
    )
    
    db.add(nueva_transaccion)
    db.commit()
    db.refresh(nueva_transaccion)
    return nueva_transaccion


# --- RUTA PROTEGIDA ---
@router.get("/", response_model=List[schemas.TransactionResponse])
def obtener_transacciones(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    # 🔒 El Guardia protege la lectura
    current_user: models.User = Depends(get_current_user)
):
    # Aislamiento de Datos forzado. El usuario solo puede ver lo suyo.
    # Fíjate que ya no le pedimos el user_id en la URL, el servidor lo sabe automáticamente.
    transacciones = db.query(models.Transaction)\
        .filter(models.Transaction.user_id == current_user.id)\
        .offset(skip).limit(limit).all()
        
    return transacciones


# --- RUTA PROTEGIDA ---
@router.delete("/{transaction_id}")
def eliminar_transaccion(
    transaction_id: int,
    db: Session = Depends(get_db),
    # 🔒 El Guardia protege la eliminación
    current_user: models.User = Depends(get_current_user)
):
    transaccion = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    
    if not transaccion:
        raise HTTPException(status_code=404, detail="La transacción no existe.")
        
    # 🔒 Programación Defensiva Crítica:
    # Verificamos que el usuario que intenta borrar la transacción, SEA el dueño real.
    if transaccion.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar esta transacción.")
    
    db.delete(transaccion)
    db.commit()
    return {"estado": "OK", "mensaje": "Transacción eliminada."}