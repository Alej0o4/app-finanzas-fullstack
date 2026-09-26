import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.budget_alerts import spent_por_categoria_y_moneda
from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.core.database import get_db
from app.core.exceptions import InternalServerError, NotFoundError
from app.core.periods import limites_mes_utc, resolver_mes
from app.core.security import get_current_user
from app.models import models
from app.schemas import schemas

router = APIRouter()
logger = logging.getLogger(__name__)


def _first_transaction_month(db: Session, user_id: int) -> str | None:
    """Mes UTC `"YYYY-MM"` de la transacción más antigua del usuario, o `None`.

    Es el límite inferior del `◀` del dashboard, que gobierna la página entera, así que
    va sobre **todas** las cuentas y no solo las destacadas (las barras, los presupuestos
    y la lista de transacciones usan todas). El filtro global de borrado lógico de
    `core/database.py` ya lo aplica a este agregado del ORM, igual que al resto de las
    queries del módulo.
    """
    min_date = db.query(func.min(models.Transaction.date)).filter(models.Transaction.user_id == user_id).scalar()
    if min_date is None:
        return None
    # `func.min` devuelve tz-aware en Postgres (columna `timestamptz`) y naive en SQLite
    # (los tests). `astimezone()` sobre un naive asumiría la zona local del proceso y
    # desplazaría el mes en el borde — solo se convierte cuando viene con tz.
    if min_date.tzinfo is not None:
        min_date = min_date.astimezone(UTC)
    return f"{min_date.year:04d}-{min_date.month:02d}"


def _monedas_con_gasto(db: Session, user_id: int, inicio: datetime, limite: datetime) -> list[str]:
    """Monedas distintas con gasto (`type == "expense"`) en el rango dado, sobre TODAS las
    cuentas del usuario (B7).

    Universo deliberadamente distinto al de `monthly_expense_by_currency`: aquel solo
    suma las cuentas destacadas y alimenta la tarjeta de flujo (Q16, sin cambios); este
    alimenta los chips de moneda de "Gastos por categoría", y las barras que el chip
    filtra sí cuentan todas las cuentas. Tomar las monedas del agregado destacado dejaría
    sin chip justamente el caso que motivó la fase: una cuenta USD creada después del
    onboarding no genera su chip, aunque las barras tengan datos en USD.
    """
    return [
        fila[0]
        for fila in db.query(models.Transaction.currency)
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == "expense",
            models.Transaction.date >= inicio,
            models.Transaction.date <= limite,
        )
        .distinct()
        .all()
    ]


@router.get("/summary", response_model=schemas.DashboardSummary)
def obtener_resumen(
    year: int | None = Query(None, description="Año del mes a consultar (UTC); enviar junto a `month`, o ninguno"),
    month: int | None = Query(None, description="Mes a consultar entre 1 y 12 (UTC); enviar junto a `year`, o ninguno"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Sin `year`/`month` el período es el mes actual UTC: el dashboard de siempre no
    # cambia (User Story 47). Cualquier período inválido o futuro es un 422 de
    # `core/periods.resolver_mes`, no una respuesta silenciosa.
    ahora = datetime.now(UTC)
    year, month, es_mes_actual = resolver_mes(year, month, ahora)
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

    # El rango del mes lo acota `core/periods.limites_mes_utc`: el límite superior real
    # de "este mes" es hoy, no el fin de calendario — de lo contrario una transacción con
    # fecha futura (mismo mes) cuenta como "ya gastado/recibido" aquí pero queda afuera de
    # category-distribution/cashflow-series, que sí acotan a `hoy` (Fase 11 §11.4/Fase 17
    # §17.1.3). Para un mes ya cerrado el techo es el fin de mes real.
    primer_dia, limite_gasto = limites_mes_utc(year, month, ahora)

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
            models.Transaction.date <= limite_gasto,
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
            models.Transaction.date <= limite_gasto,
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

    expense_currencies = _monedas_con_gasto(db, current_user.id, primer_dia, limite_gasto)
    expense_currencies.sort(key=sort_key)

    # Gasto del mes en la moneda preferida — el mismo criterio de las dos ramas de abajo
    # (y de Fase 11 §11.3): las demás monedas se ignoran, no se convierten.
    gasto_moneda_preferida = next(
        (item["total"] for item in expense if item["currency"] == preferred_currency),
        Decimal("0.00"),
    )

    # Tarjeta de flujo (Fase 11 §11.3 + Fase 29 B2). El mismo campo cubre dos bases, y
    # `monthly_flow_basis` le dice al front cuál es:
    # - Mes en curso: ingreso mensual DECLARADO por el usuario menos el gasto del mes. None
    #   si el usuario no ha fijado monthly_income todavía — el frontend debe distinguir
    #   "0" de "sin definir".
    # - Mes cerrado: ingresos REALES registrados menos gastos reales, en la moneda
    #   preferida, desde las mismas filas agrupadas de arriba. NUNCA None (User Story 12):
    #   sin filas vale 0.00, aunque monthly_income sea None — el histórico siempre tiene un
    #   número.
    if es_mes_actual:
        monthly_flow_balance = (
            current_user.monthly_income - gasto_moneda_preferida if current_user.monthly_income is not None else None
        )
    else:
        ingreso_real = next(
            (item["total"] for item in income if item["currency"] == preferred_currency),
            Decimal("0.00"),
        )
        monthly_flow_balance = ingreso_real - gasto_moneda_preferida

    return {
        "balances": balances,
        "monthly_income_by_currency": income,
        "monthly_expense_by_currency": expense,
        "monthly_flow_balance": monthly_flow_balance,
        "monthly_flow_basis": "declared" if es_mes_actual else "actual",
        "first_transaction_month": _first_transaction_month(db, current_user.id),
        "expense_currencies": expense_currencies,
    }


@router.get("/budgets-progress", response_model=list[schemas.BudgetProgress])
def obtener_progreso_presupuestos(
    year: int | None = Query(None, description="Año del mes a consultar (UTC); enviar junto a `month`, o ninguno"),
    month: int | None = Query(None, description="Mes a consultar entre 1 y 12 (UTC); enviar junto a `year`, o ninguno"),
    currency: str | None = Query(None, description="Si se pasa, solo devuelve presupuestos en esa moneda"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    year, month, es_mes_actual = resolver_mes(year, month, datetime.now(UTC))

    # El dashboard es la página de aterrizaje: genera aquí los presupuestos recurrentes
    # del mes en curso antes de consultarlos (Fase 8 §3, Decisión 3.1). Fase 29 (B3) lo
    # acota al mes en curso: revisar el histórico tiene que mostrar los presupuestos que
    # existían, no los que la plantilla recurrente habría generado retroactivamente
    # (User Story 18). El `if` envuelve la llamada y no filtra resultados después porque
    # `ensure_recurring_budgets_for_period` hace su propio `db.commit()`.
    if es_mes_actual:
        ensure_recurring_budgets_for_period(db, current_user.id, month, year)

    presupuestos = (
        db.query(models.Budget)
        .filter(models.Budget.user_id == current_user.id, models.Budget.month == month, models.Budget.year == year)
        .all()
    )

    if not presupuestos:
        return []

    category_ids = [p.category_id for p in presupuestos]

    # Fase 13 §13.3: el cálculo de `spent` agrupado por (category_id, currency) vive en
    # `app/core/budget_alerts.py` y lo comparten el dashboard y el motor de alertas —
    # "cuánto gasté" no puede divergir entre la vista y el aviso (Fase 11 §11.1). Usa el
    # período RESUELTO, no el mes en curso: en un mes cerrado el gasto de ese mes es
    # completo, sin el techo de `hoy` que sí aplica al mes actual.
    spent_map = spent_por_categoria_y_moneda(db, current_user.id, category_ids, month, year)

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

    # Fase 17 §17.2.3 (Decisión P4): el filtro por moneda se aplica sobre la lista YA
    # calculada — no recalcula `spent` ni toca la query SQL (el `spent` de cada fila
    # sigue siendo el agregado de todas las cuentas del usuario en esa moneda).
    if currency is not None:
        progreso_lista = [p for p in progreso_lista if p["currency"] == currency]
    return progreso_lista


@router.get("/cashflow-series", response_model=list[schemas.CashflowData])
def obtener_serie_flujo_caja(
    start_date: datetime,
    end_date: datetime,
    period: str = Query("day", pattern="^(day|month)$", description="Agrupar por 'day' o 'month'"),
    currency: str | None = Query(None, description="Moneda a filtrar; por defecto la preferida del usuario"),
    account_id: int | None = Query(None, description="Filtra a las transacciones de una sola cuenta"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Mismo patrón de ownership que category-distribution (Fase 17 §17.1.3): 404 si la
    # cuenta no existe o no es del usuario, nunca 403.
    if account_id is not None:
        cuenta = (
            db.query(models.Account)
            .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
            .first()
        )
        if not cuenta:
            raise NotFoundError("La cuenta no existe o no tienes permisos.")

    filtro_moneda = currency or current_user.preferred_currency or "COP"
    try:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            pg_fmt = "YYYY-MM" if period == "month" else "YYYY-MM-DD"
            date_label = func.to_char(models.Transaction.date, pg_fmt).label("date_label")
        else:
            fmt = "%Y-%m" if period == "month" else "%Y-%m-%d"
            date_label = func.strftime(fmt, models.Transaction.date).label("date_label")

        filtros = [
            models.Transaction.user_id == current_user.id,
            models.Transaction.currency == filtro_moneda,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        ]
        if account_id is not None:
            filtros.append(models.Transaction.account_id == account_id)

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
            .filter(*filtros)
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
        raise InternalServerError("Error al obtener serie de flujo de caja") from None


@router.get("/category-distribution", response_model=list[schemas.CategoryDistributionData])
def obtener_distribucion_categorias(
    start_date: datetime,
    end_date: datetime,
    type: str = Query("expense", pattern="^(income|expense)$", description="Filtrar por tipo de transacción"),
    neto: bool = Query(False, description="Si es True, calcula gasto neto (expense - income) por categoría"),
    currency: str | None = Query(None, description="Moneda a filtrar; por defecto la preferida del usuario"),
    account_id: int | None = Query(None, description="Filtra a las transacciones de una sola cuenta"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Fase 17 §17.1.3: `account_id` requiere que la cuenta exista y pertenezca al
    # usuario — método de 404 idéntico al de accounts.py (nunca 403).
    if account_id is not None:
        cuenta = (
            db.query(models.Account)
            .filter(models.Account.id == account_id, models.Account.user_id == current_user.id)
            .first()
        )
        if not cuenta:
            raise NotFoundError("La cuenta no existe o no tienes permisos.")

    filtro_moneda = currency or current_user.preferred_currency or "COP"
    filtros = [
        models.Transaction.user_id == current_user.id,
        models.Transaction.currency == filtro_moneda,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ]
    if account_id is not None:
        # `currency` y `account_id` son ortogonales: filtrar por cuenta NO deriva su
        # moneda — el caller pasa `currency=account.currency` explícitamente si quiere
        # ambos (Decisión 17.1.3).
        filtros.append(models.Transaction.account_id == account_id)

    if neto:
        sum_expense = func.sum(case((models.Transaction.type == "expense", models.Transaction.amount), else_=0))
        sum_income = func.sum(case((models.Transaction.type == "income", models.Transaction.amount), else_=0))
        net_total = sum_expense - sum_income

        rows = (
            db.query(
                models.Transaction.category_id,
                models.Category.name,
                models.Category.icon,  # 🆕 Fase 24 §24.4 — mismo campo que BudgetProgress
                net_total.label("total"),
            )
            .join(models.Category, models.Category.id == models.Transaction.category_id)
            .filter(*filtros)
            .group_by(
                models.Transaction.category_id,
                models.Category.name,
                models.Category.icon,  # 🆕 Fase 24 §24.4
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
                models.Category.icon,  # 🆕 Fase 24 §24.4 — mismo campo que BudgetProgress
                func.sum(models.Transaction.amount).label("total"),
            )
            .join(models.Category, models.Category.id == models.Transaction.category_id)
            .filter(*filtros, models.Transaction.type == type)
            .group_by(
                models.Transaction.category_id,
                models.Category.name,
                models.Category.icon,  # 🆕 Fase 24 §24.4
            )
            .order_by(func.sum(models.Transaction.amount).desc())
            .all()
        )

    return [
        {"category_id": r.category_id, "category_name": r.name, "category_icon": r.icon, "total": r.total} for r in rows
    ]
