"""Bandeja de avisos in-app (Fase 13 §13.5).

Endpoints de lectura/estado sobre la tabla `notifications` — la escritura la hace el
motor de presupuestos (`app/core/budget_alerts.py`, §13.3) y, en el futuro, el resumen
semanal de Fase 14. Todos autenticados y sin rate limiting (hallazgo 7 del spec:
autenticados, sin vector de abuso nuevo — mismo criterio que budgets/dashboard).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.get("/", response_model=schemas.PaginatedResponse[schemas.NotificationResponse])
def listar_notificaciones(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Lista las notificaciones del usuario actual, más recientes primero (mismo patrón
    de paginación que GET /transactions). El badge de no leídas usa /unread-count aparte
    para no disparar la query de lista completa en cada poll corto (Decisión 13.5.4)."""
    query = db.query(models.Notification).filter(models.Notification.user_id == current_user.id)

    total = query.with_entities(func.count()).scalar()

    notificaciones = (
        query.order_by(desc(models.Notification.created_at), desc(models.Notification.id))
        .offset(skip)
        .limit(limit)
        .all()
    )

    page = (skip // limit) + 1 if limit > 0 else 1

    return schemas.PaginatedResponse(
        items=notificaciones,
        total=total,
        page=page,
        page_size=limit,
    )


@router.get("/unread-count", response_model=schemas.UnreadCountResponse)
def contar_no_leidas(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """`COUNT(*) WHERE user_id=? AND read_at IS NULL` — barata, cubierta por el índice
    compuesto `ix_notifications_user_id_created_at` (el endpoint que el frontend poll
    con `refetchInterval` corto, Decisión 13.5.4)."""
    count = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.read_at.is_(None),
        )
        .count()
    )
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=schemas.NotificationResponse)
def marcar_leida(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Marca una notificación como leída (`read_at = now()`). Ownership check → 404 si no
    es del usuario (mismo patrón que budgets/transactions, nunca 403)."""
    notificacion = db.query(models.Notification).filter(models.Notification.id == notification_id).first()

    if not notificacion or notificacion.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La notificación no existe o no tienes permisos.")

    notificacion.read_at = datetime.now(UTC)
    db.commit()
    db.refresh(notificacion)
    return notificacion


@router.patch("/read-all", response_model=schemas.UnreadCountResponse)
def marcar_todas_leidas(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Acción "marcar todo como leído" de la bandeja: pone `read_at` en todas las no
    leídas del usuario. Devuelve el nuevo conteo de no leídas (0)."""
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.read_at.is_(None),
    ).update({models.Notification.read_at: datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return {"count": 0}
