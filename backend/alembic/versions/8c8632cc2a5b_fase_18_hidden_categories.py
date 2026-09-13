"""fase_18_hidden_categories

Revision ID: 8c8632cc2a5b
Revises: b5a09d0bed5e
Create Date: 2026-09-12 19:13:44.116028

Tabla puente `hidden_categories` ("oculta para mí" sobre `Category`, docs/specs/fase_18_spec.md
Decisión Q1): overlay por usuario, una fila por par (user_id, category_id) con PRIMARY KEY
compuesta — no hay columna `id` serial a propósito.

Revisada a mano tras `--autogenerate`:
- PK compuesta (user_id, category_id) — autogenerate la detectó limpio vía
  `sa.PrimaryKeyConstraint('user_id', 'category_id')`, sin `id` autoincrement.
- FKs a `users.id` y `categories.id` SIN `ondelete` — mismo patrón que el resto de
  models.py (seguro: ni User ni Category tienen borrado físico, ambos SoftDeleteMixin).
- `hidden_at` con `server_default=func.now()` — el autogenerate lo rindió como
  `(CURRENT_TIMESTAMP)` con paréntesis; se normaliza sin paréntesis para coincidir con
  las migraciones previas (mismo criterio documentado en fase_13/fase_14/fase_16).

Tabla nueva, sin backfill: sin usuarios reales aún (docs/ROADMAP.md:630-631), el registro
pre-siembra las filas desde el código (Fase 18 §18.2), no desde esta migración.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c8632cc2a5b"
down_revision: str | None = "b5a09d0bed5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hidden_categories",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "category_id"),
    )


def downgrade() -> None:
    op.drop_table("hidden_categories")
