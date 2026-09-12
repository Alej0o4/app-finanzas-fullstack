"""fase_17_budget_currency_unique_index

Revision ID: b5a09d0bed5e
Revises: e460a42926d7
Create Date: 2026-09-12 16:59:36.266676

Ítem 17.2.2 del spec docs/specs/fase_17_spec.md (Decisión 17.2.2): ensanchar el
índice único parcial `uq_budgets_user_category_period_active` de `budgets` de
(user_id, category_id, month, year) a (user_id, category_id, month, year, currency)
— un presupuesto por (categoría, período) POR moneda, en vez de uno total sin
importar la moneda. Sin esto, el selector de moneda del ítem 17.2 sería cosmético:
el índice de hoy seguiría rechazando un segundo presupuesto en otra moneda para la
misma categoría/período (Hallazgo 3 de la spec).

Sin backfill de datos: todos los `budgets` existentes tienen `currency='COP'` por
default y ya eran únicos por el 4-tuple original — ensanchar el índice no puede
introducir una colisión retroactiva (el 4-tuple es un sub-conjunto más estricto).

Revisada a mano tras `--autogenerate`: autogenerate detectó el reemplazo del índice
y generó drop + recreate; se limpia el `drop_index` (sin `sqlite_where`, misma
firma que la definición del baseline) y el `downgrade` recrea el índice sin
`currency`, como estaba antes de la Fase 17.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5a09d0bed5e"
down_revision: str | None = "e460a42926d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_budgets_user_category_period_active", table_name="budgets")
    op.create_index(
        "uq_budgets_user_category_period_active",
        "budgets",
        ["user_id", "category_id", "month", "year", "currency"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_budgets_user_category_period_active",
        table_name="budgets",
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_budgets_user_category_period_active",
        "budgets",
        ["user_id", "category_id", "month", "year"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
