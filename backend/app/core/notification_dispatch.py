"""Helper compartido de notificación/push (Fase 14 §14.2, Decisión 14.2.1).

Extraído de `budget_alerts.py` (que era, de facto, utilidades compartidas disfrazadas de
módulo de un solo propósito — `dashboard.py` ya importaba `spent_por_categoria_y_moneda` de
ahí). Ahora tanto el motor de presupuestos (Fase 13) como el resumen semanal (Fase 14)
persisten avisos en `notifications` y disparan el push sobre la misma fila.
"""

import json
import logging
import os

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.models import models

logger = logging.getLogger(__name__)


def crear_y_enviar_notificacion(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    body: str,
    budget_id: int | None = None,
    period_key: str | None = None,
) -> models.Notification:
    """Persiste el aviso en la bandeja in-app y dispara el push sobre la misma fila
    (Decisión 13.2.3, ahora compartida entre el motor de presupuestos y el resumen
    semanal). Un fallo aquí es un fallo del caller — este helper no atrapa excepciones
    de escritura en `notifications`, solo las de envío push (ver `enviar_push`)."""
    notificacion = models.Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        budget_id=budget_id,
        period_key=period_key,
    )
    db.add(notificacion)
    db.commit()
    enviar_push(db, notificacion)
    return notificacion


def enviar_push(db: Session, notificacion: models.Notification) -> None:
    """Envía el aviso por Web Push a todas las suscripciones del usuario.

    Fallo silencioso con log si VAPID no está configurado (mismo criterio que
    `app/core/email.py` con SMTP): NUNCA debe romper la creación de transacciones —
    el aviso ya quedó en la bandeja in-app y el push es un canal adicional.
    Cada suscripción se envuelve en su propio try/except (Decisión 13.2.3): una
    suscripción caducada (WebPushException 404/410) se borra y se continúa con las
    demás; el resto de fallos solo se loguean.
    """
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    private_key = os.getenv("VAPID_PRIVATE_KEY")
    subject = os.getenv("VAPID_SUBJECT")
    if not public_key or not private_key or not subject:
        logger.warning(
            "VAPID no configurado (faltan VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY/VAPID_SUBJECT) — "
            "push no enviado; el aviso queda en la bandeja in-app"
        )
        return

    suscripciones = (
        db.query(models.PushSubscription).filter(models.PushSubscription.user_id == notificacion.user_id).all()
    )
    if not suscripciones:
        return

    # Fase 14 (§14.5): el push deep-linkea al destino según el tipo de aviso. Las
    # alertas de presupuesto (Fase 13) apuntan a /budgets; el resumen semanal al home.
    url = "/budgets" if notificacion.type != "weekly_summary" else "/"

    payload = json.dumps(
        {
            "title": notificacion.title,
            "body": notificacion.body,
            "budget_id": notificacion.budget_id,
            "url": url,
        }
    )

    for suscripcion in suscripciones:
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {"p256dh": suscripcion.p256dh_key, "auth": suscripcion.auth_key},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                # El push es un canal adicional, best-effort, sobre un request que ya
                # confirmó el movimiento contable (Decisión 13.2.3) — un push service lento
                # o colgado no debe demorar la respuesta HTTP indefinidamente.
                timeout=5,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                # Suscripción caducada/revocada por el navegador: se limpia esa fila
                # específica y se sigue con las demás (Decisión 13.2.3).
                logger.warning(
                    "Suscripción push %s eliminada por respuesta %s del push service",
                    suscripcion.id,
                    status,
                )
                db.delete(suscripcion)
                db.commit()
            else:
                logger.exception("Error WebPush al enviar a la suscripción %s", suscripcion.id)
        except Exception:
            logger.exception("Error al enviar push a la suscripción %s", suscripcion.id)
