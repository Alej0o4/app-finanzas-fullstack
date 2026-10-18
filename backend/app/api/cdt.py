"""Router de CDT (Fase 38). Delgado: la lógica vive en `app/services/cdt.py`.

El router es dueño del `commit`. Un CDT no toca cuentas, transacciones ni `ledger.py` (D1).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas
from app.services import cdt as servicio

router = APIRouter()


def _ahora() -> datetime:
    return datetime.now(UTC)


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
    respuesta = servicio.redimir(db, current_user, cdt_id, datos, _ahora())
    db.commit()
    return respuesta


@router.delete("/{cdt_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cdt(cdt_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    servicio.eliminar(db, current_user, cdt_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
