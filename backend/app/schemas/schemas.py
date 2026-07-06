from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from decimal import Decimal
from typing import Optional, Generic, TypeVar
from enum import Enum

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

# --- USUARIOS ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=150)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: int
    preferred_currency: str = "COP"
    preferred_locale: str = "es-CO"
    class Config:
        from_attributes = True

# --- TRANSACCIONES ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"

class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="El monto debe ser mayor a cero")
    type: TransactionType
    description: Optional[str] = Field(None, max_length=500)
    account_id: int
    category_id: int
    date: Optional[datetime] = None

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
    user_id: Optional[int] = None
    class Config:
        from_attributes = True

# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    amount_limit: Decimal = Field(..., gt=0, decimal_places=2, description="El presupuesto debe ser mayor a cero")
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
class DashboardSummary(BaseModel):
    total_balance: Decimal      # 🔁 antes: float
    monthly_income: Decimal     # 🔁 antes: float
    monthly_expense: Decimal    # 🔁 antes: float

class BudgetProgress(BaseModel):
    budget_id: int
    category_name: str
    amount_limit: Decimal   # 🔁 antes: float
    spent: Decimal          # 🔁 antes: float
    percentage: float       # ✅ se queda float, es un porcentaje calculado, no dinero


# --- AUTENTICACIÓN ---
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str


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