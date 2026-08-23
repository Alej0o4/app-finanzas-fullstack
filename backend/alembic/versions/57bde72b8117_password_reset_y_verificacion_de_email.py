"""password reset y verificacion de email

Revision ID: 57bde72b8117
Revises: 0001
Create Date: 2026-08-22 23:15:44.556048

Agrega las tablas `password_reset_tokens` y `email_verification_tokens` (Fase 7,
§2.1/§2.2 del spec) y la columna `users.email_verified`. `email_verified` se agrega con
`server_default=false` porque, a diferencia de la migración baseline (0001, generada
contra una DB vacía), esta corre sobre una base que ya puede tener filas en `users`
(la cuenta de pruebas `test@test.com` sembrada por `app/core/seed.py`) — un
`ALTER TABLE ... ADD COLUMN ... NOT NULL` sin default falla en Postgres si la tabla no
está vacía.

También se corrige a mano el `server_default` de `created_at` en ambas tablas nuevas:
autogenerate (corrido contra Postgres) emitió `sa.text("now()")`, que no existe en SQLite
(el fallback local sin Docker) y rompe `alembic upgrade head` ahí con
`OperationalError: unknown function: now()`. Se reemplaza por `CURRENT_TIMESTAMP`, la
misma expresión ya usada en la migración baseline (0001) para el resto de columnas
`created_at`, que sí es portable entre ambos dialectos.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57bde72b8117"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_tokens_id"), "email_verification_tokens", ["id"], unique=False)
    op.create_index(
        op.f("ix_email_verification_tokens_token_hash"), "email_verification_tokens", ["token_hash"], unique=False
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_password_reset_tokens_id"), "password_reset_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_password_reset_tokens_token_hash"), "password_reset_tokens", ["token_hash"], unique=False)
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Se agrega server_default arriba solo para poder poblar filas existentes; se retira
    # después para que quede alineado con el modelo (default en Python, no en el schema
    # de DB), consistente con el resto de columnas booleanas del proyecto (ej.
    # `accounts.highlighted`). batch_alter_table es necesario para que el DROP DEFAULT
    # también funcione en SQLite (fallback local sin Docker), que no soporta
    # `ALTER TABLE ... ALTER COLUMN` de forma nativa — Alembic lo emula recreando la
    # tabla solo cuando se usa el modo batch.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "email_verified")
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_id"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
