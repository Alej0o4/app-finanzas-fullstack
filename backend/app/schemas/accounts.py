"""Schemas del dominio cuentas (Fase 25 §25.2)."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import MAX_DIGITS_MONEY


# --- CUENTAS ---
class AccountType(str, Enum):
    cash = "cash"
    debit = "debit"
    credit = "credit"


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType
    currency: str = "COP"
    highlighted: bool = False


class AccountCreate(AccountBase):
    balance: Decimal = Field(0, ge=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY, description="Saldo inicial")


class AccountUpdate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: Decimal  # 🔁 antes: float
    opening_balance: Decimal  # Fase 16 §16.4: saldo de apertura, inmutable tras la creación

    class Config:
        from_attributes = True


class AccountReconcileResponse(BaseModel):
    """Resultado de POST /accounts/{account_id}/reconcile (Fase 16 §16.4.3)."""

    account_id: int
    previous_balance: Decimal
    recalculated_balance: Decimal
    discrepancy: Decimal  # recalculated_balance - previous_balance; 0.00 si no había desviación
    opening_balance: Decimal


class AccountMonthlySummary(BaseModel):
    """Balance del mes de una sola cuenta (Fase 17 §17.1.4, Decisión 17.1.4).

    Igual que `DashboardSummary.monthly_flow_balance` desde Fase 31 (Decisión B9): se
    deriva íntegramente de transacciones reales de la cuenta en el mes en curso, sin
    ningún dato declarado de por medio — `monthly_flow_balance` nunca es `None`, mínimo
    0.00. Antes de esa fase la comparación era con un `monthly_flow_balance` que sí
    podía ser `null`; ya no es el caso.
    """

    currency: str
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_flow_balance: Decimal  # monthly_income - monthly_expense; nunca None
