import calendar
import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=schemas.DashboardSummary)
def obtener_resumen(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    preferred_currency = current_user.preferred_currency or "COP"

    # Contar cuentas destacadas
    highlighted_count = (
        db.query(models.Account)
        .filter(
            models.Account.user_id == current_user.id,
            models.Account.highlighted == True,  # noqa: E712
        )
        .count()
    )

    # Si hay destacadas, filtrar por ellas; si no, usar todas
    account_filter = [models.Account.user_id == current_user.id]
    if highlighted_count > 0:
        account_filter.append(models.Account.highlighted == True)  # noqa: E712

    # Agrupar saldos de cuentas por moneda
    balances_rows = (
        db.query(
            models.Account.currency,
            func.sum(models.Account.balance).label("total"),
        )
        .filter(
            *account_filter,
        )
        .group_by(models.Account.currency)
        .all()
    )

    hoy = datetime.now(UTC)
    primer_dia = datetime(hoy.year, hoy.month, 1)
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    ultimo_dia = datetime(hoy.year, hoy.month, ultimo_dia_mes, 23, 59, 59)

    # Transacciones del mes solo de cuentas destacadas (o todas si no hay)
    tx_account_ids = db.query(models.Account.id).filter(*account_filter).subquery()

    # Ingresos del mes agrupados por moneda
    income_rows = (
        db.query(
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("total"),
        )
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.type == "income",
            models.Transaction.account_id.in_(tx_account_ids),
            models.Transaction.date >= primer_dia,
            models.Transaction.date <= ultimo_dia,
        )
        .group_by(models.Transaction.currency)
        .all()
    )

    # Gastos del mes agrupados por moneda
    expense_rows = (
        db.query(
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("total"),
        )
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.type == "expense",
            models.Transaction.account_id.in_(tx_account_ids),
            models.Transaction.date >= primer_dia,
            models.Transaction.date <= ultimo_dia,
        )
        .group_by(models.Transaction.currency)
        .all()
    )

    # Ordenar: moneda preferida primero, luego alfabético
    def sort_key(currency: str) -> tuple[int, str]:
        return (0 if currency == preferred_currency else 1, currency)

    balances = [{"currency": r.currency, "total": r.total} for r in balances_rows]
    income = [{"currency": r.currency, "total": r.total} for r in income_rows]
    expense = [{"currency": r.currency, "total": r.total} for r in expense_rows]

    balances.sort(key=lambda x: sort_key(x["currency"]))
    income.sort(key=lambda x: sort_key(x["currency"]))
    expense.sort(key=lambda x: sort_key(x["currency"]))

    # Balance de flujo mensual (Fase 11 §11.3): ingreso mensual declarado por el usuario
    # menos el gasto del mes en su moneda preferida. None si el usuario no ha fijado
    # monthly_income todavía — el frontend debe distinguir "0" de "sin definir".
    monthly_flow_balance = None
    if current_user.monthly_income is not None:
        gasto_moneda_preferida = next(
            (item["total"] for item in expense if item["currency"] == preferred_currency),
            Decimal("0.00"),
        )
        monthly_flow_balance = current_user.monthly_income - gasto_moneda_preferida

    return {
        "balances": balances,
        "monthly_income_by_currency": income,
        "monthly_expense_by_currency": expense,
        "monthly_flow_balance": monthly_flow_balance,
    }


@router.get("/budgets-progress", response_model=list[schemas.BudgetProgress])
def obtener_progreso_presupuestos(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    hoy = datetime.now(UTC)
    primer_dia = datetime(hoy.year, hoy.month, 1)
    ultimo_dia = datetime(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1], 23, 59, 59)

    # El dashboard es la página de aterrizaje: genera aquí los presupuestos recurrentes
    # del mes en curso antes de consultarlos (Fase 8 §3, Decisión 3.1).
    ensure_recurring_budgets_for_period(db, current_user.id, hoy.month, hoy.year)

    presupuestos = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == current_user.id, models.Budget.month == hoy.month, models.Budget.year == hoy.year
        )
        .all()
    )

    if not presupuestos:
        return []

    category_ids = [p.category_id for p in presupuestos]

    spent_rows = (
        db.query(
            models.Transaction.category_id,
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("spent"),
        )
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.type == "expense",
            models.Transaction.category_id.in_(category_ids),
            models.Transaction.date >= primer_dia,
            models.Transaction.date <= ultimo_dia,
        )
        .group_by(models.Transaction.category_id, models.Transaction.currency)
        .all()
    )

    spent_map: dict[tuple[int, str], Decimal] = {(r.category_id, r.currency): r.spent for r in spent_rows}

    categorias = db.query(models.Category).filter(models.Category.id.in_(category_ids)).all()
    cat_info_map: dict[int, tuple[str, str | None]] = {c.id: (c.name, c.icon) for c in categorias}

    progreso_lista = []
    for presupuesto in presupuestos:
        gastado = spent_map.get((presupuesto.category_id, presupuesto.currency), Decimal("0.00"))
        porcentaje = float(gastado / presupuesto.amount_limit) * 100 if presupuesto.amount_limit > 0 else 0
        cat_name, cat_icon = cat_info_map.get(presupuesto.category_id, ("Desconocida", None))
        progreso_lista.append(
            {
                "budget_id": presupuesto.id,
                "category_name": cat_name,
                "category_icon": cat_icon,
                "amount_limit": presupuesto.amount_limit,
                "spent": gastado,
                "percentage": round(porcentaje, 2),
                "currency": presupuesto.currency,
            }
        )

    return progreso_lista


@router.get("/cashflow-series", response_model=list[schemas.CashflowData])
def obtener_serie_flujo_caja(
    start_date: datetime,
    end_date: datetime,
    period: str = Query("day", pattern="^(day|month)$", description="Agrupar por 'day' o 'month'"),
    currency: str | None = Query(None, description="Moneda a filtrar; por defecto la preferida del usuario"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filtro_moneda = currency or current_user.preferred_currency or "COP"
    try:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            pg_fmt = "YYYY-MM" if period == "month" else "YYYY-MM-DD"
            date_label = func.to_char(models.Transaction.date, pg_fmt).label("date_label")
        else:
            fmt = "%Y-%m" if period == "month" else "%Y-%m-%d"
            date_label = func.strftime(fmt, models.Transaction.date).label("date_label")

        rows = (
            db.query(
                date_label,
                func.sum(
                    case((models.Transaction.type == "income", models.Transaction.amount), else_=Decimal("0.00"))
                ).label("income"),
                func.sum(
                    case((models.Transaction.type == "expense", models.Transaction.amount), else_=Decimal("0.00"))
                ).label("expense"),
            )
            .filter(
                models.Transaction.user_id == current_user.id,
                models.Transaction.currency == filtro_moneda,
                models.Transaction.date >= start_date,
                models.Transaction.date <= end_date,
            )
            .group_by(date_label)
            .order_by(date_label)
            .all()
        )

        return [
            {"date_label": r.date_label, "income": r.income or Decimal("0.00"), "expense": r.expense or Decimal("0.00")}
            for r in rows
        ]
    except Exception:
        logger.exception("Error in cashflow-series")
        raise HTTPException(status_code=500, detail="Error al obtener serie de flujo de caja") from None


@router.get("/category-distribution", response_model=list[schemas.CategoryDistributionData])
def obtener_distribucion_categorias(
    start_date: datetime,
    end_date: datetime,
    type: str = Query("expense", pattern="^(income|expense)$", description="Filtrar por tipo de transacción"),
    neto: bool = Query(False, description="Si es True, calcula gasto neto (expense - income) por categoría"),
    currency: str | None = Query(None, description="Moneda a filtrar; por defecto la preferida del usuario"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filtro_moneda = currency or current_user.preferred_currency or "COP"
    if neto:
        sum_expense = func.sum(case((models.Transaction.type == "expense", models.Transaction.amount), else_=0))
        sum_income = func.sum(case((models.Transaction.type == "income", models.Transaction.amount), else_=0))
        net_total = sum_expense - sum_income

        rows = (
            db.query(
                models.Transaction.category_id,
                models.Category.name,
                net_total.label("total"),
            )
            .join(models.Category, models.Category.id == models.Transaction.category_id)
            .filter(
                models.Transaction.user_id == current_user.id,
                models.Transaction.currency == filtro_moneda,
                models.Transaction.date >= start_date,
                models.Transaction.date <= end_date,
            )
            .group_by(
                models.Transaction.category_id,
                models.Category.name,
            )
            .having(net_total > 0)
            .order_by(net_total.desc())
            .all()
        )
    else:
        rows = (
            db.query(
                models.Transaction.category_id,
                models.Category.name,
                func.sum(models.Transaction.amount).label("total"),
            )
            .join(models.Category, models.Category.id == models.Transaction.category_id)
            .filter(
                models.Transaction.user_id == current_user.id,
                models.Transaction.type == type,
                models.Transaction.currency == filtro_moneda,
                models.Transaction.date >= start_date,
                models.Transaction.date <= end_date,
            )
            .group_by(
                models.Transaction.category_id,
                models.Category.name,
            )
            .order_by(func.sum(models.Transaction.amount).desc())
            .all()
        )

    return [{"category_id": r.category_id, "category_name": r.name, "total": r.total} for r in rows]
