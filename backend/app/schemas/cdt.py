"""Schemas del dominio CDT (Fase 38 §B6)."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import CURRENCY_PATTERN, MAX_DIGITS_MONEY, nombre_sin_espacios


class CdtStatus(str, Enum):
    active = "active"
    redeemed = "redeemed"


class CdtCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    currency: str = Field("COP", pattern=CURRENCY_PATTERN)
    principal: Decimal = Field(..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    # Puntos porcentuales E.A.: 11.5 = 11,5 % (D7).
    rate_ea: Decimal = Field(..., gt=0, le=100, decimal_places=4, max_digits=7)
    # Días de calendario en la zona del usuario (D15).
    opened_on: date
    maturity_on: date
    # Fase 39 (D12): cuenta de la que salió el capital. Opcional: sin ella el CDT queda aislado
    # (el dinero nunca estuvo en la app). Con ella se crea la transferencia de constitución.
    source_account_id: int | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        return nombre_sin_espacios(v)


class CdtUpdate(BaseModel):
    """Actualización parcial de un CDT vigente (`model_fields_set`). Campos desconocidos y `null`
    explícito son `422`: nada se ignora en silencio."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    currency: str | None = Field(None, pattern=CURRENCY_PATTERN)
    principal: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    rate_ea: Decimal | None = Field(None, gt=0, le=100, decimal_places=4, max_digits=7)
    opened_on: date | None = None
    maturity_on: date | None = None
    # Fase 39 (D12): cambia la cuenta de origen (o vincula una si no había). No se puede desvincular.
    source_account_id: int | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str | None) -> str | None:
        return None if v is None else nombre_sin_espacios(v)

    @model_validator(mode="after")
    def _sin_nulos(self):
        nulos = [c for c in self.model_fields_set if getattr(self, c) is None]
        if nulos:
            raise ValueError(f"Los campos no admiten null: {', '.join(sorted(nulos))}.")
        return self


class CdtRedeem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redeemed_on: date | None = None
    final_amount: Decimal | None = Field(None, ge=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    # Fase 39 (D11): cuenta destino del capital; el interés entra como ingreso "Rendimientos".
    account_id: int | None = None


class CdtResponse(BaseModel):
    id: int
    name: str
    currency: str
    principal: Decimal
    rate_ea: Decimal
    opened_on: date
    maturity_on: date
    status: CdtStatus
    redeemed_on: date | None = None
    final_amount: Decimal | None = None
    realized_interest: Decimal | None = None
    term_days: int
    elapsed_days: int
    accrued_interest: Decimal
    current_value: Decimal
    maturity_interest: Decimal
    maturity_value: Decimal
    days_to_maturity: int | None = None
    alert: Literal["ok", "due_soon", "matured"]
    created_at: datetime | None = None
    # Fase 39: transferencias vinculadas (constitución: cuenta -> CDT; redención: CDT -> cuenta).
    source_account_id: int | None = None
    source_transfer_id: int | None = None
    redeem_account_id: int | None = None
    redeem_transfer_id: int | None = None


class CdtTotals(BaseModel):
    currency: str
    principal: Decimal
    accrued_interest: Decimal
    current_value: Decimal
    maturity_value: Decimal


class CdtListResponse(BaseModel):
    items: list[CdtResponse]
    totals: list[CdtTotals]
