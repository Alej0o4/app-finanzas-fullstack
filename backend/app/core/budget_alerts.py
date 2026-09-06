"""Motor de evaluación de umbrales de presupuesto (Fase 13 §13.3).

Se invoca después de confirmar el movimiento contable de una transacción de tipo
"expense" (crear o actualizar). Reutiliza exactamente el mismo cálculo de `spent` que
`dashboard.obtener_progreso_presupuestos` (agrupado por currency, Fase 11 §11.1) para
no reintroducir el bug de mezclar monedas que ya se corrigió una vez ahí.
"""

import logging
from calendar import monthrange
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.core.notification_dispatch import crear_y_enviar_notificacion
from app.models import models

logger = logging.getLogger(__name__)

# (umbral %, tipo de aviso, plantilla de título). Orden deliberado: 100 antes que 80 —
# si una sola transacción cruza ambos umbrales de una pasada, se notifica el más grave
# y el `break` del loop evita el ruido de dos avisos simultáneos (Decisión 13.3.2).
THRESHOLDS = [
    (100, "budget_threshold_100", "Superaste tu presupuesto de {category}"),
    (80, "budget_threshold_80", "Vas en el 80% de tu presupuesto de {category}"),
]


def spent_por_categoria_y_moneda(
    db: Session, user_id: int, category_ids: list[int], month: int, year: int
) -> dict[tuple[int, str], Decimal]:
    """Gasto del período agrupado por `(category_id, currency)` — Fase 11 §11.1.

    Fuente única de "cuánto gasté" para presupuestos: lo usa tanto
    `dashboard.obtener_progreso_presupuestos` (lectura) como
    `evaluate_budget_thresholds_for_category` (escritura de avisos). El motor de
    alertas NO recalcula el gasto de otra forma para no divergir del dashboard.
    """
    primer_dia = datetime(year, month, 1)
    ultimo_dia = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)

    spent_rows = (
        db.query(
            models.Transaction.category_id,
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("spent"),
        )
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == "expense",
            models.Transaction.category_id.in_(category_ids),
            models.Transaction.date >= primer_dia,
            models.Transaction.date <= ultimo_dia,
        )
        .group_by(models.Transaction.category_id, models.Transaction.currency)
        .all()
    )

    return {(r.category_id, r.currency): r.spent for r in spent_rows}


def _spent_for_budget(db: Session, presupuesto: models.Budget) -> Decimal:
    """`spent` del presupuesto filtrado por su propia moneda (hallazgo 5 del spec).

    Dos presupuestos de la misma categoría en monedas distintas evalúan cada uno con
    su propio `spent` — la agrupación por `(category_id, currency)` de
    `spent_por_categoria_y_moneda` ya separa las monedas; aquí se descarta la que no
    corresponde al presupuesto.
    """
    spent_map = spent_por_categoria_y_moneda(
        db, presupuesto.user_id, [presupuesto.category_id], presupuesto.month, presupuesto.year
    )
    return spent_map.get((presupuesto.category_id, presupuesto.currency), Decimal("0.00"))


def evaluate_budget_thresholds_safely(
    db: Session, user_id: int, category_id: int, fecha: datetime, contexto: str
) -> None:
    """Envuelve `evaluate_budget_thresholds_for_category` en su propio try/except + rollback
    (Decisión 13.3.4): un fallo del motor nunca debe tumbar el request que ya confirmó el
    movimiento contable. El rollback es necesario, no cosmético — sin él, una excepción a
    mitad de camino (p. ej. el `IntegrityError` del índice único de `notifications` bajo
    carrera) deja la sesión en estado de transacción abortada, y una evaluación posterior en
    el mismo request (la categoría de origen tras reclasificar un gasto) fallaría también.
    Único punto de llamada al motor desde los routers — evita que crear/actualizar
    transacción diverjan en cómo manejan sus propios fallos."""
    try:
        evaluate_budget_thresholds_for_category(db, user_id, category_id, fecha.month, fecha.year)
    except Exception:
        db.rollback()
        logger.exception("Error al evaluar umbrales de presupuesto (%s)", contexto)


def evaluate_budget_thresholds_for_category(db: Session, user_id: int, category_id: int, month: int, year: int) -> None:
    """Evalúa si el gasto de (usuario, categoría, período) cruzó un umbral y, de ser así,
    persiste el aviso en `notifications` (una sola vez por umbral y período — Decisión
    13.3.2: unicidad garantizada por índice único parcial, no solo por este chequeo)."""
    # Decisión 13.3.3 (hallazgo 6): si el usuario registra un gasto el primer día de un
    # mes nuevo antes de abrir el dashboard, la fila recurrente de ese mes no existe —
    # sin este paso el aviso de ese mes nunca se dispararía hasta visitar el dashboard.
    ensure_recurring_budgets_for_period(db, user_id, month, year)

    presupuesto = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.category_id == category_id,
            models.Budget.month == month,
            models.Budget.year == year,
        )
        .first()
    )
    if not presupuesto or presupuesto.amount_limit <= 0:
        return  # sin presupuesto para esta categoría/período, nada que evaluar

    gastado = _spent_for_budget(db, presupuesto)  # mismo query pattern que dashboard.py
    porcentaje = float(gastado / presupuesto.amount_limit) * 100

    for umbral, tipo, plantilla_titulo in THRESHOLDS:
        if porcentaje < umbral:
            continue
        ya_existe = (
            db.query(models.Notification)
            .filter(models.Notification.budget_id == presupuesto.id, models.Notification.type == tipo)
            .first()
        )
        if ya_existe:
            break  # este umbral ya se avisó en este período — tampoco evaluar los menores
        _crear_notificacion(db, presupuesto, tipo, plantilla_titulo, porcentaje)
        break  # si ya cruzó el 100%, no evaluar también el 80% en la misma pasada


def _crear_notificacion(
    db: Session, presupuesto: models.Budget, tipo: str, plantilla_titulo: str, porcentaje: float
) -> models.Notification:
    """Persiste el aviso en la bandeja in-app y dispara el push sobre la misma fila.

    La persistencia y el push viven en `app.core.notification_dispatch` (Decisión
    14.2.1, compartido con el resumen semanal de Fase 14). Un fallo aquí es un fallo
    del motor — el caller lo envuelve en su propio try/except (Decisión 13.3.4) y la
    transacción contable ya fue confirmada antes."""
    nombre_categoria = presupuesto.category.name if presupuesto.category else "sin categoría"
    titulo = plantilla_titulo.format(category=nombre_categoria)
    body = (
        f"Ya vas por el {porcentaje:.0f}% del presupuesto de {nombre_categoria} "
        f"(límite {presupuesto.amount_limit:,.2f} {presupuesto.currency})."
    )
    return crear_y_enviar_notificacion(
        db,
        user_id=presupuesto.user_id,
        type=tipo,
        title=titulo,
        body=body,
        budget_id=presupuesto.id,
    )
