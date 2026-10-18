"""Schemas del dominio recurrentes (Fase 37 §B7)."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import MAX_DIGITS_MONEY, nombre_sin_espacios


class RecurringType(str, Enum):
    income = "income"
    expense = "expense"


class RecurringFrequency(str, Enum):
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class RecurringStatus(str, Enum):
    active = "active"
    paused = "paused"


class RecurringCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: RecurringType
    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    account_id: int
    category_id: int
    frequency: RecurringFrequency
    # Día de calendario en la zona del usuario; ancla del calendario (D4, D5).
    start_date: date

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        return nombre_sin_espacios(v)


class RecurringUpdate(BaseModel):
    """Actualización parcial (`model_fields_set`). `frequency`, `start_date` y `type` no se editan
    (D6): enviarlos es un `422` (`extra="forbid"`), no se ignoran en silencio."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    amount: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    account_id: int | None = None
    category_id: int | None = None
    status: RecurringStatus | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str | None) -> str | None:
        return None if v is None else nombre_sin_espacios(v)


class RecurringConfirm(BaseModel):
    occurrence_date: date
    # `null` o ausente = el monto de la regla.
    amount: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)


class RecurringSkip(BaseModel):
    occurrence_date: date


class RecurringResponse(BaseModel):
    id: int
    name: str
    type: RecurringType
    amount: Decimal
    # Moneda de la cuenta; `None` si la cuenta se borró (`account_missing`).
    currency: str | None = None
    account_id: int
    category_id: int
    frequency: RecurringFrequency
    start_date: date
    next_date: date
    status: RecurringStatus
    monthly_equivalent: Decimal
    is_annual: bool
    # Activa y con la próxima ocurrencia vencida (`next_date <= hoy` en la zona del usuario).
    is_due: bool
    account_missing: bool
    category_missing: bool
    created_at: datetime | None = None


class PendingOccurrenceResponse(BaseModel):
    rule_id: int
    name: str
    type: RecurringType
    amount: Decimal
    currency: str
    account_id: int
    category_id: int
    frequency: RecurringFrequency
    occurrence_date: date
    # Solo la ocurrencia más antigua de cada regla se puede confirmar o saltar (D9).
    is_next: bool


class CalendarItem(BaseModel):
    rule_id: int
    name: str
    type: RecurringType
    amount: Decimal
    currency: str
    date: date
    is_annual: bool
    is_overdue: bool


class CalendarTotals(BaseModel):
    currency: str
    income: Decimal
    expense: Decimal
    net: Decimal


class CalendarMonth(BaseModel):
    month: str  # YYYY-MM
    items: list[CalendarItem]
    totals: list[CalendarTotals]


class MonthlyCommitment(BaseModel):
    currency: str
    amount: Decimal


class CalendarResponse(BaseModel):
    months: list[CalendarMonth]
    monthly_commitment: list[MonthlyCommitment]


class SuggestionResponse(BaseModel):
    name: str
    account_id: int
    category_id: int
    currency: str
    amount: Decimal
    last_date: date
    suggested_start_date: date
    occurrences: int
