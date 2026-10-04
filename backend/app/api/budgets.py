from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.post("/", response_model=schemas.BudgetResponse)
def crear_presupuesto(
    presupuesto: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == presupuesto.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )
    if not categoria:
        raise NotFoundError("La categoría asignada no existe.")

    presupuesto_existente = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == current_user.id,
            models.Budget.category_id == presupuesto.category_id,
            models.Budget.month == presupuesto.month,
            models.Budget.year == presupuesto.year,
            # Fase 17 §17.2.5: la unicidad es por (categoría, mes, año) POR moneda —
            # sin este filtro el pre-chequeo rechazaría un segundo presupuesto en otra
            # moneda para el mismo período aunque el índice de la base ya lo permita.
            models.Budget.currency == presupuesto.currency,
        )
        .first()
    )

    if presupuesto_existente:
        raise BadRequestError("Ya existe un presupuesto para esta categoría, moneda, mes y año.")

    nuevo_presupuesto = models.Budget(**presupuesto.model_dump(), user_id=current_user.id)
    try:
        db.add(nuevo_presupuesto)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BadRequestError("Ya existe un presupuesto para esta categoría, moneda, mes y año.") from None
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto


@router.get("/", response_model=list[schemas.BudgetResponse])
def obtener_presupuestos(
    # Rangos copiados de `BudgetBase.month/year` (`app/schemas/budgets.py`), que es la
    # frontera donde el mismo dato entra por el body de POST/PUT. Aquí se repiten porque
    # acá también es entrada de usuario: `?month=13&year=99999` pasaba de largo, la
    # generación perezosa clonaba las plantillas recurrentes a ese período basura, y como
    # esas filas no se podían serializar (QA-023) el endpoint quedaba en 500 permanente —
    # la página de presupuestos, en skeleton eterno. Mismo criterio que `MAX_DIGITS_MONEY`
    # para el dinero: el límite se declara en el schema, no se deja que la base lo rechace.
    #
    # Por qué NO `core/periods.resolver_mes`, que es lo que usan los endpoints del
    # dashboard: es más estricto de lo que este endpoint necesita en dos puntos.
    #   (a) `resolver_mes` rechaza los meses FUTUROS, y el presupuesto anticipado es un
    #       caso válido: `core/budget_alerts.py` evalúa umbrales de meses futuros de
    #       presupuestos ya creados (se disparan con la fecha de la transacción).
    #   (b) `resolver_mes` exige mandar `year` y `month` juntos o ninguno. Este endpoint
    #       hoy tolera `month` solo o `year` solo, y los filtros son opcionales y
    #       combinables (`backend/docs/BUSINESS_RULES.md`, sección "Presupuestos"): se
    #       filtra por lo que venga y solo se genera cuando vienen los dos.
    month: int | None = Query(None, ge=1, le=12, description="Mes del período a listar, entre 1 y 12"),
    year: int | None = Query(None, ge=2020, le=2100, description="Año del período a listar"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Generación perezosa (Fase 8 §3): solo cuando el caller pide un período concreto.
    # Sin filtros se devuelve el historial completo sin generar nada nuevo — no hay un
    # período que "asegurar".
    if month is not None and year is not None:
        ensure_recurring_budgets_for_period(db, current_user.id, month, year)

    query = db.query(models.Budget).filter(models.Budget.user_id == current_user.id)

    if month is not None:
        query = query.filter(models.Budget.month == month)
    if year is not None:
        query = query.filter(models.Budget.year == year)

    return query.all()


@router.delete("/{budget_id}")
def eliminar_presupuesto(
    budget_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    presupuesto = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not presupuesto or presupuesto.user_id != current_user.id:
        raise NotFoundError("El presupuesto no existe o no tienes permisos.")

    presupuesto.deleted_at = datetime.now(UTC)
    db.commit()
    return {"estado": "OK", "mensaje": "Presupuesto eliminado exitosamente."}


@router.put("/{budget_id}", response_model=schemas.BudgetResponse)
def actualizar_presupuesto(
    budget_id: int,
    presupuesto_actualizado: schemas.BudgetBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Budget:
    presupuesto_db = (
        db.query(models.Budget).filter(models.Budget.id == budget_id, models.Budget.user_id == current_user.id).first()
    )

    if not presupuesto_db:
        raise NotFoundError("Presupuesto no encontrado.")

    # Validamos que la nueva categoría exista
    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == presupuesto_actualizado.category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )
    if not categoria:
        raise NotFoundError("La nueva categoría asignada no existe.")

    # Actualizamos los datos
    presupuesto_db.amount_limit = presupuesto_actualizado.amount_limit
    presupuesto_db.month = presupuesto_actualizado.month
    presupuesto_db.year = presupuesto_actualizado.year
    presupuesto_db.category_id = presupuesto_actualizado.category_id
    # Fase 17 §17.2.5: `currency` se asignaba en silencio desde Fase 11 pero el handler
    # nunca la aplicaba — mismo patrón de bug que AccountUpdate.currency (TODO.md).
    presupuesto_db.currency = presupuesto_actualizado.currency
    era_recurrente = presupuesto_db.is_recurring
    presupuesto_db.is_recurring = presupuesto_actualizado.is_recurring

    # Desmarcar "Repetir cada mes" (True → False) significa "de aquí en adelante no repitas":
    # las filas activas posteriores de la misma serie (categoría y moneda resultantes) dejan
    # de ser recurrentes, sin tocar montos. `deleted_at IS NULL` explícito: el filtro global
    # no aplica a `update()` en bloque (mismo criterio que `services/ledger.py`).
    if era_recurrente and not presupuesto_db.is_recurring:
        db.query(models.Budget).filter(
            models.Budget.user_id == current_user.id,
            models.Budget.category_id == presupuesto_db.category_id,
            models.Budget.currency == presupuesto_db.currency,
            models.Budget.deleted_at.is_(None),
            models.Budget.is_recurring.is_(True),
            (models.Budget.year > presupuesto_db.year)
            | ((models.Budget.year == presupuesto_db.year) & (models.Budget.month > presupuesto_db.month)),
        ).update({"is_recurring": False, "updated_at": datetime.now(UTC)}, synchronize_session=False)

    # Editar la moneda puede chocar con el índice único ensanchado (otro presupuesto
    # activo para la misma categoría/período en la moneda nueva) — sin este try/except
    # ese choque terminaría en un 500 no manejado (Fase 17 §17.2.5).
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BadRequestError("Ya existe un presupuesto para esta categoría, moneda, mes y año.") from None
    db.refresh(presupuesto_db)
    return presupuesto_db
