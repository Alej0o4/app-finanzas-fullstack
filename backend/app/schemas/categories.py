"""Schemas del dominio categorías (Fase 25 §25.2)."""

from enum import Enum

from pydantic import BaseModel, Field


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
    is_hidden: bool = False  # 🆕 Fase 18 — computado por usuario, no persistido en Category

    class Config:
        from_attributes = True
