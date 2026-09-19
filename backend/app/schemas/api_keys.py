"""Schemas del dominio API keys (Fase 25 §25.2)."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- API KEYS (Fase 16 §16.1) ---
class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str  # texto plano — SOLO aparece en esta respuesta (Decisión 16.1.5)
    key_prefix: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
