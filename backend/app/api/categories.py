from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.core.security import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.CategoryResponse)
def crear_categoria(
    categoria: schemas.CategoryCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    nueva_categoria = models.Category(**categoria.model_dump(), user_id=current_user.id)
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    return nueva_categoria

@router.get("/", response_model=List[schemas.CategoryResponse])
def obtener_categorias(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    categorias = db.query(models.Category).filter(
        or_(
            models.Category.user_id.is_(None),
            models.Category.user_id == current_user.id
        )
    ).all()
    return list(categorias)

@router.get("/{category_id}", response_model=schemas.CategoryResponse)
def obtener_categoria(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()
    
    # Las categorías del sistema tienen user_id NULL y deben ser visibles para todos.
    if not categoria or (categoria.user_id is not None and categoria.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")
    
    return categoria

@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def actualizar_categoria(
    category_id: int,
    categoria_actualizada: schemas.CategoryBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Category:
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()
    
    if not categoria or (categoria.user_id != current_user.id and categoria.user_id is not None):
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")
    
    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden modificar las categorías base del sistema.")
        
    categoria.name = categoria_actualizada.name
    categoria.type = categoria_actualizada.type
    
    db.commit()
    db.refresh(categoria)
    return categoria

@router.delete("/{category_id}")
def eliminar_categoria(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()
    
    if not categoria or (categoria.user_id != current_user.id and categoria.user_id is not None):
         raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")
        
    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden eliminar las categorías base del sistema.")
    
    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar la categoría porque tiene transacciones asociadas."
        )
    
    tiene_presupuestos = db.query(models.Budget).filter(models.Budget.category_id == category_id).first()
    if tiene_presupuestos:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar la categoría porque tiene presupuestos activos. Elimínalos primero."
        )
        
    db.delete(categoria)
    db.commit()
    return {"estado": "OK", "mensaje": "Categoría eliminada exitosamente."}