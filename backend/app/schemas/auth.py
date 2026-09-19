"""Schemas del dominio autenticación (Fase 25 §25.2)."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import _validate_password_strength


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


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class GoogleLoginRequest(BaseModel):
    """ID token firmado de Google Identity Services (Fase 20 §20.3).

    El backend lo verifica contra el JWKS de Google (`verify_oauth2_token`) y emite los
    tokens de Oikos con la misma forma que `POST /auth/login` — el frontend no bifurca
    lógica de manejo de tokens (Decisión 20.3.5/P1).
    """

    id_token: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
