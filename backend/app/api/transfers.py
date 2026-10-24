"""Router de transferencias (Fase 39). Delgado: la lógica vive en `app/services/transfers.py`.

El router es dueño del `commit`. Una transferencia no es flujo: no toca transacciones ni KPI (D1).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.periods import RANGO_DESC
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas
from app.services import transfers as servicio

router = APIRouter()

_MSG_DESBORDE = "La operación dejaría el saldo de la cuenta fuera del rango permitido."


def _ahora() -> datetime:
    return datetime.now(UTC)


@router.get("/", response_model=schemas.PaginatedResponse[schemas.TransferResponse])
def listar_transferencias(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    account_id: int | None = Query(None, description="Origen o destino"),
    start_date: str | None = Query(None, description=RANGO_DESC),
    end_date: str | None = Query(None, description=RANGO_DESC),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    items, total = servicio.listar(
        db, current_user, account_id=account_id, start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )
    return schemas.PaginatedResponse(items=items, total=total, page=(skip // limit) + 1, page_size=limit)


@router.post("/", response_model=schemas.TransferResponse)
def crear_transferencia(
    datos: schemas.TransferCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        respuesta = servicio.crear(db, current_user, datos, _ahora())
        db.commit()
    except DataError:
        db.rollback()
        raise ValidationError(_MSG_DESBORDE) from None
    return respuesta


@router.get("/{transfer_id}", response_model=schemas.TransferResponse)
def obtener_transferencia(
    transfer_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return servicio.detalle(db, current_user, transfer_id)


@router.put("/{transfer_id}", response_model=schemas.TransferResponse)
def actualizar_transferencia(
    transfer_id: int,
    datos: schemas.TransferUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        respuesta = servicio.actualizar(db, current_user, transfer_id, datos, _ahora())
        db.commit()
    except DataError:
        db.rollback()
        raise ValidationError(_MSG_DESBORDE) from None
    return respuesta


@router.delete("/{transfer_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_transferencia(
    transfer_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    try:
        servicio.eliminar(db, current_user, transfer_id)
        db.commit()
    except DataError:
        db.rollback()
        raise ValidationError(_MSG_DESBORDE) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
