from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

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
class TransactionBase(BaseModel):
    amount: float
    type: str
    description: Optional[str] = None
    account_id: int
    category_id: int

class TransactionCreate(TransactionBase):
    pass # Eliminado user_id

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
    balance: float = 0.0

class AccountCreate(AccountBase):
    pass # Eliminado user_id

class AccountResponse(AccountBase):
    id: int
    user_id: int
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
    amount_limit: float
    month: int
    year: int
    category_id: int

class BudgetCreate(BudgetBase):
    pass # Eliminado user_id

class BudgetResponse(BudgetBase):
    id: int
    user_id: int
    class Config:
        from_attributes = True