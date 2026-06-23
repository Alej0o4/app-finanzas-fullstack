from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal  # 🔁 nuevo import
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

    hoy = datetime.utcnow()
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
    hoy = datetime.utcnow()
    
    presupuestos = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.month == hoy.month,
        models.Budget.year == hoy.year
    ).all()

    progreso_lista = []

    for presupuesto in presupuestos:
        gastado = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.category_id == presupuesto.category_id,
            models.Transaction.type == "expense",
            models.Transaction.date >= datetime(hoy.year, hoy.month, 1),
            models.Transaction.date <= datetime(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1], 23, 59, 59)
        ).scalar() or Decimal("0.00")  # 🔁 antes: 0.0

        # 🔁 percentage sigue siendo float — es un cálculo de presentación, no un monto acumulable
        porcentaje = float(gastado / presupuesto.amount_limit) * 100 if presupuesto.amount_limit > 0 else 0

        categoria = db.query(models.Category).filter(models.Category.id == presupuesto.category_id).first()
        nombre_cat = categoria.name if categoria else "Desconocida"

        progreso_lista.append({
            "budget_id": presupuesto.id,
            "category_name": nombre_cat,
            "amount_limit": presupuesto.amount_limit,
            "spent": gastado,
            "percentage": round(porcentaje, 2)
        })

    return progreso_lista