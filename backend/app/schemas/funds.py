"""Schemas del dominio sobres (Fase 35 §B8, §B10)."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import MAX_DIGITS_MONEY, nombre_sin_espacios


class FundKind(str, Enum):
    annual_expense = "annual_expense"
    emergency = "emergency"
    goal = "goal"


class FundStatus(str, Enum):
    active = "active"
    archived = "archived"


class FundCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    kind: FundKind
    account_id: int
    target_amount: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    # Solo el fondo de emergencia: meta = N meses del gasto promedio (D3).
    target_months: int | None = Field(None, ge=1, le=60)
    # Día elegido, interpretado en la zona del usuario (D9).
    target_date: date | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        return nombre_sin_espacios(v)

    @model_validator(mode="after")
    def _meta_valida(self):
        if (self.target_amount is None) == (self.target_months is None):
            raise ValueError("Indica `target_amount` o `target_months`, uno solo.")
        if self.target_months is not None and self.kind != FundKind.emergency:
            raise ValueError("`target_months` solo aplica al fondo de emergencia.")
        # A4: un gasto anual sin vencimiento no es un gasto anual.
        if self.kind == FundKind.annual_expense and self.target_date is None:
            raise ValueError("Un gasto anual necesita `target_date` (su fecha de vencimiento).")
        return self


class FundUpdate(BaseModel):
    """Actualización parcial (`model_fields_set`): solo cambian los campos enviados. No se puede
    cambiar `kind` ni la moneda. Enviar `target_date: null` quita la fecha."""

    name: str | None = Field(None, min_length=1, max_length=100)
    account_id: int | None = None
    target_amount: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    target_months: int | None = Field(None, ge=1, le=60)
    target_date: date | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str | None) -> str | None:
        return None if v is None else nombre_sin_espacios(v)


class FundMovement(BaseModel):
    """Body de aportar y de retirar: el monto es siempre positivo; el signo lo pone el tipo."""

    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    note: str | None = Field(None, max_length=200)

    @field_validator("note", mode="after")
    @classmethod
    def _nota_recortada(cls, v: str | None) -> str | None:
        v = v.strip() if v else v
        return v or None


class FundEntryResponse(BaseModel):
    id: int
    fund_id: int
    amount: Decimal  # con signo: aporte > 0, retiro < 0
    type: Literal["contribution", "withdrawal", "adjustment"]
    occurred_at: datetime
    period: str
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FundResponse(BaseModel):
    id: int
    name: str
    kind: FundKind
    status: FundStatus
    account_id: int
    currency: str
    balance: Decimal
    # Meta efectiva: la fija, o `target_months x monthly_expense_avg`; `None` si no hay historial.
    target_amount: Decimal | None = None
    target_months: int | None = None
    target_date: date | None = None
    progress_pct: float | None = None
    remaining: Decimal | None = None
    months_remaining: int | None = None
    required_contribution: Decimal | None = None
    # A2: cuota sugerida del mes siguiente con el saldo actual; `None` si no hay fecha, es el
    # último mes o no queda nada por aportar.
    next_month_contribution: Decimal | None = None
    pace: Literal["completed", "on_track", "behind"] | None = None
    monthly_expense_avg: Decimal | None = None
    runway_months: Decimal | None = None
    # Lo apartado en los sobres activos de la cuenta que excede su saldo (D4); 0 si está respaldado.
    backing_shortfall: Decimal
    created_at: datetime | None = None


class FundDetailResponse(FundResponse):
    entries: list[FundEntryResponse]
