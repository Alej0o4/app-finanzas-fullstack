"""fase 08 modelo de datos mvp

Revision ID: f8c1e5a7d902
Revises: 57bde72b8117
Create Date: 2026-08-23

Migración ÚNICA de Fase 8 (Decisión 0.1 del spec docs/specs/fase_08_spec.md), sobre la
misma condición de Fase 7: sin usuarios reales, consolidar es gratis. Incluye:

- Item 1: `users.monthly_income` Numeric(14,2) nullable.
- Item 2: `transactions.payment_method` String(20) nullable.
- Item 3: `budgets.is_recurring` Boolean NOT NULL (default Python-side).
- Item 6: `updated_at` y `deleted_at` en las 5 tablas de dominio (users, accounts,
  categories, transactions, budgets — NO en las de token, Decisión 6.3), y el swap
  del UNIQUE de `budgets` por un índice único parcial que ignora filas soft-deleted
  (Decisión 6.2).
- Item 5 (Decisión 5.2): backfill de datos — usuarios sin ninguna cuenta reciben una
  cuenta "Efectivo" (cash, saldo 0, destacada). No-op sobre bases sin usuarios.

Notas de portabilidad dual PostgreSQL/SQLite (lección de 57bde72b8117):
- `server_default=sa.text("CURRENT_TIMESTAMP")`, nunca `now()` (no existe en SQLite).
- `updated_at` NO puede llevar server_default en esta migración: SQLite rechaza
  `ALTER TABLE ... ADD COLUMN` con default no constante ("Cannot add a column with
  non-constant default"). Equivalente portable: agregarla nullable + backfill
  UPDATE con CURRENT_TIMESTAMP (filas existentes quedan con el timestamp de la
  migración, misma semántica que un DEFAULT en Postgres). Para filas nuevas el
  modelo provee el valor vía default=func.now() del ORM.
- El DROP CONSTRAINT del UNIQUE de `budgets` requiere batch_alter_table: SQLite no
  soporta `ALTER TABLE ... DROP CONSTRAINT` nativo y el constraint vive inline en el
  CREATE TABLE de la migración baseline (0001); batch recrea la tabla.
- El índice parcial se crea DESPUÉS del drop del constraint: si se creara antes, la
  recreación de tabla por batch en SQLite re-reflexiona los índices existentes y puede
  perder el `sqlite_where` del índice parcial.
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c1e5a7d902"
down_revision: str | None = "57bde72b8117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLAS_DE_DOMINIO = ("users", "accounts", "categories", "transactions", "budgets")


def upgrade() -> None:
    # --- Item 1: monthly_income ---
    op.add_column("users", sa.Column("monthly_income", sa.Numeric(precision=14, scale=2), nullable=True))

    # --- Item 2: payment_method ---
    op.add_column("transactions", sa.Column("payment_method", sa.String(length=20), nullable=True))

    # --- Item 3: is_recurring ---
    # server_default solo para poblar filas existentes; se retira después para quedar
    # alineado con el modelo (default Python-side), mismo patrón que email_verified
    # en 57bde72b8117.
    op.add_column(
        "budgets",
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    with op.batch_alter_table("budgets") as batch_op:
        batch_op.alter_column("is_recurring", server_default=None)

    # --- Item 6: updated_at / deleted_at ---
    # updated_at sin server_default: ver nota de portabilidad en el docstring.
    for tabla in _TABLAS_DE_DOMINIO:
        op.add_column(tabla, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(tabla, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.execute(f"UPDATE {tabla} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

    # --- Item 6 (Decisión 6.2): swap del UNIQUE por índice único parcial ---
    with op.batch_alter_table("budgets") as batch_op:
        batch_op.drop_constraint("uq_budgets_user_category_period", type_="unique")
    op.create_index(
        "uq_budgets_user_category_period_active",
        "budgets",
        ["user_id", "category_id", "month", "year"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    # --- Item 5 (Decisión 5.2): backfill de cuentas por defecto ---
    _backfill_default_accounts()


def _backfill_default_accounts() -> None:
    """Crea una cuenta 'Efectivo' para cada usuario que no tenga NINGUNA cuenta.

    Cualquier persona registrada entre el despliegue de Fase 7 y el de Fase 8 quedó con
    0 cuentas y con el bug de onboarding sin resolver para su cuenta (ya verificó su
    email, no puede re-registrarse). Sobre una base sin usuarios huérfanos (el caso
    actual) es un no-op. No se revierte en downgrade: son datos creados, misma política
    que los renames legacy de 0001.
    """
    bind = op.get_bind()

    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("preferred_currency", sa.String),
    )
    accounts = sa.table(
        "accounts",
        sa.column("user_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("balance", sa.Numeric(precision=14, scale=2)),
        sa.column("currency", sa.String),
        sa.column("highlighted", sa.Boolean),
    )

    usuarios = bind.execute(sa.select(users.c.id, users.c.preferred_currency)).fetchall()
    ids_con_cuenta = {row[0] for row in bind.execute(sa.select(accounts.c.user_id)).fetchall()}

    for user_id, preferred_currency in usuarios:
        if user_id in ids_con_cuenta:
            continue
        bind.execute(
            accounts.insert().values(
                name="Efectivo",
                type="cash",
                balance=Decimal("0.00"),
                currency=preferred_currency or "COP",
                highlighted=True,
                user_id=user_id,
            )
        )


def downgrade() -> None:
    # El backfill de cuentas (Decisión 5.2) NO se revierte: son datos creados, y no hay
    # forma confiable de distinguirlos de cuentas "Efectivo" creadas orgánicamente
    # (precedente: 0001 tampoco revierte sus renames legacy de categorías).
    op.drop_index("uq_budgets_user_category_period_active", table_name="budgets")
    # Recrear el constraint exige batch en SQLite (recreación de tabla). Falla si
    # existen presupuestos soft-deleted que violen la unicidad plena — caso documentado
    # y aceptado para un downgrade (ver docstring del módulo).
    with op.batch_alter_table("budgets") as batch_op:
        batch_op.create_unique_constraint(
            "uq_budgets_user_category_period",
            ["user_id", "category_id", "month", "year"],
        )

    for tabla in _TABLAS_DE_DOMINIO:
        op.drop_column(tabla, "deleted_at")
        op.drop_column(tabla, "updated_at")

    op.drop_column("budgets", "is_recurring")
    op.drop_column("transactions", "payment_method")
    op.drop_column("users", "monthly_income")
