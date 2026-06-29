from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal
import calendar
from typing import List
from collections import defaultdict

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

@router.get("/cashflow-series", response_model=List[schemas.CashflowData])
def obtener_serie_flujo_caja(
    start_date: datetime,
    end_date: datetime,
    period: str = Query("day", pattern="^(day|month)$", description="Agrupar por 'day' o 'month'"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Consulta SQL simplificada (Sin CAST ni agrupaciones problemáticas)
    # Extraemos solo los datos crudos del usuario en el rango de fechas
    resultados = db.query(
        models.Transaction.date,
        models.Transaction.type,
        models.Transaction.amount
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date
    ).all()

    # 2. Agrupación 100% en memoria (Agnóstica al motor de Base de Datos)
    agrupacion = defaultdict(lambda: {"income": Decimal("0.00"), "expense": Decimal("0.00")})

    for fecha, tipo_tx, amount in resultados:
        if period == "month":
            label = f"{fecha.year}-{fecha.month:02d}"
        else:
            # fecha ya es un objeto datetime de Python aquí
            label = fecha.strftime("%Y-%m-%d")

        # Aseguramos la conversión a Decimal por si SQLite lo devuelve como float
        valor_decimal = Decimal(str(amount)) if amount else Decimal("0.00")
        agrupacion[label][tipo_tx] += valor_decimal

    # 3. Serialización ordenada cronológicamente
    serie_tiempo = [
        {
            "date_label": key,
            "income": values["income"],
            "expense": values["expense"]
        }
        for key, values in sorted(agrupacion.items())
    ]

    return serie_tiempo


@router.get("/category-distribution", response_model=List[schemas.CategoryDistributionData])
def obtener_distribucion_categorias(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    resultados = db.query(
        models.Transaction.category_id,
        models.Category.name,
        models.Transaction.amount
    ).join(
        models.Category, models.Category.id == models.Transaction.category_id
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == "expense",
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date
    ).all()

    agrupacion = defaultdict(lambda: {"category_name": "Desconocida", "total": Decimal("0.00")})

    for category_id, category_name, amount in resultados:
        valor_decimal = Decimal(str(amount)) if amount else Decimal("0.00")
        agrupacion[category_id]["category_name"] = category_name or "Desconocida"
        agrupacion[category_id]["total"] += valor_decimal

    return [
        {
            "category_id": category_id,
            "category_name": values["category_name"],
            "total": values["total"]
        }
        for category_id, values in sorted(
            agrupacion.items(),
            key=lambda item: item[1]["total"],
            reverse=True
        )
    ]