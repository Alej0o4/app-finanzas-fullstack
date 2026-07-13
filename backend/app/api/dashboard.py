from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timezone
from decimal import Decimal
import calendar
from typing import List

from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.core.security import get_current_user

router = APIRouter()

@router.get("/summary", response_model=schemas.DashboardSummary)
def obtener_resumen(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    total_balance = db.query(func.sum(models.Account.balance)).filter(
        models.Account.user_id == current_user.id
    ).scalar() or Decimal("0.00")  # 🔁 antes: 0.0

    hoy = datetime.now(timezone.utc)
    primer_dia = datetime(hoy.year, hoy.month, 1)
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    ultimo_dia = datetime(hoy.year, hoy.month, ultimo_dia_mes, 23, 59, 59)

    ingresos = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == "income",
        models.Transaction.date >= primer_dia,
        models.Transaction.date <= ultimo_dia
    ).scalar() or Decimal("0.00")  # 🔁 antes: 0.0

    gastos = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == "expense",
        models.Transaction.date >= primer_dia,
        models.Transaction.date <= ultimo_dia
    ).scalar() or Decimal("0.00")  # 🔁 antes: 0.0

    return {
        "total_balance": total_balance,
        "monthly_income": ingresos,
        "monthly_expense": gastos
    }


@router.get("/budgets-progress", response_model=List[schemas.BudgetProgress])
def obtener_progreso_presupuestos(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    hoy = datetime.now(timezone.utc)
    primer_dia = datetime(hoy.year, hoy.month, 1)
    ultimo_dia = datetime(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1], 23, 59, 59)

    presupuestos = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.month == hoy.month,
        models.Budget.year == hoy.year
    ).all()

    if not presupuestos:
        return []

    category_ids = [p.category_id for p in presupuestos]

    spent_rows = db.query(
        models.Transaction.category_id,
        func.sum(models.Transaction.amount).label("spent"),
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == "expense",
        models.Transaction.category_id.in_(category_ids),
        models.Transaction.date >= primer_dia,
        models.Transaction.date <= ultimo_dia,
    ).group_by(models.Transaction.category_id).all()

    spent_map: dict[int, Decimal] = {r.category_id: r.spent for r in spent_rows}

    categorias = db.query(models.Category).filter(models.Category.id.in_(category_ids)).all()
    cat_name_map: dict[int, str] = {c.id: c.name for c in categorias}

    progreso_lista = []
    for presupuesto in presupuestos:
        gastado = spent_map.get(presupuesto.category_id, Decimal("0.00"))
        porcentaje = float(gastado / presupuesto.amount_limit) * 100 if presupuesto.amount_limit > 0 else 0
        progreso_lista.append({
            "budget_id": presupuesto.id,
            "category_name": cat_name_map.get(presupuesto.category_id, "Desconocida"),
            "amount_limit": presupuesto.amount_limit,
            "spent": gastado,
            "percentage": round(porcentaje, 2),
        })

    return progreso_lista

@router.get("/cashflow-series", response_model=List[schemas.CashflowData])
def obtener_serie_flujo_caja(
    start_date: datetime,
    end_date: datetime,
    period: str = Query("day", pattern="^(day|month)$", description="Agrupar por 'day' o 'month'"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            pg_fmt = "YYYY-MM" if period == "month" else "YYYY-MM-DD"
            date_label = func.to_char(models.Transaction.date, pg_fmt).label("date_label")
        else:
            fmt = "%Y-%m" if period == "month" else "%Y-%m-%d"
            date_label = func.strftime(fmt, models.Transaction.date).label("date_label")

        rows = db.query(
            date_label,
            func.sum(case((models.Transaction.type == "income", models.Transaction.amount), else_=Decimal("0.00"))).label("income"),
            func.sum(case((models.Transaction.type == "expense", models.Transaction.amount), else_=Decimal("0.00"))).label("expense"),
        ).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        ).group_by(date_label).order_by(date_label).all()

        return [
            {"date_label": r.date_label, "income": r.income or Decimal("0.00"), "expense": r.expense or Decimal("0.00")}
            for r in rows
        ]
    except Exception as e:
        import logging
        logging.exception("Error in cashflow-series")
        raise HTTPException(status_code=500, detail=f"Error al obtener serie de flujo de caja: {str(e)}")


@router.get("/category-distribution", response_model=List[schemas.CategoryDistributionData])
def obtener_distribucion_categorias(
    start_date: datetime,
    end_date: datetime,
    type: str = Query("expense", pattern="^(income|expense)$", description="Filtrar por tipo de transacción"),
    neto: bool = Query(False, description="Si es True, calcula gasto neto (expense - income) por categoría"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if neto:
        sum_expense = func.sum(case((models.Transaction.type == "expense", models.Transaction.amount), else_=0))
        sum_income = func.sum(case((models.Transaction.type == "income", models.Transaction.amount), else_=0))
        net_total = sum_expense - sum_income

        rows = db.query(
            models.Transaction.category_id,
            models.Category.name,
            net_total.label("total"),
        ).join(
            models.Category, models.Category.id == models.Transaction.category_id
        ).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        ).group_by(
            models.Transaction.category_id,
            models.Category.name,
        ).having(net_total > 0).order_by(net_total.desc()).all()
    else:
        rows = db.query(
            models.Transaction.category_id,
            models.Category.name,
            func.sum(models.Transaction.amount).label("total"),
        ).join(
            models.Category, models.Category.id == models.Transaction.category_id
        ).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.type == type,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        ).group_by(
            models.Transaction.category_id,
            models.Category.name,
        ).order_by(func.sum(models.Transaction.amount).desc()).all()

    return [
        {"category_id": r.category_id, "category_name": r.name, "total": r.total}
        for r in rows
    ]