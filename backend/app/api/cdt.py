"""Router de CDT (Fase 38). Delgado: la lógica vive en `app/services/cdt.py`.

El router es dueño del `commit`. Un CDT solo toca cuentas si el dueño lo vincula (Fase 39): la
constitución/redención son transferencias y el interés realizado un ingreso "Rendimientos".
"""

from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas
from app.services import cdt as servicio

router = APIRouter()


def _ahora() -> datetime:
    return datetime.now(UTC)


@contextmanager
def _sin_desborde(db: Session):
    """Un desborde de `Numeric(14,2)` en el saldo de la cuenta vinculada es 422, no 500."""
    try:
        yield
    except DataError:
        db.rollback()
        raise ValidationError("La operación dejaría el saldo de la cuenta fuera del rango permitido.") from None


@router.get("/", response_model=schemas.CdtListResponse)
def listar_cdts(
    estado: schemas.CdtStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.listar(db, current_user, _ahora(), estado.value if estado else None)


@router.post("/", response_model=schemas.CdtResponse)
def crear_cdt(
    datos: schemas.CdtCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    with _sin_desborde(db):
        respuesta = servicio.crear(db, current_user, datos, _ahora())
        db.commit()
    return respuesta


@router.put("/{cdt_id}", response_model=schemas.CdtResponse)
def actualizar_cdt(
    cdt_id: int,
    datos: schemas.CdtUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    with _sin_desborde(db):
        respuesta = servicio.actualizar(db, current_user, cdt_id, datos, _ahora())
        db.commit()
    return respuesta


@router.post("/{cdt_id}/redeem", response_model=schemas.CdtResponse)
def redimir_cdt(
    cdt_id: int,
    datos: schemas.CdtRedeem,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    with _sin_desborde(db):
        respuesta = servicio.redimir(db, current_user, cdt_id, datos, _ahora())
        db.commit()
    return respuesta


@router.delete("/{cdt_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cdt(cdt_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    with _sin_desborde(db):
        servicio.eliminar(db, current_user, cdt_id)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
