"""Schemas del dominio dashboard (Fase 25 §25.2)."""

from decimal import Decimal

from pydantic import BaseModel


# --- DASHBOARD ---
class BalanceByCurrency(BaseModel):
    currency: str
    total: Decimal


class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    monthly_flow_balance: Decimal | None = None


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
