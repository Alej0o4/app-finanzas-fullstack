from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field

# --- USUARIOS ---
class UserBase(BaseModel):
    email: str

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
    amount: float = Field(..., gt=0, description="El monto debe ser mayor a cero")
    type: TransactionType  # 🔒 ¡Ya no es un texto libre (str)! Ahora está blindado.
    description: Optional[str] = None
    account_id: int
    category_id: int

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

# En la creación SÍ permitimos un balance inicial (ej. saldo con el que abro la app)
class AccountCreate(AccountBase):
    balance: float = Field(0.0, ge=0, description="Saldo inicial")

# 🔒 NUEVO: Molde estricto para editar. NO tiene la variable 'balance'
class AccountUpdate(AccountBase):
    pass 

class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: float # 🔒 El balance ahora es solo de lectura (salida)
    class Config:
        from_attributes = True

# --- CATEGORÍAS ---
class CategoryType(str, Enum):
    income = "income"   
    expense = "expense" 

class CategoryBase(BaseModel):
    name: str
    type: CategoryType  

class CategoryCreate(CategoryBase):
    pass # Eliminado user_id para que el sistema asigne automáticamente o quede como None global

class CategoryResponse(CategoryBase):
    id: int
    user_id: Optional[int] = None
    class Config:
        from_attributes = True

# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    # 🔒 Blindaje: El límite también debe ser mayor a 0
    amount_limit: float = Field(..., gt=0, description="El presupuesto debe ser mayor a cero")
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int
    category_id: int

class BudgetCreate(BudgetBase):
    pass # Eliminado user_id

class BudgetResponse(BudgetBase):
    id: int
    user_id: int
    class Config:
        from_attributes = True

# --- DASHBOARD ---
class DashboardSummary(BaseModel):
    total_balance: float
    monthly_income: float
    monthly_expense: float

class BudgetProgress(BaseModel):
    budget_id: int
    category_name: str
    amount_limit: float
    spent: float
    percentage: float