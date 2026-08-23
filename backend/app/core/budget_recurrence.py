"""Generación perezosa de presupuestos recurrentes (Fase 8 §3, Decisión 3.1).

Vive en `app/core/`, no en un router: tanto `budgets.py` como `dashboard.py` disparan
la misma lógica y ningún router importa otro router (mismo criterio que
`app/core/email.py` / `app/core/security.py`).
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import models


def ensure_recurring_budgets_for_period(db: Session, user_id: int, month: int, year: int) -> None:
    """Genera, bajo demanda, las filas recurrentes pendientes para (month, year).

    Para cada categoría con una plantilla recurrente (`is_recurring=True`) que aún no
    tenga fila en el período pedido, clona la plantilla más reciente como nueva fila del
    período con `is_recurring=True` — así sigue generando los meses siguientes sin
    intervención. La plantilla siempre es "la fila recurrente más reciente": editar el
    monto del mes actual se convierte automáticamente en el monto de los futuros.
    """
    plantillas = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.is_recurring == True,  # noqa: E712
            (models.Budget.month != month) | (models.Budget.year != year),
        )
        .all()
    )
    if not plantillas:
        return

    mas_reciente_por_categoria: dict[int, models.Budget] = {}
    for presupuesto in sorted(plantillas, key=lambda p: (p.year, p.month), reverse=True):
        mas_reciente_por_categoria.setdefault(presupuesto.category_id, presupuesto)

    categorias_con_fila = {
        fila[0]
        for fila in db.query(models.Budget.category_id)
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.month == month,
            models.Budget.year == year,
        )
        .all()
    }

    nuevos = [
        models.Budget(
            amount_limit=plantilla.amount_limit,
            currency=plantilla.currency,
            month=month,
            year=year,
            is_recurring=True,
            user_id=user_id,
            category_id=category_id,
        )
        for category_id, plantilla in mas_reciente_por_categoria.items()
        if category_id not in categorias_con_fila
    ]
    if not nuevos:
        return

    try:
        db.add_all(nuevos)
        db.commit()
    except IntegrityError:
        # Carrera concurrente: otra petición generó primero la misma fila. El índice
        # único parcial resuelve sin duplicados; descartamos nuestro lote completo y
        # seguimos — la query posterior del endpoint ve las filas que dejó la ganadora.
        db.rollback()
