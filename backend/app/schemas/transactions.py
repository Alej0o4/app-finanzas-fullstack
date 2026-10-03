"""Schemas del dominio transacciones (Fase 25 §25.2)."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import CURRENCY_PATTERN, MAX_DIGITS_MONEY


# --- TRANSACCIONES ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    transfer = "transfer"


class TransactionBase(BaseModel):
    amount: Decimal = Field(
        ..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY, description="El monto debe ser mayor a cero"
    )
    # QA-025: patrón en el schema de request (el de la fila es `String(3)`, que trunca en
    # vez de rechazar). El valor se ignora y lo pisa `cuenta.currency` en el router — la
    # validación queda porque el campo ES parte del contrato de entrada. La nota de por qué
    # el response NO lo revalida está en `TransactionResponse`.
    currency: str = Field("COP", pattern=CURRENCY_PATTERN)
    type: TransactionType
    description: str | None = Field(None, max_length=500)
    account_id: int | None = None  # antes: obligatorio (Fase 16 §16.2, Decisión 16.2.4)
    category_id: int | None = None  # antes: obligatorio
    category: str | None = Field(None, max_length=100)  # alternativa por nombre (Decisión 16.2.2)
    date: datetime | None = None
    payment_method: PaymentMethod | None = None

    @model_validator(mode="after")
    def category_id_xor_category_name(self) -> "TransactionBase":
        if (self.category_id is None) == (self.category is None):
            raise ValueError("Especificar exactamente uno de 'category_id' o 'category'.")
        return self


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int
    date: datetime
    user_id: int

    # 🔓 Un response model NO revalida reglas de input (QA-025): `currency` se REDECLARA
    # para no heredar el patrón de `TransactionBase`. Sin esto, una fila con una moneda
    # heredada fuera de patrón (p. ej. `"ZZ"`, que `String(3)` acepta) dejaría
    # `GET /transactions/` y `PUT /transactions/{id}` en 500 para siempre — un
    # `ResponseValidationError` no tiene salida. Mismo criterio que QA-023 con
    # `Budget.month`/`year`: la regla va en el request, el response tolera la fila.
    currency: str = "COP"

    class Config:
        from_attributes = True

    @field_validator("category", mode="before")
    @classmethod
    def _categoria_relacion_orm_a_none(cls, v):
        """`models.Transaction` ya tiene una RELACIÓN (`category` → objeto `Category`),
        que colisiona con el campo de texto `category` de Fase 16 §16.2. Al serializar
        desde el ORM (`from_attributes`), Pydantic leería ese objeto y fallaría la
        validación de `str | None` — este validator solo aplica al RESPONSE (no a los
        schemas de request): cualquier valor no-string se normaliza a None. El campo
        `category` es de entrada (nombre a resolver en el router); en respuestas siempre
        es None, tal como `TransactionResponse` lo declara."""
        if v is None or isinstance(v, str):
            return v
        return None
