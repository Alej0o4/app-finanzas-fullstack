"""Router de sobres virtuales (Fase 35). Delgado: la lógica vive en `app/services/funds.py`."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas
from app.services import funds as servicio

router = APIRouter()


def _ahora() -> datetime:
    return datetime.now(UTC)


@router.get("/", response_model=list[schemas.FundResponse])
def listar_sobres(
    include_archived: bool = Query(False, description="Incluye los sobres archivados"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.listar(db, current_user, _ahora(), include_archived)


@router.post("/", response_model=schemas.FundResponse)
def crear_sobre(
    datos: schemas.FundCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.crear(db, current_user, datos, _ahora())


@router.get("/{fund_id}", response_model=schemas.FundDetailResponse)
def obtener_sobre(fund_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.detalle(db, current_user, fund_id, _ahora())


@router.put("/{fund_id}", response_model=schemas.FundResponse)
def actualizar_sobre(
    fund_id: int,
    datos: schemas.FundUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.actualizar(db, current_user, fund_id, datos, _ahora())


@router.delete("/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_sobre(fund_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    servicio.eliminar(db, current_user, fund_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{fund_id}/contributions", response_model=schemas.FundEntryResponse)
def aportar(
    fund_id: int,
    datos: schemas.FundMovement,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.registrar_movimiento(db, current_user, fund_id, "contribution", datos.amount, datos.note, _ahora())


@router.post("/{fund_id}/withdrawals", response_model=schemas.FundEntryResponse)
def retirar(
    fund_id: int,
    datos: schemas.FundMovement,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.registrar_movimiento(db, current_user, fund_id, "withdrawal", datos.amount, datos.note, _ahora())


@router.post("/{fund_id}/archive", response_model=schemas.FundResponse)
def archivar_sobre(fund_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.archivar(db, current_user, fund_id, _ahora())


@router.post("/{fund_id}/unarchive", response_model=schemas.FundResponse)
def desarchivar_sobre(
    fund_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return servicio.desarchivar(db, current_user, fund_id, _ahora())
