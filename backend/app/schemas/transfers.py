"""Schemas de transferencias y del feed de movimientos (Fase 39 §B3, §B4)."""

import re
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.schemas.common import MAX_DIGITS_MONEY, PaginatedResponse
from app.schemas.transactions import TransactionResponse

_SOLO_DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_ADAPTER = TypeAdapter(datetime)


class TransferBase(BaseModel):
    """Body de `POST`/`PUT /transfers`. Las monedas no se envían: salen de las cuentas.

    `exchange_rate` (COP por 1 unidad de la moneda extranjera) y `amount_in` son mutuamente
    excluyentes; la coherencia con las monedas la valida el servicio (D2/D9)."""

    model_config = ConfigDict(extra="forbid")

    from_account_id: int
    to_account_id: int
    amount_out: Decimal = Field(..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    amount_in: Decimal | None = Field(None, gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY)
    exchange_rate: Decimal | None = Field(None, gt=0, decimal_places=6, max_digits=18)
    # Mismas reglas que `Transaction.date` (D13): `YYYY-MM-DD` (zona del usuario) o datetime.
    date: datetime | date_type | None = None
    description: str | None = Field(None, max_length=500)

    @field_validator("date", mode="before")
    @classmethod
    def _separar_solo_dia_de_datetime(cls, v):
        if isinstance(v, str):
            if _SOLO_DIA.match(v):
                return date_type.fromisoformat(v)
            return _DATETIME_ADAPTER.validate_python(v)
        if isinstance(v, int | float) and not isinstance(v, bool):
            return _DATETIME_ADAPTER.validate_python(v)
        return v

    @model_validator(mode="after")
    def _cuentas_distintas(self) -> "TransferBase":
        if self.from_account_id == self.to_account_id:
            raise ValueError("La cuenta de origen y la de destino deben ser distintas.")
        return self


class TransferCreate(TransferBase):
    pass


class TransferUpdate(TransferBase):
    """`PUT`: reemplazo completo de cuentas y montos. `date` ausente/`null` conserva la fecha;
    `description` ausente conserva, `null` explícito la limpia (`model_fields_set`)."""


class TransferWarning(BaseModel):
    code: Literal["BELOW_COMMITTED"]
    account_id: int
    currency: str
    committed: Decimal
    balance_after: Decimal


class TransferResponse(BaseModel):
    id: int
    from_account_id: int | None = None
    to_account_id: int | None = None
    cdt_id: int | None = None
    cdt_name: str | None = None
    amount_out: Decimal
    currency_out: str
    amount_in: Decimal
    currency_in: str
    # COP por 1 unidad extranjera; `None` si la transferencia es en una sola moneda o sin COP.
    exchange_rate: Decimal | None = None
    date: datetime
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Solo `POST`/`PUT`; `GET` lo deja vacío.
    warnings: list[TransferWarning] = []


# --- Feed de movimientos (B4) ---
class TransactionMovement(TransactionResponse):
    kind: Literal["transaction"] = "transaction"


class TransferMovement(TransferResponse):
    kind: Literal["transfer"] = "transfer"


Movement = Annotated[TransactionMovement | TransferMovement, Field(discriminator="kind")]


class MovementsResponse(PaginatedResponse[Movement]):
    pass
