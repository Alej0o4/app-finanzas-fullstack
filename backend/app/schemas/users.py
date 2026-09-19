"""Schemas del dominio usuarios (Fase 25 §25.2)."""

from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.common import _validate_password_strength


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
    monthly_income: Decimal | None = None
    has_transaction_history: bool = False  # Fase 19 §19.1 — solo se calcula en GET /users/me
    has_password: bool = False  # 🆕 Fase 22 §22.4 (Decisión D4)

    @model_validator(mode="before")
    @classmethod
    def _compute_has_password(cls, data):
        # Solo cubre el path real hoy: los tres endpoints de users.py devuelven el objeto
        # ORM `User` directamente (from_attributes=True), nunca un dict armado a mano —
        # mismo path que ya usa `TransactionResponse._categoria_relacion_orm_a_none`
        # (schemas.py) como precedente de validador "before" sobre datos crudos del ORM,
        # aunque ahí es field_validator porque solo lee el campo que transforma;
        # acá hace falta model_validator porque lee un atributo (`password_hash`) distinto
        # del que expone (`has_password`).
        if hasattr(data, "password_hash"):
            data.has_password = data.password_hash is not None
        return data

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    preferred_currency: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    weekly_summary_enabled: bool | None = None  # Fase 14
    # Fase 22 §22.1 (Decisión A5): instrucción de "además, cascadeá" para esta request
    # puntual — no se persiste (ni en User ni en Account), solo orquesta la cascada de
    # `update_preferences`. Se excluye de `model_dump(exclude_none=True)` en el handler
    # para que el `setattr` no cree un atributo fantasma en el ORM.
    apply_to_default_account: bool = False


class UserProfileUpdate(BaseModel):
    """Dato financiero de dominio, separado de PreferencesUpdate (Decisión 1.1 del spec).

    Limitación conocida (igual que PreferencesUpdate): el handler usa exclude_none,
    así que un valor ya seteado no se puede volver a None desde la API.
    """

    monthly_income: Decimal | None = Field(None, ge=0, decimal_places=2)


class UserDeleteRequest(BaseModel):
    """Reconfirmación de contraseña para `DELETE /users/me` (Fase 21 §21.2, Decisión A4)."""

    password: str
