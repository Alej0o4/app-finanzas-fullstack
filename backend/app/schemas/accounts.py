"""Schemas del dominio cuentas (Fase 25 §25.2)."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import CURRENCY_PATTERN, MAX_DIGITS_MONEY, nombre_sin_espacios


# --- CUENTAS ---
class AccountType(str, Enum):
    cash = "cash"
    debit = "debit"
    credit = "credit"


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType
    # QA-025: `Account.currency` es `String(3)` en el modelo, así que un valor más largo
    # ("zzzzzz") llegaba hasta el INSERT y volvía como 500 (`StringDataRightTruncation` es
    # un `DataError`). El patrón vive SOLO en los schemas de request —la nota larga de por
    # qué está en `AccountResponse` más abajo—. Sin normalización a propósito: "cop" en
    # minúsculas es un 422, no un "COP" silencioso.
    currency: str = Field("COP", pattern=CURRENCY_PATTERN)
    highlighted: bool = False

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        """Rechaza el nombre en blanco (QA-028). `min_length=1` no alcanza: `"   "` tiene
        longitud 3 y pasaba el filtro. Va con `mode="after"` porque el tipo `str` ya está
        garantizado ahí y los límites de `Field` siguen corriendo antes."""
        return nombre_sin_espacios(v)


class AccountCreate(AccountBase):
    balance: Decimal = Field(0, ge=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY, description="Saldo inicial")


class AccountUpdate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: Decimal  # 🔁 antes: float
    opening_balance: Decimal  # Fase 16 §16.4: saldo de apertura, inmutable tras la creación

    # 🔓 Un RESPONSE MODEL NO REVALIDA REGLAS DE INPUT (QA-025 / QA-028). Los dos campos
    # siguientes se REDECLARAN para no heredar de `AccountBase` ni el patrón de `currency`
    # ni el validador de `name`: redeclarar el campo saca el `Field(...)`, pero NO el
    # `@field_validator` heredado (Pydantic los junta por MRO y los aplica por nombre de
    # campo), así que el validador se sobreescribe abajo con un pass-through.
    #
    # Si no se hiciera, una fila heredada —una cuenta con `currency="ZZ"` o más corta, que
    # `String(3)` acepta sin problema, o con un nombre en blanco de una versión anterior—
    # dejaría `GET /accounts/` y `GET /accounts/{id}` en 500 PARA SIEMPRE, porque un
    # `ResponseValidationError` no tiene salida: no hay request que "corregir". Es
    # exactamente el modo de falla de QA-023 (datos que una versión anterior dejó entrar
    # sin validar): la regla va en el request, y el response tolera la fila.
    name: str
    currency: str = "COP"

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        """Override deliberado del validador de `AccountBase`: acá la respuesta tiene que
        poder describir una fila vieja con nombre en blanco sin tirar el endpoint (ver la
        nota de arriba). Mismo nombre y mismo modo que el del padre a propósito — así
        Pydantic lo reemplaza en vez de acumular los dos."""
        return v

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
    ningún dato declarado de por medio — `monthly_flow_balance` nunca es `None` (vale
    0.00 sin movimientos y puede ser negativo). Antes de esa fase la comparación era con un `monthly_flow_balance` que sí
    podía ser `null`; ya no es el caso.
    """

    currency: str
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_flow_balance: Decimal  # monthly_income - monthly_expense; nunca None
