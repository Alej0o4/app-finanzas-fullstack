from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum
from typing import Optional

# 1. ESQUEMA BASE: Lo que comparten todas las direcciones
class TransactionBase(BaseModel):
    amount: float
    type: str
    description: Optional[str] = None
    account_id: int
    category_id: int

# 2. ESQUEMA DE CREACIÓN (Entrada): Hereda la base. 
# Por ahora pediremos el user_id hasta que implementemos seguridad.
class TransactionCreate(TransactionBase):
    user_id: int

# 3. ESQUEMA DE RESPUESTA (Salida): Hereda la base, pero LE SUMA lo que genera la base de datos.
class TransactionResponse(TransactionBase):
    id: int
    date: datetime
    user_id: int # Lo enviaremos por ahora para verificar que se guardó bien

    # Esta configuración es MÁGICA: le dice a Pydantic que el dato no viene de un
    # diccionario normal, sino de un objeto del ORM SQLAlchemy.
    class Config:
        from_attributes = True

# 1. ESQUEMA BASE
class UserBase(BaseModel):
    email: str

# 2. ESQUEMA DE CREACIÓN (Entrada)
class UserCreate(UserBase):
    password: str  # El usuario envía su clave en texto plano

# 3. ESQUEMA DE RESPUESTA (Salida)
class UserResponse(UserBase):
    id: int
    # Nota de seguridad: NO incluimos el password aquí bajo ninguna circunstancia.
    
    class Config:
        from_attributes = True
# Añade esto al final de app/schemas/schemas.py

# 2. Creamos la "Lista Blanca" o Enumerador estricto
class AccountType(str, Enum):
    cash = "cash"
    debit = "debit"
    credit = "credit"

# 3. Actualizamos el Esquema Base usando el Enum en lugar de 'str'
class AccountBase(BaseModel):
    name: str
    type: AccountType  # 🔒 ¡Ya no es un texto libre! Ahora está blindado.
    balance: float = 0.0

class AccountCreate(AccountBase):
    user_id: int

class AccountResponse(AccountBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

# 1. Lista blanca estricta para el tipo de categoría
class CategoryType(str, Enum):
    income = "income"   # Ingreso
    expense = "expense" # Gasto

# 2. Esquema Base
class CategoryBase(BaseModel):
    name: str
    type: CategoryType  # 🔒 Blindado con el Enum

# 3. Esquema de Creación (Entrada)
class CategoryCreate(CategoryBase):
    user_id: Optional[int] = None  # Puede ser nulo para categorías globales

# 4. Esquema de Respuesta (Salida)
class CategoryResponse(CategoryBase):
    id: int
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


# 1. Esquema Base para Presupuestos
class BudgetBase(BaseModel):
    amount_limit: float
    month: int
    year: int
    category_id: int

# 2. Esquema de Creación (Entrada)
class BudgetCreate(BudgetBase):
    user_id: int  # Temporal hasta el sistema de login

# 3. Esquema de Respuesta (Salida)
class BudgetResponse(BudgetBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True