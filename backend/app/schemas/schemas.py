from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


# --- POLÍTICA DE CONTRASEÑAS (Fase 7, §2.3) ---
# NIST 800-63B recomienda priorizar longitud sobre complejidad artificial — por eso
# min_length=10 en vez de reglas de "1 mayúscula + 1 símbolo", y una lista corta de
# contraseñas comunes en vez de zxcvbn u otra dependencia externa.
_COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "password123",
    "qwerty123",
    "qwerty1234",
    "qwerty123456",
    "abc123456",
    "abcd1234",
    "letmein123",
    "welcome123",
    "admin1234",
    "admin123",
    "iloveyou1",
    "123123123",
    "monkey123",
    "football1",
    "baseball1",
    "dragon123",
    "master123",
    "hello1234",
    "freedom123",
    "whatever1",
    "trustno123",
    "superman1",
    "1q2w3e4r5t",
    "zaq12wsx1",
    "qazwsx123",
    "passw0rd1",
    "changeme1",
    "letmein12",
    "sunshine1",
    "princess1",
    "shadow123",
    "starwars1",
    "batman123",
    "michael123",
    "computer1",
}


def _validate_password_strength(value: str) -> str:
    if value.isdigit() or value.isalpha():
        raise ValueError("La contraseña debe combinar letras y números.")
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError("Esta contraseña es demasiado común.")
    return value


# --- USUARIOS ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=150)


class UserCreate(UserBase):
    password: str = Field(..., min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserResponse(UserBase):
    id: int
    preferred_currency: str = "COP"
    preferred_locale: str = "es-CO"
    preferred_theme: str = "dark"

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    preferred_currency: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None


# --- TRANSACCIONES ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="El monto debe ser mayor a cero")
    currency: str = "COP"
    type: TransactionType
    description: str | None = Field(None, max_length=500)
    account_id: int
    category_id: int
    date: datetime | None = None


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int
    date: datetime
    user_id: int

    class Config:
        from_attributes = True


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
    balance: Decimal = Field(0, ge=0, decimal_places=2, description="Saldo inicial")


class AccountUpdate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: Decimal  # 🔁 antes: float

    class Config:
        from_attributes = True


# --- CATEGORÍAS --- (sin cambios, no maneja dinero)
class CategoryType(str, Enum):
    income = "income"
    expense = "expense"


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: CategoryType


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    user_id: int | None = None
    icon: str | None = None

    class Config:
        from_attributes = True


# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    amount_limit: Decimal = Field(..., gt=0, decimal_places=2, description="El presupuesto debe ser mayor a cero")
    currency: str = "COP"
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int = Field(..., ge=2020, le=2100)
    category_id: int


class BudgetCreate(BudgetBase):
    pass


class BudgetResponse(BudgetBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


# --- DASHBOARD ---
class BalanceByCurrency(BaseModel):
    currency: str
    total: Decimal


class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]


class BudgetProgress(BaseModel):
    budget_id: int
    category_name: str
    category_icon: str | None = None
    amount_limit: Decimal  # 🔁 antes: float
    spent: Decimal  # 🔁 antes: float
    percentage: float  # ✅ se queda float, es un porcentaje calculado, no dinero


# --- AUTENTICACIÓN ---
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class CashflowData(BaseModel):
    date_label: str
    income: Decimal
    expense: Decimal

    class Config:
        from_attributes = True


class CategoryDistributionData(BaseModel):
    category_id: int
    category_name: str
    total: Decimal

    class Config:
        from_attributes = True
