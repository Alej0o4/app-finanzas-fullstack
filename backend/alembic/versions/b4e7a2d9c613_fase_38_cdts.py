"""fase_38_cdts

Revision ID: b4e7a2d9c613
Revises: a9c3d6e1f845
Create Date: 2026-10-18 18:00:00.000000

Fase 38 (docs/specs/fase_38_spec.md §B1): tabla nueva `cdts`. Migración puramente aditiva: no toca
ninguna tabla existente ni migra datos. Los CHECK (montos, tasa, fechas, estado y coherencia de la
redención) son una garantía de base de datos, no solo de aplicación.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e7a2d9c613"
down_revision: str | None = "a9c3d6e1f845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cdts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("principal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("rate_ea", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("maturity_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("redeemed_on", sa.Date(), nullable=True),
        sa.Column("final_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.CheckConstraint("principal > 0", name="ck_cdts_principal_positive"),
        sa.CheckConstraint("rate_ea > 0 AND rate_ea <= 100", name="ck_cdts_rate_ea_range"),
        sa.CheckConstraint("maturity_on > opened_on", name="ck_cdts_maturity_after_opened"),
        sa.CheckConstraint("status IN ('active', 'redeemed')", name="ck_cdts_status"),
        sa.CheckConstraint("final_amount IS NULL OR final_amount >= 0", name="ck_cdts_final_amount_nonneg"),
        sa.CheckConstraint(
            "(status = 'redeemed') = (redeemed_on IS NOT NULL AND final_amount IS NOT NULL)",
            name="ck_cdts_redeemed_coherent",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cdts_id"), "cdts", ["id"], unique=False)
    op.create_index("ix_cdts_user_id_status", "cdts", ["user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cdts_user_id_status", table_name="cdts")
    op.drop_index(op.f("ix_cdts_id"), table_name="cdts")
    op.drop_table("cdts")
