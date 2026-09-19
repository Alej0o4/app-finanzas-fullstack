"""Schemas del dominio presupuestos (Fase 25 §25.2)."""

from decimal import Decimal

from pydantic import BaseModel, Field


# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    amount_limit: Decimal = Field(..., gt=0, decimal_places=2, description="El presupuesto debe ser mayor a cero")
    currency: str = "COP"
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int = Field(..., ge=2020, le=2100)
    category_id: int
    is_recurring: bool = False


class BudgetCreate(BudgetBase):
    pass


class BudgetResponse(BudgetBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
