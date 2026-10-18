"""fase_36_indice_fund_entries_transaction

Revision ID: e8a1c4d7b290
Revises: d5f2a8c1e703
Create Date: 2026-10-17 18:00:00.000000

Fase 36 (docs/specs/fase_36_spec.md §B1, D13): índice NO único sobre
`fund_entries.transaction_id`, la columna que enlaza un gasto con su sobre. Las consultas de
"monto aplicado a una transacción" y de "transacciones enlazadas" agrupan por esa columna. Que
una transacción pertenezca a lo sumo a un sobre lo garantiza el servicio con el row-lock del
sobre, no la base. Migración puramente aditiva: sin cambios de columnas, CHECK ni datos.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a1c4d7b290"
down_revision: str | None = "d5f2a8c1e703"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_fund_entries_transaction_id", "fund_entries", ["transaction_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fund_entries_transaction_id", table_name="fund_entries")
