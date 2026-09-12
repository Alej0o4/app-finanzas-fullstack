from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


# --- POLÍTICA DE CONTRASEÑAS (Fase 7, §2.3) ---
# NIST 800-63B recomienda priorizar longitud sobre complejidad artificial — por eso
# min_length=10 en vez de reglas de "1 mayúscula + 1 símbolo", y una lista corta de
# contraseñas comunes en vez de zxcvbn u otra dependencia externa.
_COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "password123",
    "qwerty123",
    "qwerty1234",
    "qwerty123456",
    "abc123456",
    "abcd1234",
    "letmein123",
    "welcome123",
    "admin1234",
    "admin123",
    "iloveyou1",
    "123123123",
    "monkey123",
    "football1",
    "baseball1",
    "dragon123",
    "master123",
    "hello1234",
    "freedom123",
    "whatever1",
    "trustno123",
    "superman1",
    "1q2w3e4r5t",
    "zaq12wsx1",
    "qazwsx123",
    "passw0rd1",
    "changeme1",
    "letmein12",
    "sunshine1",
    "princess1",
    "shadow123",
    "starwars1",
    "batman123",
    "michael123",
    "computer1",
}


def _validate_password_strength(value: str) -> str:
    if value.isdigit() or value.isalpha():
        raise ValueError("La contraseña debe combinar letras y números.")
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError("Esta contraseña es demasiado común.")
    return value


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

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    preferred_currency: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    weekly_summary_enabled: bool | None = None  # Fase 14


class UserProfileUpdate(BaseModel):
    """Dato financiero de dominio, separado de PreferencesUpdate (Decisión 1.1 del spec).

    Limitación conocida (igual que PreferencesUpdate): el handler usa exclude_none,
    así que un valor ya seteado no se puede volver a None desde la API.
    """

    monthly_income: Decimal | None = Field(None, ge=0, decimal_places=2)


# --- TRANSACCIONES ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    transfer = "transfer"


class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="El monto debe ser mayor a cero")
    currency: str = "COP"
    type: TransactionType
    description: str | None = Field(None, max_length=500)
    account_id: int | None = None  # antes: obligatorio (Fase 16 §16.2, Decisión 16.2.4)
    category_id: int | None = None  # antes: obligatorio
    category: str | None = Field(None, max_length=100)  # alternativa por nombre (Decisión 16.2.2)
    date: datetime | None = None
    payment_method: PaymentMethod | None = None

    @model_validator(mode="after")
    def category_id_xor_category_name(self) -> "TransactionBase":
        if (self.category_id is None) == (self.category is None):
            raise ValueError("Especificar exactamente uno de 'category_id' o 'category'.")
        return self


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int
    date: datetime
    user_id: int

    class Config:
        from_attributes = True

    @field_validator("category", mode="before")
    @classmethod
    def _categoria_relacion_orm_a_none(cls, v):
        """`models.Transaction` ya tiene una RELACIÓN (`category` → objeto `Category`),
        que colisiona con el campo de texto `category` de Fase 16 §16.2. Al serializar
        desde el ORM (`from_attributes`), Pydantic leería ese objeto y fallaría la
        validación de `str | None` — este validator solo aplica al RESPONSE (no a los
        schemas de request): cualquier valor no-string se normaliza a None. El campo
        `category` es de entrada (nombre a resolver en el router); en respuestas siempre
        es None, tal como `TransactionResponse` lo declara."""
        if v is None or isinstance(v, str):
            return v
        return None


# --- CUENTAS ---
class AccountType(str, Enum):
    cash = "cash"
    debit = "debit"
    credit = "credit"


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType
    currency: str = "COP"
    highlighted: bool = False


class AccountCreate(AccountBase):
    balance: Decimal = Field(0, ge=0, decimal_places=2, description="Saldo inicial")


class AccountUpdate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: Decimal  # 🔁 antes: float
    opening_balance: Decimal  # Fase 16 §16.4: saldo de apertura, inmutable tras la creación

    class Config:
        from_attributes = True


class AccountReconcileResponse(BaseModel):
    """Resultado de POST /accounts/{account_id}/reconcile (Fase 16 §16.4.3)."""

    account_id: int
    previous_balance: Decimal
    recalculated_balance: Decimal
    discrepancy: Decimal  # recalculated_balance - previous_balance; 0.00 si no había desviación
    opening_balance: Decimal


class AccountMonthlySummary(BaseModel):
    """Balance del mes de una sola cuenta (Fase 17 §17.1.4, Decisión 17.1.4).

    A diferencia de `DashboardSummary.monthly_flow_balance` (que puede ser `null` si el
    usuario no fijó `monthly_income`), este balance SIEMPRE se calcula: se deriva
    íntegramente de transacciones reales de la cuenta en el mes en curso, sin ningún
    dato declarado de por medio — `monthly_flow_balance` nunca es `None`, mínimo 0.00.
    """

    currency: str
    monthly_income: Decimal
    monthly_expense: Decimal
    monthly_flow_balance: Decimal  # monthly_income - monthly_expense; nunca None


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

    class Config:
        from_attributes = True


# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    amount_limit: Decimal = Field(..., gt=0, decimal_places=2, description="El presupuesto debe ser mayor a cero")
    currency: str = "COP"
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int = Field(..., ge=2020, le=2100)
    category_id: int
    is_recurring: bool = False


class BudgetCreate(BudgetBase):
    pass


class BudgetResponse(BudgetBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


# --- DASHBOARD ---
class BalanceByCurrency(BaseModel):
    currency: str
    total: Decimal


class DashboardSummary(BaseModel):
    balances: list[BalanceByCurrency]
    monthly_income_by_currency: list[BalanceByCurrency]
    monthly_expense_by_currency: list[BalanceByCurrency]
    monthly_flow_balance: Decimal | None = None


class BudgetProgress(BaseModel):
    budget_id: int
    category_name: str
    category_icon: str | None = None
    amount_limit: Decimal  # 🔁 antes: float
    spent: Decimal  # 🔁 antes: float
    percentage: float  # ✅ se queda float, es un porcentaje calculado, no dinero
    currency: str


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


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class CashflowData(BaseModel):
    date_label: str
    income: Decimal
    expense: Decimal

    class Config:
        from_attributes = True


class CategoryDistributionData(BaseModel):
    category_id: int
    category_name: str
    total: Decimal

    class Config:
        from_attributes = True


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
