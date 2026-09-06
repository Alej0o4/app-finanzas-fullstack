from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base, SoftDeleteMixin


class User(Base, SoftDeleteMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)  # 🆕 nuevo campo
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    preferred_currency = Column(String(3), default="COP")
    preferred_locale = Column(String(10), default="es-CO")
    preferred_theme = Column(String(10), default="dark")
    email_verified = Column(Boolean, nullable=False, default=False)
    monthly_income = Column(Numeric(14, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # default=func.now(): el INSERT del ORM puebla updated_at también en bases
    # migradas, donde la migración no pudo dejar DEFAULT en DB (SQLite no permite
    # ADD COLUMN con default no constante); server_default cubre create_all/tests.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), onupdate=func.now())

    accounts = relationship("Account", back_populates="owner")
    categories = relationship("Category", back_populates="owner")
    transactions = relationship("Transaction", back_populates="owner")
    budgets = relationship("Budget", back_populates="owner")


class Account(Base, SoftDeleteMixin):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)
    balance = Column(Numeric(14, 2), default=0)  # 🔁 antes: Float
    currency = Column(String(3), default="COP", nullable=False)
    highlighted = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), onupdate=func.now())

    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")


class Category(Base, SoftDeleteMixin):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)
    icon = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")


class Transaction(Base, SoftDeleteMixin):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(14, 2), nullable=False)  # 🔁 antes: Float
    currency = Column(String(3), default="COP", nullable=False)
    type = Column(String)
    date = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(String, nullable=True)
    payment_method = Column(String(20), nullable=True)  # cash/card/transfer; valida el enum en schemas
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), onupdate=func.now())

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)

    owner = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    __table_args__ = (Index("ix_transactions_user_id_date", "user_id", "date"),)


class Budget(Base, SoftDeleteMixin):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    amount_limit = Column(Numeric(14, 2), nullable=False)  # 🔁 antes: Float
    currency = Column(String(3), default="COP", nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    is_recurring = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), onupdate=func.now())

    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))

    owner = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")

    # Índice único PARCIAL (Decisión 6.2): las filas soft-deleted no ocupan slot de
    # unicidad — borrar un presupuesto y crear otro para la misma categoría/período
    # debe funcionar. Sustituye al UniqueConstraint de Fase 7.
    __table_args__ = (
        Index(
            "uq_budgets_user_category_period_active",
            "user_id",
            "category_id",
            "month",
            "year",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="refresh_tokens")


class PasswordResetToken(Base):
    """Token de un solo uso para recuperación de contraseña (ver docs/specs/fase_07_spec.md §2.1).

    Expiración corta (`security.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`) porque es de alto
    riesgo si se filtra por email — a diferencia de `RefreshToken`, que dura 30 días.
    """

    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="password_reset_tokens")


class EmailVerificationToken(Base):
    """Token de un solo uso para verificar el email en el registro (ver §2.2 del spec).

    Expiración más larga que `PasswordResetToken` (`security.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS`)
    porque no es tan sensible como un reset de contraseña.
    """

    __tablename__ = "email_verification_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="email_verification_tokens")


class IdempotencyKey(Base):
    """Bitácora de reintentos seguros para POST /transactions (Fase 10, ROADMAP).

    No es una tabla polimórfica a propósito (Decisión 10.4.1 del spec de Fase 10): el
    alcance actual es un solo endpoint. Sin SoftDeleteMixin, mismo criterio que
    RefreshToken/PasswordResetToken/EmailVerificationToken (Decisión 6.3 de Fase 8):
    es bitácora técnica, no un dato de dominio que el usuario liste o borre.
    """

    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)  # sha256 hex del payload canónico
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("uq_idempotency_keys_user_key", "user_id", "key", unique=True),)


class Notification(Base):
    """Aviso persistido para la bandeja in-app (Fase 13 §13.5).

    Fuente única de avisos: tanto el motor de presupuestos (§13.3) como, en el futuro,
    el resumen semanal de Fase 14, insertan aquí. El envío push (§13.2) es un canal
    adicional sobre la misma fila, no una tabla paralela — evita que un aviso "exista"
    en push pero no en la bandeja, o viceversa.
    """

    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(
        String(30), nullable=False
    )  # "budget_threshold_80" | "budget_threshold_100" (Fase 14 agrega "weekly_summary")
    title = Column(String(200), nullable=False)
    body = Column(String(500), nullable=False)
    # Referencia opcional a la entidad que originó el aviso, para que el frontend pueda
    # enlazar "Ver presupuesto" — nullable porque Fase 14 (resumen semanal) no apunta a
    # un presupuesto puntual.
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="notifications")
    budget = relationship("Budget")

    # Decisión 13.3.2: la idempotencia "un aviso por umbral por período" es una garantía
    # de base de datos, no solo de aplicación — dos transacciones concurrentes que
    # empujan el mismo presupuesto sobre el 100% no pueden generar dos avisos. El índice
    # es PARCIAL (budget_id IS NOT NULL) porque las notificaciones de Fase 14 (resumen
    # semanal) no apuntan a un presupuesto y no deben ocupar slot de unicidad.
    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index(
            "uq_notifications_budget_type_active",
            "budget_id",
            "type",
            unique=True,
            postgresql_where=text("budget_id IS NOT NULL"),
            sqlite_where=text("budget_id IS NOT NULL"),
        ),
    )


class PushSubscription(Base):
    """Suscripción push de un navegador/dispositivo (Fase 13 §13.2).

    Un usuario puede tener varias filas (multi-dispositivo). Sin SoftDeleteMixin — una
    suscripción revocada por el navegador (410 Gone al enviar) se borra de verdad, no
    tiene valor histórico (Decisión 6.3 de Fase 8, mismo criterio que RefreshToken).
    """

    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="push_subscriptions")

    # `endpoint` es único GLOBALMENTE (no por usuario): el estándar Web Push garantiza
    # un endpoint único por navegador/instalación — si el mismo endpoint se re-registra
    # (cierre de sesión y re-login en el mismo dispositivo), se actualiza la fila en vez
    # de duplicar (upsert por endpoint, Decisión 13.2.3 del spec).
    __table_args__ = (Index("uq_push_subscriptions_endpoint", "endpoint", unique=True),)
