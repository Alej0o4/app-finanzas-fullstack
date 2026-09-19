"""Schemas del dominio notificaciones (Fase 25 §25.2)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# --- NOTIFICACIONES (Fase 13 §13.5) ---
# Decisión 13.5.2: el Enum vive en schemas, no en la columna `notifications.type`
# (String(30) libre) — Fase 14 agrega "weekly_summary" sin migración de esquema.
class NotificationType(str, Enum):
    budget_threshold_80 = "budget_threshold_80"
    budget_threshold_100 = "budget_threshold_100"
    weekly_summary = "weekly_summary"  # Fase 14


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str
    budget_id: int | None = None
    period_key: str | None = None  # Fase 14
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    count: int
