from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.core.security import get_current_user
from sqlalchemy import or_

router = APIRouter()

@router.post("/", response_model=schemas.BudgetResponse)
def crear_presupuesto(
    presupuesto: schemas.BudgetCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    categoria = db.query(models.Category).filter(
        models.Category.id == presupuesto.category_id,
        or_(models.Category.user_id == None, models.Category.user_id == current_user.id)
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría asignada no existe.")

    presupuesto_existente = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.category_id == presupuesto.category_id,
        models.Budget.month == presupuesto.month,
        models.Budget.year == presupuesto.year
    ).first()
    
    if presupuesto_existente:
        raise HTTPException(
            status_code=400, 
            detail="Ya existe un presupuesto para esta categoría en este mes y año."
        )

    nuevo_presupuesto = models.Budget(**presupuesto.dict(), user_id=current_user.id)
    db.add(nuevo_presupuesto)
    db.commit()
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto

@router.get("/", response_model=List[schemas.BudgetResponse])
def obtener_presupuestos(
    month: int = None, 
    year: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Budget).filter(models.Budget.user_id == current_user.id)
    
    if month:
        query = query.filter(models.Budget.month == month)
    if year:
        query = query.filter(models.Budget.year == year)
        
    return query.all()

@router.delete("/{budget_id}")
def eliminar_presupuesto(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    presupuesto = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not presupuesto or presupuesto.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="El presupuesto no existe o no tienes permisos.")
        
    db.delete(presupuesto)
    db.commit()
    return {"estado": "OK", "mensaje": "Presupuesto eliminado exitosamente."}

@router.put("/{budget_id}", response_model=schemas.BudgetResponse)
def actualizar_presupuesto(
    budget_id: int,
    presupuesto_actualizado: schemas.BudgetBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Budget:
    
    presupuesto_db = db.query(models.Budget).filter(
        models.Budget.id == budget_id,
        models.Budget.user_id == current_user.id
    ).first()
    
    if not presupuesto_db:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")

    # Validamos que la nueva categoría exista
    categoria = db.query(models.Category).filter(
        models.Category.id == presupuesto_actualizado.category_id,
        or_(models.Category.user_id == None, models.Category.user_id == current_user.id)
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La nueva categoría asignada no existe.")

    # Actualizamos los datos
    presupuesto_db.amount_limit = presupuesto_actualizado.amount_limit
    presupuesto_db.month = presupuesto_actualizado.month
    presupuesto_db.year = presupuesto_actualizado.year
    presupuesto_db.category_id = presupuesto_actualizado.category_id

    db.commit()
    db.refresh(presupuesto_db)
    return presupuesto_db