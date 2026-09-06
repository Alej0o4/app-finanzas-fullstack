"""Infraestructura de push web (Fase 13 §13.2).

Suscripciones Web Push autenticadas (upsert por `endpoint`) + clave VAPID pública.
El ENVÍO no vive aquí: se dispara desde `app/core/budget_alerts._crear_notificacion`
sobre la misma fila de `notifications` (Decisión 13.2.3) — el push es un canal
adicional sobre el aviso in-app, no un canal alternativo con su propio dato.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()


@router.get("/vapid-public-key")
def obtener_clave_vapid_publica():
    """Clave pública VAPID sin autenticación — por diseño del protocolo es pública, y el
    frontend la necesita antes de poder generar la suscripción (el prompt de push solo se
    muestra dentro del dashboard, de todos modos ya autenticado)."""
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    if not public_key:
        raise HTTPException(
            status_code=503,
            detail="VAPID no está configurado en el servidor. Agregá VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY/VAPID_SUBJECT al entorno.",
        )
    return {"public_key": public_key}


@router.post("/subscribe", response_model=schemas.PushSubscriptionResponse)
def suscribir(
    payload: schemas.PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Registra/actualiza una suscripción push del usuario autenticado (upsert por
    `endpoint`). Si el endpoint ya existe — re-registro del mismo navegador/dispositivo,
    incluso tras un cierre de sesión con otro usuario — se actualiza la fila en vez de
    duplicar (el estándar Web Push garantiza endpoint único por instalación)."""
    suscripcion = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()

    if suscripcion:
        suscripcion.user_id = current_user.id
        suscripcion.p256dh_key = payload.keys.p256dh
        suscripcion.auth_key = payload.keys.auth
    else:
        suscripcion = models.PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
        )
        db.add(suscripcion)

    db.commit()
    db.refresh(suscripcion)
    return suscripcion


@router.delete("/subscribe")
def desuscribir(
    payload: schemas.PushSubscriptionDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Elimina la suscripción push del usuario autenticado (desactiva notificaciones o el
    navegador invalidó la suscripción). Ownership check → 404, mismo criterio que el resto."""
    suscripcion = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()

    if not suscripcion or suscripcion.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="La suscripción no existe o no tienes permisos.")

    db.delete(suscripcion)
    db.commit()
    return {"estado": "OK", "mensaje": "Suscripción eliminada exitosamente."}
