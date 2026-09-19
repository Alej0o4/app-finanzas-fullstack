# backend/app/schemas/schemas.py — Fase 25 §25.2: shim de compatibilidad.
# Las 48 clases que antes vivían acá ahora están partidas por dominio (ver
# backend/app/schemas/{common,users,transactions,accounts,categories,budgets,
# dashboard,auth,notifications,push,api_keys}.py). Este archivo re-exporta todo bajo
# el mismo namespace `schemas.Foo` que los 11 routers de app/api/ ya usan
# (`from app.schemas import schemas`) — evita tocar esos 11 archivos en este ítem.
# Migrar los routers a importar directo del módulo de dominio (`from app.schemas.auth
# import TokenResponse`) queda como mejora oportunista futura, no parte de esta fase.
from app.schemas.accounts import (
    AccountBase,
    AccountCreate,
    AccountMonthlySummary,
    AccountReconcileResponse,
    AccountResponse,
    AccountType,
    AccountUpdate,
)
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.auth import (
    GoogleLoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    ResendVerificationRequest,
    TokenResponse,
)
from app.schemas.budgets import BudgetBase, BudgetCreate, BudgetResponse
from app.schemas.categories import CategoryBase, CategoryCreate, CategoryResponse, CategoryType
from app.schemas.common import PaginatedResponse
from app.schemas.dashboard import (
    BalanceByCurrency,
    BudgetProgress,
    CashflowData,
    CategoryDistributionData,
    DashboardSummary,
)
from app.schemas.notifications import NotificationResponse, NotificationType, UnreadCountResponse
from app.schemas.push import (
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionKeys,
    PushSubscriptionResponse,
)
from app.schemas.transactions import (
    PaymentMethod,
    TransactionBase,
    TransactionCreate,
    TransactionResponse,
    TransactionType,
)
from app.schemas.users import (
    PreferencesUpdate,
    UserBase,
    UserCreate,
    UserDeleteRequest,
    UserProfileUpdate,
    UserResponse,
)

__all__ = [
    "AccountBase",
    "AccountCreate",
    "AccountMonthlySummary",
    "AccountReconcileResponse",
    "AccountResponse",
    "AccountType",
    "AccountUpdate",
    "ApiKeyCreate",
    "ApiKeyCreateResponse",
    "ApiKeyResponse",
    "BalanceByCurrency",
    "BudgetBase",
    "BudgetCreate",
    "BudgetProgress",
    "BudgetResponse",
    "CashflowData",
    "CategoryBase",
    "CategoryCreate",
    "CategoryDistributionData",
    "CategoryResponse",
    "CategoryType",
    "DashboardSummary",
    "GoogleLoginRequest",
    "LogoutRequest",
    "NotificationResponse",
    "NotificationType",
    "PaginatedResponse",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "PaymentMethod",
    "PreferencesUpdate",
    "PushSubscriptionCreate",
    "PushSubscriptionDelete",
    "PushSubscriptionKeys",
    "PushSubscriptionResponse",
    "RefreshRequest",
    "ResendVerificationRequest",
    "TokenResponse",
    "TransactionBase",
    "TransactionCreate",
    "TransactionResponse",
    "TransactionType",
    "UnreadCountResponse",
    "UserBase",
    "UserCreate",
    "UserDeleteRequest",
    "UserProfileUpdate",
    "UserResponse",
]
