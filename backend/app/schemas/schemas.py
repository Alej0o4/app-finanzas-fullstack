from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum

# --- USUARIOS ---
class UserBase(BaseModel):
    email: str
    full_name: str

class UserCreate(UserBase):
    password: str 

class UserResponse(UserBase):
    id: int
    class Config:
        from_attributes = True

# --- TRANSACCIONES ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"

class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="El monto debe ser mayor a cero")  # 🔁 antes: float
    type: TransactionType
    description: Optional[str] = None
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
    name: str
    type: AccountType 

class AccountCreate(AccountBase):
    balance: Decimal = Field(0, ge=0, decimal_places=2, description="Saldo inicial")  # 🔁 antes: float

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
    name: str
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
    amount_limit: Decimal = Field(..., gt=0, decimal_places=2, description="El presupuesto debe ser mayor a cero")  # 🔁 antes: float
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int
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