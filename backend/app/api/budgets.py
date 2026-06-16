from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

# Ruta A: CREAR PRESUPUESTO (POST)
@router.post("/", response_model=schemas.BudgetResponse)
def crear_presupuesto(
    presupuesto: schemas.BudgetCreate, 
    db: Session = Depends(get_db)
):
    # 🔒 Programación Defensiva 1: Verificar que el usuario exista
    usuario = db.query(models.User).filter(models.User.id == presupuesto.user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="El usuario no existe.")
        
    # 🔒 Programación Defensiva 2: Verificar que la categoría exista
    categoria = db.query(models.Category).filter(models.Category.id == presupuesto.category_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría asignada no existe.")

    # 🔒 Programación Defensiva Avanzada: Evitar presupuestos duplicados para el mismo mes/año/categoría
    presupuesto_existente = db.query(models.Budget).filter(
        models.Budget.user_id == presupuesto.user_id,
        models.Budget.category_id == presupuesto.category_id,
        models.Budget.month == presupuesto.month,
        models.Budget.year == presupuesto.year
    ).first()
    
    if presupuesto_existente:
        raise HTTPException(
            status_code=400, 
            detail="Ya existe un presupuesto para esta categoría en este mes y año."
        )

    # Inyección en la base de datos
    nuevo_presupuesto = models.Budget(**presupuesto.dict())
    db.add(nuevo_presupuesto)
    db.commit()
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto


# Ruta B: OBTENER PRESUPUESTOS DEL USUARIO (GET)
@router.get("/", response_model=List[schemas.BudgetResponse])
def obtener_presupuestos(
    user_id: int, 
    month: int = None, # Parámetros opcionales para filtrar por mes y año
    year: int = None,
    db: Session = Depends(get_db)
):
    # Iniciamos la consulta filtrando siempre por el usuario (Aislamiento de datos)
    query = db.query(models.Budget).filter(models.Budget.user_id == user_id)
    
    # Si el cliente nos envía el mes y/o año en la URL, añadimos esos filtros a la consulta SQL
    if month:
        query = query.filter(models.Budget.month == month)
    if year:
        query = query.filter(models.Budget.year == year)
        
    return query.all()


# Ruta C: ELIMINAR PRESUPUESTO (DELETE)
@router.delete("/{budget_id}")
def eliminar_presupuesto(
    budget_id: int,
    db: Session = Depends(get_db)
):
    presupuesto = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not presupuesto:
        raise HTTPException(status_code=404, detail="El presupuesto no existe.")
        
    db.delete(presupuesto)
    db.commit()
    return {"estado": "OK", "mensaje": f"Presupuesto con ID {budget_id} eliminado exitosamente."}