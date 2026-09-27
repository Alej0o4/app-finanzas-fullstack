"""Schemas del dominio dashboard (Fase 25 §25.2)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# --- DASHBOARD ---
class BalanceByCurrency(BaseModel):
    currency: str
    total: Decimal


class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    # 🔁 Fase 31 (Decisión B9, Q9/Q14): ingreso real - gasto real en la moneda preferida,
    # igual en el mes en curso que en un mes cerrado. Nunca `None` (User Story 34): sin
    # filas vale 0.00, y puede ser negativo (a principio de mes, antes de cobrar). Antes
    # de esta fase era `Decimal | None` con dos bases distintas según el mes — ver
    # `monthly_flow_basis` abajo.
    monthly_flow_balance: Decimal
    # 🆕 Fase 29 (Decisiones B2/B6) — SIN default a propósito. `obtener_resumen` devuelve
    # un dict plano, no una instancia de este schema, así que un default aquí no
    # "protegería" al handler: lo ocultaría en silencio. Sin default, si el handler dejara
    # de setear el campo, el 422 de validación de Pydantic lo hace visible de inmediato.
    # 🔁 Fase 31 (Decisión B9): el tipo se estrecha a `Literal["actual"]` — ya no hay una
    # base "declared", así que el campo queda `deprecated` (sale como `deprecated: true`
    # en OpenAPI) pero se conserva, sin default, por el mismo motivo de arriba: un
    # cliente que siga leyéndolo ve siempre "actual", nunca un campo ausente.
    monthly_flow_basis: Literal["actual"] = Field(deprecated=True)
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


# --- CASH FLOW SERIES (Fase 30 B1) ---
class CashflowSeries(BaseModel):
    """Respuesta de GET /dashboard/cashflow-series a partir de Fase 30.

    Antes devolvía `list[CashflowData]`. Ahora devuelve un objeto con los buckets y
    los totales del período calculados en Python (misma suma que los buckets), para
    que el frontend no tenga que sumar en cliente (Q6).
    """

    buckets: list[CashflowData]
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
