"""Generación perezosa de presupuestos recurrentes (Fase 8 §3, Decisión 3.1).

Vive en `app/core/`, no en un router: tanto `budgets.py` como `dashboard.py` disparan
la misma lógica y ningún router importa otro router (mismo criterio que
`app/core/email.py` / `app/core/security.py`).
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Se importa con alias porque `ValidationError` también es el nombre de la excepción de
# Pydantic, y acá el dominio manda — mismo criterio que `core/periods.py`.
from app.core.exceptions import ValidationError as DomainValidationError
from app.models import models


def ensure_recurring_budgets_for_period(db: Session, user_id: int, month: int, year: int) -> None:
    """Genera, bajo demanda, las filas recurrentes pendientes para (month, year).

    Para cada categoría con una plantilla recurrente (`is_recurring=True`) que aún no
    tenga fila en el período pedido — ni activa ni borrada, ver abajo — clona la plantilla
    más reciente como nueva fila del período con `is_recurring=True` — así sigue generando
    los meses siguientes sin intervención. La plantilla siempre es "la fila recurrente más
    reciente": editar el monto del mes actual se convierte automáticamente en el monto de
    los futuros.

    **La fila soft-deleted del período es una lápida: borrarla saltea ese mes.** Es la
    decisión tomada para QA-024 (un presupuesto recurrente del mes en curso era
    imposible de borrar: al recargar la página reaparecía, porque la generación perezosa
    clonaba de nuevo la plantilla más reciente). Contar las filas borradas al decidir "esta
    categoría ya tiene fila en este período" las convierte en la marca explícita de un mes
    que el usuario decidió no presupuestar, sin columna nueva ni migración. Y como el
    filtro global de borrado lógico saca la fila borrada de `plantillas`, borrar un
    recurrente además deja de propagar su monto: la recurrencia sigue en los meses
    siguientes, pero desde la plantilla activa más reciente que quede (puede ser de un mes
    anterior). Borrar y volver a crear en el mismo período sigue siendo posible a mano
    (`POST /budgets/`): el índice único de `models.py` es parcial y solo mira filas activas,
    y la fila nueva vuelve a bloquear la generación por la misma regla.
    """
    # Defensa en profundidad del período (QA-023). El rango (`1..12` / `2020..2100`) está
    # declarado en `app/schemas/budgets.py::BudgetBase.month/year` —el schema de request,
    # la otra frontera donde este mismo dato entra— y también en el `Query` de
    # `api/budgets.py::obtener_presupuestos`. No se importa de acá porque `app/core/` no
    # importa `app/schemas/` (el sentido de la dependencia); son tres literales
    # deliberadamente duplicados y comentados.
    #
    # Los tres callers de esta función llegan con un período válido: `api/budgets.py`
    # (validado por el `Query`), `api/dashboard.py:221` (pasa por
    # `core/periods.resolver_mes`) y `core/budget_alerts.py:124` (deriva de la fecha de una
    # transacción, que siempre da un mes de 1 a 12). La guarda existe para que un caller
    # FUTURO no reintroduzca la basura de QA-023: un período inválido no es un período sin
    # budgetary, es un bug, y acá se clonarían filas que después ni se pueden serializar.
    #
    # Tradeoff honesto: si esta guarda saltara dentro de
    # `budget_alerts.evaluate_budget_thresholds_safely`, su `except Exception` +
    # `db.rollback()` la tragaría en silencio (mismo criterio que el docstring de
    # `rango_mes_utc` en `core/periods.py`) — el motor de alertas moriría sin avisar. Ese
    # camino no puede dispararla hoy, porque el período sale de la fecha de una transacción
    # y por lo tanto siempre cae en 1..12; si algún día el caller cambia, el síntoma sería
    # "dejaron de llegar avisos", no un 500 visible.
    if not 1 <= month <= 12 or not 2020 <= year <= 2100:
        raise DomainValidationError("`month` debe estar entre 1 y 12 y `year` entre 2020 y 2100.")

    # `plantillas`: la fila recurrente más reciente por categoría, de cualquier período
    # MENOS el pedido. Solo activas — el filtro global de borrado lógico de
    # `app/core/database.py` deja las soft-deleted afuera, que es justo lo que hace que la
    # lápida de abajo deje de ser plantilla (ver el docstring).
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

    # QA-024: el chequeo de "¿esta categoría ya tiene fila en este período?" tiene que
    # contar TAMBIÉN las soft-deleted, y por eso NO puede ser el `db.query(models.Budget.
    # category_id)` que había: el filtro global de borrado lógico de `app/core/database.py`
    # se aplica a toda consulta ORM-enabled y hacía que la fila borrada no bloqueara nada,
    # que es el bug (el presupuesto borrado reaparecía al recargar).
    #
    # Por qué `db.connection()` y no `db.execute(...)`: el evento `do_orm_execute` de
    # `app/core/database.py` inyecta el `with_loader_criteria` en lo que ve pasar por
    # `Session.execute`, y ese handler NO mira `execute_state.is_orm_statement` — se
    # aplica igual a un `select()` Core, porque el `Select` de SQLAlchemy 2.0.50 acepta
    # `.options()`. Verificado en esta versión: `db.execute(select(...))` compilaba con el
    # `AND deleted_at IS NULL` y la lápida seguía sin verse. `db.connection()` ejecuta el
    # MISMO `select()` tipado (con parámetros bindeados, sin SQL a mano) pero saltea el
    # evento, que está registrado sobre la clase `Session`. Es el mismo motivo por el que
    # `app/services/ledger.py` lleva su `deleted_at IS NULL` explícito en el `update()`
    # (Decisión 6.1).
    categorias_con_fila_o_lapida = {
        fila[0]
        for fila in db.connection()
        .execute(
            select(models.Budget.category_id).where(
                models.Budget.user_id == user_id,
                models.Budget.month == month,
                models.Budget.year == year,
            )
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
        if category_id not in categorias_con_fila_o_lapida
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
