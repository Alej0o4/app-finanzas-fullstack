"""fase_34_user_timezone

Revision ID: a34c0de1b7f2
Revises: 5b79ad1d27e4
Create Date: 2026-10-04 00:00:00.000000

Zona horaria por usuario (docs/specs/fase_34_spec.md, Decisión B1): `users.timezone`
String(64) NOT NULL con `server_default 'America/Bogota'`. El default hace el backfill de
los usuarios existentes a Bogotá sin paso extra y se conserva en la columna (el modelo
declara el mismo `server_default`, así `alembic check` no ve diferencias).

`batch_alter_table` para que SQLite (opt-in offline de la suite) también migre.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a34c0de1b7f2"
down_revision: str | None = "5b79ad1d27e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/Bogota")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("timezone")
