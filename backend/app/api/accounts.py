from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

#Ruta A: CREAR CUENTA
@router.post("/", response_model=schemas.AccountResponse)
def crear_cuenta(
    cuenta: schemas.AccountCreate, 
    db: Session = Depends(get_db)
):
    # Programación Defensiva: Verificar que el usuario dueño REALMENTE exista
    usuario_dueno = db.query(models.User).filter(models.User.id == cuenta.user_id).first()
    if not usuario_dueno:
        raise HTTPException(
            status_code=404, 
            detail=f"Error: No se puede crear la cuenta. El usuario con ID {cuenta.user_id} no existe."
        )
    
    # Inyección en la base de datos
    nueva_cuenta = models.Account(**cuenta.dict())
    db.add(nueva_cuenta)
    db.commit()
    db.refresh(nueva_cuenta)
    return nueva_cuenta

#Ruta B: LISTAR CUENTAS PERSONALES DE UN USUARIO
@router.get("/", response_model=List[schemas.AccountResponse])
def obtener_cuentas(
    user_id: int,                     # 🔒 Exigimos el ID del usuario para saber quién pregunta
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    # Aplicamos un filtro estricto (.filter) usando la llave foránea
    cuentas = db.query(models.Account).filter(models.Account.user_id == user_id).offset(skip).limit(limit).all()
    return cuentas

# Añade esto al final de app/api/accounts.py

# Ruta C: ACTUALIZAR CUENTA (PUT)
@router.put("/{account_id}", response_model=schemas.AccountResponse)
def actualizar_cuenta(
    account_id: int,
    cuenta_actualizada: schemas.AccountBase, # Reutilizamos el molde base para validar los cambios
    db: Session = Depends(get_db)
) -> models.Account:
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta a actualizar no existe.")
    
    # Sobrescribimos los valores físicos con los nuevos datos entrantes
    cuenta.name = cuenta_actualizada.name
    cuenta.type = cuenta_actualizada.type
    cuenta.balance = cuenta_actualizada.balance
    
    db.commit()
    db.refresh(cuenta)
    return cuenta


# Ruta D: ELIMINAR CUENTA (DELETE)
@router.delete("/{account_id}")
def eliminar_cuenta(
    account_id: int,
    db: Session = Depends(get_db)
):
    cuenta = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta a eliminar no existe.")
    
    # 🔒 Programación Defensiva: Verificar si la cuenta tiene transacciones amarradas
    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.account_id == account_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar la cuenta porque tiene transacciones asociadas. Elimina primero las transacciones."
        )
    
    db.delete(cuenta)
    db.commit()
    return {"estado": "OK", "mensaje": f"Cuenta con ID {account_id} eliminada exitosamente."}