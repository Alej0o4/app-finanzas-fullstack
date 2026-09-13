from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


def _esta_oculta(db: Session, user_id: int, category_id: int) -> bool:
    """Fase 18 (§18.3, Decisión Q1/Q4): una categoría está "oculta" si existe una fila en
    `hidden_categories` para el par (user_id, category_id). El flag es por usuario y NO se
    persiste en `Category` — se computa en cada lectura."""
    return db.query(models.HiddenCategory).filter_by(user_id=user_id, category_id=category_id).first() is not None


@router.post("/", response_model=schemas.CategoryResponse)
def crear_categoria(
    categoria: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    nueva_categoria = models.Category(**categoria.model_dump(), user_id=current_user.id)
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    # Fase 18 (Decisión 18.3.2): una categoría recién creada nunca puede estar ya oculta —
    # is_hidden=False sin query extra, construido explícito (no vía default de Pydantic).
    return schemas.CategoryResponse(
        id=nueva_categoria.id,
        name=nueva_categoria.name,
        type=nueva_categoria.type,
        user_id=nueva_categoria.user_id,
        icon=nueva_categoria.icon,
        is_hidden=False,
    )


@router.get("/", response_model=list[schemas.CategoryResponse])
def obtener_categorias(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    categorias = (
        db.query(models.Category)
        .filter(or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id))
        .all()
    )
    # Fase 18 (Decisión 18.3.2): el set de ocultas del usuario se recolecta en UNA query,
    # no una por categoría.
    ocultas_ids = {
        row.category_id
        for row in db.query(models.HiddenCategory.category_id)
        .filter(models.HiddenCategory.user_id == current_user.id)
        .all()
    }
    return [
        schemas.CategoryResponse(
            id=c.id,
            name=c.name,
            type=c.type,
            user_id=c.user_id,
            icon=c.icon,
            is_hidden=c.id in ocultas_ids,
        )
        for c in categorias
    ]


@router.get("/{category_id}", response_model=schemas.CategoryResponse)
def obtener_categoria(
    category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()

    # Las categorías del sistema tienen user_id NULL y deben ser visibles para todos.
    if not categoria or (categoria.user_id is not None and categoria.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")

    return schemas.CategoryResponse(
        id=categoria.id,
        name=categoria.name,
        type=categoria.type,
        user_id=categoria.user_id,
        icon=categoria.icon,
        is_hidden=_esta_oculta(db, current_user.id, categoria.id),
    )


@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def actualizar_categoria(
    category_id: int,
    categoria_actualizada: schemas.CategoryBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()

    if not categoria or (categoria.user_id != current_user.id and categoria.user_id is not None):
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")

    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden modificar las categorías base del sistema.")

    categoria.name = categoria_actualizada.name
    categoria.type = categoria_actualizada.type

    db.commit()
    db.refresh(categoria)
    return schemas.CategoryResponse(
        id=categoria.id,
        name=categoria.name,
        type=categoria.type,
        user_id=categoria.user_id,
        icon=categoria.icon,
        is_hidden=_esta_oculta(db, current_user.id, categoria.id),
    )


@router.delete("/{category_id}")
def eliminar_categoria(
    category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    categoria = db.query(models.Category).filter(models.Category.id == category_id).first()

    if not categoria or (categoria.user_id != current_user.id and categoria.user_id is not None):
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")

    if categoria.user_id is None:
        raise HTTPException(status_code=403, detail="No se pueden eliminar las categorías base del sistema.")

    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).first()
    if tiene_transacciones:
        raise HTTPException(
            status_code=400, detail="No se puede eliminar la categoría porque tiene transacciones asociadas."
        )

    tiene_presupuestos = db.query(models.Budget).filter(models.Budget.category_id == category_id).first()
    if tiene_presupuestos:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar la categoría porque tiene presupuestos activos. Elimínalos primero.",
        )

    categoria.deleted_at = datetime.now(UTC)
    db.commit()
    return {"estado": "OK", "mensaje": "Categoría eliminada exitosamente."}


@router.post("/{category_id}/hide", status_code=204)
def ocultar_categoria(
    category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Fase 18 (§18.3.3, Decisión 18.3.4): marca "oculta para mí" una categoría propia o de
    sistema. Idempotente: la PK compuesta de `hidden_categories` garantiza una sola fila por
    par, y el guard `if not _esta_oculta(...)` evita el IntegrityError del duplicado."""
    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")
    if not _esta_oculta(db, current_user.id, category_id):
        db.add(models.HiddenCategory(user_id=current_user.id, category_id=category_id))
        db.commit()


@router.delete("/{category_id}/hide", status_code=204)
def mostrar_categoria(
    category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Fase 18 (§18.3.3): des-oculta. Idempotente y no-op si no había fila — el DELETE sin
    condición previa cubre ambos casos."""
    db.query(models.HiddenCategory).filter_by(user_id=current_user.id, category_id=category_id).delete()
    db.commit()
