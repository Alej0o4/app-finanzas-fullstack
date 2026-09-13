"""fase_20_google_oauth_user_columns

Revision ID: 5b79ad1d27e4
Revises: 8c8632cc2a5b
Create Date: 2026-09-13 00:00:00.000000

Login con Google (docs/specs/fase_20_spec.md, Decisión 20.3.1/P5):
- `users.password_hash` pasa de NOT NULL a nullable — una cuenta creada solo por Google
  nunca tiene hash de contraseña (NULL explícito en vez de un hash centinela: no hay
  ningún código que trate "no nulo" como señal de negocio, Hallazgo 3 del spec).
- `users.google_id` nueva columna (String, unique, indexed, nullable) — el `sub` del ID
  token de Google, para vincular cuentas de forma idempotente.

Escrita a mano (no `--autogenerate`): autogenerate necesita acceso a una base y no siempre
detecta el `ALTER COLUMN ... DROP NOT NULL`; SQLite no soporta ALTER COLUMN nativo, así que
se usa `batch_alter_table` (mismo patrón que f8c1e5a7d902:67-79 y 57bde72b8117:76-77).

Sin backfill: toda fila existente ya tiene un `password_hash` real, así que aflojar la
restricción no puede introducir datos inválidos retroactivamente; `google_id` nace NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b79ad1d27e4"
down_revision: str | None = "8c8632cc2a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(), nullable=True)
        batch_op.add_column(sa.Column("google_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_users_google_id"), "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_google_id"), table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("google_id")
        batch_op.alter_column("password_hash", existing_type=sa.String(), nullable=False)
