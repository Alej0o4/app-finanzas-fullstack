from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy import or_, desc, update, func
from datetime import datetime

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
    nueva_transaccion = models.Transaction(**transaccion.model_dump(exclude_none=True), user_id=current_user.id)
    nueva_transaccion.currency = cuenta.currency  # hereda la moneda de la cuenta
    
    # 🧮 3. Lógica Contable: Actualizar saldo de forma atómica en SQL
    delta = transaccion.amount if transaccion.type == "income" else -transaccion.amount

    try:
        db.add(nueva_transaccion)
        db.execute(
            update(models.Account)
            .where(models.Account.id == transaccion.account_id)
            .values(balance=models.Account.balance + delta)
        )
        db.commit()
        db.refresh(nueva_transaccion)
        return nueva_transaccion
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.")


# --- RUTA PROTEGIDA ---
@router.get("/", response_model=schemas.PaginatedResponse[schemas.TransactionResponse])
def obtener_transacciones(
    skip: int = 0, 
    limit: int = 100, 
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="La fecha inicial no puede ser mayor que la fecha final.")

    query = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id)
    
    if account_id is not None:
        query = query.filter(models.Transaction.account_id == account_id)
        
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)

    if start_date is not None:
        query = query.filter(models.Transaction.date >= start_date)

    if end_date is not None:
        query = query.filter(models.Transaction.date <= end_date)

    total = query.with_entities(func.count()).scalar()
    
    transacciones = query.order_by(
        desc(models.Transaction.date),
        desc(models.Transaction.id)
    ).offset(skip).limit(limit).all()
    
    page = (skip // limit) + 1 if limit > 0 else 1

    return schemas.PaginatedResponse(
        items=transacciones,
        total=total,
        page=page,
        page_size=limit,
    )


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
    
    # 🧮 2. Lógica Contable Inversa: Revertir el impacto de forma atómica
    if cuenta:
        delta = -transaccion.amount if transaccion.type == "income" else transaccion.amount
        db.execute(
            update(models.Account)
            .where(models.Account.id == transaccion.account_id)
            .values(balance=models.Account.balance + delta)
        )

    try:
        db.delete(transaccion)
        db.commit()
        return {"estado": "OK", "mensaje": "Transacción eliminada y saldo de cuenta revertido exitosamente."}
    except Exception:
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

    old_delta = transaccion_db.amount if transaccion_db.type == "income" else -transaccion_db.amount
    new_delta = transaccion_actualizada.amount if transaccion_actualizada.type == "income" else -transaccion_actualizada.amount

    try:
        if cuenta_vieja.id == cuenta_nueva.id:
            net_delta = new_delta - old_delta
            db.execute(
                update(models.Account)
                .where(models.Account.id == cuenta_vieja.id)
                .values(balance=models.Account.balance + net_delta)
            )
        else:
            db.execute(
                update(models.Account)
                .where(models.Account.id == cuenta_vieja.id)
                .values(balance=models.Account.balance - old_delta)
            )
            db.execute(
                update(models.Account)
                .where(models.Account.id == cuenta_nueva.id)
                .values(balance=models.Account.balance + new_delta)
            )

        transaccion_db.amount = transaccion_actualizada.amount
        transaccion_db.type = transaccion_actualizada.type
        transaccion_db.description = transaccion_actualizada.description
        transaccion_db.account_id = transaccion_actualizada.account_id
        transaccion_db.category_id = transaccion_actualizada.category_id
        if transaccion_actualizada.date is not None:
            transaccion_db.date = transaccion_actualizada.date

        db.commit()
        db.refresh(transaccion_db)
        return transaccion_db

    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al recalcular saldos en la actualización.")