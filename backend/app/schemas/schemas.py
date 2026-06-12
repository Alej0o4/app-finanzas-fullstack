from pydantic import BaseModel
from datetime import datetime
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