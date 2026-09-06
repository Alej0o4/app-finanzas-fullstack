"""Cálculo y envío del resumen semanal automático (Fase 14 §14.3-§14.5).

Funciones puras de cálculo (`build_weekly_summary`) + el entry point que persiste y
envía (`run_weekly_summary_for_user`) + el job del scheduler que itera a todos los
usuarios elegibles (`run_weekly_summary_job`).

Decisiones clave:
- Semana = lunes 00:00 a domingo 23:59:59 en `America/Bogota` fijo (Decisión 14.3.1),
  no por usuario.
- Total y categoría principal SOLO en `preferred_currency` (Decisión 14.3.3); las otras
  monedas se ignoran (no se convierten, no se listan).
- Se envía SIEMPRE, incluso con $0 gastado (Decisión 14.3.4) — plantilla distinta.
- Delta vs semana anterior como porcentaje (`None` si la semana anterior fue 0,
  Decisión 14.3.5).
- Idempotencia por `(user_id, type, period_key)` garantizada por el índice único
  parcial de la DB (Decisión 14.1.2), no solo por chequeo de aplicación.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.notification_dispatch import crear_y_enviar_notificacion
from app.models import models

logger = logging.getLogger(__name__)

# Zona horaria fija de despliegue para el resumen semanal (Decisión 14.3.1) — coherente
# con los defaults actuales del producto (User.preferred_currency="COP", locale es-CO).
SUMMARY_TIMEZONE = ZoneInfo("America/Bogota")


def spent_por_categoria_y_moneda_en_rango(
    db: Session, user_id: int, start: datetime, end: datetime
) -> list[tuple[int, str, Decimal]]:
    """(category_id, currency, spent) para todo el gasto del usuario en [start, end].

    Mismo idioma de query que `budget_alerts.spent_por_categoria_y_moneda` (agrupar por
    category_id + currency, filtrar type == "expense") pero sin restringir category_ids
    de antemano — el resumen semanal no sabe qué categorías tuvieron gasto hasta
    calcularlo (Decisión 14.3.2).
    """
    rows = (
        db.query(
            models.Transaction.category_id,
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("spent"),
        )
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == "expense",
            models.Transaction.date >= start,
            models.Transaction.date <= end,
        )
        .group_by(models.Transaction.category_id, models.Transaction.currency)
        .all()
    )
    return [(r.category_id, r.currency, r.spent) for r in rows]


def _limites_semana(reference_date: datetime, tz) -> tuple[datetime, datetime]:
    """Lunes 00:00 a domingo 23:59:59 de la semana ISO que contiene `reference_date`.

    `reference_date` se convierte a la zona de despliegue y se trunca al día; a partir
    del `isocalendar()` (la semana lunes-domingo) se resta `weekday` días para llegar al
    lunes. Sin tzinfo en el resultado (solo la ventana de fechas), coherente con el resto
    del modelo `Transaction.date`.
    """
    ref = reference_date.astimezone(tz)
    weekday = ref.weekday()  # lunes = 0 ... domingo = 6
    lunes = datetime(ref.year, ref.month, ref.day) - timedelta(days=weekday)
    domingo = lunes + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return lunes, domingo


def build_weekly_summary(db: Session, user: models.User, reference_date: datetime) -> dict:
    """Calcula el resumen de la semana ISO que contiene `reference_date` (lunes-domingo,
    America/Bogota — Decisión 14.3.1). Pura función de cálculo, sin efectos secundarios —
    `run_weekly_summary_for_user` (más abajo) es quien persiste y envía."""
    tz = SUMMARY_TIMEZONE
    start, end = _limites_semana(reference_date, tz)  # lunes 00:00 - domingo 23:59:59
    start_prev, end_prev = _limites_semana(reference_date - timedelta(days=7), tz)

    moneda = user.preferred_currency or "COP"
    filas = spent_por_categoria_y_moneda_en_rango(db, user.id, start, end)
    filas_prev = spent_por_categoria_y_moneda_en_rango(db, user.id, start_prev, end_prev)

    total = sum((s for _, c, s in filas if c == moneda), Decimal("0.00"))
    total_prev = sum((s for _, c, s in filas_prev if c == moneda), Decimal("0.00"))

    categoria_principal_id = max(
        ((cat_id, s) for cat_id, c, s in filas if c == moneda), key=lambda x: x[1], default=(None, None)
    )[0]

    return {
        "period_key": start.strftime("%G-W%V"),  # semana ISO, p. ej. "2026-W37"
        "total": total,
        "currency": moneda,
        "categoria_principal_id": categoria_principal_id,
        "delta_pct": None if total_prev == 0 else float((total - total_prev) / total_prev * 100),
    }


def _categoria_nombre(db: Session, category_id: int | None) -> str:
    """Nombre de la categoría principal para el cuerpo del mensaje; "sin categoría" si no
    hay categoría principal (None) o si el nombre no se puede resolver. Una categoría
    borrada (soft-delete) conserva su fila, así que su nombre se resuelve igual."""
    if category_id is None:
        return "sin categoría"
    categoria = db.get(models.Category, category_id)
    return categoria.name if categoria is not None else "sin categoría"


def run_weekly_summary_for_user(db: Session, user: models.User, reference_date: datetime) -> None:
    """Construye el resumen de la semana de `reference_date` para `user`, persiste el
    aviso en la bandeja y dispara el push (Decisión 14.5.1, vía el helper compartido).

    La unicidad de la Decisión 14.1.2 hace que una segunda invocación para el mismo
    usuario/semana falle con `IntegrityError` en el `commit()` — se atrapa en el loop del
    scheduler (`run_weekly_summary_job`), siguiendo el mismo criterio que
    `ensure_recurring_budgets_for_period`."""
    resumen = build_weekly_summary(db, user, reference_date)
    if resumen["total"] == 0:
        title = "Tu resumen semanal"
        body = "Esta semana no registraste gastos — ¿todo tranquilo?"
    else:
        categoria = _categoria_nombre(db, resumen["categoria_principal_id"])
        delta_txt = "" if resumen["delta_pct"] is None else f" ({resumen['delta_pct']:+.0f}% vs. semana pasada)"
        title = "Tu resumen semanal"
        body = f"Gastaste {resumen['total']:,.2f} {resumen['currency']} — el mayor gasto fue en {categoria}{delta_txt}."

    crear_y_enviar_notificacion(
        db,
        user_id=user.id,
        type="weekly_summary",
        title=title,
        body=body,
        period_key=resumen["period_key"],
    )


def run_weekly_summary_job() -> None:
    """Entry point del scheduler — abre su propia sesión (no hay request HTTP del que
    tomarla, a diferencia del motor de alertas de Fase 13). Query batch (no loop de N+1)
    y commit por usuario dentro del loop: un fallo a mitad no revierte ni bloquea a los
    usuarios ya procesados (Decisión 14.4.3)."""
    db = SessionLocal()
    try:
        usuarios = (
            db.query(models.User)
            .filter(models.User.weekly_summary_enabled.is_(True), models.User.deleted_at.is_(None))
            .all()
        )
        ahora = datetime.now(UTC)
        for user in usuarios:
            try:
                run_weekly_summary_for_user(db, user, ahora)
            except IntegrityError:
                db.rollback()  # ya se envió esta semana para este usuario (Decisión 14.1.2) — no es un error
            except Exception:
                db.rollback()
                logger.exception("Error al generar el resumen semanal del usuario %s", user.id)
    finally:
        db.close()
