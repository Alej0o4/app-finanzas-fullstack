"""fase_16_opening_balance

Revision ID: e460a42926d7
Revises: 6c9bbf3564cc
Create Date: 2026-09-06 17:58:14.902035

Ítem 16.4 del spec docs/specs/fase_16_spec.md (Decisión 16.4.1): columna nueva
`accounts.opening_balance` (saldo de apertura, inmutable tras la creación de la
cuenta) + backfill de datos en el mismo `upgrade()` — mismo patrón que Fase 8 usó
para `updated_at` (columna nueva + backfill en la migración, no en un script aparte).

Estrategia de backfill (Decisión 16.4.3):
`opening_balance = balance_actual - neto(todas las transacciones no eliminadas de la
cuenta)`. Resultado: en el momento exacto de la migración, `reconciliar_cuenta` para
cualquier cuenta da discrepancia `0.00` — un punto de partida limpio hacia adelante.

⚠️ Límite honesto del backfill (ver backend/docs/BUSINESS_RULES.md, §16.4.4 del spec):
NO detecta retroactivamente desviaciones que ya hayan ocurrido antes de la migración
— no existe ningún snapshot histórico del saldo más antiguo que "el balance actual"
para comparar. Es una línea de base limpia, no una auditoría del pasado.

El `server_default="0"` se mantiene en la columna (no se dropea después, a diferencia
del patrón de `updated_at`) porque `opening_balance=0` es un default legítimo para
creación de cuentas sin depósito inicial, no un placeholder temporal de migración.
Downgrade pierde el valor backfillado (aceptable — recalculable con el mismo UPDATE).

Revisada a mano tras `--autogenerate`: el `UPDATE` de backfill NO lo genera el
autogenerate (solo detectó el `ADD COLUMN`), se agrega a mano según el snippet del
spec §16.4.4.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e460a42926d7"
down_revision: str | None = "6c9bbf3564cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("opening_balance", sa.Numeric(precision=14, scale=2), nullable=False, server_default=sa.text("0")),
    )
    op.execute(
        """
        UPDATE accounts
        SET opening_balance = accounts.balance - COALESCE((
            SELECT SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END)
            FROM transactions t
            WHERE t.account_id = accounts.id AND t.deleted_at IS NULL
        ), 0)
        """
    )


def downgrade() -> None:
    op.drop_column("accounts", "opening_balance")
