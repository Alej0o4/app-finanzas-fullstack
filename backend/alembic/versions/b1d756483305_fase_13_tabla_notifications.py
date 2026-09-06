"""fase 13 tabla notifications

Revision ID: b1d756483305
Revises: f2727c013363
Create Date: 2026-09-05 19:48:35.059096

Ítem 13.5 del spec docs/specs/fase_13_spec.md: tabla nueva `notifications` (bandeja
in-app) + índice único parcial de la Decisión 13.3.2 en la misma migración (ambos se
declaran en el mismo `__table_args__` del modelo).

Revisada a mano tras `--autogenerate`:
- El índice PARCIAL `uq_notifications_budget_type_active` se autogeneró correctamente
  con `postgresql_where`/`sqlite_where` (budget_id IS NOT NULL) — NO hay que agregarlo
  a mano; verifica la unicidad "(budget_id, type)" solo para filas con presupuesto.
- `created_at` usa `server_default=CURRENT_TIMESTAMP` y no `now()` (SQLite no conoce
  `now()` — misma lección de portabilidad de 0001/f8c1e5a7d902). El autogenerate lo
  rindió como `(CURRENT_TIMESTAMP)` con paréntesis; se normaliza sin paréntesis para
  coincidir con el resto de las migraciones del repo.
- Sin SoftDeleteMixin (mismo criterio que `IdempotencyKey`/`RefreshToken`, Decisión
  6.3 de Fase 8): es bitácora de avisos, se borra de verdad si hace falta limpiar.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1d756483305"
down_revision: str | None = "f2727c013363"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"], unique=False)
    op.create_index(
        "uq_notifications_budget_type_active",
        "notifications",
        ["budget_id", "type"],
        unique=True,
        postgresql_where=sa.text("budget_id IS NOT NULL"),
        sqlite_where=sa.text("budget_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notifications_budget_type_active",
        table_name="notifications",
        postgresql_where=sa.text("budget_id IS NOT NULL"),
        sqlite_where=sa.text("budget_id IS NOT NULL"),
    )
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
