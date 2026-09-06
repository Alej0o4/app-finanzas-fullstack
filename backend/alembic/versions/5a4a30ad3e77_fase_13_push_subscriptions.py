"""fase 13 push subscriptions

Revision ID: 5a4a30ad3e77
Revises: b1d756483305
Create Date: 2026-09-05 19:56:14.388680

Ítem 13.2 del spec docs/specs/fase_13_spec.md: tabla nueva `push_subscriptions`
(Decisión 13.2.3) — una fila por combinación (usuario, dispositivo/navegador), con
`endpoint` único GLOBAL porque el estándar Web Push garantiza un endpoint único por
instalación: si el mismo endpoint se re-registra, se actualiza la fila en vez de
duplicar (upsert por endpoint, no una columna en `User`).

Revisada a mano tras `--autogenerate`: el diff detectado contenía únicamente esta
tabla y sus tres índices, sin cambios espurios. `created_at` se normaliza a
`CURRENT_TIMESTAMP` (sin paréntesis) igual que en la migración b1d756483305. Sin
SoftDeleteMixin (mismo criterio que `RefreshToken`, Decisión 6.3 de Fase 8): una
suscripción revocada por el navegador (410 Gone) se borra de verdad, no tiene valor
histórico.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a4a30ad3e77"
down_revision: str | None = "b1d756483305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_push_subscriptions_id"), "push_subscriptions", ["id"], unique=False)
    op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False)
    op.create_index("uq_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
