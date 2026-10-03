from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import get_current_user
from app.core.text import normalizar_nombre
from app.models import models
from app.schemas import schemas

router = APIRouter()


def _esta_oculta(db: Session, user_id: int, category_id: int) -> bool:
    """Fase 18 (§18.3, Decisión Q1/Q4): una categoría está "oculta" si existe una fila en
    `hidden_categories` para el par (user_id, category_id). El flag es por usuario y NO se
    persiste en `Category` — se computa en cada lectura."""
    return db.query(models.HiddenCategory).filter_by(user_id=user_id, category_id=category_id).first() is not None


def _rechazar_nombre_duplicado(
    db: Session, user_id: int, nombre: str, tipo: str, excluir_categoria_id: int | None = None
) -> None:
    """400 si el usuario ya tiene OTRA categoría activa con el mismo nombre normalizado y
    el mismo `type` (QA-028).

    El ámbito (por usuario, por `type`, entre activas) no es arbitrario: es exactamente el
    del resolver por nombre de Fase 16 §16.2 (`_resolver_categoria_por_nombre`), que da
    `409` ("Tenés más de una categoría propia llamada 'X'") cuando encuentra dos propias que
    matchean. El fix va donde el bug se manifiesta —crear/editar una categoría que ya no se
    puede resolver sin ambigüedad— en vez de dejar que el 409 aparezca más tarde, en la
    captura de una transacción. La comparación es la MISMA (`normalizar_nombre`, shared con
    el resolver): sin acentos, sin mayúsculas y sin espacios.

    - Solo categorías PROPIAS: las de sistema (`user_id IS NULL`) no bloquean, porque el
      resolver prioriza la propia del usuario sobre la de sistema (Decisión 16.2.2) — crear
      una propia "Mercado" es un caso soportado, no un conflicto.
    - Solo activas: el filtro global de borrado lógico (`core/database.py`) ya saca las
      soft-deleted de esta query, así que borrar una categoría libera su nombre (test
      `test_categoria_borrada_no_bloquea_el_nombre`).
    - Sin restricción equivalente en DB, a propósito: es la misma política que el pre-chequeo
      de duplicados de presupuestos en `api/budgets.py:51` — `400` de dominio en la API,
      nada de índice único (que además obligaría a una migración y a decidir qué hacer con
      las filas que ya están duplicadas).

    `excluir_categoria_id` saca del chequeo a la categoría que se está editando, para que
    reenviarle su propio nombre sea un no-op y no un 400 (mismo criterio que el guard de
    moneda de `actualizar_cuenta`, Fase 24 Decisión C2).
    """
    objetivo = normalizar_nombre(nombre)
    propias = (
        db.query(models.Category)
        .filter(
            models.Category.user_id == user_id,
            # `CategoryType` (schema) es un str Enum y `Category.type` es un str en la base:
            # comparar contra el string plano evita depender de que el driver sepa adaptar
            # el enum al bind param.
            models.Category.type == tipo,
        )
        .all()
    )
    duplicada = next(
        (c for c in propias if c.id != excluir_categoria_id and normalizar_nombre(c.name) == objetivo),
        None,
    )
    if duplicada is not None:
        raise BadRequestError(f"Ya existe una categoría de tipo {tipo} llamada '{nombre}'.")


@router.post("/", response_model=schemas.CategoryResponse)
def crear_categoria(
    categoria: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _rechazar_nombre_duplicado(db, current_user.id, categoria.name, categoria.type.value)
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
        raise NotFoundError("La categoría no existe o no tienes permisos.")

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
        raise NotFoundError("La categoría no existe o no tienes permisos.")

    if categoria.user_id is None:
        raise ForbiddenError("No se pueden modificar las categorías base del sistema.")

    # 🚨 QA-027: cambiar el `type` de una categoría con movimientos o presupuestos debajo
    # rompe la naturaleza del dato — después, "Comida" sería un ingreso y los presupuestos
    # de gastos apuntarían a una categoría de ingreso. Es válido lo que la Fase 31 decidió
    # (un reembolso es un `income` en una categoría de gasto, Q10), pero eso se decide AL
    # CREAR la transacción, no al mutar la categoría debajo de movimientos ya existentes.
    #
    # Las dos queries son las MISMAS de `eliminar_categoria` (y con el mismo criterio: el
    # filtro global de soft-delete deja fuera solo las activas). Editar el nombre, o guardar
    # el mismo `type`, NO dispara el chequeo — el guard es solo del cambio de tipo.
    #
    # El `409` es deliberado y NO es el mismo status de los guards de delete (que siguen en
    # `BadRequestError`, 400): son la misma clase de conflicto en el estado del dominio, así
    # que un cliente no debería tener que aprender dos códigos. Igualarlos está fuera del
    # alcance de este fix — cambiar los guards de delete tocaría su contrato documentado.
    if categoria_actualizada.type.value != categoria.type:
        tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).first()
        if tiene_transacciones:
            raise ConflictError("No se puede cambiar el tipo de una categoría con transacciones asociadas.")
        tiene_presupuestos = db.query(models.Budget).filter(models.Budget.category_id == category_id).first()
        if tiene_presupuestos:
            raise ConflictError(
                "No se puede cambiar el tipo de una categoría con presupuestos activos. Eliminá los presupuestos primero."
            )

    # QA-028: el nombre tiene que quedar único en el ámbito (usuario, `type`) — el mismo que
    # usa el resolver por nombre. Se valida contra el `type` RESULTANTE, que es el que queda
    # en la fila cuando el PUT además cambia el tipo; y la propia categoría queda excluida
    # para que reenviarle su nombre no se bloquee a sí misma.
    _rechazar_nombre_duplicado(
        db,
        current_user.id,
        categoria_actualizada.name,
        categoria_actualizada.type.value,
        excluir_categoria_id=categoria.id,
    )

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
        raise NotFoundError("La categoría no existe o no tienes permisos.")

    if categoria.user_id is None:
        raise ForbiddenError("No se pueden eliminar las categorías base del sistema.")

    tiene_transacciones = db.query(models.Transaction).filter(models.Transaction.category_id == category_id).first()
    if tiene_transacciones:
        raise BadRequestError("No se puede eliminar la categoría porque tiene transacciones asociadas.")

    tiene_presupuestos = db.query(models.Budget).filter(models.Budget.category_id == category_id).first()
    if tiene_presupuestos:
        raise BadRequestError(
            "No se puede eliminar la categoría porque tiene presupuestos activos. Elimínalos primero."
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
        raise NotFoundError("La categoría no existe o no tienes permisos.")
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
