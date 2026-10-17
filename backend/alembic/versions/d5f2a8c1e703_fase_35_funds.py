"""fase_35_funds

Revision ID: d5f2a8c1e703
Revises: c7d3e9a4b1f6
Create Date: 2026-10-17 12:00:00.000000

Fase 35 (docs/specs/fase_35_spec.md §B3): tablas nuevas `funds` (sobres virtuales) y
`fund_entries` (libro append-only). Migración puramente aditiva: no toca ninguna tabla
existente ni migra datos. Los CHECK (kind, status, target XOR, signo del movimiento) son una
garantía de base de datos, no solo de aplicación. `downgrade` borra `fund_entries` primero
(FK a `funds`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f2a8c1e703"
down_revision: str | None = "c7d3e9a4b1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "funds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("target_months", sa.Integer(), nullable=True),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint("kind IN ('annual_expense', 'emergency', 'goal')", name="ck_funds_kind"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_funds_status"),
        sa.CheckConstraint("target_amount IS NULL OR target_amount > 0", name="ck_funds_target_amount_positive"),
        sa.CheckConstraint(
            "target_months IS NULL OR (target_months >= 1 AND target_months <= 60)", name="ck_funds_target_months_range"
        ),
        sa.CheckConstraint("(target_amount IS NOT NULL) <> (target_months IS NOT NULL)", name="ck_funds_target_xor"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_funds_id"), "funds", ["id"], unique=False)
    op.create_index(op.f("ix_funds_account_id"), "funds", ["account_id"], unique=False)
    op.create_index("ix_funds_user_id_status", "funds", ["user_id", "status"], unique=False)

    op.create_table(
        "fund_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fund_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("type", sa.String(length=12), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.CheckConstraint("type IN ('contribution', 'withdrawal', 'adjustment')", name="ck_fund_entries_type"),
        sa.CheckConstraint("amount <> 0", name="ck_fund_entries_amount_nonzero"),
        sa.CheckConstraint(
            "(type <> 'contribution' OR amount > 0) AND (type <> 'withdrawal' OR amount < 0)",
            name="ck_fund_entries_sign",
        ),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fund_entries_id"), "fund_entries", ["id"], unique=False)
    op.create_index("ix_fund_entries_fund_id_occurred_at", "fund_entries", ["fund_id", "occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fund_entries_fund_id_occurred_at", table_name="fund_entries")
    op.drop_index(op.f("ix_fund_entries_id"), table_name="fund_entries")
    op.drop_table("fund_entries")
    op.drop_index("ix_funds_user_id_status", table_name="funds")
    op.drop_index(op.f("ix_funds_account_id"), table_name="funds")
    op.drop_index(op.f("ix_funds_id"), table_name="funds")
    op.drop_table("funds")
