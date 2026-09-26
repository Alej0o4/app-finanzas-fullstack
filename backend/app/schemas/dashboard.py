"""Schemas del dominio dashboard (Fase 25 §25.2)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


# --- DASHBOARD ---
class BalanceByCurrency(BaseModel):
    currency: str
    total: Decimal


class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    # `null` solo es posible con basis "declared" (el usuario no ha fijado monthly_income).
    monthly_flow_balance: Decimal | None = None
    # 🆕 Fase 29 (Decisiones B2/B6) — SIN default a propósito. `obtener_resumen` devuelve
    # un dict plano, no una instancia de este schema, así que un default aquí no
    # "protegería" al handler: lo ocultaría en silencio. Sin default, si el handler dejara
    # de setear el campo, el 422 de validación de Pydantic lo hace visible de inmediato.
    # "declared" = mes en curso (ingreso declarado - gastos); "actual" = mes cerrado
    # (ingresos reales - gastos reales). El front elige el rótulo con esto, sin comparar
    # fechas locales (User Story 49).
    monthly_flow_basis: Literal["declared", "actual"]
    # 🆕 Fase 29 (B2): mes UTC "YYYY-MM" de la transacción más antigua del usuario, o
    # `null` si no tiene ninguna. Es el límite inferior del `◀` del dashboard, que
    # gobierna la página entera — por eso se calcula sobre TODAS las cuentas, no solo las
    # destacadas (las barras, los presupuestos y la lista de transacciones usan todas).
    first_transaction_month: str | None = None
    # 🆕 Fase 29 (B7): monedas distintas con gasto en el mes pedido, sobre TODAS las
    # cuentas (el mismo universo que las barras que filtra el chip), con la preferida
    # primero. La preferida NO se agrega si no tiene gasto: el front la suma a las
    # opciones para que el chip nunca quede sin nada que mostrar.
    expense_currencies: list[str] = []


class BudgetProgress(BaseModel):
    budget_id: int
    category_name: str
    category_icon: str | None = None
    amount_limit: Decimal  # 🔁 antes: float
    spent: Decimal  # 🔁 antes: float
    percentage: float  # ✅ se queda float, es un porcentaje calculado, no dinero
    currency: str


class CashflowData(BaseModel):
    date_label: str
    income: Decimal
    expense: Decimal

    class Config:
        from_attributes = True


class CategoryDistributionData(BaseModel):
    category_id: int
    category_name: str
    category_icon: str | None = None  # 🆕 Fase 24 §24.4 — mismo campo que BudgetProgress
    total: Decimal

    class Config:
        from_attributes = True
