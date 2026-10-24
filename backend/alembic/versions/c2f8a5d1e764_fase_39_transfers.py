"""fase_39_transfers

Revision ID: c2f8a5d1e764
Revises: b4e7a2d9c613
Create Date: 2026-10-24 12:00:00.000000

Fase 39 (docs/specs/fase_39_spec.md §B1): tabla nueva `transfers`. Migración puramente aditiva: no
toca ninguna tabla existente ni migra datos (la corrección de saldo inicial y las transferencias de
los CDT reales las hace el script `scripts/fase39_corregir_bancolombia.py`, una sola vez, a mano).
La categoría base "Rendimientos" no va acá: la siembra `ensure_default_categories` en el arranque.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f8a5d1e764"
down_revision: str | None = "b4e7a2d9c613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("from_account_id", sa.Integer(), nullable=True),
        sa.Column("to_account_id", sa.Integer(), nullable=True),
        sa.Column("cdt_id", sa.Integer(), nullable=True),
        sa.Column("amount_out", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency_out", sa.String(length=3), nullable=False),
        sa.Column("amount_in", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency_in", sa.String(length=3), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint("amount_out > 0", name="ck_transfers_amount_out_positive"),
        sa.CheckConstraint("amount_in > 0", name="ck_transfers_amount_in_positive"),
        sa.CheckConstraint(
            "(cdt_id IS NULL AND from_account_id IS NOT NULL AND to_account_id IS NOT NULL "
            "AND from_account_id <> to_account_id) "
            "OR (cdt_id IS NOT NULL AND ((from_account_id IS NULL) <> (to_account_id IS NULL)))",
            name="ck_transfers_endpoints",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["from_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["to_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["cdt_id"], ["cdts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transfers_id"), "transfers", ["id"], unique=False)
    op.create_index("ix_transfers_user_id_date", "transfers", ["user_id", "date"], unique=False)
    op.create_index("ix_transfers_from_account_id", "transfers", ["from_account_id"], unique=False)
    op.create_index("ix_transfers_to_account_id", "transfers", ["to_account_id"], unique=False)
    op.create_index("ix_transfers_cdt_id", "transfers", ["cdt_id"], unique=False)
    op.create_index(
        "uq_transfers_cdt_constitucion",
        "transfers",
        ["cdt_id"],
        unique=True,
        postgresql_where=sa.text("cdt_id IS NOT NULL AND from_account_id IS NOT NULL"),
        sqlite_where=sa.text("cdt_id IS NOT NULL AND from_account_id IS NOT NULL"),
    )
    op.create_index(
        "uq_transfers_cdt_redencion",
        "transfers",
        ["cdt_id"],
        unique=True,
        postgresql_where=sa.text("cdt_id IS NOT NULL AND to_account_id IS NOT NULL"),
        sqlite_where=sa.text("cdt_id IS NOT NULL AND to_account_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transfers_cdt_redencion", table_name="transfers")
    op.drop_index("uq_transfers_cdt_constitucion", table_name="transfers")
    op.drop_index("ix_transfers_cdt_id", table_name="transfers")
    op.drop_index("ix_transfers_to_account_id", table_name="transfers")
    op.drop_index("ix_transfers_from_account_id", table_name="transfers")
    op.drop_index("ix_transfers_user_id_date", table_name="transfers")
    op.drop_index(op.f("ix_transfers_id"), table_name="transfers")
    op.drop_table("transfers")
