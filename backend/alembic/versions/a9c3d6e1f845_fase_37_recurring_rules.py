"""fase_37_recurring_rules

Revision ID: a9c3d6e1f845
Revises: e8a1c4d7b290
Create Date: 2026-10-18 12:00:00.000000

Fase 37 (docs/specs/fase_37_spec.md §B1): tabla nueva `recurring_rules` (reglas recurrentes).
Migración puramente aditiva: no toca ninguna tabla existente ni migra datos. Los CHECK (tipo,
monto positivo, frecuencia, estado) son una garantía de base de datos, no solo de aplicación.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3d6e1f845"
down_revision: str | None = "e8a1c4d7b290"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("next_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint("type IN ('income', 'expense')", name="ck_recurring_rules_type"),
        sa.CheckConstraint("amount > 0", name="ck_recurring_rules_amount_positive"),
        sa.CheckConstraint("frequency IN ('weekly', 'monthly', 'yearly')", name="ck_recurring_rules_frequency"),
        sa.CheckConstraint("status IN ('active', 'paused')", name="ck_recurring_rules_status"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recurring_rules_id"), "recurring_rules", ["id"], unique=False)
    op.create_index(op.f("ix_recurring_rules_account_id"), "recurring_rules", ["account_id"], unique=False)
    op.create_index("ix_recurring_rules_user_id_status", "recurring_rules", ["user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recurring_rules_user_id_status", table_name="recurring_rules")
    op.drop_index(op.f("ix_recurring_rules_account_id"), table_name="recurring_rules")
    op.drop_index(op.f("ix_recurring_rules_id"), table_name="recurring_rules")
    op.drop_table("recurring_rules")
