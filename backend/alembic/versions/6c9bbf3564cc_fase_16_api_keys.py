"""fase_16_api_keys

Revision ID: 6c9bbf3564cc
Revises: 418c35db8cbc
Create Date: 2026-09-06 17:57:50.172355

Ítem 16.1 del spec docs/specs/fase_16_spec.md: tabla nueva `api_keys` (API keys
personales revocables) + el índice compuesto `ix_api_keys_user_id_revoked_at` de la
Decisión 16.1.1 en la misma migración. Sin backfill de datos — no hay filas
preexistentes que migrar.

Revisada a mano tras `--autogenerate`:
- El índice compuesto `ix_api_keys_user_id_revoked_at` se autogeneró correctamente
  (es un índice simple sin `where` parcial, a diferencia de los índices únicos
  parciales de Fases 13/14 — no lleva `postgresql_where`).
- `created_at` usa `server_default=CURRENT_TIMESTAMP` — el autogenerate lo rindió como
  `(CURRENT_TIMESTAMP)` con paréntesis; se normaliza sin paréntesis para coincidir con
  el resto de las migraciones del repo (SQLite no conoce `now()`, misma lección de
  portabilidad de 0001/b1d756483305).
- La columna `accounts.opening_balance` que el autogenerate detectó junto con la tabla
  se RETIRÓ de esta revisión: pertenece a su propia migración
  (`fase_16_opening_balance`, §16.4 del spec — migraciones separadas, Decisión
  transversal del spec).
- Sin SoftDeleteMixin (mismo criterio que `IdempotencyKey`/`RefreshToken`, Decisión
  6.3 de Fase 8): es credencial/bitácora técnica, no un dato de dominio que el usuario
  liste como historial.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c9bbf3564cc"
down_revision: str | None = "418c35db8cbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=False)
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False)
    op.create_index("ix_api_keys_user_id_revoked_at", "api_keys", ["user_id", "revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_id_revoked_at", table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_id"), table_name="api_keys")
    op.drop_table("api_keys")
