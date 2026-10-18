"""Router de recurrentes (Fase 37). Delgado: la lógica vive en `app/services/recurring.py`.

El router es dueño del `commit`. Las rutas fijas (`/pending`, `/calendar`, `/suggestions`) se
declaran ANTES de `/{rule_id}`.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.budget_alerts import evaluate_budget_thresholds_safely
from app.core.database import get_db
from app.core.exceptions import DomainError, InternalServerError, ValidationError
from app.core.security import get_current_user
from app.core.timezones import get_zoneinfo
from app.models import models
from app.schemas import schemas
from app.services import recurring as servicio

router = APIRouter()
logger = logging.getLogger(__name__)


def _ahora() -> datetime:
    return datetime.now(UTC)


@router.get("/", response_model=list[schemas.RecurringResponse])
def listar_reglas(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.listar(db, current_user, _ahora())


@router.post("/", response_model=schemas.RecurringResponse)
def crear_regla(
    datos: schemas.RecurringCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    respuesta = servicio.crear(db, current_user, datos, _ahora())
    db.commit()
    return respuesta


@router.get("/pending", response_model=list[schemas.PendingOccurrenceResponse])
def listar_pendientes(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.pendientes(db, current_user, _ahora())


@router.get("/calendar", response_model=schemas.CalendarResponse)
def calendario(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.calendario(db, current_user, _ahora())


@router.get("/suggestions", response_model=list[schemas.SuggestionResponse])
def sugerencias(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return servicio.sugerencias(db, current_user, _ahora())


@router.put("/{rule_id}", response_model=schemas.RecurringResponse)
def actualizar_regla(
    rule_id: int,
    datos: schemas.RecurringUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    respuesta = servicio.actualizar(db, current_user, rule_id, datos, _ahora())
    db.commit()
    return respuesta


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_regla(rule_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    servicio.eliminar(db, current_user, rule_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{rule_id}/confirm", response_model=schemas.TransactionResponse)
def confirmar_ocurrencia(
    rule_id: int,
    datos: schemas.RecurringConfirm,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        transaccion = servicio.confirmar(db, current_user, rule_id, datos.occurrence_date, datos.amount, _ahora())
        db.commit()
        db.refresh(transaccion)
    except DomainError:
        db.rollback()
        raise
    except DataError:
        # Mismo caso que `crear_transaccion` (QA-015): el UPDATE de `Account.balance` desborda.
        db.rollback()
        raise ValidationError("La operación dejaría el saldo de la cuenta fuera del rango permitido.") from None
    except Exception:
        db.rollback()
        logger.exception("Error al confirmar la regla recurrente %s del usuario %s", rule_id, current_user.id)
        raise InternalServerError("Error interno al procesar la transacción contable.") from None

    # Mismo hook que `crear_transaccion` (Decisión 13.3.4): un fallo del motor de presupuestos
    # nunca revierte lo ya confirmado.
    if transaccion.type == "expense":
        evaluate_budget_thresholds_safely(
            db,
            current_user.id,
            transaccion.category_id,
            transaccion.date,
            f"confirmar recurrente {rule_id} (transacción {transaccion.id}) del usuario {current_user.id}",
            get_zoneinfo(current_user.timezone),
        )
    return transaccion


@router.post("/{rule_id}/skip", response_model=schemas.RecurringResponse)
def saltar_ocurrencia(
    rule_id: int,
    datos: schemas.RecurringSkip,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    respuesta = servicio.saltar(db, current_user, rule_id, datos.occurrence_date, _ahora())
    db.commit()
    return respuesta
