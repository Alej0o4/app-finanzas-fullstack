"""Schemas del dominio push web (Fase 25 §25.2)."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- PUSH WEB (Fase 13 §13.2) ---
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    """Shape estándar de `PushSubscription.toJSON()` del navegador."""

    endpoint: str = Field(..., min_length=1, max_length=500)
    keys: PushSubscriptionKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=500)


class PushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    created_at: datetime

    class Config:
        from_attributes = True
