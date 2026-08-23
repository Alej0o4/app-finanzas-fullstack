"""fase 10 idempotencia en POST transactions

Revision ID: f2727c013363
Revises: f8c1e5a7d902
Create Date: 2026-08-23 17:26:00.888705

Ítem 10.4 del spec docs/specs/fase_10_spec.md: tabla nueva `idempotency_keys`
(Decisión 10.4.1) — bitácora de reintentos seguros del header `Idempotency-Key`
en POST /transactions. Revisada a mano tras `--autogenerate`: el diff detectado
ya contenía únicamente esta tabla y sus dos índices, sin cambios espurios.

Notas:
- Sin SoftDeleteMixin (mismo criterio que las tablas de token, Decisión 6.3 de
  Fase 8): es bitácora técnica, no dato de dominio. Por eso el índice único
  `(user_id, key)` es SIMPLE, no parcial como el de `budgets` — no conviven filas
  activas y soft-deleted que deban compartir el slot de unicidad.
- `created_at` usa `server_default=CURRENT_TIMESTAMP` y no `now()`: SQLite no
  conoce `now()` (misma lección de portabilidad de 57bde72b8117/f8c1e5a7d902).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2727c013363"
down_revision: str | None = "f8c1e5a7d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        # sha256 hex del payload canónico (Decisión 10.4.3)
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_idempotency_keys_id"), "idempotency_keys", ["id"], unique=False)
    op.create_index("uq_idempotency_keys_user_key", "idempotency_keys", ["user_id", "key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_idempotency_keys_user_key", table_name="idempotency_keys")
    op.drop_index(op.f("ix_idempotency_keys_id"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
