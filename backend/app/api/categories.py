from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_  # Para hacer consultas con lógica "O" (OR)
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

# Ruta A: CREAR CATEGORÍA
@router.post("/", response_model=schemas.CategoryResponse)
def crear_categoria(
    categoria: schemas.CategoryCreate, 
    db: Session = Depends(get_db)
):
    # Si nos envían un user_id, validamos defensivamente que el usuario exista
    if categoria.user_id is not None:
        usuario = db.query(models.User).filter(models.User.id == categoria.user_id).first()
        if not usuario:
            raise HTTPException(
                status_code=404, 
                detail=f"Error: El usuario con ID {categoria.user_id} no existe."
            )
            
    nueva_categoria = models.Category(**categoria.dict())
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    return nueva_categoria


# Ruta B: LISTAR CATEGORÍAS (Lógica Avanzada de Aislamiento)
@router.get("/", response_model=List[schemas.CategoryResponse])
def obtener_categorias(
    user_id: int, # El ID del usuario que consulta
    db: Session = Depends(get_db)
):
    # 🔒 Filtrado Inteligente: Traemos las categorías donde:
    # El user_id sea NULL (del sistema) O el user_id coincida con el usuario actual
    categorias = db.query(models.Category).filter(
        or_(
            models.Category.user_id == None,
            models.Category.user_id == user_id
        )
    ).all()
    return list(categorias)

# Añade esto al final de app/api/categories.py

# Ruta C: ACTUALIZAR CATEGORÍA (PUT)
@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def actualizar_categoria(
    category_id: int,
    categoria_actualizada: schemas.CategoryBase,
    db: Session = Depends(get_db)
) -> models.Category:
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría no existe.")
    
    # 🔒 Blindaje: Si el user_id es NULL, es del sistema y no se puede modificar
    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden modificar las categorías base del sistema.")
        
    categoria.name = categoria_actualizada.name
    categoria.type = categoria_actualizada.type
    
    db.commit()
    db.refresh(categoria)
    return categoria


# Ruta D: ELIMINAR CATEGORÍA (DELETE)
@router.delete("/{category_id}")
def eliminar_categoria(
    category_id: int,
    db: Session = Depends(get_db)
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría no existe.")
        
    # 🔒 Blindaje: Evitar borrar categorías globales
    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden eliminar las categorías base del sistema.")
    
    # 🔒 Verificar si tiene transacciones asociadas
    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar la categoría porque tiene transacciones asociadas."
        )
        
    db.delete(categoria)
    db.commit()
    return {"estado": "OK", "mensaje": f"Categoría con ID {category_id} eliminada exitosamente."}