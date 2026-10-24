"""Feed de movimientos (Fase 39 §B4): transacciones + transferencias en una sola lista paginada."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.periods import RANGO_DESC
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas
from app.schemas.transactions import TransactionType
from app.services import movements as servicio

router = APIRouter()


@router.get("/", response_model=schemas.MovementsResponse)
def listar_movimientos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    account_id: int | None = Query(None, description="Una transferencia aparece si la cuenta es origen o destino"),
    category_id: int | None = Query(None, description="Excluye las transferencias"),
    type: TransactionType | None = Query(None, description="income | expense; excluye las transferencias"),
    search: str | None = Query(None, max_length=100, description="Texto en la descripción; excluye las transferencias"),
    start_date: str | None = Query(None, description=RANGO_DESC),
    end_date: str | None = Query(None, description=RANGO_DESC),
    include_transfers: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return servicio.listar(
        db,
        current_user,
        account_id=account_id,
        category_id=category_id,
        tipo=type.value if type else None,
        busqueda=search,
        start_date=start_date,
        end_date=end_date,
        include_transfers=include_transfers,
        skip=skip,
        limit=limit,
    )
