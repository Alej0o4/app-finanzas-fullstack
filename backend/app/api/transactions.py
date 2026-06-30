from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import or_, desc

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
    current_user: models.User = Depends(get_current_user) 
):
    # 🔒 1. Verificar que la cuenta de destino exista y PERTENEZCA al usuario
    cuenta = db.query(models.Account).filter(
        models.Account.id == transaccion.account_id,
        models.Account.user_id == current_user.id
    ).first()
    
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta especificada no existe o no te pertenece.")
    
    categoria = db.query(models.Category).filter(
        models.Category.id == transaccion.category_id,
        or_(models.Category.user_id == None, models.Category.user_id == current_user.id)
    ).first()
    
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría especificada no existe o no tienes permisos para usarla.")
        
    # 2. Ensamblar la transacción
    nueva_transaccion = models.Transaction(**transaccion.dict(exclude_none=True), user_id=current_user.id)
    
    # 🧮 3. Lógica Contable: Actualizar el saldo de la cuenta en la RAM
    if transaccion.type == "income":
        cuenta.balance += transaccion.amount
    elif transaccion.type == "expense":
        cuenta.balance -= transaccion.amount
        
    try:
        # 4. Intentamos guardar ambas cosas en el disco duro al mismo tiempo
        db.add(nueva_transaccion)
        db.commit() # ¡El gatillo atómico! Guarda transacción y actualiza cuenta
        db.refresh(nueva_transaccion)
        return nueva_transaccion
    except Exception as e:
        # 🛡️ 5. Si algo explota (ej. caída de red), revertimos todo para no corromper los saldos
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.")


# --- RUTA PROTEGIDA ---
@router.get("/", response_model=List[schemas.TransactionResponse])
def obtener_transacciones(
    skip: int = 0, 
    limit: int = 100, 
    account_id: Optional[int] = None,   # <-- 1. Parámetro opcional
    category_id: Optional[int] = None,  # <-- 2. Parámetro opcional
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id)
    
    if account_id is not None:
        query = query.filter(models.Transaction.account_id == account_id)
        
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
        
    transacciones = query.order_by(
        desc(models.Transaction.date),
        desc(models.Transaction.id)
    ).offset(skip).limit(limit).all()
    
    return transacciones


# --- RUTA PROTEGIDA ---
@router.delete("/{transaction_id}")
def eliminar_transaccion(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    transaccion = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    
    if not transaccion or transaccion.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La transacción no existe o no tienes permisos.")
        
    # 1. Obtener la cuenta asociada a esta transacción
    cuenta = db.query(models.Account).filter(models.Account.id == transaccion.account_id).first()
    
    # 🧮 2. Lógica Contable Inversa: Revertimos el impacto del saldo en la RAM
    if cuenta:
        if transaccion.type == "income":
            cuenta.balance -= transaccion.amount # Si era ingreso y lo borro, pierdo plata
        elif transaccion.type == "expense":
            cuenta.balance += transaccion.amount # Si era gasto y lo borro, recupero plata
            
    try:
        # 3. Ejecutamos el borrado y la actualización de saldo en un solo movimiento
        db.delete(transaccion)
        db.commit()
        return {"estado": "OK", "mensaje": "Transacción eliminada y saldo de cuenta revertido exitosamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al intentar eliminar y revertir saldos.")

@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def actualizar_transaccion(
    transaction_id: int,
    transaccion_actualizada: schemas.TransactionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Transaction:
    
    # 1. Buscamos la transacción original
    transaccion_db = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == current_user.id
    ).first()
    
    if not transaccion_db:
        raise HTTPException(status_code=404, detail="Transacción no encontrada.")

    # 2. Buscamos las cuentas (la vieja y la nueva, por si el usuario movió el gasto a otra cuenta)
    cuenta_vieja = db.query(models.Account).filter(models.Account.id == transaccion_db.account_id).first()
    cuenta_nueva = db.query(models.Account).filter(
        models.Account.id == transaccion_actualizada.account_id,
        models.Account.user_id == current_user.id
    ).first()
    
    if not cuenta_nueva:
        raise HTTPException(status_code=404, detail="La nueva cuenta asignada no existe o no te pertenece.")
    
    categoria = db.query(models.Category).filter(
        models.Category.id == transaccion_actualizada.category_id,
        or_(models.Category.user_id == None, models.Category.user_id == current_user.id)
    ).first()
    
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría especificada no existe o no tienes permisos para usarla.")

    try:
        # 🧮 A. Revertimos el impacto de la transacción VIEJA en la cuenta VIEJA
        if transaccion_db.type == "income":
            cuenta_vieja.balance -= transaccion_db.amount
        elif transaccion_db.type == "expense":
            cuenta_vieja.balance += transaccion_db.amount

        # 🧮 B. Aplicamos el impacto de la transacción NUEVA en la cuenta NUEVA
        if transaccion_actualizada.type == "income":
            cuenta_nueva.balance += transaccion_actualizada.amount
        elif transaccion_actualizada.type == "expense":
            cuenta_nueva.balance -= transaccion_actualizada.amount

        # C. Actualizamos los datos físicos de la transacción
        transaccion_db.amount = transaccion_actualizada.amount
        transaccion_db.type = transaccion_actualizada.type
        transaccion_db.description = transaccion_actualizada.description
        transaccion_db.account_id = transaccion_actualizada.account_id
        transaccion_db.category_id = transaccion_actualizada.category_id
        if transaccion_actualizada.date is not None:
            transaccion_db.date = transaccion_actualizada.date

        # D. Guardamos todo de forma Atómica
        db.commit()
        db.refresh(transaccion_db)
        return transaccion_db

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al recalcular saldos en la actualización.")