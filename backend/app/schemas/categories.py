"""Schemas del dominio categorías (Fase 25 §25.2)."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import nombre_sin_espacios


# --- CATEGORÍAS --- (sin cambios, no maneja dinero)
class CategoryType(str, Enum):
    income = "income"
    expense = "expense"


class CategoryBase(BaseModel):
    # ⚠️ `CategoryBase` es a la vez el body de `PUT /categories/{id}` y la base de
    # `CategoryCreate`/`CategoryResponse` — por eso el validador de nombre vive acá y
    # `CategoryResponse` lo sobreescribe (ver abajo).
    name: str = Field(..., min_length=1, max_length=100)
    type: CategoryType

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        """Rechaza el nombre en blanco (QA-028). `min_length=1` no alcanza: `"   "` tiene
        longitud 3 y pasaba el filtro, dejando una categoría cuyo nombre en la UI es
        indistinguible de otro. `mode="after"` porque el tipo `str` ya está garantizado ahí
        y los límites de `Field` siguen corriendo antes."""
        return nombre_sin_espacios(v)


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    user_id: int | None = None
    icon: str | None = None
    is_hidden: bool = False  # 🆕 Fase 18 — computado por usuario, no persistido en Category

    # 🔓 Un response model NO revalida reglas de input (QA-028): `name` se REDECLARA para
    # no heredar ni el `min_length`/`max_length` del `Field` ni el validador de
    # `CategoryBase` (redeclarar el campo saca el `Field(...)`, pero NO el
    # `@field_validator` heredado — Pydantic los junta por MRO y los aplica por nombre de
    # campo, así que el validador se sobreescribe abajo con un pass-through).
    #
    # Sin esto, una categoría vieja con nombre en blanco tumbaría `GET /categories/` con un
    # `ResponseValidationError` — 500 para siempre, sin salida: a diferencia de un request,
    # el cliente no tiene nada que corregir.
    name: str

    @field_validator("name", mode="after")
    @classmethod
    def _nombre_sin_espacios(cls, v: str) -> str:
        """Override deliberado del validador de `CategoryBase` (ver la nota de arriba).
        Mismo nombre y mismo modo que el del padre a propósito — así Pydantic lo reemplaza
        en vez de acumular los dos."""
        return v

    class Config:
        from_attributes = True
